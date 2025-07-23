from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Type, Optional

class CSVGenerator:
    """Génère des fichiers CSV et crée des sections markdown pour le téléchargement."""

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path.home() / "Downloads"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # Move this method outside of __init__ and directly under the class
    def create_enhanced_download_section(
            self,
            data: List[Dict[str, Any]],
            filename_prefix: str = "analysis",
            analysis_type: str = "business",
            description: str = "Données complètes de l'analyse"
    ) -> str:
        """Crée une section markdown complète avec le lien de téléchargement du CSV."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{filename_prefix}_{analysis_type}_{timestamp}.csv"
            file_path = self.output_dir / filename

            df = pd.DataFrame(data)
            df.to_csv(file_path, index=False, encoding='utf-8-sig')

            if not file_path.exists():
                raise FileNotFoundError(f"La création du fichier a échoué : {file_path}")

            file_size_kb = round(os.path.getsize(file_path) / 1024, 2)

            return f"""## 📊 Vos Données Prêtes à Télécharger

    [**Télécharger le fichier CSV ({file_size_kb} KB)**]({file_path.as_uri()})

    **Détails du fichier :**
    - **Nom :** `{filename}`
    - **Registres :** `{len(data)}`
    - **Emplacement :** `{self.output_dir}`

    *{description}*
    """
        except Exception as e:
            return f"""## Erreur de Génération CSV
    Une erreur est survenue : {str(e)}"""


class CSVFileCreatorInput(BaseModel):
     """Schéma d'input pour l'outil de création de fichiers CSV."""
     data: List[Dict[str, Any]] = Field(..., description="Liste de dictionnaires (données brutes) à sauvegarder en CSV.")
     analysis_type: str = Field(default="export", description="Type d'analyse (ex: 'b2b', 'b2c') pour nommer le fichier.")
     filename_prefix: str = Field(default="analysis_results", description="Préfixe personnalisé pour le nom du fichier.")

class CSVFileCreatorTool(BaseTool):
    name: str = "CSV File Creator"
    description: str = (
        "Outil indispensable pour sauvegarder une liste de données structurées (dictionnaires) "
        "dans un fichier CSV et générer une section markdown complète avec un lien de téléchargement. "
        "À utiliser systématiquement lorsque des données doivent être fournies à l'utilisateur."
    )
    args_schema: Type[BaseModel] = CSVFileCreatorInput
    csv_generator: CSVGenerator = CSVGenerator()

    def _run(self, data: List[Dict[str, Any]], analysis_type: str = "export", filename_prefix: str = "analysis_results") -> str:
        """Exécute la logique de création de CSV et retourne la section markdown."""
        print(f"--- Executing CSVFileCreatorTool for {analysis_type} ---")
        return self.csv_generator.create_enhanced_download_section(
            data=data,
            filename_prefix=filename_prefix,
            analysis_type=analysis_type,
            description=f"Données exportées suite à l'analyse de type {analysis_type}."
        )