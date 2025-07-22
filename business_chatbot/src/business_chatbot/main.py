#!/usr/bin/env python
import sys
import warnings
from crew import BusinessChatbot

# Ignorer les avertissements de syntaxe non critiques
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def run_crew():
    """
    Permet à l'utilisateur de choisir un mode de test (consultation ou analyse de fichier)
    et lance le crew avec les inputs correspondants.
    """
    print("🤖 Bienvenue dans l'outil de test de BusinessChatbot 🤖")
    print("Veuillez choisir le mode d'exécution :")
    print("1: Consultation Directe (basée sur une simple question)")
    print("2: Analyse de Données (basée sur une question et un fichier CSV)")

    mode = input("Votre choix (1 ou 2) : ").strip()

    if mode == '1':
        print("\n=== Mode : Consultation Directe ===")
        user_question = input("Entrez votre question business/marketing : ").strip()
        if not user_question:
            print("Erreur : aucune question fournie. Annulation.")
            return
        # Les inputs pour la tâche de consultation directe
        inputs = {'demande': user_question}

    elif mode == '2':
        print("\n=== Mode : Analyse de Données (CSV) ===")
        user_question = input("Entrez votre question pour guider l'analyse : ").strip()
        csv_path = input("Entrez le chemin vers votre fichier CSV : ").strip()

        if not user_question or not csv_path:
            print("Erreur : question ou chemin de fichier manquant. Annulation.")
            return

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                csv_content = f.read()
            print(f"Fichier CSV '{csv_path}' lu avec succès.")

            # Les inputs pour la tâche d'analyse de données.
            # Le contenu du CSV est passé dans le contexte via le dictionnaire 'inputs'.
            # La clé 'csv_data' est un exemple ; assurez-vous que votre 'crew'
            # est configuré pour la transmettre correctement à la tâche.
            inputs = {
                'demande': user_question,
                'csv_data': csv_content
            }

        except FileNotFoundError:
            print(f"\nErreur : Le fichier '{csv_path}' n'a pas été trouvé.")
            return
        except Exception as e:
            print(f"\nUne erreur est survenue lors de la lecture du fichier : {e}")
            return

    else:
        print("Choix invalide. Veuillez redémarrer et choisir 1 ou 2.")
        return

    # Initialisation et lancement du crew
    try:
        print("\n🚀 Lancement du crew...")
        chatbot_crew = BusinessChatbot().crew()
        result = chatbot_crew.kickoff(inputs=inputs)

        print("\n--- ✅ Réponse Finale de l'Agent ---")
        print(result)

    except Exception as e:
        print(f"\nUne erreur critique est survenue pendant l'exécution du crew : {e}")


def replay():
    """
    Relance l'exécution d'un crew à partir d'une tâche spécifique (pour le débogage).
    """
    if len(sys.argv) < 2:
        print("Usage: python main.py replay <task_id>")
        return

    task_id = sys.argv[1]
    print(f"=== Tentative de Replay pour la tâche : {task_id} ===")

    try:
        BusinessChatbot().crew().replay(task_id=task_id)
    except Exception as e:
        print(f"Erreur lors du replay : {e}")


if __name__ == "__main__":
    # Permet d'appeler la fonction de replay via la ligne de commande,
    # ex: python main.py replay <ID_DE_LA_TACHE>
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'replay':
        replay()
    else:
        run_crew()