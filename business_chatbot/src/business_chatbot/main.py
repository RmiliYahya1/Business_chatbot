import logging
import json
import time
import threading
import uuid
import queue
import requests
from business_chatbot.src.business_chatbot.business_flow import BusinessChatbotFlow as Processor

from business_chatbot.src.business_chatbot.crew import BusinessChatbot
from flask import Flask, jsonify, request, Response, stream_with_context


from  flask_cors import CORS

from business_chatbot.src.business_chatbot.tools.streaming_listener import flask_streaming_listener

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
            return jsonify({
                "message": "Use streaming endpoint for default queries",
                "streaming_url": "/api/stream"
            }), 200

        elif user_choice == 'b2c':
            response = crews_result
            return response
        elif user_choice == 'b2b':
            response = crews_result
            return response
    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        return jsonify({"response": "Désolé, une erreur s'est produite."}), 500


@app.route('/api/stream', methods=['POST'])
def stream_response():
    data = request.get_json()
    user_input = data.get('input', '')

    if not user_input.strip():
        return jsonify({'error': 'Input is required'}), 400

    client_id = str(uuid.uuid4())

    @stream_with_context
    def generate():
        try:
            # Enregistrer le client pour le streaming
            flask_streaming_listener.register_client(client_id)

            # Envoyer le message de démarrage
            yield f"data: {json.dumps({'type': 'start', 'message': 'Initialisation de l IA...', 'client_id': client_id})}\n\n"

            # Créer et exécuter le processor dans un thread séparé

            def run_processor():
                try:
                    user_info = {'choice': 'default', 'input': user_input}
                    processor = Processor()

                    # Exécuter le flow (le streaming se fait via les event listeners)
                    result = processor.kickoff(inputs=user_info)
                    processor.plot("my_flow_plot")

                    # Envoyer le résultat final
                    final_data = {
                        'type': 'final_result',
                        'content': str(result.raw) if hasattr(result, 'raw') else str(result),
                        'timestamp': time.time()
                    }

                    if client_id in flask_streaming_listener.client_queues:
                        flask_streaming_listener.client_queues[client_id].put(final_data)

                except Exception as e:
                    logger.error(f"Error in processor thread: {str(e)}")
                    error_data = {
                        'type': 'error',
                        'message': f'Erreur lors du traitement: {str(e)}',
                        'timestamp': time.time()
                    }

                    try:
                        if client_id in flask_streaming_listener.client_queues:
                            flask_streaming_listener.client_queues[client_id].put(error_data)
                    except Exception as put_error:
                        logger.error(f"Error putting error data to queue: {put_error}")

            # Démarrer le processor en arrière-plan
            processor_thread = threading.Thread(target=run_processor)
            processor_thread.daemon = True
            processor_thread.start()

            # Streamer les événements depuis la queue
            timeout_count = 0
            max_timeout = 30  # 30 secondes de timeout total

            while flask_streaming_listener.active_streams.get(client_id, False):
                try:
                    # Récupérer les données de la queue avec timeout
                    event_data = flask_streaming_listener.client_queues[client_id].get(timeout=1)

                    # Réinitialiser le compteur de timeout
                    timeout_count = 0

                    # Envoyer les données au client
                    yield f"data: {json.dumps(event_data)}\n\n"

                    # Vérifier si le streaming est terminé
                    if event_data.get('type') in ['complete', 'final_result', 'error']:
                        # Envoyer un message de fin
                        end_data = {'type': 'end', 'timestamp': time.time()}
                        yield f"data: {json.dumps(end_data)}\n\n"
                        break

                except queue.Empty:
                    timeout_count += 1

                    # Envoyer un heartbeat pour maintenir la connexion
                    heartbeat_data = {
                        'type': 'heartbeat',
                        'timestamp': time.time(),
                        'timeout_count': timeout_count
                    }
                    yield f"data: {json.dumps(heartbeat_data)}\n\n"

                    # Timeout global
                    if timeout_count >= max_timeout:
                        timeout_data = {
                            'type': 'timeout',
                            'message': 'Délai d attente dépassé',
                                                                 'timestamp': time.time()
                        }
                        yield f"data: {json.dumps(timeout_data)}\n\n"
                        break

                except Exception as e:
                    logger.error(f"Error in streaming loop: {str(e)}")
                    error_data = {
                        'type': 'stream_error',
                        'message': str(e),
                        'timestamp': time.time()
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                    break

        except Exception as e:
            logger.error(f"Error in stream generation: {str(e)}")
            error_data = {
                'type': 'generation_error',
                'message': str(e),
                'timestamp': time.time()
            }
            yield f"data: {json.dumps(error_data)}\n\n"

        finally:
            # Nettoyer les ressources du client
            flask_streaming_listener.unregister_client(client_id)
            logger.info(f"Streaming completed for client {client_id}")

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control',
            'X-Accel-Buffering': 'no'  # Pour nginx
        }
    )


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'active_streams': len(flask_streaming_listener.active_streams),
        'timestamp': time.time()
    })


# Gestionnaire d'erreurs pour les routes streaming
@app.errorhandler(Exception)
def handle_streaming_error(error):
    if request.path.startswith('/api/stream'):
        logger.error(f"Streaming error: {str(error)}")

        def error_stream():
            error_data = {
                'type': 'server_error',
                'message': 'Erreur interne du serveur',
                'timestamp': time.time()
            }
            yield f"data: {json.dumps(error_data)}\n\n"

        return Response(error_stream(), mimetype='text/event-stream', status=500)

    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # Importer et initialiser l'event listener
    print("Initializing streaming event listener...")

    app.run(debug=True, port=3002, threaded=True)