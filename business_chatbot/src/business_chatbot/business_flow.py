from crewai.flow.flow import Flow, start, router, listen
import logging
from pydantic import BaseModel
from business_chatbot.src.business_chatbot.crew import BusinessChatbot


logger = logging.getLogger(__name__)

class UserChoice(BaseModel):
    choice: str = ""
    input: str = ""

class BusinessChatbotFlow(Flow[UserChoice]):
    def __init__(self):
        super().__init__()
        self.business_chatbot = BusinessChatbot()

    def kickoff(self, inputs=None):
        if inputs:
            for key, value in inputs.items():
                if hasattr(self.state, key):
                    setattr(self.state, key, value)
        return super().kickoff(inputs=inputs)

    @start()
    def button_choice(self):
        logger.info(f"Running flow with choice: {self.state.choice}, input: {self.state.input}")
        return self.state.choice

    @router(button_choice)
    def routing(self):
        if self.state.choice == 'default':
            return "default"
        elif self.state.choice == 'b2b':
            return "b2b"
        elif self.state.choice == 'b2c':
            return "b2c"

    @listen('default')
    def consultation_direct(self):
        user_query = self.state.input
        logger.info(f"Executing consultation_direct with query: {user_query}")
        crew_result = self.business_chatbot.consultation_direct().kickoff(inputs={'user_query':user_query})
        logger.info(f"Crew result: {crew_result}")
        return crew_result
