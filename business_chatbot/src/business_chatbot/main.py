from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import logging
from business_chatbot.src.business_chatbot.business_flow import BusinessChatbotFlow as Processor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


@app.route('/api/crew', methods=['POST'])
def run():
    """Point d'entrée principal de l'API"""
    try:
        # Validation des données
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Aucune donnée JSON fournie'}), 400

        user_input = data.get('input')
        chosen_agent = data.get('choice')

        if not user_input:
            return jsonify({'error': 'Input utilisateur manquant'}), 400

        print(f"[MAIN] Requête reçue - Input: '{user_input}', Choice: '{chosen_agent}'")

        # Traitement avec l'approche choisie
        processor = Processor()

        flow_inputs = {
            'user_input': user_input,
            'choice': chosen_agent
        }
        print(f"[MAIN] Inputs pour le Flow: {flow_inputs}")

        processor.plot()
        result = processor.kickoff(inputs=flow_inputs)


        print(f"[MAIN] Type du résultat: {type(result)}")
        print(f"[MAIN] Contenu du résultat: {result}")

        # Vérification que le résultat n'est pas None
        if result is None:
            return jsonify({'error': 'Le processeur a retourné None - vérifiez les logs'}), 500

        return _handle_result(result)

    except Exception as e:
        logger.error(f"[MAIN] Erreur dans /api/crew: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


def _handle_result(result) -> Response:
    """Traite le résultat et retourne la réponse appropriée"""

    # Vérification de sécurité
    if result is None:
        return jsonify({'error': 'Résultat vide'}), 500

    # Si result n'est pas un dict, on le convertit
    if not isinstance(result, dict):
        return jsonify({
            'response': str(result),
            'type': 'raw_output'
        })

    result_type = result.get('type', 'unknown')
    print(f"[MAIN] Traitement résultat type: {result_type}")

    if result_type == 'direct_response':
        return jsonify({
            'response': result.get('response', 'Pas de réponse'),
            'type': 'consultation'
        })

    elif result_type == 'data_analysis':
        return jsonify({
            'response': result.get('response', 'Pas de réponse'),
            'type': 'analysis',
            'csv_available': True,
            'csv_data': result.get('csv_data', ''),
            'record_count': len(result.get('csv_data', '').split('\n')) - 2 if result.get('csv_data') else 0
        })

    elif result_type == 'error':
        return jsonify({
            'error': result.get('error', 'Erreur inconnue'),
            'type': 'error'
        }), 500

    else:
        return jsonify({
            'response': str(result),
            'type': 'unknown'
        })


if __name__ == '__main__':
    app.run(debug=True, port=3002)