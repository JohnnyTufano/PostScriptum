import json
import re
from typing import List
from google import genai
from google.genai import types

# Importiamo lo schema Pydantic dal modulo models.py
from models import Scene

def dividi_script_in_scene(testo_script: str) -> List[str]:
    """Divide la sceneggiatura in scene basandosi su INT./EST."""
    pattern_intestazione = r'(?=(?:INT\.|EST\.|INT/EST\.|EXT\.)\s+)'
    scene = re.split(pattern_intestazione, testo_script, flags=re.IGNORECASE)
    return [scena.strip() for scena in scene if scena.strip()]


def analizza_scena_con_ai(client: genai.Client, testo_scena: str, numero_scena: int) -> Scene:
    """Invia il testo della scena all'API di Gemini e ritorna l'oggetto Scene."""
    
    prompt = f"""
    Sei un assistente cinematografico esperto nello Script Breakdown.
    Analizza attentamente la Scena #{numero_scena} descritta di seguito ed estrai le entità richieste.

    Testo Scena:
    {testo_scena}
    """

    # Utilizziamo il modello aggiornato richiesto dall'API: gemini-3.6-flash
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Scene,
            temperature=0.1,
        ),
    )
    
    dati_json = json.loads(response.text)
    return Scene(**dati_json)