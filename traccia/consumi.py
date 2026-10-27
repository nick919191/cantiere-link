"""Token usati con ChatGPT: per cantiere (consumi.json nella cartella) e totale (consumi.json nella radice dati).

Il piano ChatGPT non espone un costo in euro: si contano soltanto i token dichiarati dal servizio a fine risposta.
"""

import json
import threading
from pathlib import Path

from . import percorsi

_LOCK = threading.Lock()
VUOTO = {"chiamate": 0, "ingresso": 0, "uscita": 0}


def _leggi(f: Path) -> dict:
    try:
        return {**VUOTO, **json.loads(f.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return dict(VUOTO)


def _aggiungi(f: Path, ingresso: int, uscita: int) -> None:
    dati = _leggi(f)
    dati["chiamate"] += 1
    dati["ingresso"] += ingresso
    dati["uscita"] += uscita
    f.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = f.with_suffix(".tmp")
    temporaneo.write_text(json.dumps(dati), encoding="utf-8")
    temporaneo.replace(f)


def registra(cartella: Path, consumo: dict) -> None:
    """`consumo` è il dizionario riempito da chatgpt.response: {"ingresso": n, "uscita": n}."""
    ingresso, uscita = int(consumo.get("ingresso", 0)), int(consumo.get("uscita", 0))
    if not consumo.get("chiamata"):
        return
    with _LOCK:
        _aggiungi(cartella / "consumi.json", ingresso, uscita)
        _aggiungi(percorsi.RADICE / "consumi.json", ingresso, uscita)


def cantiere(cartella: Path) -> dict:
    return _leggi(cartella / "consumi.json")


def totale() -> dict:
    return _leggi(percorsi.RADICE / "consumi.json")
