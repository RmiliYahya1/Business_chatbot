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
from flask import Response
import time
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

        def generate_response():
            try:
                logger.info("Starting B2B consultation...")
                yield f"data: {json.dumps({'status': 'starting', 'message': 'Initialisation du processus d\'extraction B2B...', 'progress': 10})}\n\n"

                # 1. Generate query with B2B crew
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Génération de requête', 'progress': 20})}\n\n"
                query = self.business_chatbot.b2b_crew().kickoff(inputs=inputs_dict)
                logger.info(f"B2B Query result: {query}")
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Requête générée avec succès', 'progress': 30})}\n\n"

                # 2. Handle CrewOutput conversion
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Traitement de la sortie...', 'progress': 35})}\n\n"
                if hasattr(query, 'raw_output'):
                    query_dict = query.raw_output
                elif hasattr(query, 'result'):
                    query_dict = query.result
                else:
                    try:
                        query_dict = json.loads(str(query))
                    except json.JSONDecodeError:
                        yield f"data: {json.dumps({'status': 'error', 'message': 'Failed to parse CrewAI output', 'progress': 35})}\n\n"
                        return

                # 3. Make API request
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Envoyer la requête API pour récupérer des données...', 'progress': 40})}\n\n"
                result = make_post_request(b2b_api_url, query_dict, headers, params)
                yield f"data: {json.dumps({'status': 'processing', 'message': 'API request accompli', 'progress': 50})}\n\n"

                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError:
                        yield f"data: {json.dumps({'status': 'error', 'message': 'Invalid API response format', 'progress': 50})}\n\n"
                        return

                # 4. Process data
                desired_fields = [
                    "placeId", "name", "description", "isSpendingOnAds", "reviews", "rating",
                    "website", "mockEmail", "phone", "canClaim", "ownerId", "ownerName",
                    "ownerLink", "featuredImage", "mainCategory", "categories", "workdayTiming",
                    "isTemporarilyClosed", "isPermanentlyClosed","address","closedOn",
                    "link", "status", "priceRange", "featuredQuestion", "reviewsLink",
                    "latitude", "longitude", "plusCode", "ward", "street", "city",
                    "postalCode", "state", "countryCode", "timeZone", "cid", "dataId",
                    "about", "images", "hours", "popularTimes", "mostPopularTimes",
                    "featuredReviews", "detailedReviews", "query", "score", "scoreCategory",
                    "competitors", "reviewKeywords", "reviewsPerRating", "coordinates"
                ]

                records = []
                if 'results' in result:
                    records = result['results']
                elif 'page' in result and 'content' in result['page']:
                    records = result['page']['content']

                if not records:
                    yield f"data: {json.dumps({'status': 'error', 'message': 'Aucun enregistrement trouvé dans la réponse de l\'API', 'progress': 60})}\n\n"
                    return

                records = [record for record in records if isinstance(record, dict)]
                if not records:
                    yield f"data: {json.dumps({'status': 'error', 'message': 'No valid records after filtering', 'progress': 60})}\n\n"
                    return

                logger.info(f"Processed {len(records)} B2B records")
                yield f"data: {json.dumps({'status': 'processing', 'message': f'Found {len(records)} valid records', 'progress': 65})}\n\n"

                # 5. Create CSV
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Création d\'un fichier CSV à partir de données traitées...', 'progress': 70})}\n\n"
                df = pd.DataFrame(records)
                # Filter for columns that actually exist in the DataFrame
                available_columns = [col for col in desired_fields if col in df.columns]
                df1 = df[available_columns]
                csv_data = df1.to_csv(index=False, encoding='utf-8')
                yield f"data: {json.dumps({'status': 'processing', 'message': 'CSV généré avec succès', 'progress': 75})}\n\n"

                # 6. Create RAG analysis
                with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp:
                    tmp.write(csv_data)
                    csv_path = tmp.name
                    logger.info(f"Created temporary CSV at: {csv_path}")

                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Configuration de l\'outil d\'analyse RAG...', 'progress': 80})}\n\n"
                    rag = CSVSearchTool(
                        file_path=csv_path,
                        description="Tool to search through the provided B2B business data"
                    )

                    BusinessChatbot().set_rag_tool(rag)
                    inputs_dict.update({
                        'dataset_info': f"Dataset loaded with {len(df)} B2B records. Use the search tool to analyze a random sample of data."
                    })

                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Début de l\'analyse des données...', 'progress': 85})}\n\n"
                    logger.info("Calling expert_crew2 for analysis...")
                    response = BusinessChatbot().expert_crew2().kickoff(inputs=inputs_dict)
                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Analyse terminée', 'progress': 95})}\n\n"

                    # Final result
                    final_result = {
                        "status": "success",
                        "response": str(response),
                        "csv": csv_data,
                        "headers": df.columns.tolist()
                    }
                    yield f"data: {json.dumps(final_result)}\n\n"
                    yield f"data: {json.dumps({'status': 'completed', 'message': 'Extraction et analyse B2B terminées avec succès', 'progress': 100})}\n\n"

            except Exception as e:
                logger.error(f"B2B extraction error: {str(e)}")
                yield f"data: {json.dumps({'status': 'error', 'message': f'Data processing failed: {str(e)}', 'progress': -1})}\n\n"

        return Response(
            generate_response(),
            mimetype='text/event-stream',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
        )

    @listen('b2c')
    def b2c_extraction(self):
        user_query = self.state.input
        inputs_dict = {'user_query': user_query}

        def generate_response():
            try:
                logger.info("Starting B2C extraction...")
                yield f"data: {json.dumps({'status': 'starting', 'message': 'Initialisation du processus d\'extraction B2C...', 'progress': 10})}\n\n"
                time.sleep(0.5)
                # 1. Générer la requête avec le crew B2C
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Génération de requête...', 'progress': 20})}\n\n"
                query = self.business_chatbot.b2c_crew().kickoff(inputs=inputs_dict)
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Requête générée avec succès', 'progress': 30})}\n\n"

                # 2. Handle CrewOutput conversion
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Traitement de la sortie...', 'progress': 35})}\n\n"
                if hasattr(query, 'raw_output'):
                    query_dict = query.raw_output
                elif hasattr(query, 'result'):
                    query_dict = query.result
                else:
                    try:
                        query_dict = json.loads(str(query))
                    except json.JSONDecodeError:
                        yield f"data: {json.dumps({'status': 'error', 'message': 'Failed to parse CrewAI output', 'progress': 35})}\n\n"
                        return

                # 3. Make API request
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Envoyer la requête API pour récupérer des données...', 'progress': 40})}\n\n"
                result = make_post_request(b2c_api_url, query_dict, headers, params)
                yield f"data: {json.dumps({'status': 'processing', 'message': 'API request accompli', 'progress': 50})}\n\n"

                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError:
                        yield f"data: {json.dumps({'status': 'error', 'message': 'Invalid API response format', 'progress': 50})}\n\n"
                        return

                # 4. Process data
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Processing and filtering data records...', 'progress': 60})}\n\n"
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
                    yield f"data: {json.dumps({'status': 'error', 'message': 'Aucun enregistrement trouvé dans la réponse de l\'API', 'progress': 60})}\n\n"
                    return

                records = [
                    record for record in records if isinstance(record, dict)
                ]

                if not records:
                    yield f"data: {json.dumps({'status': 'error', 'message': 'No valid records after filtering', 'progress': 60})}\n\n"
                    return

                yield f"data: {json.dumps({'status': 'processing', 'message': f'Found {len(records)} valid records', 'progress': 65})}\n\n"

                # 5. Create CSV
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Création d\'un fichier CSV à partir de données traitées...', 'progress': 70})}\n\n"
                df = pd.DataFrame(records)
                csv_data = df.to_csv(index=False, encoding='utf-8')
                yield f"data: {json.dumps({'status': 'processing', 'message': 'CSV généré avec succès', 'progress': 75})}\n\n"

                # 6. Create RAG analysis
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Configuration de l\'outil d\'analyse RAG...', 'progress': 80})}\n\n"
                with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp:
                    tmp.write(csv_data)
                    csv_path = tmp.name

                rag = CSVSearchTool(
                    file_path=csv_path,
                    description="Tool to search through the provided B2C consumer data"
                )

                BusinessChatbot().set_rag_tool(rag)  # Set the RAG tool
                inputs_dict.update({
                                       'dataset_info': f"Dataset loaded with {len(df)} B2C records. Use the search tool to analyze a random sample of data."})

                yield f"data: {json.dumps({'status': 'processing', 'message': 'Début de l\'analyse des données...', 'progress': 85})}\n\n"
                logger.info("Calling expert_crew2 for analysis...")
                # ✅ Appel correct de expert_crew2 (paramètre positionnel)
                response = BusinessChatbot().expert_crew2().kickoff(inputs=inputs_dict)
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Analyse terminée', 'progress': 95})}\n\n"

                yield f"data: {json.dumps({'status': 'completed', 'message': 'Extraction et analyse B2B terminées avec succès', 'progress': 100})}\n\n"

                # Send final result
                final_result = {
                    "status": "success",
                    "response": str(response),
                    "csv": csv_data,
                    "headers": df.columns.tolist()
                }
                yield f"data: {json.dumps(final_result)}\n\n"

            except Exception as e:
                logger.error(f"B2C extraction error: {str(e)}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                yield f"data: {json.dumps({'status': 'error', 'message': f'Data processing failed: {str(e)}', 'progress': -1})}\n\n"

        return Response(
            generate_response(),
            mimetype='text/event-stream',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
        )