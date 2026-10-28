"""Prova del flusso veloce dell'app (traccia.veloce) su una copia di un cantiere, in una radice temporanea.

Le letture esistenti non si toccano. L'OCR già pagato della prova 2 si copia nella cache, se c'è.
La chiave Mistral si prende dalla variabile MISTRAL_API_KEY solo per questa prova (l'app usa il portachiavi).
Uso: .venv\\Scripts\\python esperimenti\\ocr_mistral\\prova_app.py <cartella del lavoro>
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

QUI = Path(__file__).parent
lavoro = Path(sys.argv[1]).resolve()
radice = Path(tempfile.mkdtemp(prefix="cantiere-veloce-"))
os.environ["TRACCIA_RADICE"] = str(radice)  # prima di ogni import di traccia: la radice si fissa all'import
sys.path.insert(0, str(QUI))
sys.path.insert(0, str(QUI.parents[1]))
import prova as p1  # noqa: E402

from traccia import agente, configurazione, ocr, percorsi  # noqa: E402
from traccia import lavoro as lv  # noqa: E402
from traccia.controlli import piatto  # noqa: E402

# letture di riferimento: quelle dell'app attuale, nell'archivio vero
assert percorsi.RADICE == radice
vero = configurazione.directory() / "dati" / "archivio" / "letture"
copia = percorsi.lavori() / lavoro.name
shutil.copytree(lavoro, copia, ignore=shutil.ignore_patterns("uscita", "eventi.jsonl", "tentativi.json", "consumi.json"))
cache = QUI / "risultati" / f"{lavoro.name}_v2" / "ocr"
pagine = lv.pagine(copia)
for p in pagine:
    if (cache / f"{p['pid']}.json").exists():
        dest = percorsi.archivio() / "ocr" / f"{p['impronta']}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(cache / f"{p['pid']}.json", dest)

ocr._chiave = p1.chiave_mistral
modello, sforzo = agente._options()
inizio = time.perf_counter()
try:
    agente.analizza(copia, modello, sforzo)
    esito = "completata"
except Exception as exc:  # noqa: BLE001
    esito = f"{type(exc).__name__}: {exc}"
secondi = time.perf_counter() - inizio

confronto = {"uguali": 0, "solo_forma": 0, "diversi": 0, "solo_attuale": 0, "solo_nuovo": 0}
lette = 0
for p in pagine:
    nuova = lv.scheda_pagina(p)
    lette += bool(nuova)
    f = next(vero.glob(f"{p['impronta']}_*.json"), None)
    if not (nuova and f):
        continue
    for _, a, n in p1._valori(json.loads(f.read_text(encoding="utf-8")), nuova):
        e = ("uguali" if piatto(a) == piatto(n) else "solo_attuale" if not n else "solo_nuovo" if not a
             else "solo_forma" if piatto(a) in piatto(n) or piatto(n) in piatto(a) else "diversi")
        confronto[e] += 1
consumi = json.loads((copia / "consumi.json").read_text(encoding="utf-8")) if (copia / "consumi.json").exists() else {}
print(json.dumps({"esito": esito, "secondi": round(secondi, 1), "pagine_lette": f"{lette}/{len(pagine)}",
                  "excel": (copia / "uscita").exists(), "consumi": consumi, "confronto_campi": confronto,
                  "radice": str(radice)}, ensure_ascii=False, indent=1))
