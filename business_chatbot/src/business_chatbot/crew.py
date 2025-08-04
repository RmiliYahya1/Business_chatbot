from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.memory import LongTermMemory, ShortTermMemory
from uuid import uuid4
from crewai.memory.storage.ltm_sqlite_storage import LTMSQLiteStorage
from crewai.project import CrewBase, agent, crew, task
from typing import List, Optional
import os
from dotenv import load_dotenv
from tools.custom_tool import CSVFileCreatorTool
from crewai_tools import CSVSearchTool

load_dotenv()
MODEL = os.getenv('MODEL')
csv_tool = CSVFileCreatorTool()
os.environ["CREWAI_STORAGE_DIR"] = "./my_project_storage"

@CrewBase
class BusinessChatbot:
    """BusinessChatbot crew"""
    agents: List[BaseAgent]
    tasks: List[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self):
        super().__init__()
        self._rag_tool = None  # Store the RAG tool as an instance variable


    def set_rag_tool(self, rag_tool):
        """Set the RAG tool to be used by the business expert"""
        self._rag_tool = rag_tool

    @agent
    def b2b_specialist(self) -> Agent:
        return Agent(
            config=self.agents_config['b2b_specialist'],
            llm=MODEL,
            allow_delegation=False,
            verbose=True
        )

    @agent
    def b2c_specialist(self) -> Agent:
        return Agent(
            config=self.agents_config['b2c_specialist'],
            llm=MODEL,
            allow_delegation=False,
            verbose=True
        )

    @agent
    def business_expert(self) -> Agent:
        """Business expert agent with optional RAG tool"""
        tools = []
        if self._rag_tool is not None:
            tools = [self._rag_tool]

        return Agent(
            config=self.agents_config['business_expert'],
            llm=MODEL,
            allow_delegation=False,
            verbose=True,
            tools=tools,
            respect_context_window=False,
            max_iter=1,
            memory=True
        )

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
            agent=self.business_expert()
        )

    @task
    def data_analysis_synthesis_task(self) -> Task:
        return Task(
            config=self.tasks_config['data_analysis_synthesis'],
            agent=self.business_expert()
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

    @crew
    def expert_crew(self) -> Crew:
        """Creates an expert crew with business expert"""
        return Crew(
            agents=[self.business_expert()],
            tasks=[self.direct_consultation_task(), self.data_analysis_synthesis_task()],
            process=Process.sequential,
            verbose=True,
            output_json=True
        )

    @crew
    def expert_crew1(self) -> Crew:
        """Creates an expert crew for consultation only"""
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
    def expert_crew2(self) -> Crew:
        """Creates an expert crew for data analysis"""
        return Crew(
            agents=[self.business_expert()],
            tasks=[self.data_analysis_synthesis_task()],
            process=Process.sequential,
            verbose=True,
            output_json=True
        )

    def expert_crew2_with_rag(self, rag_tool) -> Crew:
        """Creates an expert crew for data analysis with specific RAG tool"""
        # Temporarily set the RAG tool
        old_rag = self._rag_tool
        self._rag_tool = rag_tool

        crew = Crew(
            agents=[self.business_expert()],
            tasks=[self.data_analysis_synthesis_task()],
            process=Process.sequential,
            verbose=True,
            output_json=True
        )

        # Restore the old RAG tool
        self._rag_tool = old_rag
        return crew

    def crew(self):
        pass






