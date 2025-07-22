from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool, WebsiteSearchTool
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()
MODEL = os.getenv('MODEL')


@CrewBase
class BusinessChatbot():
    """BusinessChatbot crew"""
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"  # IMPORTANT: Ajout manquant

    search_tool = SerperDevTool()
    website_search = WebsiteSearchTool()

    @agent
    def business_expert(self) -> Agent:
        return Agent(
            config=self.agents_config['business_expert'],
            llm=MODEL,
            allow_delegation=False,
            memory=True,
            verbose=True,
            respect_context_window=False,
            max_iter=5,
            tools=[self.search_tool, self.website_search]
        )

    @task
    def direct_consultation_task(self) -> Task:
        return Task(
            config=self.tasks_config['direct_consultation'],
            agent=self.business_expert()  # IMPORTANT: Assignation explicite
        )

    @crew
    def crew(self) -> Crew:
        """Creates the BusinessChatbot crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )