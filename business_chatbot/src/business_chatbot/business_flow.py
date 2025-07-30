import json
import tempfile
import warnings

import pandas as pd
from crewai.flow.flow import Flow, start, router, listen
import logging

from crewai_tools.tools.csv_search_tool.csv_search_tool import CSVSearchTool
from flask import jsonify, request, abort, Response, stream_with_context
import requests
from pydantic import BaseModel
from business_chatbot.src.business_chatbot.crew import BusinessChatbot

Rag=CSVSearchTool()
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
from  flask_cors import CORS
# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information
agents=BusinessChatbot()
b2b_api_url = "http://15.236.152.46:8080/api/b2b/searchByAttrExact"  # @param {type:"string"}
b2c_api_url = "http://15.236.152.46:8080/api/b2c/searchByAttrExact"
# Proper variable assignment for payload
payload = {

}

headers = {
    "Content-Type": "application/json",
    "Accept": "*/*"
}

params = {'page': 10, 'size': 10, 'sortBy': '_score', 'direction': 'desc'}

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
        crew_result = self.business_chatbot.consultation_direct().kickoff(inputs={'user_query':user_query})
        logger.info(f"Crew result: {crew_result}")
        return crew_result

    @listen('b2c')
    def b2c_extraction(self):
        user_query = self.state.input
        input={'user_query':user_query}
        query = BusinessChatbot().b2c_crew().kickoff(inputs=input)
        # Handle CrewOutput conversion
        if hasattr(query, 'raw_output'):
            query_dict = query.raw_output
        elif hasattr(query, 'result'):
            query_dict = query.result
        else:
            try:
                query_dict = json.loads(str(query))
            except json.JSONDecodeError:
                return jsonify({"error": "Failed to parse CrewAI output"}), 400

        # Make API request and handle response
        result = make_post_request(b2c_api_url, query_dict, headers, params)

        # Ensure result is a dictionary
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                return jsonify({
                    "error": "Invalid API response format",
                    "raw_response": result[:200]
                }), 400

        desired_fields = [
            "idS", "userId", "phoneNumber", "firstName", "lastName", "gender",
            "currentCity", "currentCountry", "hometownCity", "hometownCountry",
            "relationshipStatus", "workplace", "email", "currentDepartment", "currentRegion"
        ]

        # Process the data
        try:
            records = []
            if 'results' in result:
                records = result['results']
            elif 'page' in result and 'content' in result['page']:
                records = result['page']['content']

            filtered_records = [
                {field: record.get(field) for field in desired_fields}
                for record in records
                if isinstance(record, dict)
            ]

            if not filtered_records:
                return jsonify({"error": "No valid records found after filtering"}), 404

            # Create DataFrame
            df = pd.DataFrame(records)

            # Create response with both JSON and CSV
            '''response = {
                "status": "success",
                "record_count": len(df),
                "sample_data": df.head().to_dict('records'),
                "csv_data": df.to_csv(index=False, encoding='utf-8')
            }'''
            '''return Response(
            df.to_csv(index=False, encoding='utf-8'),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=data.csv'}
            )'''
            csv_data = df.to_csv(index=False, encoding='utf-8')
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp:
                tmp.write(csv_data)
                csv_path = tmp.name

            rag = CSVSearchTool(
                file_path=csv_path,
                description="Tool to search through the provided business data"
            )

            BusinessChatbot().set_rag_tool(rag)  # Set the RAG tool
            input.update({
                'dataset_info': f"Dataset loaded with {len(df)} B2C records. Use the search tool to analyze the data."})

            # Now call expert_crew2 without parameters
            response = BusinessChatbot().expert_crew2().kickoff(inputs=input)

            return jsonify({
                "response": str(response),
                "csv": csv_data
            }), 200
        except Exception as e:
            return jsonify({"error": f"Data processing failed: {str(e)}"}), 500
