"""Famiglie di documento e campi della scheda.

Una sola fonte: le righe "testata:" e "righe:" dei file istruzioni/famiglie/*.md, cioè le stesse che legge Claude.
"""

import re
from functools import cache

from .percorsi import ISTRUZIONI

FAMIGLIE = [
    "packing_costruttore",
    "dop_costruttore",
    "ddt",
    "certificato_31",
    "dop_ce_prodotto",
    "lettera_accompagnamento",
    "da_escludere",
    "illeggibile",
]
NOMI = {
    "packing_costruttore": "Packing e tabelle del costruttore",
    "dop_costruttore": "DoP del costruttore",
    "ddt": "DDT",
    "certificato_31": "Certificati 3.1",
    "dop_ce_prodotto": "DoP e CE di prodotto",
    "lettera_accompagnamento": "Lettere di accompagnamento",
    "da_escludere": "Non pertinenti",
    "illeggibile": "Illeggibili",
}
TIPI_RIFERIMENTO = ["ddt", "certificato", "ordine", "dop", "fpc", "commessa"]
TIPI_SEGNO = ["freccia", "cerchio", "evidenziatore", "croce", "spunta", "scritta"]


def _elenco(riga: str) -> list[str]:
    valore = riga.split(":", 1)[1].strip()
    if valore.startswith("("):
        return []
    return [c.strip() for c in valore.split(",") if c.strip()]


@cache
def campi() -> dict[str, tuple[list[str], list[str]]]:
    """famiglia -> (campi della testata, campi delle righe)."""
    risultato = {f: ([], []) for f in FAMIGLIE}
    for file in sorted((ISTRUZIONI / "famiglie").glob("*.md")):
        testo = file.read_text(encoding="utf-8")
        testata = re.search(r"^testata:.*$", testo, re.M)
        righe = re.search(r"^righe:.*$", testo, re.M)
        if file.stem in risultato and testata and righe:
            risultato[file.stem] = (_elenco(testata.group(0)), _elenco(righe.group(0)))
    return risultato
