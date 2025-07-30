from crewai import Agent, Crew, Process, Task, LLM
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
import os, queue
from crewai.utilities.events import LLMStreamChunkEvent, crewai_event_bus,CrewKickoffCompletedEvent
from crewai.utilities.events.base_event_listener import BaseEventListener
from dotenv import load_dotenv

load_dotenv()
MODEL = os.getenv('MODEL')
token_queue = queue.Queue()

class StreamListener(BaseEventListener):
    def setup_listeners(self, crewai_event_bus):
        @crewai_event_bus.on(CrewKickoffCompletedEvent)
        def on_llm_chunk(source, event):
            token_queue.put(event.chunk)
stream_listener = StreamListener()

my_llm = LLM(
    model=MODEL,
    stream=True
)

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
            llm=my_llm,
            allow_delegation=False,
            verbose=True,
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
            verbose=True,
        )










