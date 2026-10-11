import hashlib
import json
import os
import random
import re
import time
from pathlib import Path

from google.genai import errors, types

from models import (AnalisiBlocco, Costume, Location, Materiale,
                    Personaggio, Sceneggiatura)

# Verifica i nomi disponibili con: [m.name for m in client.models.list()]
NOME_MODELLO = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
RPM = int(os.getenv("GEMINI_RPM", "5"))          # richieste/minuto del tuo piano free
CACHE_DIR = Path(".cache_analisi")

ISTRUZIONI = (
    "Sei un assistente di produzione cinematografica (spoglio di sceneggiatura). "
    "Per ogni scena del testo estrai: oggetti di scena/materiali, costumi per personaggio, "
    "location e un riassunto breve. Estrai anche ogni personaggio che compare. "
    "Non inventare nulla che non sia nel testo o chiaramente implicito. "
    "Usa lo stesso nome identico per lo stesso personaggio/location in tutte le scene. "
    "Rispondi in italiano."
)


class QuotaGiornalieraEsaurita(RuntimeError):
    pass


class ModelloSovraccarico(RuntimeError):
    pass


# ---------------------------------------------------------------- split & pack
RE_SCENA = re.compile(
    r"^\s*(?:\d+[A-Z]?\s*[\.\)\-–—:]*\s*)?"
    r"(?:INT\.?\s*/\s*EXT|EXT\.?\s*/\s*INT|INT|EXT|I/E|SCENA\s*\d+)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


def _spezza_lunga(testo: str, max_char: int) -> list[str]:
    """Se una 'scena' e' enorme (riconoscimento fallito), la spezza a fine riga."""
    pezzi, corrente = [], ""
    for riga in testo.splitlines(keepends=True):
        if corrente and len(corrente) + len(riga) > max_char:
            pezzi.append(corrente.strip())
            corrente = ""
        corrente += riga
    if corrente.strip():
        pezzi.append(corrente.strip())
    return pezzi


RE_RUMORE = re.compile(
    r"^\s*(?:\(CONTINUED\)|CONTINUED:\s*\d*\.?|\(MORE\)(?:\s*\(CONTINUED\))?|\d{1,3}\.)\s*$",
    re.IGNORECASE,
)


def pulisci_testo(testo: str) -> str:
    """Toglie il rumore da PDF: (CONTINUED), CONTINUED: 7., (MORE), numeri di pagina."""
    righe = [r for r in testo.splitlines() if not RE_RUMORE.match(r)]
    return "\n".join(righe)


def dividi_in_scene(testo: str, max_scena=60_000) -> list[str]:
    """Divide lo script in scene localmente (0 richieste API)."""
    inizi = [m.start() for m in RE_SCENA.finditer(testo)]
    if not inizi:  # nessuna intestazione riconosciuta: fallback a pezzi
        print("⚠️  Nessuna intestazione di scena riconosciuta: divido il testo a pezzi.")
        return _spezza_lunga(testo, 8_000)

    # il frontespizio prima della scena 1 viene unito alla scena 1 (non e' una scena)
    inizi[0] = 0
    inizi.append(len(testo))
    scene = [testo[a:b].strip() for a, b in zip(inizi, inizi[1:]) if testo[a:b].strip()]

    out = []
    for sc in scene:
        # una scena si spezza solo se e' davvero enorme
        out.extend(_spezza_lunga(sc, max_scena) if len(sc) > max_scena else [sc])
    return out


def raggruppa_in_blocchi(scene: list[str], max_scene=15, max_char=40_000) -> list[list[str]]:
    """Più scene per richiesta = meno richieste. Limite dato da output token e caratteri."""
    blocchi, corrente, char = [], [], 0
    for s in scene:
        if corrente and (len(corrente) >= max_scene or char + len(s) > max_char):
            blocchi.append(corrente)
            corrente, char = [], 0
        corrente.append(s)
        char += len(s)
    if corrente:
        blocchi.append(corrente)
    return blocchi


# ---------------------------------------------------------------- chiamata API
_ultima_chiamata = 0.0


def _rispetta_rpm():
    global _ultima_chiamata
    attesa = _ultima_chiamata + 60 / RPM - time.time()
    if attesa > 0:
        print(f"⏸️  Pausa {attesa:.0f}s per rispettare {RPM} RPM...")
        time.sleep(attesa)
    _ultima_chiamata = time.time()


def _secondi_di_attesa(msg: str, default: int) -> int:
    m = re.search(r"retry in ([\d.]+)s", msg, re.I) or re.search(r"retryDelay'?\"?:\s*'?\"?(\d+)", msg)
    return int(float(m.group(1))) + 2 if m else default


def _modelli_disponibili(client) -> str:
    try:
        nomi = [m.name.replace("models/", "") for m in client.models.list()
                if "generateContent" in (m.supported_actions or [])]
        flash = [n for n in nomi if "flash" in n and "image" not in n and "tts" not in n]
        return "  " + "\n  ".join(sorted(flash or nomi))
    except Exception as ex:
        return f"  (impossibile ottenere l'elenco: {ex})"


def _chiama(client, prompt: str, modello: str, max_retries=5) -> AnalisiBlocco:
    config = types.GenerateContentConfig(
        system_instruction=ISTRUZIONI,
        response_mime_type="application/json",
        response_schema=AnalisiBlocco,
        temperature=0.1,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    for tentativo in range(1, max_retries + 1):
        _rispetta_rpm()
        try:
            resp = client.models.generate_content(model=modello, contents=prompt, config=config)
            if resp.parsed is not None:
                return resp.parsed
            return AnalisiBlocco.model_validate_json(resp.text)

        except errors.ClientError as e:
            msg = str(e)
            if e.code == 404:
                raise RuntimeError(
                    f"Modello '{NOME_MODELLO}' non trovato.\n"
                    f"Modelli disponibili con la tua chiave:\n{_modelli_disponibili(client)}\n"
                    "Imposta quello scelto in key.env: GEMINI_MODEL=nome-modello"
                ) from e
            if e.code == 429:
                if "PerDay" in msg:  # quota giornaliera: inutile riprovare ora
                    raise QuotaGiornalieraEsaurita(msg) from e
                s = _secondi_di_attesa(msg, 35 * tentativo)
                print(f"⚠️  429 (tentativo {tentativo}/{max_retries}) - attendo {s}s")
                time.sleep(s)
                continue
            raise
        except errors.ServerError as e:  # 500/503 sovraccarico
            s = min(15 * 2 ** (tentativo - 1), 120) + random.randint(0, 5)
            print(f"⚠️  Errore server ({e.code}), riprovo tra {s}s")
            time.sleep(s)
        except ValueError as e:  # JSON non valido
            print(f"⚠️  Risposta non valida ({e}), riprovo")
    raise ModelloSovraccarico(f"Il modello {modello} e' sovraccarico o non risponde.")


def chiama_gemini(client, prompt: str) -> AnalisiBlocco:
    """Prova il modello principale; se e' sovraccarico usa quello di riserva (se impostato)."""
    try:
        return _chiama(client, prompt, NOME_MODELLO)
    except ModelloSovraccarico as e:
        riserva = os.getenv("GEMINI_FALLBACK_MODEL", "").strip()
        if not riserva or riserva == NOME_MODELLO:
            raise
        print(f"🔁 {e} Provo il modello di riserva: {riserva}")
        return _chiama(client, prompt, riserva)


# ---------------------------------------------------------------- cache
def _cache_path(prompt: str) -> Path:
    h = hashlib.sha256((NOME_MODELLO + ISTRUZIONI + prompt).encode()).hexdigest()[:16]
    return CACHE_DIR / f"{h}.json"


def analizza_blocco(client, scene: list[str]) -> AnalisiBlocco:
    prompt = "Analizza queste scene:\n\n" + "\n\n".join(scene)
    path = _cache_path(prompt)
    if path.exists():
        print("💾 Blocco già in cache, nessuna richiesta usata.")
        return AnalisiBlocco.model_validate_json(path.read_text(encoding="utf-8"))
    risultato = chiama_gemini(client, prompt)
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(risultato.model_dump_json(indent=2), encoding="utf-8")
    return risultato


# ---------------------------------------------------------------- merge
def _k(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _unisci_materiali(dest: list[Materiale], nuovi: list[Materiale]):
    visti = {_k(m.nome) for m in dest}
    for m in nuovi:
        if _k(m.nome) not in visti:
            dest.append(m)
            visti.add(_k(m.nome))


def unisci_risultati(blocchi: list[AnalisiBlocco], titolo="") -> Sceneggiatura:
    out = Sceneggiatura(titolo=titolo or "Senza titolo")
    pers: dict[str, Personaggio] = {}
    locs: dict[str, Location] = {}

    for b in blocchi:
        out.scene.extend(b.scene)

        for p in b.personaggi:
            esistente = pers.setdefault(_k(p.nome), Personaggio(nome=p.nome))
            if len(p.descrizione) > len(esistente.descrizione):
                esistente.descrizione = p.descrizione
            _unisci_materiali(esistente.materiali, p.materiali)

        for s in b.scene:
            for l in s.locations:
                e = locs.setdefault(_k(l.nome), Location(nome=l.nome))
                if len(l.descrizione) > len(e.descrizione):
                    e.descrizione = l.descrizione
                _unisci_materiali(e.materiali, l.materiali)
            # costume principale del personaggio = primo visto; il dettaglio resta per scena
            for c in s.costumi:
                p = pers.setdefault(_k(c.personaggio), Personaggio(nome=c.personaggio))
                if not p.costume.descrizione:
                    p.costume = Costume(personaggio=p.nome, descrizione=c.descrizione)

    out.personaggi = list(pers.values())
    out.locations = list(locs.values())
    return out


# ---------------------------------------------------------------- entry point
def analizza_script(client, testo_script: str, max_scene=15, max_char=40_000) -> Sceneggiatura:
    testo_script = pulisci_testo(testo_script)
    scene = dividi_in_scene(testo_script)
    blocchi = raggruppa_in_blocchi(scene, max_scene, max_char)
    print(f"📋 {len(scene)} scene → {len(blocchi)} richieste API (max).")

    risultati = []
    try:
        for i, blocco in enumerate(blocchi, 1):
            print(f"\n🔄 [Blocco {i}/{len(blocchi)}] {len(blocco)} scene")
            risultati.append(analizza_blocco(client, blocco))
            print(f"✅ [Blocco {i}/{len(blocchi)}] ok")
    except QuotaGiornalieraEsaurita:
        print("\n🛑 Quota giornaliera esaurita. I blocchi già fatti sono in cache: "
              "rilancia domani e ripartirà da dove si è fermato.")
        raise

    # Il titolo lo prendi dal nome del file / prima riga: zero richieste extra
    primo_rigo = testo_script.strip().splitlines()[0].strip() if testo_script.strip() else ""
    return unisci_risultati(risultati, titolo=primo_rigo[:100])