import requests
import json
from typing import Dict, Any


class APIClient:
    """Client pour interagir avec l'API B2B/B2C"""

    def __init__(self):
        self.base_url = "http://15.236.152.46:8080"
        self.headers = {"Content-Type": "application/json"}
        self.timeout = 30

    def call_b2b_api(self, query_dict: Dict[str, Any], use_fuzzy: bool = False) -> Dict[str, Any]:
        """Appel API B2B avec gestion fuzzy/exact"""
        endpoint = "/api/b2b/searchByAttrFuzz" if use_fuzzy else "/api/b2b/searchByAttrExact"
        url = f"{self.base_url}{endpoint}"
        return self._make_request(url, query_dict)

    def call_b2c_api(self, query_dict: Dict[str, Any], use_fuzzy: bool = False) -> Dict[str, Any]:
        """Appel API B2C avec gestion fuzzy/exact"""
        endpoint = "/api/b2c/searchByAttrFuzz" if use_fuzzy else "/api/b2c/searchByAttrExact"
        url = f"{self.base_url}{endpoint}"
        return self._make_request(url, query_dict)

    def _make_request(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Effectue la requête HTTP avec gestion d'erreurs"""
        try:
            response = requests.post(
                url,
                json=data,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Erreur API ({url}): {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Réponse API invalide: {str(e)}")