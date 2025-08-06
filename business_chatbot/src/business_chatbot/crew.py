from crewai import Agent, Crew, Process, Task, LLM
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
import os, queue
from dotenv import load_dotenv
from crewai.memory import LongTermMemory, ShortTermMemory
from uuid import uuid4
from crewai.memory.storage.ltm_sqlite_storage import LTMSQLiteStorage


from business_chatbot.src.business_chatbot.tools.custom_tool import CSVFileCreatorTool

load_dotenv()
MODEL = os.getenv('MODEL')
token_queue = queue.Queue()
csv_tool = CSVFileCreatorTool()
os.environ["CREWAI_STORAGE_DIR"] = "./my_project_storage"


my_llm = LLM(
    model=f"openai/{MODEL}",
    api_key=os.getenv("OPENAI_API_KEY"),
    stream=True,
    temperature=0.7,
)

@CrewBase
class BusinessChatbot:
    """BusinessChatbot crews"""

    agents_config="config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self):
        super().__init__()
        self._rag_tool = None  # Store the RAG tool as an instance variable

    def set_rag_tool(self, rag_tool):
        """Set the RAG tool to be used by the business expert"""
        self._rag_tool = rag_tool

#------------------------------------------------------------AGENTS--------------------------------------------------------------------------
    @agent
    def business_expert(self) -> Agent:
        """Business expert agent with optional RAG tool"""
        tools = []
        if self._rag_tool is not None:
            tools = [self._rag_tool]

        return Agent(
            config=self.agents_config['business_expert'],
            llm=my_llm,
            allow_delegation=False,
            memory=True,
            verbose=True,
            tools=tools,
            respect_context_window=False,
            max_iter=1,
        )


    @agent
    def b2b_specialist(self) -> Agent:
        return Agent(
            config=self.agents_config['b2b_specialist'],
            llm=my_llm,
            allow_delegation=False,
            verbose=True
        )

    @agent
    def b2c_specialist(self) -> Agent:
        return Agent(
            config=self.agents_config['b2c_specialist'],
            llm=my_llm,
            allow_delegation=False,
            verbose=True
        )


# ------------------------------------------------------------TASKS--------------------------------------------------------------------------


    @task
    def b2b_retreiving(self) -> Task:
        return Task(
            config=self.tasks_config['b2b_retreiving'],
            agent=self.b2b_specialist()
        )

    @task
    def b2c_retreiving(self) -> Task:
        return Task(
            config=self.tasks_config['b2c_retreiving'],
            agent=self.b2c_specialist()
        )

    @task
    def direct_consultation_task(self) -> Task:
        return Task(
            config=self.tasks_config['direct_consultation'],
            agent=self.business_expert(),
        )

    @task
    def data_analysis_synthesis_task(self) -> Task:
        return Task(
            config=self.tasks_config['data_analysis_synthesis'],
            agent=self.business_expert()
        )

# ------------------------------------------------------------CREWS--------------------------------------------------------------------------

    @crew
    def consultation_direct(self) -> Crew:
        """Crew pour consultation directe"""
        return Crew(
            agents=[self.business_expert()],
            tasks=[self.direct_consultation_task()],
            process=Process.sequential,
            verbose=True,
            memory=True,
            long_term_memory=LongTermMemory(
                storage=LTMSQLiteStorage(
                    db_path=f"./my_project_storage"
                )
            ),
            short_term_memory=ShortTermMemory(),
            output_json=True,
        )

    @crew
    def data_analysis_synthesis(self) -> Crew:

        return Crew(
            agents=[self.business_expert()],
            tasks=[self.data_analysis_synthesis_task()],
            process=Process.sequential,
            verbose=True,
            output_json=True
        )

    @crew
    def b2c_crew(self) -> Crew:
        """Creates a B2C focused crew"""
        return Crew(
            agents=[self.b2c_specialist()],
            tasks=[self.b2c_retreiving()],
            process=Process.sequential,
            verbose=True,
            output_json=True,
            stream=True
        )

    @crew
    def b2b_crew(self) -> Crew:
        """Creates a B2B focused crew"""
        return Crew(
            agents=[self.b2b_specialist()],
            tasks=[self.b2b_retreiving()],
            process=Process.sequential,
            verbose=True,
            output_json=True,
            stream=True
        )









