from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
import os
from dotenv import load_dotenv
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

load_dotenv()
MODEL = os.getenv('MODEL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not MODEL:
    raise ValueError("MODEL environment variable not set. Please check your .env file.")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set. Please check your .env file.")

@CrewBase
class BusinessChatbot:
    """BusinessChatbot crew"""
    agents: List[BaseAgent]
    tasks: List[Task]
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools

    agents_config="config/agents.yaml"
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
    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task

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

