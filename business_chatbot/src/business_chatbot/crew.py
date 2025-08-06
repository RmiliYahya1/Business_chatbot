from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
import os, queue
from dotenv import load_dotenv
from business_chatbot.src.business_chatbot.tools.custom_tool import CSVFileCreatorTool
from crewai.utilities.paths import db_storage_path

load_dotenv()
MODEL = os.getenv('MODEL')
token_queue = queue.Queue()
csv_tool = CSVFileCreatorTool()
my_llm = LLM(
    model=f"openai/{MODEL}",
    api_key=os.getenv("OPENAI_API_KEY"),
    stream=True,
    temperature=0.7,
)

#storage path
def log_storage_path():
    storage_path = db_storage_path()

    print(f"Storage path: {storage_path}")
    print(f"Path exists: {os.path.exists(storage_path)}")
    print(f"Is writable: {os.access(storage_path, os.W_OK) if os.path.exists(storage_path) else 'Path does not exist'}")

    if os.path.exists(storage_path):
        print("\nStored files and directories:")
        try:
            for item in os.listdir(storage_path):
                item_path = os.path.join(storage_path, item)
                if os.path.isdir(item_path):
                    print(f"📁 {item}/")
                    for subitem in os.listdir(item_path):
                        print(f"   └── {subitem}")
                else:
                    print(f"📄 {item}")
        except PermissionError:
            print(f"Permission refusée pour accéder à {storage_path}")
        except Exception as e:
            print(f"Une erreur est survenue : {e}")
    else:
        print("No CrewAI storage directory found yet.")


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
        log_storage_path()
        return Crew(
            agents=[self.business_expert()],
            tasks=[self.direct_consultation_task()],
            process=Process.sequential,
            verbose=True,
            memory=True,
            output_json=True,
        )

    @crew
    def expert_crew2(self) -> Crew:

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
            output_json=True
        )

    @crew
    def b2b_crew(self) -> Crew:
        """Creates a B2B focused crew"""
        return Crew(
            agents=[self.b2b_specialist()],
            tasks=[self.b2b_retreiving()],
            process=Process.sequential,
            verbose=True,
            output_json=True
        )









