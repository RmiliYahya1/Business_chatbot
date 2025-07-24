from crewai.flow.flow import Flow, start, router, listen
from business_chatbot.src.business_chatbot.crew import BusinessChatbot
from business_chatbot.src.business_chatbot.tools.api_client import APIClient
from business_chatbot.src.business_chatbot.tools.csv_tools import CSVProcessor
from typing import Dict, Any, Literal
import json

class BusinessChatbotFlow(Flow):
    def __init__(self):
        super().__init__()
        self.crews = BusinessChatbot()
        self.api_client = APIClient()
        self.csv_processor = CSVProcessor()
        self.user_input = ""
        self.button_choice = None
        self._last_result = None  # Ajout pour stocker le contexte

    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.user_input = inputs.get('user_input', '')
        self.button_choice = inputs.get('choice', None)
        return super().kickoff(inputs)

    @start()
    def analyze_request(self) -> Dict[str, Any]:
        route = self._determine_route(self.button_choice)
        return {
            'user_query': self.user_input,
            'choice': self.button_choice,
            'route_decision': route
        }

    def _determine_route(self, choice: str) -> str:
        if choice == 'b2b':
            return 'b2b_pipeline'
        elif choice == 'b2c':
            return 'b2c_pipeline'
        else:
            return 'direct_consultation'

    @router(analyze_request)
    def route_request(self, result: Dict[str, Any]) -> Literal["direct_consultation", "b2b_pipeline", "b2c_pipeline"]:
        self._last_result = result  # Stocke le contexte complet
        return result['route_decision']

    @listen("direct_consultation")
    def direct_consultation(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if 'user_query' not in result and self._last_result:
            result = self._last_result
        if not result.get('user_query', '').strip():
            return {'type': 'error', 'error': 'Demande utilisateur vide', 'status': 'done'}
        consultation_result = self.crews.consultation_direct().kickoff(inputs={'demande': result['user_query']})
        response_text = self._extract_crew_output(consultation_result)
        return {'type': 'direct_response', 'response': response_text, 'status': 'done'}

    @listen("b2b_pipeline")
    def b2b_pipeline(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if 'user_query' not in result and self._last_result:
            result = self._last_result
        return self._pipeline_common(result, 'b2b')

    @listen("b2c_pipeline")
    def b2c_pipeline(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if 'user_query' not in result and self._last_result:
            result = self._last_result
        return self._pipeline_common(result, 'b2c')

    def _pipeline_common(self, result: Dict[str, Any], mode: str) -> Dict[str, Any]:
        if not result.get('user_query', '').strip():
            return {'type': 'error', 'error': f'Demande utilisateur vide pour pipeline {mode.upper()}', 'status': 'done'}
        crew_method = getattr(self.crews, f"{mode}_crew")()
        json_query_result = crew_method.kickoff(inputs={'user_query': result['user_query']})
        query_dict = self._parse_crew_output(json_query_result)
        api_method = getattr(self.api_client, f"call_{mode}_api")
        api_response = api_method(query_dict)
        csv_method = getattr(self.csv_processor, f"process_{mode}_data")
        csv_data = csv_method(api_response)
        return {
            'type': 'data_analysis',
            'csv_data': csv_data,
            'user_query': result['user_query'],
            'status': 'done'
        }

    def _extract_crew_output(self, crew_result):
        if hasattr(crew_result, 'raw'):
            output = crew_result.raw
        elif hasattr(crew_result, 'output'):
            output = crew_result.output
        elif hasattr(crew_result, 'result'):
            output = crew_result.result
        else:
            output = str(crew_result)
        return output if output is not None else "Pas de réponse"

    def _parse_crew_output(self, crew_result):
        raw_output = self._extract_crew_output(crew_result)
        if isinstance(raw_output, dict):
            return raw_output
        try:
            cleaned = str(raw_output).strip('`').strip()
            if cleaned.startswith('json'):
                cleaned = cleaned[4:].strip()
            return json.loads(cleaned)
        except Exception:
            return {}