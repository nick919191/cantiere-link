"""Stato di un lavoro, archivio delle letture, eventi per la piattaforma.

Lo stato si ricalcola sempre dai file: pagine preparate + letture in archivio + tentativi. Per questo una sessione
chiusa a metà riprende da sola: le pagine con una lettura in archivio non si rileggono mai.
"""

import json
import threading
import time
import uuid
from pathlib import Path

from . import configurazione, consumi, percorsi
from .famiglie import FAMIGLIE

MAX_TENTATIVI = 4
DIMENSIONE_LOTTO = 8


# ---------- archivio ----------
def chiave_lettura(impronta: str) -> str:
    return f"{impronta}_{percorsi.versione_lettura()}"


def file_lettura(impronta: str, parziale: bool = False) -> Path:
    """La lettura della pagina; con `parziale` la scheda salvata a metà (famiglia e testata, senza righe), che vale
    finché non arriva una lettura completa e intanto fa entrare il documento nelle prove."""
    return percorsi.archivio() / "letture" / f"{chiave_lettura(impronta)}{'.parziale' if parziale else ''}.json"


def leggi_lettura(impronta: str) -> dict | None:
    for f in (file_lettura(impronta), file_lettura(impronta, parziale=True)):
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    return None


def salva_lettura(impronta: str, scheda: dict) -> None:
    completa = file_lettura(impronta)
    f = file_lettura(impronta, parziale=True) if scheda.get("parziale") else completa
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists() or completa.exists():  # congelata: mai riscritta (una parziale lascia il posto alla completa)
        return
    # Nome del temporaneo univoco: due copie della stessa pagina lette da lotti paralleli non si pestano i piedi.
    temporaneo = f.with_name(f"{f.stem}.{uuid.uuid4().hex}.tmp")
    temporaneo.write_text(json.dumps(scheda, ensure_ascii=False, indent=1), encoding="utf-8")
    if f.exists():  # l'altro lotto è arrivato prima: la sua lettura resta, questa si scarta
        temporaneo.unlink(missing_ok=True)
        return
    try:
        temporaneo.replace(f)
    except (FileExistsError, FileNotFoundError, PermissionError):
        temporaneo.unlink(missing_ok=True)


def cartella_ritagli() -> Path:
    return percorsi.archivio() / "ritagli"


# ---------- verifiche (Verifica finale) ----------
def file_verifica(impronta: str) -> Path:
    """La scheda verificata della pagina: lettura ripassata sul documento dal modello come ultimo controllo. Chiave
    distinta dalla lettura (versione delle istruzioni di verifica in coda): la lettura originale resta intatta."""
    from .verifica import versione  # import qui: verifica usa questo modulo

    return percorsi.archivio() / "verifiche" / f"{chiave_lettura(impronta)}_{versione()}.json"


def leggi_verifica(impronta: str) -> dict | None:
    f = file_verifica(impronta)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def salva_verifica(impronta: str, scheda: dict) -> None:
    """Congelata come la lettura: stessa impronta e stesse istruzioni = pagina giÃ  verificata, non si rifÃ ."""
    f = file_verifica(impronta)
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists():
        return
    temporaneo = f.with_name(f"{f.stem}.{uuid.uuid4().hex}.tmp")
    temporaneo.write_text(json.dumps(scheda, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        temporaneo.replace(f)
    except (FileExistsError, FileNotFoundError, PermissionError):
        temporaneo.unlink(missing_ok=True)


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


def _json_tollerante(f: Path, vuoto):
    """File di contorno (info, tentativi, riepilogo): se corrotto o del tipo sbagliato vale come assente."""
    try:
        valore = _json(f, vuoto)
    except (OSError, ValueError):
        return vuoto
    return valore if isinstance(valore, type(vuoto)) else vuoto


def tentativi(cartella: Path) -> dict[str, int]:
    t = _json_tollerante(cartella / "tentativi.json", {})
    return {k: v for k, v in t.items() if isinstance(k, str) and isinstance(v, int)}


def segna_tentativi(cartella: Path, pids: list[str]) -> None:
    t = tentativi(cartella)
    for pid in pids:
        t[pid] = t.get(pid, 0) + 1
    configurazione.scrivi_json(cartella / "tentativi.json", t)


def pagine(cartella: Path) -> list[dict]:
    return [p for p in _json(cartella / "pagine.json", []) if p.get("pid")]


def scheda_pagina(p: dict) -> dict | None:
    """Lettura della pagina: la verifica finale se c'Ã¨, altrimenti la lettura dall'archivio, oppure automatica per le
    pagine bianche (nessuna chiamata)."""
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
    return leggi_verifica(p["impronta"]) or leggi_lettura(p["impronta"])


def _letta(p: dict) -> bool:
    """Come `scheda_pagina(p) is not None`, ma senza aprire la lettura (la home e l'impronta non ne hanno bisogno)."""
    return completa(p) or file_lettura(p["impronta"], parziale=True).exists()


def completa(p: dict) -> bool:
    """Lettura completa in archivio: la pagina non si legge più. Una lettura parziale si ritenta finché ci sono
    tentativi."""
    return bool(p.get("bianca")) or file_lettura(p["impronta"]).exists() or file_verifica(p["impronta"]).exists()


def stato(cartella: Path, leggero: bool = False) -> dict:
    """Stato del lavoro. Con `leggero` non apre le letture: niente famiglie, ma conteggi e fase uguali e veloci."""
    info = _json_tollerante(cartella / "info.json", {})
    elenco = pagine(cartella)
    t = tentativi(cartella)
    per_famiglia = {f: 0 for f in FAMIGLIE}
    lette, da_leggere, non_lette, dettagli = 0, [], [], []
    for p in elenco:
        voce = {"pid": p["pid"], "file": p["file"], "pagina": p["pagina"]}
        esaurita = t.get(p["pid"], 0) >= MAX_TENTATIVI
        if (completa(p) or esaurita) and leggero and _letta(p):
            lette += 1
            voce.update(stato="letta")
        elif (completa(p) or esaurita) and not leggero and (s := scheda_pagina(p)):
            lette += 1
            per_famiglia[s["famiglia"]] = per_famiglia.get(s["famiglia"], 0) + 1
            voce.update(famiglia=s["famiglia"], stato="letta", orientamento=s.get("orientamento", 0))
            if s.get("parziale"):
                voce.update(parziale=True)
        elif esaurita:
            non_lette.append(p["pid"])
            voce.update(stato="non_letta")
        else:
            da_leggere.append(p["pid"])
            voce.update(stato="da_leggere")
        dettagli.append(voce)
    preparata = (cartella / "pagine.json").exists()
    composto = _json_tollerante(cartella / "uscita" / "riepilogo.json", {}) or None
    motivo = ""
    if not preparata:
        fase = "preparazione"
    elif not elenco:
        fase, motivo = "errore", "Nessuna pagina leggibile nei file caricati: controlla formato e contenuto."
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
        "motivo": motivo,
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
    """Cambia se cambia una lettura o una verifica, la versione delle istruzioni o le pagine non lette."""
    import hashlib

    from .motore import VERSIONE

    h = hashlib.sha256((percorsi.versione_lettura() + VERSIONE).encode())
    t = tentativi(cartella)
    for p in pagine(cartella):
        # la verifica entra nell'impronta solo quando c'è: i cantieri composti prima della 0.8.0 restano «pronti»
        letta = f"{completa(p)}/{_letta(p)}" + ("/verificata" if file_verifica(p["impronta"]).exists() else "")
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
            evento(cartella, tipo="lettura", testo=f"L'agente legge {len(da)} pagine in {len(lotti)} lotti")
            return {"lavoro": cartella.name, "lotti": lotti}
        if s["fase"] == "composizione":
            return {"lavoro": cartella.name, "componi": True}
    return None
