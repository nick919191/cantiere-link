"""Impara il dizionario del modulo da tutti i cantieri SCL e lo salva in risultati/dizionario.json (fuori da git).

Uso: .venv\\Scripts\\python esperimenti\\coltellino\\impara.py "<cartella SCL>"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import coltellino  # noqa: E402
import corpus  # noqa: E402

pagine = corpus.carica(Path(sys.argv[1]))
dizionario = coltellino.impara(pagine, lambda p: [v for _, v in p["sonde"]])
coltellino.salva(dizionario, coltellino.DIZIONARIO)
print(f"{len(dizionario)} forme di modulo da {len(pagine)} pagine -> {coltellino.DIZIONARIO}")
