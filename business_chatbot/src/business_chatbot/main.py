from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import logging
from business_chatbot.src.business_chatbot.business_flow import BusinessChatbotFlow as Processor



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

if __name__ == '__main__':
    app.run(debug=True, port=3002)