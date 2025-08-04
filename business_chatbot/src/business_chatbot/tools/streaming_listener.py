# streaming_listener.py
from crewai.utilities.events import (
    LLMStreamChunkEvent,
    LLMCallStartedEvent,
    LLMCallCompletedEvent
)
from crewai.utilities.events.base_event_listener import BaseEventListener
import queue
import threading
import time
import json


class FlaskStreamingListener(BaseEventListener):
    def __init__(self):
        super().__init__()
        self.client_queues = {}  # Stockage des queues par client
        self.active_streams = {}  # État des streams actifs
        self.current_chunks = {}  # Chunks actuels par client
        self.final_answer_started = {}  # Suivi si Final Answer a commencé
        self.final_answer_sent_length = {}  # Longueur déjà envoyée de Final Answer

    def register_client(self, client_id):
        """Enregistrer un nouveau client pour le streaming"""
        self.client_queues[client_id] = queue.Queue(maxsize=1000)
        self.active_streams[client_id] = True
        self.current_chunks[client_id] = []
        self.final_answer_started[client_id] = False
        self.final_answer_sent_length[client_id] = 0
        print(f"Client {client_id} registered for streaming")

    def unregister_client(self, client_id):
        """Nettoyer les ressources du client"""
        self.active_streams[client_id] = False
        if client_id in self.client_queues:
            # Vider la queue avant suppression
            while not self.client_queues[client_id].empty():
                try:
                    self.client_queues[client_id].get_nowait()
                except queue.Empty:
                    break
            del self.client_queues[client_id]
        if client_id in self.current_chunks:
            del self.current_chunks[client_id]
        if client_id in self.final_answer_started:
            del self.final_answer_started[client_id]
        if client_id in self.final_answer_sent_length:
            del self.final_answer_sent_length[client_id]
        print(f"Client {client_id} unregistered")

    def setup_listeners(self, crewai_event_bus):
        @crewai_event_bus.on(LLMCallStartedEvent)
        def on_llm_started(source, event):
            print(f"LLM call started: {event}")
            # Réinitialiser les chunks et variables de suivi pour tous les clients actifs
            for client_id in self.active_streams:
                if self.active_streams[client_id]:
                    self.current_chunks[client_id] = []
                    self.final_answer_started[client_id] = False
                    self.final_answer_sent_length[client_id] = 0
                    try:
                        self.client_queues[client_id].put_nowait({
                            'type': 'llm_start',
                            'timestamp': time.time(),
                            'message': 'AI is thinking...'
                        })
                    except queue.Full:
                        print(f"Queue full for client {client_id} on LLM start")

        @crewai_event_bus.on(LLMStreamChunkEvent)
        def on_chunk_received(source, event: LLMStreamChunkEvent):
            chunk_content = event.chunk
            print(f"Received chunk: {chunk_content[:50]}...")  # Debug

            # Envoyer le chunk à tous les clients actifs
            for client_id in list(self.client_queues.keys()):
                if self.active_streams.get(client_id, False):
                    # Ajouter le chunk au buffer complet
                    self.current_chunks[client_id].append(chunk_content)
                    full_content = ''.join(self.current_chunks[client_id])

                    # Vérifier si nous avons atteint "Final Answer:"
                    if "Final Answer:" in full_content:
                        # Extraire seulement la partie après "Final Answer:"
                        final_answer_index = full_content.find("Final Answer:")
                        if final_answer_index != -1:
                            final_answer_start = final_answer_index + len("Final Answer:")
                            final_answer_content = full_content[final_answer_start:].strip()

                            # Calculer le nouveau chunk à envoyer
                            if not hasattr(self, 'final_answer_started'):
                                self.final_answer_started = {}
                            if not hasattr(self, 'final_answer_sent_length'):
                                self.final_answer_sent_length = {}

                            if client_id not in self.final_answer_started:
                                self.final_answer_started[client_id] = True
                                self.final_answer_sent_length[client_id] = 0

                            # Envoyer seulement la nouvelle partie de la Final Answer
                            if len(final_answer_content) > self.final_answer_sent_length[client_id]:
                                new_chunk = final_answer_content[self.final_answer_sent_length[client_id]:]
                                self.final_answer_sent_length[client_id] = len(final_answer_content)

                                chunk_data = {
                                    'type': 'chunk',
                                    'content': new_chunk,
                                    'timestamp': time.time(),
                                    'total_length': len(final_answer_content)
                                }

                                try:
                                    self.client_queues[client_id].put_nowait(chunk_data)
                                except queue.Full:
                                    print(f"Queue full for client {client_id}")
                    else:
                        # Si nous n'avons pas encore atteint "Final Answer:", ne rien envoyer
                        # Mais garder les chunks pour les analyser plus tard
                        pass

        @crewai_event_bus.on(LLMCallCompletedEvent)
        def on_llm_completed(source, event):
            print("LLM call completed")

            # Envoyer la notification de completion à tous les clients
            for client_id in list(self.client_queues.keys()):
                if self.active_streams.get(client_id, False):
                    full_response = ''.join(self.current_chunks.get(client_id, []))

                    # Extraire seulement la Final Answer
                    final_answer = full_response
                    if "Final Answer:" in full_response:
                        final_answer_index = full_response.find("Final Answer:")
                        if final_answer_index != -1:
                            final_answer = full_response[final_answer_index + len("Final Answer:"):].strip()

                    completion_data = {
                        'type': 'complete',
                        'full_response': final_answer,  # Envoyer seulement la Final Answer
                        'timestamp': time.time(),
                        'total_chunks': len(self.current_chunks.get(client_id, []))
                    }

                    try:
                        self.client_queues[client_id].put_nowait(completion_data)
                    except queue.Full:
                        print(f"Queue full for client {client_id} on completion")


# Instance globale pour l'intégration Flask
flask_streaming_listener = FlaskStreamingListener()