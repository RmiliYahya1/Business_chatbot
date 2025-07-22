#!/usr/bin/env python
import sys
import warnings
from datetime import datetime
from crew import BusinessChatbot

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def run():
    """
    Run the crew with user input for direct consultation.
    """
    print("=== Test de l'agent business_expert - Consultation Directe ===")
    user_input = input("Entrez votre question business/marketing : ").strip()

    if not user_input:
        print("Erreur : aucun input utilisateur fourni.")
        return

    chatbot_crew = BusinessChatbot().crew()
    inputs = {'demande': user_input}

    print("Mode consultation directe sélectionné.")

    try:
        # Since only direct_consultation_task is active, it will be the only task in the crew's list
        # and will be executed by default when kickoff is called.
        print("Lancement du crew pour consultation directe...")
        result = chatbot_crew.kickoff(inputs=inputs)
        print("\n--- Réponse de l'agent ---\n")
        print(result)

    except Exception as e:
        print(f"\nUne erreur est survenue pendant l'exécution du crew : {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        # If you only have one task, the task_id might be predictable or you can adapt this.
        BusinessChatbot().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        print(f"Erreur lors du replay : {e}")



if __name__ == "__main__":
    run()