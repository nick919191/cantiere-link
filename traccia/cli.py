"""Comandi `python -m traccia ...`: gli unici con cui Claude legge e scrive su disco.

avvia                          avvia la piattaforma (se non è già attiva) e apre il browser
attendi                        aspetta lavoro: lotti di pagine da leggere, oppure un'uscita da comporre
pagina ID PID                  dati della pagina per il lettore (immagine, testo nativo, file della risposta)
ritaglia ID PID x0 y0 x1 y1 M  ritaglio ad alta risoluzione, salvato in archivio e mostrato all'utente
nota ID PID|- TESTO            una riga per l'utente nella piattaforma
salva ID PID                   valida la scheda scritta dal lettore e la congela in archivio
componi ID                     prove -> motore -> Excel, prove HTML, fascicolo ordinato
prepara ID                     (manuale) prepara di nuovo le pagine di un lavoro

Chat con la documentazione (sottoagente assistente):
  domanda ID QID                 testo della domanda e file dove scrivere la risposta
  cerca ID PAROLE...             pagine lette che contengono le parole, con estratti
  scheda ID PID                  scheda salvata della pagina (trascrizione e valori)
  voci ID                        voci dell'Excel con stato e note (se l'uscita è pronta)
  rispondi ID QID                valida la risposta (citazioni nelle pagine) e la registra
"""

import json
import subprocess
import sys
import time
import urllib.request
import webbrowser

from . import chat, percorsi
from . import lavoro as lv
from .controlli import aggiungi_zone_esatte, valida
from .preparazione import info_pagina, prepara, ritaglio

ATTESA_MASSIMA_S = 540


def _stampa(dati) -> None:
    print(json.dumps(dati, ensure_ascii=False, indent=1))


def _attiva() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{percorsi.PORTA}/api/salute", timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def avvia() -> int:
    url = f"http://127.0.0.1:{percorsi.PORTA}/"
    if not _attiva():
        flag = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
        percorsi.RADICE.mkdir(parents=True, exist_ok=True)
        log = (percorsi.RADICE / "piattaforma.log").open("ab")
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "traccia.server:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(percorsi.PORTA),
            ],
            cwd=percorsi.CODICE,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            creationflags=flag,
            start_new_session=sys.platform != "win32",
        )
        for _ in range(40):
            if _attiva():
                break
            time.sleep(0.5)
    if not _attiva():
        _stampa({"errore": "la piattaforma non parte: vedi piattaforma.log"})
        return 1
    webbrowser.open(url)
    _stampa({"piattaforma": url})
    return 0


def _prossima_domanda() -> dict | None:
    radice = percorsi.lavori()
    if not radice.exists():
        return None
    for cartella in sorted((c for c in radice.iterdir() if c.is_dir()), key=lambda c: c.name):
        attesa = chat.in_attesa(cartella)
        if attesa:
            return {"lavoro": cartella.name, "domanda": attesa[0]["id"], "testo": attesa[0]["testo"]}
    return None


def attendi() -> int:
    """Le domande della chat hanno la precedenza: si risponde tra un lotto di lettura e l'altro."""
    fine = time.monotonic() + ATTESA_MASSIMA_S
    while time.monotonic() < fine:
        lavoro = _prossima_domanda() or lv.prossimo_lavoro()
        if lavoro:
            _stampa(lavoro)
            return 0
        time.sleep(2)
    _stampa({"niente": True})
    return 0


def _file_risposta(id_lavoro: str, pid: str):
    return percorsi.lavoro(id_lavoro) / "risposte" / f"{pid}.json"


def pagina(id_lavoro: str, pid: str) -> int:
    cartella = percorsi.lavoro(id_lavoro)
    info = info_pagina(cartella, pid)
    risposta = _file_risposta(id_lavoro, pid)
    risposta.parent.mkdir(parents=True, exist_ok=True)
    lv.evento(cartella, tipo="lettura_pagina", pid=pid, testo=f"Claude guarda {info['file']} · pagina {info['pagina']}")
    _stampa(
        {
            "immagine": str(cartella / "pagine" / f"{pid}.png"),
            "file": info["file"],
            "pagina": info["pagina"],
            "pagine_file": info["pagine_file"],
            "testo_nativo": info["testo_nativo"][:15000] or "(nessun testo nativo: pagina scansionata)",
            "scrivi_la_scheda_in": str(risposta),
            "gia_letta": lv.leggi_lettura(info["impronta"]) is not None,
        }
    )
    return 0


def ritaglia(id_lavoro: str, pid: str, x0: str, y0: str, x1: str, y1: str, motivo: str = "") -> int:
    cartella = percorsi.lavoro(id_lavoro)
    info = info_pagina(cartella, pid)
    zona = [int(x0), int(y0), int(x1), int(y1)]
    png = ritaglio(cartella, info, zona)
    nome = f"{info['impronta']}_{'-'.join(map(str, zona))}.png"
    f = lv.cartella_ritagli() / nome
    f.parent.mkdir(parents=True, exist_ok=True)
    if not f.exists():
        f.write_bytes(png)
    indice = lv.cartella_ritagli() / f"{info['impronta']}.json"
    elenco = json.loads(indice.read_text(encoding="utf-8")) if indice.exists() else []
    if nome not in [r["file"] for r in elenco]:
        elenco.append({"file": nome, "zona": zona, "motivo": motivo})
        indice.write_text(json.dumps(elenco, ensure_ascii=False, indent=1), encoding="utf-8")
    lv.evento(cartella, tipo="ritaglio", pid=pid, ritaglio=nome, testo=motivo or "ritaglio")
    _stampa({"ritaglio": str(f)})
    return 0


def nota(id_lavoro: str, pid: str, *testo: str) -> int:
    lv.evento(percorsi.lavoro(id_lavoro), tipo="nota", pid=None if pid == "-" else pid, testo=" ".join(testo)[:300])
    _stampa({"ok": True})
    return 0


def salva(id_lavoro: str, pid: str) -> int:
    cartella = percorsi.lavoro(id_lavoro)
    info = info_pagina(cartella, pid)
    if lv.leggi_lettura(info["impronta"]):
        _stampa({"ok": True, "nota": "pagina già in archivio: lettura non rifatta"})
        return 0
    risposta = _file_risposta(id_lavoro, pid)
    try:
        scheda = json.loads(risposta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        _stampa({"ok": False, "errori": [f"risposta non leggibile come JSON ({type(e).__name__})"]})
        return 1
    errori = valida(scheda, info["testo_nativo"])
    if errori:
        lv.evento(cartella, tipo="correzione", pid=pid, testo=f"{len(errori)} correzioni chieste al lettore")
        _stampa({"ok": False, "errori": errori[:30]})
        return 1
    aggiungi_zone_esatte(scheda, info["parole"])
    ritagli = lv.cartella_ritagli() / f"{info['impronta']}.json"
    scheda["ritagli"] = json.loads(ritagli.read_text(encoding="utf-8")) if ritagli.exists() else []
    scheda["versione_lettura"] = percorsi.versione_lettura()
    scheda["impronta"] = info["impronta"]
    lv.salva_lettura(info["impronta"], scheda)
    sintesi = _sintesi(scheda)
    lv.evento(cartella, tipo="scheda", pid=pid, famiglia=scheda["famiglia"], testo=sintesi)
    _stampa({"ok": True, "famiglia": scheda["famiglia"]})
    return 0


def _sintesi(scheda: dict) -> str:
    t = scheda.get("testata", {})
    pezzi = [
        t[k]["v"]
        for k in ("produttore", "emittente", "fabbricante", "costruttore", "numero", "numero_dop", "data")
        if k in t and t[k]["v"]
    ]
    righe = len(scheda.get("righe", []))
    timbri = len(scheda.get("timbri", []))
    extra = [f"{righe} righe"] if righe else []
    extra += [f"{timbri} timbri"] if timbri else []
    return " · ".join(pezzi[:4] + extra) or scheda.get("motivo", "")


def componi(id_lavoro: str) -> int:
    from .uscita import componi as fai

    cartella = percorsi.lavoro(id_lavoro)
    riepilogo = fai(cartella)
    _stampa({"ok": True, "voci": riepilogo["conteggio"], "excel": riepilogo["excel"]})
    return 0


def prepara_lavoro(id_lavoro: str) -> int:
    cartella = percorsi.lavoro(id_lavoro)
    elenco = prepara(cartella, avviso=lambda **d: lv.evento(cartella, **d))
    _stampa({"pagine": len([p for p in elenco if p.get("pid")])})
    return 0


def _file_chat(id_lavoro: str, qid: str):
    if not qid.isalnum():
        raise ValueError("identificativo della domanda non valido")
    return percorsi.lavoro(id_lavoro) / "chat" / f"{qid}.json"


def domanda(id_lavoro: str, qid: str) -> int:
    cartella = percorsi.lavoro(id_lavoro)
    d = next((m for m in chat.messaggi(cartella) if m["ruolo"] == "utente" and m["id"] == qid), None)
    if not d:
        raise ValueError(f"domanda {qid} non trovata")
    f = _file_chat(id_lavoro, qid)
    f.parent.mkdir(exist_ok=True)
    stato = lv.stato(cartella)
    precedenti = [m for m in chat.messaggi(cartella) if m["ruolo"] == "claude"][-3:]
    lv.evento(cartella, tipo="nota", testo="Claude cerca la risposta nei documenti")
    _stampa(
        {
            "domanda": d["testo"],
            "scrivi_la_risposta_in": str(f),
            "pagine_lette": stato["lette"],
            "pagine_totali": stato["pagine_totali"],
            "uscita_pronta": stato["fase"] == "pronto",
            "ultime_risposte": [m["testo"][:300] for m in precedenti],
        }
    )
    return 0


def cerca(id_lavoro: str, *parole: str) -> int:
    _stampa(chat.cerca(percorsi.lavoro(id_lavoro), " ".join(parole)))
    return 0


def scheda(id_lavoro: str, pid: str) -> int:
    cartella = percorsi.lavoro(id_lavoro)
    p = next((x for x in lv.pagine(cartella) if x["pid"] == pid), None)
    if not p:
        raise ValueError(f"pagina {pid} non trovata")
    s = lv.scheda_pagina(p) or {}
    valori = {k: v["v"] for k, v in s.get("testata", {}).items() if v.get("v")}
    righe = [{k: v["v"] for k, v in r.items() if v.get("v")} for r in s.get("righe", [])]
    _stampa(
        {
            "file": p["file"],
            "pagina": p["pagina"],
            "famiglia": s.get("famiglia"),
            "testata": valori,
            "righe": righe,
            "timbri": s.get("timbri", []),
            "avvisi": s.get("avvisi", []),
            "trascrizione": s.get("trascrizione", ""),
            "immagine": str(cartella / "pagine" / f"{pid}.png"),
        }
    )
    return 0


def voci(id_lavoro: str) -> int:
    f = percorsi.lavoro(id_lavoro) / "uscita" / "risultato.json"
    if not f.exists():
        _stampa({"pronta": False, "nota": "l'Excel non è ancora pronto"})
        return 0
    r = json.loads(f.read_text(encoding="utf-8"))
    _stampa(
        {
            "conteggio": r["conteggio"],
            "voci": [
                {
                    "n": v["n"],
                    "voce": v["voce"],
                    "stato": v["stato"],
                    "note": v["note"],
                    **{
                        c: v["colonne"][c]["v"]
                        for c in ("PRODUTTORE", "COLATA", "CERT 3.1 ACCIAIERIA", "DDT COMMERCIANTE")
                    },
                    "pagine": v["pagine"],
                }
                for v in r["voci"]
            ],
        }
    )
    return 0


def rispondi(id_lavoro: str, qid: str) -> int:
    cartella = percorsi.lavoro(id_lavoro)
    try:
        risposta = json.loads(_file_chat(id_lavoro, qid).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        _stampa({"ok": False, "errori": [f"risposta non leggibile come JSON ({type(e).__name__})"]})
        return 1
    errori = chat.rispondi(cartella, qid, risposta)
    _stampa({"ok": not errori, "errori": errori} if errori else {"ok": True})
    return 1 if errori else 0


COMANDI = {
    "domanda": domanda,
    "cerca": cerca,
    "scheda": scheda,
    "voci": voci,
    "rispondi": rispondi,
    "avvia": avvia,
    "attendi": attendi,
    "pagina": pagina,
    "ritaglia": ritaglia,
    "nota": nota,
    "salva": salva,
    "componi": componi,
    "prepara": prepara_lavoro,
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMANDI:
        print(__doc__)
        return 2
    try:
        return COMANDI[argv[0]](*argv[1:]) or 0
    except TypeError:
        print(__doc__)
        return 2
    except (ValueError, FileNotFoundError) as e:
        _stampa({"ok": False, "errori": [f"{type(e).__name__}: {e}"]})
        return 1
