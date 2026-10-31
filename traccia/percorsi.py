"""Cartelle dell'app. Tutto sta sotto la radice della cartella del cliente (o sotto TRACCIA_RADICE nei test)."""

import hashlib
import os
import time
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


_VERSIONE: tuple[tuple, str] | None = None  # (firma dei file, versione): si ricalcola solo se un file cambia
_VERSIONE_CONTROLLATA = 0.0
_VERSIONE_OGNI = 1.0  # secondi tra un controllo dei file e il successivo


def versione_lettura() -> str:
    """Versione delle istruzioni: cambia da sola se cambia anche un solo carattere di istruzioni/.

    Si chiama una volta per pagina a ogni aggiornamento dello stato: rileggere tutti i file ogni volta rendeva lenta
    la home. Al massimo una volta al secondo si guarda se un file ha cambiato nome, data o dimensione; solo allora si
    rileggono.
    """
    global _VERSIONE, _VERSIONE_CONTROLLATA
    adesso = time.monotonic()
    if _VERSIONE and adesso - _VERSIONE_CONTROLLATA < _VERSIONE_OGNI:
        return _VERSIONE[1]
    file = sorted(ISTRUZIONI.rglob("*.md"))
    firma = tuple((f.as_posix(), (st := f.stat()).st_mtime_ns, st.st_size) for f in file)
    _VERSIONE_CONTROLLATA = adesso
    if _VERSIONE and _VERSIONE[0] == firma:
        return _VERSIONE[1]
    h = hashlib.sha256()
    for f in file:
        h.update(f.relative_to(ISTRUZIONI).as_posix().encode())
        h.update(f.read_bytes().replace(b"\r\n", b"\n"))
    _VERSIONE = (firma, "lettura2-" + h.hexdigest()[:10])
    return _VERSIONE[1]
