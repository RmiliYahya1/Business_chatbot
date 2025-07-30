from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import logging
import threading
import queue
from business_chatbot.src.business_chatbot.business_flow import BusinessChatbotFlow as Processor
from business_chatbot.src.business_chatbot.crew import token_queue, crewai_event_bus
import sys
import warnings
import requests
import tempfile
from datetime import datetime
import pandas as pd
import json
from crewai_tools import CSVSearchTool
from business_chatbot.src.business_chatbot.crew import BusinessChatbot
from flask import Flask, jsonify, request, abort, Response, stream_with_context

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


app= Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route('/api/crew', methods=['POST'])
def handle_Requests():
    try:
        data = request.get_json()
        logger.info(data)

        user_choice = data['choice']
        user_input = data['input']
        logger.info(f"Choice: {user_choice}, Input: {user_input}")

        user_info = {'choice': user_choice, 'input': user_input}
        processor = Processor()
        crews_result = processor.kickoff(inputs=user_info)
        logger.info(f"Crew result: {crews_result}")

        if user_choice == 'default':
            response_text = str(crews_result.raw) if hasattr(crews_result, 'raw') else str(crews_result)
            return jsonify({"response": response_text}), 200

        elif user_choice == 'b2c':

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

        elif user_choice == 'b2b':
            query = BusinessChatbot().b2b_crew().kickoff(inputs=input)
            print(query)
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
            result = make_post_request(b2b_api_url, query_dict, headers, params)
            print(result)
            # Ensure result is a dictionary
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    return jsonify({"error": "Invalid API response format"}), 400

            desired_fields = [
                "place_id",
                "city",
                "coordinates",
                "detailed_address",
                "rating"
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

                df = pd.DataFrame(records)
                csv_data = df.to_csv(index=False, encoding='utf-8')
                with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp:
                    tmp.write(csv_data)
                    csv_path = tmp.name

                rag = CSVSearchTool(
                    file_path=csv_path,
                    description="Tool to search through the provided business data"
                )

                BusinessChatbot().set_rag_tool(rag)
                input.update({
                                 'dataset_info': f"Dataset loaded with {len(df)} B2B records. Use the search tool to analyze the data."})

                # Now call expert_crew2 without parameters
                response = BusinessChatbot().expert_crew2().kickoff(inputs=input)
                return jsonify({"response": str(response)
                                   , "csv": csv_data}), 200

            except Exception as e:
                return jsonify({"error": f"Data processing failed: {str(e)}"}), 500


    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        return jsonify({"response": "Désolé, une erreur s'est produite."}), 500


@app.route('/api/crew/stream', methods=['POST'])
def stream_crew():
    data = request.get_json()
    logger.info(f"API stream request: {data}")
    processor = Processor()

    # Lancement dans un thread séparé
    thread = threading.Thread(target=lambda: processor.kickoff(inputs={'choice': data.get('choice'), 'input': data.get('input')}), daemon=True)
    thread.start()

    def event_generator():
        while thread.is_alive() or not token_queue.empty():
            try:
                token = token_queue.get(timeout=0.5)
                yield f"data: {token}\n\n"
                token_queue.task_done()
            except queue.Empty:
                continue
        yield "data: [END]\n\n"

    return Response(event_generator(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, port=3002)