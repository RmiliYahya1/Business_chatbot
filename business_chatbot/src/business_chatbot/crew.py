from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from typing import List
import os
from dotenv import load_dotenv
from tools.custom_tool import CSVFileCreatorTool

load_dotenv()
MODEL = os.getenv('MODEL')
csv_tool = CSVFileCreatorTool()

@CrewBase
class BusinessChatbot:
    """BusinessChatbot crew"""
    agents: List[BaseAgent]
    tasks: List[Task]

    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools

    agents_config="config/agents.yaml"
    tasks_config = "config/tasks.yaml"  # IMPORTANT: Ajout manquant



    @agent
    def b2b_specialist(self) -> Agent:
        return Agent(

            config=self.agents_config['b2b_specialist'],
            llm= MODEL,
            allow_delegation=False,
            verbose=True
        )
    @agent
    def b2c_specialist(self) -> Agent:
        return Agent(
            config=self.agents_config['b2c_specialist'],
            llm= MODEL,
            allow_delegation=False,
            verbose=True
        )

    @agent
    def business_expert(self) -> Agent:
            return Agent(
                config=self.agents_config['business_expert'],
                llm=MODEL,
                allow_delegation=False,
                memory=True,
                verbose=True,
                respect_context_window=False,
                max_iter=3,
                tools=[csv_tool]
            )


    @task
    def b2b_retreiving(self) -> Task:
        return Task(
            config=self.tasks_config['b2b_retreiving'], # type: ignore[index]
        )

    @task
    def b2c_retreiving(self) -> Task:
        return Task(
            config=self.tasks_config['b2c_retreiving'], # type: ignore[index]

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
        """Creates a B2B focused crew"""
        return Crew(
            agents=[self.business_expert],
            tasks=[self.direct_consultation_task],
            process=Process.sequential,
            verbose=True,
            output_json=True
        )







