"""Stato di un lavoro, archivio delle letture, eventi per la piattaforma.

Lo stato si ricalcola sempre dai file: pagine preparate + letture in archivio + tentativi. Per questo una sessione
chiusa a metà riprende da sola: le pagine con una lettura in archivio non si rileggono mai.
"""

import json
import threading
import time
from pathlib import Path

from . import consumi, percorsi
from .famiglie import FAMIGLIE

MAX_TENTATIVI = 4
DIMENSIONE_LOTTO = 8


# ---------- archivio ----------
def chiave_lettura(impronta: str) -> str:
    return f"{impronta}_{percorsi.versione_lettura()}"


def file_lettura(impronta: str) -> Path:
    return percorsi.archivio() / "letture" / f"{chiave_lettura(impronta)}.json"


def leggi_lettura(impronta: str) -> dict | None:
    f = file_lettura(impronta)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def salva_lettura(impronta: str, scheda: dict) -> None:
    f = file_lettura(impronta)
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists():  # congelata: mai riscritta
        return
    temporaneo = f.with_suffix(".tmp")
    temporaneo.write_text(json.dumps(scheda, ensure_ascii=False, indent=1), encoding="utf-8")
    temporaneo.replace(f)


def cartella_ritagli() -> Path:
    return percorsi.archivio() / "ritagli"


# ---------- eventi ----------
_SCRITTURA = threading.Lock()


def evento(cartella: Path, **dati) -> None:
    """Una riga per evento, scritta in un colpo solo. La piattaforma legge per posizione di riga."""
    riga = {"ora": time.strftime("%H:%M:%S"), "t": round(time.time()), **dati}
    with _SCRITTURA, (cartella / "eventi.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(riga, ensure_ascii=False) + "\n")


def eventi(cartella: Path, da: int = 0) -> list[dict]:
    """Eventi dalla riga `da` in poi; una riga ancora in scrittura (senza a capo) si legge la volta dopo."""
    f = cartella / "eventi.jsonl"
    if not f.exists():
        return []
    testo = f.read_text(encoding="utf-8")
    righe = testo.split("\n")[:-1]  # l'ultimo pezzo è vuoto o incompleto
    return [json.loads(r) for r in righe[da:]]


# ---------- stato ----------
def _json(f: Path, vuoto):
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else vuoto


def tentativi(cartella: Path) -> dict[str, int]:
    return _json(cartella / "tentativi.json", {})


def segna_tentativi(cartella: Path, pids: list[str]) -> None:
    t = tentativi(cartella)
    for pid in pids:
        t[pid] = t.get(pid, 0) + 1
    (cartella / "tentativi.json").write_text(json.dumps(t, indent=1), encoding="utf-8")


def pagine(cartella: Path) -> list[dict]:
    return [p for p in _json(cartella / "pagine.json", []) if p.get("pid")]


def scheda_pagina(p: dict) -> dict | None:
    """Lettura della pagina: dall'archivio, oppure automatica per le pagine bianche (nessuna chiamata)."""
    if p.get("bianca"):
        return {
            "famiglia": "da_escludere",
            "utile": False,
            "motivo": "pagina bianca (controllo sull'immagine)",
            "bianca": True,
            "automatica": True,
            "testata": {},
            "righe": [],
            "riferimenti": [],
            "timbri": [],
            "segni": [],
            "avvisi": [],
            "trascrizione": "",
            "orientamento": 0,
            "continua_pagina_prima": False,
        }
    return leggi_lettura(p["impronta"])


def stato(cartella: Path) -> dict:
    info = _json(cartella / "info.json", {})
    elenco = pagine(cartella)
    t = tentativi(cartella)
    per_famiglia = {f: 0 for f in FAMIGLIE}
    lette, da_leggere, non_lette, dettagli = 0, [], [], []
    for p in elenco:
        s = scheda_pagina(p)
        voce = {"pid": p["pid"], "file": p["file"], "pagina": p["pagina"]}
        if s:
            lette += 1
            per_famiglia[s["famiglia"]] = per_famiglia.get(s["famiglia"], 0) + 1
            voce.update(famiglia=s["famiglia"], stato="letta")
        elif t.get(p["pid"], 0) >= MAX_TENTATIVI:
            non_lette.append(p["pid"])
            voce.update(stato="non_letta")
        else:
            da_leggere.append(p["pid"])
            voce.update(stato="da_leggere")
        dettagli.append(voce)
    preparata = (cartella / "pagine.json").exists()
    composto = _json(cartella / "uscita" / "riepilogo.json", None)
    if not preparata:
        fase = "preparazione"
    elif da_leggere:
        fase = "lettura"
    elif composto and composto.get("impronta") == impronta_letture(cartella):
        fase = "pronto"
    else:
        fase = "composizione"
    totale = len(elenco)
    return {
        "lavoro": cartella.name,
        "nome": info.get("nome", cartella.name),
        "creato": info.get("creato", ""),
        "fase": fase,
        "pagine_totali": totale,
        "file": len({p["file"] for p in elenco}),
        "lette": lette,
        "da_leggere": len(da_leggere),
        "non_lette": non_lette,
        "percentuale": round(100 * (lette + len(non_lette)) / totale) if totale else 0,
        "per_famiglia": per_famiglia,
        "pagine": dettagli,
        "riepilogo": composto,
        "consumo": consumi.cantiere(cartella),
    }


def impronta_letture(cartella: Path) -> str:
    """Cambia se cambia una lettura, la versione delle istruzioni o le pagine non lette."""
    import hashlib

    from .motore import VERSIONE

    h = hashlib.sha256((percorsi.versione_lettura() + VERSIONE).encode())
    t = tentativi(cartella)
    for p in pagine(cartella):
        letta = scheda_pagina(p) is not None
        h.update(f"{p['pid']}:{p['impronta']}:{letta}:{t.get(p['pid'], 0) >= MAX_TENTATIVI}".encode())
    return h.hexdigest()[:16]


def prossimo_lavoro() -> dict | None:
    """Il primo lavoro (in ordine di creazione) che ha pagine da leggere o un'uscita da comporre."""
    radice = percorsi.lavori()
    if not radice.exists():
        return None
    for cartella in sorted((c for c in radice.iterdir() if c.is_dir()), key=lambda c: c.name):
        s = stato(cartella)
        if s["fase"] == "lettura":
            da = [p["pid"] for p in s["pagine"] if p["stato"] == "da_leggere"]
            segna_tentativi(cartella, da)
            lotti = [da[i : i + DIMENSIONE_LOTTO] for i in range(0, len(da), DIMENSIONE_LOTTO)]
            evento(cartella, tipo="lettura", testo=f"Claude legge {len(da)} pagine in {len(lotti)} lotti")
            return {"lavoro": cartella.name, "lotti": lotti}
        if s["fase"] == "composizione":
            return {"lavoro": cartella.name, "componi": True}
    return None
