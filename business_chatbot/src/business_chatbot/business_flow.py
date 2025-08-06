import json
import tempfile
import warnings
import pandas as pd
from crewai.flow.flow import Flow, start, router, listen
import logging
from crewai_tools.tools.csv_search_tool.csv_search_tool import CSVSearchTool
from flask import jsonify
import requests
from pydantic import BaseModel
from business_chatbot.src.business_chatbot.crew import BusinessChatbot

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

b2b_api_url = "http://15.236.152.46:8080/api/b2b/searchByAttrExact"
b2c_api_url = "http://15.236.152.46:8080/api/b2c/searchByAttrExact"

payload = {}
headers = {
    "Content-Type": "application/json",
    "Accept": "*/*"
}
params = {'sortBy': '_score', 'direction': 'desc'}


def make_post_request(url, payload, headers, params):
    """Make POST request and handle response"""
    try:
        print(f"Making POST request to {url}...")
        print(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(url, json=payload, headers=headers, timeout=30, params=params)
        response.raise_for_status()

        print(f"Success! Status Code: {response.status_code}")

        try:
            return response.json()
        except ValueError:
            print("Response is not JSON, returning raw text")
            return {"raw_response": response.text}

    except requests.exceptions.RequestException as e:
        print(f"Error making request: {str(e)}")
        return {"error": str(e), "type": type(e).__name__}


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
        crew_result = self.business_chatbot.consultation_direct().kickoff(inputs={'user_query': user_query})
        logger.info(f"Crew result: {crew_result}")
        return crew_result

    @listen('b2b')
    def b2b_consultation(self):
        user_query = self.state.input
        inputs_dict = {'user_query': user_query}

        try:
            logger.info("Starting B2B consultation...")

            # 1. Générer la requête avec le crew B2B
            query = self.business_chatbot.b2b_crew().kickoff(inputs=inputs_dict)
            logger.info(f"B2B Query result: {query}")

            # 2. Handle CrewOutput conversion
            if hasattr(query, 'raw_output'):
                query_dict = query.raw_output
            elif hasattr(query, 'result'):
                query_dict = query.result
            else:
                try:
                    query_dict = json.loads(str(query))
                except json.JSONDecodeError:
                    return jsonify({"error": "Failed to parse CrewAI output"}), 400

            logger.info("Making API request...")
            # 3. Make API request
            result = make_post_request(b2b_api_url, query_dict, headers, params)

            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    return jsonify({"error": "Invalid API response format"}), 400

            # 4. Process data
            desired_fields = [
                "place_id", "name", "city", "coordinates",
                "detailed_address", "rating", "phone", "opening_hours"
            ]

            records = []
            if 'results' in result:
                records = result['results']
            elif 'page' in result and 'content' in result['page']:
                records = result['page']['content']

            if not records:
                return jsonify({"error": "No records found"}), 404

            records = [
                record for record in records if isinstance(record, dict)
            ]

            if not records:
                return jsonify({"error": "No valid records after filtering"}), 404

            logger.info(f"Processed {len(records)} B2B records")

            # 5. Create CSV for download
            df = pd.DataFrame(records)
            csv_data = df.to_csv(index=False, encoding='utf-8')

            # 6. Create temporary file for RAG analysis
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp:
                tmp.write(csv_data)
                csv_path = tmp.name

            logger.info(f"Created temporary CSV at: {csv_path}")

            # 7. Create RAG tool for analysis
            rag = CSVSearchTool(
                file_path=csv_path,
                description="Tool to search through the provided B2B business data"
            )

            # 8. ✅ SOLUTION CORRIGÉE : Utiliser expert_crew2 correctement
            BusinessChatbot().set_rag_tool(rag)  # Set the RAG tool
            inputs_dict.update({'dataset_info': f"Dataset loaded with {len(df)} B2B records. Use the search tool to analyze a random sample of  data."})

            logger.info("Calling expert_crew2 for analysis...")
            # ✅ Appel correct de expert_crew2 (paramètre positionnel)
            response = BusinessChatbot().expert_crew2().kickoff(inputs=inputs_dict)

            logger.info("Analysis completed successfully")

            return jsonify({
                "response": str(response),
                "csv": csv_data
            }), 200

        except Exception as e:
            logger.error(f"B2B consultation error: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return jsonify({"error": f"Data processing failed: {str(e)}"}), 500

    @listen('b2c')
    def b2c_extraction(self):
        user_query = self.state.input
        inputs_dict = {'user_query': user_query}

        try:
            logger.info("Starting B2C extraction...")

            # 1. Générer la requête avec le crew B2C
            query = self.business_chatbot.b2c_crew().kickoff(inputs=inputs_dict)

            # 2. Handle CrewOutput conversion
            if hasattr(query, 'raw_output'):
                query_dict = query.raw_output
            elif hasattr(query, 'result'):
                query_dict = query.result
            else:
                try:
                    query_dict = json.loads(str(query))
                except json.JSONDecodeError:
                    return jsonify({"error": "Failed to parse CrewAI output"}), 400

            # 3. Make API request
            result = make_post_request(b2c_api_url, query_dict, headers, params)

            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    return jsonify({"error": "Invalid API response format"}), 400

            # 4. Process data
            desired_fields = [
                "idS", "userId", "phoneNumber", "firstName", "lastName", "gender",
                "currentCity", "currentCountry", "hometownCity", "hometownCountry",
                "relationshipStatus", "workplace", "email", "currentDepartment", "currentRegion"
            ]

            records = []
            if 'results' in result:
                records = result['results']
            elif 'page' in result and 'content' in result['page']:
                records = result['page']['content']

            if not records:
                return jsonify({"error": "No records found"}), 404

            records = [
                record for record in records if isinstance(record, dict)
            ]

            if not records:
                return jsonify({"error": "No valid records after filtering"}), 404

            # 5. Create CSV
            df = pd.DataFrame(records)
            csv_data = df.to_csv(index=False, encoding='utf-8')

            # 6. Create RAG analysis
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp:
                tmp.write(csv_data)
                csv_path = tmp.name

            rag = CSVSearchTool(
                file_path=csv_path,
                description="Tool to search through the provided B2C consumer data"
            )

            BusinessChatbot().set_rag_tool(rag)  # Set the RAG tool
            inputs_dict.update({'dataset_info': f"Dataset loaded with {len(df)} B2C records. Use the search tool to analyze a random sample of data."})

            logger.info("Calling expert_crew2 for analysis...")
            # ✅ Appel correct de expert_crew2 (paramètre positionnel)
            response = BusinessChatbot().expert_crew2().kickoff(inputs=inputs_dict)
            return jsonify({
                "response": str(response),
                "csv": csv_data
            }), 200

        except Exception as e:
            logger.error(f"B2C extraction error: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return jsonify({"error": f"Data processing failed: {str(e)}"}), 500