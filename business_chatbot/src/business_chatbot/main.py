from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import logging
import threading
import queue
from business_chatbot.src.business_chatbot.business_flow import BusinessChatbotFlow as Processor
from business_chatbot.src.business_chatbot.crew import token_queue, crewai_event_bus

app = Flask(__name__)
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

    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        return jsonify({"response": "Désolé, une erreur s'est produite."}), 500


@app.route('/api/crew/stream', methods=['POST'])
def stream_crew():
    data = request.get_json()
    logger.info(f"API stream request: {data}")

    # Réinitialiser la queue pour chaque nouvelle requête
    with token_queue.mutex:
        token_queue.queue.clear()

    processor = Processor()

    # Lancement dans un thread séparé
    thread = threading.Thread(
        target=processor.kickoff,
        kwargs={'inputs': {'choice': data.get('choice'), 'input': data.get('input')}},
        daemon=True
    )
    thread.start()

    def event_generator():
        while thread.is_alive() or not token_queue.empty():
            try:
                token = token_queue.get(timeout=1.0)
                logger.debug(f"Streaming token: {token}")
                yield f"data: {token}\n\n"
                token_queue.task_done()
            except queue.Empty:
                # Vérifier si le thread est toujours en cours
                if not thread.is_alive():
                    break
        yield "data: [END]\n\n"

    return Response(event_generator(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(debug=True, port=3002)