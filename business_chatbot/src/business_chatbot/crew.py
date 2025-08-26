from __future__ import annotations

import logging
import os
import queue
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.utilities.paths import db_storage_path
from crewai_tools import SerperDevTool

from business_chatbot.src.business_chatbot.tools.custom_tool import CSVFileCreatorTool
from business_chatbot.src.business_chatbot.tools.memory_service import MemoryService
from mem0 import Memory

# ---------------------------------------------------------------------------
# Initialisation env & logging
# ---------------------------------------------------------------------------
load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mémoire globale (lazy)
# ---------------------------------------------------------------------------
_mem: Optional[Memory] = None
_mem_service: Optional[MemoryService] = None


def get_mem_service() -> MemoryService:
    global _mem, _mem_service
    if _mem_service is None:
        _mem = Memory()
        _mem_service = MemoryService(_mem)
        logger.debug("MemoryService initialisé.")
    return _mem_service


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
MODEL = os.getenv("MODEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
if not SERPER_API_KEY:
    logger.warning("⚠️ SERPER_API_KEY est manquant : SerperDevTool ne pourra pas fonctionner.")

if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY est vide/non défini. Le LLM ne pourra pas répondre.")

my_llm = LLM(
    model=f"openai/{MODEL}",
    api_key=OPENAI_API_KEY,
    stream=True,
    temperature=0.7,
)

# Outils utilitaires
token_queue: "queue.Queue[str]" = queue.Queue()
csv_tool = CSVFileCreatorTool()


def _load_yaml_config(path_str: str) -> Dict[str, Any]:
    """
    Charge un YAML explicitement et renvoie un dict.
    Corrige l'accès à self.agents_config['key'] quand self.agents_config était un str.
    """
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Fichier de configuration introuvable: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Le YAML {path} ne contient pas un objet mapping valide.")
    return data


def log_storage_path() -> None:
    """Logging (au lieu de print) du répertoire de stockage CrewAI."""
    storage_path = db_storage_path()
    path_exists = os.path.exists(storage_path)
    writable = os.access(storage_path, os.W_OK) if path_exists else False

    logger.info("Storage path: %s", storage_path)
    logger.info("Path exists: %s", path_exists)
    logger.info("Is writable: %s", writable)

    if not path_exists:
        logger.info("No CrewAI storage directory found yet.")
        return

    try:
        entries = os.listdir(storage_path)
        if not entries:
            logger.info("Pas de fichiers stockés pour le moment.")
            return
        for item in entries:
            item_path = os.path.join(storage_path, item)
            if os.path.isdir(item_path):
                logger.info("📁 %s/", item)
                for subitem in os.listdir(item_path):
                    logger.info("   └── %s", subitem)
            else:
                logger.info("📄 %s", item)
    except PermissionError:
        logger.warning("Permission refusée pour accéder à %s", storage_path)
    except Exception as e:
        logger.exception("Erreur lors de la lecture du storage path: %s", e)


# ---------------------------------------------------------------------------
# BusinessChatbot
# ---------------------------------------------------------------------------
@CrewBase
class BusinessChatbot:
    """BusinessChatbot crews"""

    def _ensure_dynamic_tools_on_agent(self, agent):
        """Attache RAG et Serper à l'agent passé, sans doublons."""
        try:
            current = list(getattr(agent, "tools", []) or [])
        except Exception:
            current = []

        changed = False

        # Attach RAG tool
        if self._rag_tool is not None and self._rag_tool not in current:
            current.append(self._rag_tool)
            changed = True
            logging.getLogger(__name__).info("   ➕ RAG tool attaché sur agent (patch cached).")

        # Attach Serper if enabled and key present
        if self._search_enabled and SERPER_API_KEY:
            from crewai_tools import SerperDevTool
            if not any(isinstance(t, SerperDevTool) for t in current):
                try:
                    current.append(SerperDevTool())
                    changed = True
                    logging.getLogger(__name__).info("   ➕ SerperDevTool attaché sur agent (patch cached).")
                except Exception as e:
                    logging.getLogger(__name__).warning("   ⚠️ Échec init SerperDevTool (patch): %s", e)
        elif self._search_enabled and not SERPER_API_KEY:
            logging.getLogger(__name__).warning("   ⚠️ SERPER_API_KEY manquant: Serper non attaché (patch).")

        if changed:
            try:
                agent.tools = current
            except Exception:
                # fallback si .tools n’est pas assignable
                try:
                    agent.tools.clear();
                    agent.tools.extend(current)
                except Exception:
                    pass

        logging.getLogger(__name__).info("   → Tools sur agent (après patch): %d | %s",
                                         len(getattr(agent, "tools", []) or []),
                                         [type(t).__name__ for t in (getattr(agent, "tools", []) or [])])
    def _patch_cached_business_expert(self):
        """Récupère l'agent (potentiellement mis en cache par @agent) et applique les outils dynamiques."""
        try:
            agent_obj = self.business_expert()  # renvoie l'Agent (souvent déjà caché)
            if agent_obj is not None:
                self._ensure_dynamic_tools_on_agent(agent_obj)
        except Exception as e:
            logging.getLogger(__name__).debug(
                "Patch cached agent impossible (peut être normal avant première création): %s", e)


    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self) -> None:
        super().__init__()
        self._agents_cfg: Dict[str, Any] = _load_yaml_config(self.agents_config)
        self._tasks_cfg: Dict[str, Any] = _load_yaml_config(self.tasks_config)

        # Options dynamiques
        self._rag_tool = None
        self._search_enabled = False

        logger.debug("BusinessChatbot initialisé. Agents=%s | Tasks=%s",
                     list(self._agents_cfg.keys()), list(self._tasks_cfg.keys()))

    # --------------------------- Setters -----------------------------------
    def set_search_enabled(self, enabled: bool) -> None:
        self._search_enabled = bool(enabled)
        logger.info("🔎 Web search (Serper) %s", "activé" if self._search_enabled else "désactivé")

        self._patch_cached_business_expert()

    def set_rag_tool(self, rag_tool: Any) -> None:
        self._rag_tool = rag_tool
        logger.info("🔧 RAG tool défini: %s", type(rag_tool).__name__ if rag_tool else None)

        self._patch_cached_business_expert()

    # --------------------------- AGENTS ------------------------------------
    @agent
    def business_expert(self) -> Agent:
        """
        Business expert agent with optional RAG & web search tools.
        """
        tools = []

        if self._rag_tool is not None:
            tools = [self._rag_tool]
            logger.info("   ➕ RAG tool ajouté")

        if self._search_enabled:
                serper_tool = SerperDevTool()
                tools =[self._rag_tool,serper_tool]
                logger.info("   ➕ SerperDevTool ajouté avec succès")


        cfg = self._agents_cfg.get("business_expert")
        if not isinstance(cfg, dict):
            raise KeyError(
                "Section 'business_expert' introuvable dans config/agents.yaml "
                "(ou format invalide)."
            )
        logger.info(f"  Total outils: {len(tools)} - {[type(tool).__name__ for tool in tools]}")
        agent = Agent(
            config=cfg,
            llm=my_llm,
            allow_delegation=False,
            verbose=True,
            respect_context_window=False,
            max_iter=3,
        )
        self._ensure_dynamic_tools_on_agent(agent)
        return agent

    @agent
    def b2b_specialist(self) -> Agent:
        cfg = self._agents_cfg.get("b2b_specialist")
        if not isinstance(cfg, dict):
            raise KeyError(
                "Section 'b2b_specialist' introuvable dans config/agents.yaml."
            )
        return Agent(
            config=cfg,
            llm=my_llm,
            allow_delegation=False,
            verbose=True,
        )

    @agent
    def b2c_specialist(self) -> Agent:
        cfg = self._agents_cfg.get("b2c_specialist")
        if not isinstance(cfg, dict):
            raise KeyError(
                "Section 'b2c_specialist' introuvable dans config/agents.yaml."
            )
        return Agent(
            config=cfg,
            llm=my_llm,
            allow_delegation=False,
            verbose=True,
        )

    # ---------------------------- TASKS ------------------------------------
    @task
    def b2b_retreiving(self) -> Task:
        # Conserve la clé YAML telle quelle si ton fichier s'appelle 'b2b_retreiving'
        cfg = self._tasks_cfg.get("b2b_retreiving")
        if not isinstance(cfg, dict):
            raise KeyError(
                "Section 'b2b_retreiving' introuvable dans config/tasks.yaml."
            )
        return Task(config=cfg, agent=self.b2b_specialist())

    @task
    def b2c_retreiving(self) -> Task:
        cfg = self._tasks_cfg.get("b2c_retreiving")
        if not isinstance(cfg, dict):
            raise KeyError(
                "Section 'b2c_retreiving' introuvable dans config/tasks.yaml."
            )
        return Task(config=cfg, agent=self.b2c_specialist())

    @task
    def direct_consultation_task(self) -> Task:
        cfg = self._tasks_cfg.get("direct_consultation")
        if not isinstance(cfg, dict):
            raise KeyError(
                "Section 'direct_consultation' introuvable dans config/tasks.yaml."
            )
        return Task(
            config=cfg,
            agent=self.business_expert(),
        )

    def debug_configuration(self) -> dict:
        """Méthode pour débugger la configuration actuelle"""
        return {
            "rag_tool_active": self._rag_tool is not None,
            "search_enabled": self._search_enabled,
            "serper_key_present": bool(SERPER_API_KEY),
            "agents_config_loaded": bool(self._agents_cfg),
            "tasks_config_loaded": bool(self._tasks_cfg),
        }

    @task
    def data_analysis_synthesis_task(self) -> Task:
        cfg = self._tasks_cfg.get("data_analysis_synthesis")
        if not isinstance(cfg, dict):
            raise KeyError(
                "Section 'data_analysis_synthesis' introuvable dans config/tasks.yaml."
            )
        return Task(config=cfg, agent=self.business_expert())

    # ---------------------------- CREWS ------------------------------------
    @crew
    def consultation_direct(self) -> Crew:
        log_storage_path()
        return Crew(
            agents=[self.business_expert()],
            tasks=[self.direct_consultation_task()],
            process=Process.sequential,
            verbose=True,
            memory=True,
        )

    @crew
    def expert_crew2(self) -> Crew:

        return Crew(
            agents=[self.business_expert()],
            tasks=[self.data_analysis_synthesis_task()],
            process=Process.sequential,
            verbose=True,
        )

    @crew
    def b2c_crew(self) -> Crew:
        return Crew(
            agents=[self.b2c_specialist()],
            tasks=[self.b2c_retreiving()],
            process=Process.sequential,
            verbose=True,
        )

    @crew
    def b2b_crew(self) -> Crew:
        return Crew(
            agents=[self.b2b_specialist()],
            tasks=[self.b2b_retreiving()],
            process=Process.sequential,
            verbose=True,
        )
