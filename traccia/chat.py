"""Chat con la documentazione caricata.

La domanda arriva dal browser e l’agente cerca nelle pagine già lette, citando pagina e frase.
Python accetta la risposta solo se
ogni citazione si trova davvero nella pagina indicata. Le risposte non cambiano l'Excel né gli stati.
"""

import json
import re
import threading
import time
import uuid
from pathlib import Path

from . import lavoro as lv
from .controlli import piatto
from .preparazione import info_pagina

MAX_DOMANDA = 2000
MAX_RISULTATI = 8
_LOCK = threading.RLock()


def _file(cartella: Path) -> Path:
    return cartella / "chat.jsonl"


def messaggi(cartella: Path) -> list[dict]:
    f = _file(cartella)
    if not f.exists():
        return []
    with _LOCK:
        return [json.loads(r) for r in f.read_text(encoding="utf-8").splitlines() if r.strip()]


def _aggiungi(cartella: Path, messaggio: dict) -> dict:
    with _LOCK, _file(cartella).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(messaggio, ensure_ascii=False) + "\n")
    return messaggio


def chiedi(cartella: Path, testo: str, conversazione="principale", voce=None, pagine=None) -> dict:
    testo = (testo or "").strip()[:MAX_DOMANDA]
    if not testo:
        raise ValueError("domanda vuota")
    qid = "d" + uuid.uuid4().hex
    lv.evento(cartella, tipo="domanda", testo=testo[:120])
    return _aggiungi(
        cartella,
        {
            "id": qid,
            "ruolo": "utente",
            "testo": testo,
            "ora": time.strftime("%H:%M"),
            "conversazione": conversazione,
            "voce": voce,
            "pagine": pagine or [],
        },
    )


def in_attesa(cartella: Path) -> list[dict]:
    risposte = {m["domanda"] for m in messaggi(cartella) if m["ruolo"] != "utente" and "domanda" in m}
    return [m for m in messaggi(cartella) if m["ruolo"] == "utente" and m["id"] not in risposte]


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


def rispondi(cartella: Path, qid: str, risposta: dict) -> list[str]:
    """Valida e registra la risposta. Ritorna gli errori (lista vuota = registrata)."""
    domanda = next((m for m in messaggi(cartella) if m["ruolo"] == "utente" and m["id"] == qid), None)
    if not domanda:
        return [f"domanda {qid} non trovata"]
    if not isinstance(risposta, dict) or not isinstance(risposta.get("testo"), str) or not risposta["testo"].strip():
        return ['serve {"testo": "...", "fonti": [{"pid": "p0001", "cit": "..."}]}']
    fonti = risposta.get("fonti", [])
    if not isinstance(fonti, list):
        return ["fonti: lista di {pid, cit}"]
    pagine = {p["pid"]: p for p in lv.pagine(cartella)}
    errori, valide = [], []
    for i, f in enumerate(fonti):
        if (
            not isinstance(f, dict)
            or f.get("pid") not in pagine
            or not isinstance(f.get("cit"), str)
            or not piatto(f.get("cit", ""))
        ):
            errori.append(f"fonti[{i}]: pid di una pagina del lavoro e cit (testo)")
            continue
        testo = piatto(_testo_pagina(cartella, pagine[f["pid"]])).replace(" ", "")
        if piatto(f["cit"]).replace(" ", "") not in testo:
            errori.append(f"fonti[{i}]: la citazione non si trova nella pagina {f['pid']}")
            continue
        p = pagine[f["pid"]]
        valide.append({"pid": f["pid"], "file": p["file"], "pagina": p["pagina"], "cit": f["cit"][:300]})
    if errori:
        return errori
    testo = re.sub(r"\s+\n", "\n", risposta["testo"].strip())[:6000]
    _aggiungi(
        cartella,
        {
            "id": f"r{qid[1:]}",
            "ruolo": "claude",
            "domanda": qid,
            "testo": testo,
            "fonti": valide,
            "ora": time.strftime("%H:%M"),
            "conversazione": domanda.get("conversazione", "principale"),
        },
    )
    lv.evento(cartella, tipo="risposta", testo=testo[:120])
    return []


def fallita(cartella: Path, qid: str, testo: str) -> None:
    domanda = next((m for m in in_attesa(cartella) if m["id"] == qid), None)
    if domanda:
        _aggiungi(
            cartella,
            {
                "id": "e" + uuid.uuid4().hex,
                "ruolo": "stato",
                "domanda": qid,
                "testo": testo,
                "fonti": [],
                "ora": time.strftime("%H:%M"),
                "conversazione": domanda.get("conversazione", "principale"),
            },
        )
