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
    @agent
    def business_expert(self) -> Agent:
        return Agent(
            config=self.agents_config['business_expert'],
            llm= MODEL,
            allow_delegation=False,
            verbose=True
        )

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
    def generate_final_response(self) -> Task:
        return Task(
            config=self.tasks_config['generate_final_response'], # type: ignore[index]
        )

    @task
    def b2b_retreiving(self) -> Task:
        return Task(
            config=self.tasks_config['b2b_retreiving'], # type: ignore[index]
            output_file='report.md'
        )

    @task
    def b2c_retreiving(self) -> Task:
        return Task(
            config=self.tasks_config['b2c_retreiving'],  # type: ignore[index]
            output_file='report.md'
        )

    @crew
    def crew(self,agent) -> Crew:
        """Creates the BusinessChatbot crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=agent, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
