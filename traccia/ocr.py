"""OCR Mistral per la lettura veloce. La chiave sta solo nel portachiavi di sistema, mai nel progetto o nel browser.

Ogni pagina si legge una volta: il risultato si conserva in archivio/ocr/<impronta>.json e non si paga di nuovo.
"""

import base64
import json
import threading
import time
from pathlib import Path

import httpx

from . import chiavi, percorsi
from .chatgpt import AgentError

URL = "https://api.mistral.ai/v1"
SOGLIA_INCERTA = 0.80  # parole sotto questa sicurezza vengono segnalate al modello
_LOCK = threading.Lock()


def _chiave() -> str:
    return chiavi.chiave("mistral")


def configurato() -> bool:
    return bool(_chiave())


def stato() -> dict:
    return chiavi.stato("mistral") | {"configurato": configurato()}


def salva(chiave: str) -> dict:
    """Controlla la chiave con Mistral prima di salvarla: una chiave sbagliata non entra nel portachiavi."""
    chiavi.salva("mistral", chiave)
    return stato()


def rimuovi() -> dict:
    chiavi.rimuovi("mistral")
    return stato()


def _cache(impronta: str) -> Path:
    return percorsi.archivio() / "ocr" / f"{impronta}.json"


def file_cache(impronta: str) -> Path:
    """File dell'OCR già fatto per questa pagina (può non esistere)."""
    return _cache(impronta)


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
    modello = chiavi.modello("mistral")
    corpo = {"model": modello, "document": documento, "include_blocks": True, "confidence_scores_granularity": "word"}
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
        "modello": modello,
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
