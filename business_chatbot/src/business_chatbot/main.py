from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import logging
import threading
import queue
from business_chatbot.src.business_chatbot.business_flow import BusinessChatbotFlow as Processor
from business_chatbot.src.business_chatbot.crew import token_queue



app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/api/crew', methods=['POST'])
def handle_Requests():
    try:
    #recuperation de l'objet json fournie par la partie front-end
    #nous recuperrons un objet json avec deux attribut -- choice, input
        data = request.get_json()
        logging.info(data)

    #recuperer les valeur des clé de l'objet json et les stocker dans les variables -- user_choice, user_input
        user_choice = data['choice']
        user_input = data['input']
        logging.info(user_choice)
        logging.info(user_input)

    #injecter les valeur recuperé dans un objet json
        user_info ={'choice': user_choice, 'input': user_input}

        processor = Processor()
        crews_result = processor.kickoff(inputs=user_info)
        logging.info(f"Crew result: {crews_result}")

        if user_choice == 'default':
            if hasattr(crews_result, 'raw'):
                response_text = str(crews_result.raw)
            else:
                response_text = str(crews_result)

            return jsonify({"response": response_text}), 200

    except Exception as e:
        logging.error(f"Erreur: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
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