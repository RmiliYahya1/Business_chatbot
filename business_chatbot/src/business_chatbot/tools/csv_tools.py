import pandas as pd
from typing import Dict, Any, List
import io

class CSVProcessor:
    """Processeur pour conversion et traitement des données CSV"""

    def __init__(self):
        self.b2c_fields = [
            "idS", "userId", "phoneNumber", "firstName", "lastName", "gender",
            "currentCity", "currentCountry", "hometownCity", "hometownCountry",
            "relationshipStatus", "workplace", "email", "currentDepartment", "currentRegion"
        ]

        self.b2b_fields = [
            "placeId", "name", "description", "rating", "reviews", "website",
            "phone", "address", "city", "state", "countryCode", "mainCategory",
            "isSpendingOnAds", "isTemporarilyClosed", "isPermanentlyClosed"
        ]

    def _extract_records(self, api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extrait les enregistrements de la réponse API"""
        if 'content' in api_response:
            return api_response['content']
        elif 'results' in api_response:
            return api_response['results']
        elif isinstance(api_response, list):
            return api_response
        else:
            raise ValueError(f"Format de réponse API non reconnu: {list(api_response.keys())}")

    def process_b2c_data(self, api_response: Dict[str, Any]) -> str:
        """Traite les données B2C et retourne du CSV"""
        records = self._extract_records(api_response)
        filtered_records = [
            {field: record.get(field) for field in self.b2c_fields}
            for record in records if isinstance(record, dict)
        ]

        if not filtered_records:
            raise ValueError("Aucun enregistrement B2C valide trouvé")

        df = pd.DataFrame(filtered_records)
        return df.to_csv(index=False, encoding='utf-8')

    def process_b2b_data(self, api_response: Dict[str, Any]) -> str:
        """Traite les données B2B et retourne du CSV"""
        records = self._extract_records(api_response)
        filtered_records = [
            {field: record.get(field) for field in self.b2b_fields}
            for record in records if isinstance(record, dict)
        ]

        if not filtered_records:
            raise ValueError("Aucun enregistrement B2B valide trouvé")

        df = pd.DataFrame(filtered_records)
        return df.to_csv(index=False, encoding='utf-8')
