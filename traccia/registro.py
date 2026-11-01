"""Registro degli errori su file, nella cartella dati: le eccezioni inattese non si perdono più.

Il file ruota da solo (1 MB, 3 copie). Il percorso è mostrato in Impostazioni → Diagnostica.
"""

import logging
import logging.handlers
from pathlib import Path

from . import configurazione

NOME = "app.log"
_handler: logging.Handler | None = None
_percorso: Path | None = None


def percorso() -> Path:
    return configurazione.directory() / "log" / NOME


def configura() -> Path | None:
    """Collega il file di registro al logger `traccia`. Ritorna il percorso, o None se la cartella non è scrivibile."""
    global _handler, _percorso
    destinazione = percorso()
    logger = logging.getLogger("traccia")
    if _handler is not None and _percorso == destinazione:
        return destinazione
    if _handler is not None:
        logger.removeHandler(_handler)
        _handler.close()
        _handler = None
    try:
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            destinazione, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    except OSError:
        return None
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    _handler, _percorso = handler, destinazione
    return destinazione
