"""Ricerca nelle pagine già lette: parole della domanda -> pagine con estratti. Deterministica, nessuna AI."""

from pathlib import Path

from . import lavoro as lv
from .controlli import piatto
from .preparazione import info_pagina

MAX_RISULTATI = 8


def _testo_pagina(cartella: Path, p: dict) -> str:
    s = lv.scheda_pagina(p) or {}
    nativo = info_pagina(cartella, p["pid"]).get("testo_nativo", "")
    return (s.get("trascrizione", "") + "\n" + nativo).strip()


def cerca(cartella: Path, domanda: str) -> list[dict]:
    """Pagine lette che contengono le parole della domanda, in ordine di pertinenza (deterministico)."""
    parole = {w for w in piatto(domanda).split() if len(w) >= 3 or w.isdigit()}
    risultati = []
    for p in lv.pagine(cartella):
        s = lv.scheda_pagina(p)
        if not s:
            continue
        testo = _testo_pagina(cartella, p)
        piano = piatto(testo)
        trovate = [w for w in parole if w in piano.split() or (len(w) >= 5 and w in piano)]
        if not trovate:
            continue
        righe = [r for r in testo.splitlines() if any(w in piatto(r) for w in trovate)][:4]
        risultati.append(
            {
                "pid": p["pid"],
                "file": p["file"],
                "pagina": p["pagina"],
                "famiglia": s["famiglia"],
                "parole_trovate": sorted(trovate),
                "estratto": righe,
            }
        )
    risultati.sort(key=lambda r: (-len(r["parole_trovate"]), r["pid"]))
    return risultati[:MAX_RISULTATI]
