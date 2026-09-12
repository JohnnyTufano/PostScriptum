import os
import json
from google import genai

# Importiamo dal nostro modulo ai_service
from aiService import dividi_script_in_scene, analizza_scena_con_ai
from models import Sceneggiatura

if __name__ == "__main__":
    # 1. Inizializzazione Client Gemini (cerca la variabile d'ambiente GEMINI_API_KEY)
    # Oppure puoi passare la chiave diretta: genai.Client(api_key="TUA_API_KEY")
    client = genai.Client()

    # 2. Sceneggiatura di prova
    script_test = """
    INT. RISTORANTE - NOTTE
    Marco indossa una giacca di pelle nera. Siede al tavolo maneggiando un vecchio orologio d'oro.
    Giulia entra correndo, indossando un impermeabile rosso. Appoggia una pistola d'argento sul tavolo.

    EST. STRADA - NOTTE
    Giulia corre sotto la pioggia impugnando la pistola d'argento.
    """

    print("--- Avvio divisione scene ---")
    scene_estratte = dividi_script_in_scene(script_test)
    print(f"Trovate {len(scene_estratte)} scene.\n")

    lista_scene_elaborate = []

    # 3. Analisi di ogni scena tramite IA
    for i, testo_scena in enumerate(scene_estratte, start=1):
        print(f"Elaborazione Scena {i} con l'IA...")
        scena_obj = analizza_scena_con_ai(client, testo_scena, numero_scena=i)
        lista_scene_elaborate.append(scena_obj)

    # 4. Creazione dell'oggetto globale Sceneggiatura
    sceneggiatura_finale = Sceneggiatura(
        titolo="Film di Prova",
        descrizione="Script di test per il breakdown",
        scene=lista_scene_elaborate
    )

    # 5. Salvataggio su file JSON
    with open("output_breakdown.json", "w", encoding="utf-8") as f:
        json.dump(sceneggiatura_finale.model_dump(), f, indent=4, ensure_ascii=False)

    print("\n✅ Breakdown completato con successo! Il file 'output_breakdown.json' è stato generato.")