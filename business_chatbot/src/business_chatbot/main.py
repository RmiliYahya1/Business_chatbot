#!/usr/bin/env python
import sys
import warnings
import requests
from datetime import datetime
import pandas as pd
import json
from business_chatbot.src.business_chatbot.crew import BusinessChatbot
from flask import Flask, jsonify, request, abort, Response
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

params = {'page': 2, 'size': 50, 'sortBy': '_score', 'direction': 'desc'}

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
CORS(app, resources={r"/api/crew": {"origins": "http://localhost:3002"}})
@app.route('/api/crew', methods=['POST'])

def run():
    data = request.get_json()

    user_input = data.get('input')
    choosed_Agent = data.get('choice')
    input = {
        'user_query': user_input,
    }
    if not user_input or not choosed_Agent:
        return jsonify({'error': 'No input provided'}), 400

    try:
        if choosed_Agent == 'b2c':
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
                df = pd.DataFrame(filtered_records)

                # Create response with both JSON and CSV
                '''response = {
                    "status": "success",
                    "record_count": len(df),
                    "sample_data": df.head().to_dict('records'),
                    "csv_data": df.to_csv(index=False, encoding='utf-8')
                }'''
                return Response(
                df.to_csv(index=False, encoding='utf-8'),
                    mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=data.csv'}
                )

            except Exception as e:
                return jsonify({"error": f"Data processing failed: {str(e)}"}), 500

        elif choosed_Agent == 'b2b':
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

                df = pd.DataFrame(filtered_records)

                '''response = {
                    "status": "success",
                    "record_count": len(df),
                    "sample_data": df.head().to_dict('records'),
                    "csv_data": df.to_csv(index=False, encoding='utf-8')
                    "download_link": "/download-csv"
                }'''

                return Response(
                    df.to_csv(index=False, encoding='utf-8'),
                    mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=data.csv'}
                )

            except Exception as e:
                return jsonify({"error": f"Data processing failed: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"error": f"An error occurred while running the crew: {str(e)}"}), 500

def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "topic": "AI LLMs",
        'current_year': str(datetime.now().year)
    }
    try:
        BusinessChatbot().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        BusinessChatbot().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }
    
    try:
        BusinessChatbot().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


if __name__ == '__main__':
    app.run(debug=True, port=3002)