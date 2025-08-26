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
        user_id = data.get('userId', 'anonymous')
        conversation_id = data.get('conversationId', str(uuid.uuid4()))
        search_enabled = data.get('searchEnabled', False)
        logger.info(f"Choice: {user_choice}, Input: {user_input}")

        user_info = {'choice': user_choice, 'input': user_input,'user_id': user_id, 'conversation_id': conversation_id,'search_enabled': bool(search_enabled),}
        processor = Processor()
        crews_result = processor.kickoff(inputs=user_info)
        logger.info(f"Crew result: {crews_result}")



        if user_choice in ['b2c', 'b2b']:
            return crews_result


    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        return jsonify({"response": "Désolé, une erreur s'est produite."}), 500


@app.route('/api/stream', methods=['POST'])
def stream_response():
    data = request.get_json()
    user_input = data.get('input', '')
    user_id = data.get('userId', 'anonymous')
    conversation_id = data.get('conversationId')
    search_enabled = data.get('searchEnabled', False)
    client_id = conversation_id or str(uuid.uuid4())

    if not user_input.strip():
        return jsonify({'error': 'Input is required'}), 400

    @stream_with_context
    def generate():
        try:
            # Envoyer le message de démarrage
            yield f"data: {json.dumps({'type': 'start', 'message': 'Initialisation de l IA...', 'client_id': client_id})}\n\n"

            # Exécuter le processor et attendre le résultat COMPLET
            user_info = {
                'choice': 'default',
                'input': user_input,
                'user_id': user_id,
                'conversation_id': client_id,
                'search_enabled': bool(search_enabled)
            }
            processor = Processor()

            # CHANGEMENT PRINCIPAL: Exécuter sans streaming intermédiaire
            result = processor.kickoff(inputs=user_info)

            # Extraire seulement la réponse finale
            if hasattr(result, 'raw'):
                final_response = str(result.raw)
            else:
                final_response = str(result)

            # Maintenant streamer la réponse finale mot par mot pour l'effet visuel
            words = final_response.split()
            for i, word in enumerate(words):
                if i == 0:
                    token = word
                else:
                    token = " " + word

                chunk_data = {
                    'type': 'chunk',
                    'content': token,
                    'timestamp': time.time()
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
                time.sleep(0.03)  # Délai pour simuler le streaming naturel

            # Signal de fin
            end_data = {
                'type': 'final_result',
                'content': final_response,
                'timestamp': time.time()
            }
            yield f"data: {json.dumps(end_data)}\n\n"

        except Exception as e:
            logger.error(f"Error in stream generation: {str(e)}")
            error_data = {
                'type': 'error',
                'message': f'Erreur lors du traitement: {str(e)}',
                'timestamp': time.time()
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control',
            'X-Accel-Buffering': 'no'
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


app.route('/api/stream1', methods=['POST'])
def handle_streaming_requests():
    try:
        data = request.get_json()
        user_choice = data.get('choice')
        user_input = data.get('input')

        if user_choice != 'b2c':
            return jsonify({"error": "This endpoint only supports B2C streaming requests"}), 400

        def progress_generator():
            user_info = {'choice': user_choice, 'input': user_input}
            processor = Processor()

            # Yield progress updates directly from processor
            for update in processor.kickoff(inputs=user_info):
                yield f"data: {json.dumps(update)}\n\n"

        response = Response(
            progress_generator(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',  # Nginx
                'X-Sendfile-Type': '',  # Apache
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            }
        )

        # Disable buffering at the response level
        response.implicit_sequence_conversion = False
        return response

    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        return Response(
            f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n",
            mimetype='text/event-stream'
        )

if __name__ == '__main__':
    # Importer et initialiser l'event listener
    print("Initializing streaming event listener...")
    app.run(debug=True, port=3002, threaded=True, use_reloader=False)