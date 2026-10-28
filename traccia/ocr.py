"""OCR Mistral per la lettura veloce. La chiave sta solo nel portachiavi di sistema, mai nel progetto o nel browser.

Ogni pagina si legge una volta: il risultato si conserva in archivio/ocr/<impronta>.json e non si paga di nuovo.
"""

import base64
import json
import threading
import time
from pathlib import Path

import httpx
import keyring

from . import percorsi
from .chatgpt import AgentError

SERVICE = "tracciabilita-materiali.mistral"
URL = "https://api.mistral.ai/v1"
MODELLO = "mistral-ocr-latest"
SOGLIA_INCERTA = 0.80  # parole sotto questa sicurezza vengono segnalate al modello
_LOCK = threading.Lock()


def _vault():
    backend = keyring.get_keyring()
    if not type(backend).__module__.startswith(
        ("keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.SecretService")
    ):
        raise AgentError("Portachiavi sicuro non disponibile. Abilita il portachiavi del sistema e riprova.")
    return backend


def _chiave() -> str:
    try:
        return _vault().get_password(SERVICE, "api_key") or ""
    except AgentError:
        return ""


def configurato() -> bool:
    return bool(_chiave())


def stato() -> dict:
    return {"configurato": configurato()}


def salva(chiave: str) -> dict:
    """Controlla la chiave con Mistral prima di salvarla: una chiave sbagliata non entra nel portachiavi."""
    chiave = chiave.strip()
    if not chiave:
        raise AgentError("Inserisci la chiave Mistral.")
    try:
        r = httpx.get(URL + "/models", headers={"Authorization": "Bearer " + chiave}, timeout=20)
    except httpx.HTTPError as exc:
        raise AgentError("Mistral non raggiungibile: controlla la connessione e riprova.") from exc
    if r.status_code in (401, 403):
        raise AgentError("Mistral non accetta questa chiave. Controllala su console.mistral.ai.")
    if r.status_code != 200:
        raise AgentError(f"Mistral ha risposto con un errore ({r.status_code}). Riprova più tardi.")
    _vault().set_password(SERVICE, "api_key", chiave)
    return stato()


def rimuovi() -> dict:
    try:
        _vault().delete_password(SERVICE, "api_key")
    except keyring.errors.PasswordDeleteError:
        pass
    return stato()


def _cache(impronta: str) -> Path:
    return percorsi.archivio() / "ocr" / f"{impronta}.json"


def _incerte(pagina: dict) -> list[str]:
    punteggi = (pagina.get("confidence_scores") or {}).get("word_confidence_scores") or []
    out = []
    for p in punteggi:
        if isinstance(p, dict):
            testo, sicurezza = (p.get("text") or "").strip(), p.get("confidence")
            if testo and isinstance(sicurezza, (int, float)) and sicurezza < SOGLIA_INCERTA:
                out.append(testo)
    return out


def leggi(png: Path, impronta: str, client: httpx.Client) -> dict:
    """{testo, incerte, blocchi, secondi}: testo markdown con le tabelle, blocchi con la posizione in pixel."""
    file = _cache(impronta)
    if file.exists():
        return json.loads(file.read_text(encoding="utf-8"))
    documento = {
        "type": "image_url",
        "image_url": "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode(),
    }
    corpo = {"model": MODELLO, "document": documento, "include_blocks": True, "confidence_scores_granularity": "word"}
    inizio = time.perf_counter()
    for tentativo in range(3):
        try:
            r = client.post(URL + "/ocr", json=corpo)
        except httpx.HTTPError as exc:
            if tentativo == 2:
                raise AgentError("Mistral non raggiungibile: le pagine già lette restano salvate, riprova.") from exc
            time.sleep(2 * (tentativo + 1))
            continue
        if r.status_code == 429 and tentativo < 2:
            time.sleep(3 * (tentativo + 1))
            continue
        break
    if r.status_code in (401, 403):
        raise AgentError("Mistral non accetta la chiave salvata: aggiornala nelle impostazioni.")
    if r.status_code == 429:
        raise AgentError("Limite Mistral raggiunto: riprova tra qualche minuto, le pagine già lette restano salvate.")
    if r.status_code != 200:
        raise AgentError(f"OCR non riuscito (Mistral {r.status_code}). Riprova dal cantiere.")
    pagina = r.json()["pages"][0]
    risultato = {
        "testo": pagina.get("markdown", ""),
        "incerte": _incerte(pagina),
        "blocchi": [
            {
                k: v
                for k, v in b.items()
                if k in ("type", "content", "top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y")
            }
            for b in pagina.get("blocks") or []
        ],
        "secondi": round(time.perf_counter() - inizio, 2),
        "modello": MODELLO,
    }
    with _LOCK:
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(".tmp")
        tmp.write_text(json.dumps(risultato, ensure_ascii=False), encoding="utf-8")
        tmp.replace(file)
    return risultato


def client() -> httpx.Client:
    chiave = _chiave()
    if not chiave:
        raise AgentError("Chiave Mistral non impostata.")
    return httpx.Client(headers={"Authorization": "Bearer " + chiave}, timeout=120)
