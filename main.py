import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from pypdf import PdfReader

import aiService


def leggi_script(percorso: str) -> str:
    p = Path(percorso)
    if p.suffix.lower() == ".pdf":
        reader = PdfReader(str(p))
        return "\n".join(pagina.extract_text() or "" for pagina in reader.pages)
    return p.read_text(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Spoglio automatico di una sceneggiatura con Gemini")
    ap.add_argument("script", help="File di testo dello script (.txt)")
    ap.add_argument("-o", "--output", default="analisi.json")
    ap.add_argument("--scene-per-blocco", type=int, default=15)
    args = ap.parse_args()

    if Path("key.env").exists():
        load_dotenv("key.env")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("❌ GEMINI_API_KEY mancante in key.env o nelle variabili d'ambiente.")

    testo = leggi_script(args.script)
    if not testo.strip():
        sys.exit("❌ Nessun testo estratto: il PDF potrebbe essere una scansione (immagini).")
    print(f"📄 Estratti {len(testo)} caratteri dallo script.")
    Path("script_estratto.txt").write_text(testo, encoding="utf-8")  # per controllare l'estrazione
    client = genai.Client(api_key=api_key)

    try:
        risultato = aiService.analizza_script(client, testo, max_scene=args.scene_per_blocco)
    except aiService.QuotaGiornalieraEsaurita:
        sys.exit(1)
    except Exception as e:
        sys.exit(f"💥 Errore: {e}")

    Path(args.output).write_text(risultato.model_dump_json(indent=2), encoding="utf-8")
    print(f"\n🎉 Fatto: {len(risultato.scene)} scene, {len(risultato.personaggi)} personaggi, "
          f"{len(risultato.locations)} location → {args.output}")


if __name__ == "__main__":
    main()