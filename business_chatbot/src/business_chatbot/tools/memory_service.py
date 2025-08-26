from typing import List, Dict, Optional, Any
from mem0 import Memory

class MemoryService:
    def __init__(self, mem: Memory):
        self.mem = mem

    @staticmethod
    def build_ids(user_id: str, crew_name: str, agent_name: str, run_id: str):
        agent_id = f"{agent_name}:{crew_name}"
        return user_id, agent_id, run_id

    @staticmethod
    def _normalize_results(obj: Any) -> List[Dict]:
        # Mem0 OSS récent: dict avec "results"
        if isinstance(obj, dict) and "results" in obj and isinstance(obj["results"], list):
            return obj["results"]
        # Versions/retours plus anciens: liste directe
        if isinstance(obj, list):
            return obj
        return []

    def funnel_search(self, query: str, user_id: str, agent_id: str, run_id: str, limit: int = 8) -> List[Dict]:
        found = self._normalize_results(
            self.mem.search(query, user_id=user_id, agent_id=agent_id, run_id=run_id, limit=limit)
        )
        if not found:
            found = self._normalize_results(
                self.mem.search(query, user_id=user_id, agent_id=agent_id, limit=limit)
            )
        if not found:
            found = self._normalize_results(
                self.mem.search(query, user_id=user_id, limit=limit)
            )
        return found

    @staticmethod
    def to_prompt(memories: List[Dict]) -> str:
        if not memories:
            return ""
        lines = []
        for m in memories:
            # Champs possibles selon versions: "memory" (actuel), "data", "text"
            if isinstance(m, dict):
                data = m.get("memory") or m.get("data") or m.get("text") or ""
            elif isinstance(m, str):
                data = m
            else:
                data = ""
            if data:
                lines.append(f"- {data}")
        return "\n".join(lines)

    def add_interaction(self, user_id: str, agent_id: str, run_id: str,
                        user_msg: str, assistant_msg: str,
                        metadata: Optional[Dict] = None):
        messages = [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg}
        ]
        self.mem.add(messages, user_id=user_id, agent_id=agent_id, run_id=run_id, metadata=metadata or {})
