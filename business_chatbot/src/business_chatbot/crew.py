from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()
MODEL = os.getenv('MODEL')

@CrewBase
class BusinessChatbot:
    """BusinessChatbot crews"""

    agents_config="config/agents.yaml"
    tasks_config = "config/tasks.yaml"

#------------------------------------------------------------AGENTS--------------------------------------------------------------------------
    @agent
    def business_expert(self) -> Agent:
        return Agent(
            config=self.agents_config['business_expert'],
            llm=MODEL,
            allow_delegation=False,
            memory=True,
            verbose=True,
            max_iter=1,
        )

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

# ------------------------------------------------------------TASKS--------------------------------------------------------------------------

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

    @task
    def b2b_extraction_task(self) -> Task:
        return Task(
            config=self.tasks_config['b2b_retreiving'],
            agent=self.b2b_specialist()
        )

    @task
    def b2c_extraction_task(self) -> Task:
        return Task(
            config=self.tasks_config['b2c_retreiving'],
            agent=self.b2c_specialist()
        )
# ------------------------------------------------------------CREWS--------------------------------------------------------------------------

    @crew
    def consultation_direct(self) -> Crew:
        """Crew pour consultation directe"""
        return Crew(
            agents=[self.business_expert()],
            tasks=[self.direct_consultation_task()],
            process=Process.sequential,
            verbose=True
        )

    @crew
    def b2c_extraction_crew(self) -> Crew:
        """Crew pour extraction JSON B2C"""
        return Crew(
            agents=[self.b2c_specialist()],
            tasks=[self.b2c_extraction_task()],
            process=Process.sequential,
            verbose=True,
        )

    @crew
    def b2b_extraction_crew(self) -> Crew:
        """Crew pour extraction JSON B2B"""
        return Crew(
            agents=[self.b2b_specialist()],
            tasks=[self.b2b_extraction_task()],
            process=Process.sequential,
            verbose=True,
        )

    @crew
    def analysis_crew(self) -> Crew:
        """Crew pour analyse finale des données"""
        return Crew(
            agents=[self.business_expert()],
            tasks=[self.data_analysis_synthesis_task()],
            process=Process.sequential,
            verbose=True,
        )








