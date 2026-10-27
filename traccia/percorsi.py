"""Cartelle dell'app. Tutto sta sotto la radice della cartella del cliente (o sotto TRACCIA_RADICE nei test)."""

import hashlib
import os
from pathlib import Path

from .configurazione import directory

RADICE = Path(os.environ.get("TRACCIA_RADICE") or directory() / "dati")
CODICE = Path(__file__).resolve().parent.parent
ISTRUZIONI = CODICE / "istruzioni"
WEB = CODICE / "web"
PORTA = int(os.environ.get("TRACCIA_PORTA", "8765"))


def lavori() -> Path:
    return RADICE / "lavori"


def archivio() -> Path:
    return RADICE / "archivio"


def lavoro(id_lavoro: str) -> Path:
    if not id_lavoro or any(c not in "0123456789abcdefghijklmnopqrstuvwxyz-_" for c in id_lavoro):
        raise ValueError("identificativo del lavoro non valido")
    return lavori() / id_lavoro


def versione_lettura() -> str:
    """Versione delle istruzioni: cambia da sola se cambia anche un solo carattere di istruzioni/."""
    h = hashlib.sha256()
    for f in sorted(ISTRUZIONI.rglob("*.md")):
        h.update(f.relative_to(ISTRUZIONI).as_posix().encode())
        h.update(f.read_bytes().replace(b"\r\n", b"\n"))
    return "lettura2-" + h.hexdigest()[:10]
