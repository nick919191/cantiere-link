"""Collegamento per agenti (MCP, Model Context Protocol): Claude, ChatGPT o un altro agente sul computer usano l'app.

Si avvia con `python mcp_cantierelink.py` (o `CantiereLink --mcp` dall'installer) e parla con l'agente su stdin/stdout,
un messaggio JSON-RPC per riga. Non legge né decide niente da solo: chiama l'app aperta su questo computer (la apre
se è chiusa) con le stesse funzioni della finestra. Solo 127.0.0.1, con il token locale della sessione.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

from . import VERSIONE_APP, percorsi

PROTOCOLLI = ("2025-06-18", "2025-03-26", "2024-11-05")
PORTE = range(percorsi.PORTA, percorsi.PORTA + 20)


# ---------- collegamento all'app ----------
class App:
    def __init__(self):
        self.url, self.token = "", ""
        self.http = httpx.Client(timeout=120, trust_env=False)

    def _trova(self) -> str:
        for porta in PORTE:
            try:
                r = self.http.get(f"http://127.0.0.1:{porta}/api/salute", timeout=0.5)
                if r.json().get("application") == "tracciabilita-materiali":
                    return f"http://127.0.0.1:{porta}"
            except (httpx.HTTPError, ValueError):
                continue
        return ""

    def _apri(self) -> None:
        """L'app è chiusa: la apre (con la sua finestra) e aspetta che risponda."""
        comando = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "traccia.desktop"]
        flag = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
        subprocess.Popen(
            comando,
            cwd=percorsi.CODICE,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flag,
            start_new_session=sys.platform != "win32",
        )
        for _ in range(60):
            time.sleep(0.5)
            self.url = self._trova()
            if self.url:
                return
        raise RuntimeError("CantiereLink non si è aperto: avvialo a mano e riprova.")

    def pronta(self) -> None:
        if self.url and self.token:
            try:
                if self.http.get(self.url + "/api/salute", timeout=2).is_success:
                    return
            except httpx.HTTPError:
                pass
        self.url = self._trova()
        if not self.url:
            self._apri()
        self.token = self.http.get(self.url + "/api/sessione").json()["token"]

    def chiama(self, metodo: str, percorso: str, **kw):
        self.pronta()
        r = self.http.request(metodo, self.url + percorso, headers={"X-Traccia-Token": self.token}, **kw)
        try:
            dati = r.json()
        except ValueError:
            dati = {}
        if not r.is_success:
            raise RuntimeError(dati.get("detail") if isinstance(dati, dict) else f"errore {r.status_code}")
        return dati


# ---------- strumenti ----------
CANTIERE = {"type": "string", "description": "Identificativo del cantiere (campo 'lavoro' di elenco_cantieri)."}
FILE = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Percorsi completi di PDF, ZIP o immagini su questo computer.",
}
STRUMENTI = [
    {
        "name": "elenco_cantieri",
        "description": "Elenca i cantieri di CantiereLink con fase (preparazione, lettura, composizione, pronto), "
        "pagine, avanzamento e conteggio delle voci per stato.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "crea_cantiere",
        "description": "Crea un cantiere caricando i documenti (PDF, ZIP, immagini). L'analisi parte da sola quando "
        "le pagine sono pronte, se ChatGPT è collegato nell'app.",
        "inputSchema": {
            "type": "object",
            "properties": {"nome": {"type": "string", "description": "Nome del cantiere."}, "file": FILE},
            "required": ["file"],
        },
    },
    {
        "name": "aggiungi_file",
        "description": "Aggiunge documenti a un cantiere, anche durante l'analisi. I file identici a quelli già "
        "caricati non si aggiungono e le pagine già lette non si rileggono (nessun costo in più).",
        "inputSchema": {
            "type": "object",
            "properties": {"cantiere": CANTIERE, "file": FILE},
            "required": ["cantiere", "file"],
        },
    },
    {
        "name": "stato_cantiere",
        "description": "A che punto è un cantiere: fase, pagine lette su totali, pagine non lette, se è fermato, "
        "cosa sta facendo l'app in questo momento.",
        "inputSchema": {"type": "object", "properties": {"cantiere": CANTIERE}, "required": ["cantiere"]},
    },
    {
        "name": "avvia_analisi",
        "description": "Avvia o riprende l'analisi di un cantiere dalle pagine rimaste. Consuma il piano ChatGPT "
        "(e le chiavi Mistral/DeepSeek se impostate): usalo solo se l'utente lo vuole.",
        "inputSchema": {"type": "object", "properties": {"cantiere": CANTIERE}, "required": ["cantiere"]},
    },
    {
        "name": "ferma_analisi",
        "description": "Ferma l'analisi in corso per non consumare token. Le pagine già lette restano salvate; il "
        "cantiere non riparte da solo finché non si chiama avvia_analisi.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "tabella",
        "description": "Risultato della tracciabilità: per ogni voce stato (PROVATO, DEDOTTO, DA CONFERMARE, "
        "MANCANTE), valori delle colonne, perché il dato è stato usato e da quale documento e pagina viene.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cantiere": CANTIERE,
                "solo_problemi": {"type": "boolean", "description": "Solo le voci DA CONFERMARE e MANCANTE."},
            },
            "required": ["cantiere"],
        },
    },
    {
        "name": "richieste_fornitori",
        "description": "Documenti da chiedere a ogni fornitore (certificati mancanti, pagine mancanti...), con le "
        "voci interessate.",
        "inputSchema": {"type": "object", "properties": {"cantiere": CANTIERE}, "required": ["cantiere"]},
    },
    {
        "name": "cerca",
        "description": "Cerca parole o numeri (colata, n. DDT, n. certificato, profilo) nelle pagine già lette; "
        "restituisce file, pagina ed estratti.",
        "inputSchema": {
            "type": "object",
            "properties": {"cantiere": CANTIERE, "parole": {"type": "string"}},
            "required": ["cantiere", "parole"],
        },
    },
    {
        "name": "salva_excel",
        "description": "Copia l'Excel di tracciabilità del cantiere in una cartella (predefinita: Download).",
        "inputSchema": {
            "type": "object",
            "properties": {"cantiere": CANTIERE, "cartella": {"type": "string"}},
            "required": ["cantiere"],
        },
    },
]


def _carica(app: App, percorso: str, file: list[str], dati: dict | None = None):
    aperti = []
    try:
        for f in file:
            p = Path(f).expanduser()
            if not p.is_file():
                raise RuntimeError(f"file non trovato: {f}")
            aperti.append(("file", (p.name, p.open("rb"))))
        return app.chiama("POST", percorso, files=aperti, data=dati or {})
    finally:
        for _, (_, fh) in aperti:
            fh.close()


def _tabella(app: App, a: dict) -> dict:
    t = app.chiama("GET", f"/api/lavori/{a['cantiere']}/tabella")
    voci = [v for v in t["voci"] if not a.get("solo_problemi") or v["stato"] in ("DA CONFERMARE", "MANCANTE")]
    for v in voci:
        for c in v["celle"].values():
            c["documenti"] = [f"{d['file']} p. {d['pagina']}" for d in c["documenti"]]
    return {"colonne": t["colonne"], "voci": voci}


def _richieste(app: App, a: dict) -> dict:
    r = app.chiama("GET", f"/api/lavori/{a['cantiere']}/risultato")
    per: dict = {}
    for v in r.get("voci", []):
        for q in v.get("richieste", []):
            per.setdefault(v.get("fornitore") or "Fornitore non individuato", {}).setdefault(q, []).append(v["voce"])
    return {"fornitori": per or "Nessun documento da chiedere."}


def _salva_excel(app: App, a: dict) -> dict:
    stato = app.chiama("GET", f"/api/lavori/{a['cantiere']}/stato")
    excel = percorsi.lavoro(a["cantiere"]) / "uscita" / "tracciabilita.xlsx"
    if not excel.exists():
        raise RuntimeError("Excel non ancora pronto: aspetta che il cantiere sia nella fase 'pronto'.")
    cartella = Path(a.get("cartella") or Path.home() / "Downloads").expanduser()
    cartella.mkdir(parents=True, exist_ok=True)
    nome = "".join(c if c.isalnum() or c in " -_" else "_" for c in stato.get("nome", a["cantiere"])).strip()
    destinazione = cartella / f"tracciabilita_{nome or a['cantiere']}.xlsx"
    shutil.copyfile(excel, destinazione)
    return {"excel": str(destinazione), "aggiornato": stato["fase"] == "pronto"}


def esegui(app: App, nome: str, a: dict):
    if nome == "elenco_cantieri":
        return app.chiama("GET", "/api/lavori")
    if nome == "crea_cantiere":
        return _carica(app, "/api/lavori", a.get("file", []), {"nome": a.get("nome", "")})
    if nome == "aggiungi_file":
        return _carica(app, f"/api/lavori/{a['cantiere']}/file", a.get("file", []))
    if nome == "stato_cantiere":
        s = app.chiama("GET", f"/api/lavori/{a['cantiere']}/stato")
        s.pop("pagine", None)
        s.pop("riepilogo", None)
        return s | {"app": app.chiama("GET", "/api/agente")}
    if nome == "avvia_analisi":
        return app.chiama("POST", f"/api/lavori/{a['cantiere']}/analizza", json={})
    if nome == "ferma_analisi":
        return app.chiama("POST", "/api/agente/interrompi", json={})
    if nome == "tabella":
        return _tabella(app, a)
    if nome == "richieste_fornitori":
        return _richieste(app, a)
    if nome == "cerca":
        return app.chiama("GET", f"/api/lavori/{a['cantiere']}/cerca", params={"q": a.get("parole", "")})
    if nome == "salva_excel":
        return _salva_excel(app, a)
    raise RuntimeError(f"strumento sconosciuto: {nome}")


# ---------- protocollo ----------
def rispondi(app: App, messaggio: dict) -> dict | None:
    """Un messaggio JSON-RPC -> la risposta (None per le notifiche)."""
    metodo, mid, par = messaggio.get("method"), messaggio.get("id"), messaggio.get("params") or {}
    if mid is None:  # notifica (es. notifications/initialized): nessuna risposta
        return None
    if metodo == "initialize":
        richiesto = par.get("protocolVersion")
        risultato = {
            "protocolVersion": richiesto if richiesto in PROTOCOLLI else PROTOCOLLI[0],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "cantierelink", "version": VERSIONE_APP},
            "instructions": "CantiereLink ricostruisce la tracciabilità dei materiali di carpenteria metallica "
            "(distinta, DDT, certificato 3.1, colata) dai documenti di un cantiere. Gli stati li decide il motore "
            "dell'app: riportali come sono, senza cambiarli. L'analisi consuma il piano ChatGPT dell'utente.",
        }
    elif metodo == "ping":
        risultato = {}
    elif metodo == "tools/list":
        risultato = {"tools": STRUMENTI}
    elif metodo == "tools/call":
        try:
            dati = esegui(app, par.get("name", ""), par.get("arguments") or {})
            testo, errore = json.dumps(dati, ensure_ascii=False, indent=1), False
        except Exception as exc:  # l'errore va all'agente come testo leggibile, il collegamento resta aperto
            testo, errore = f"Errore: {exc}", True
        risultato = {"content": [{"type": "text", "text": testo}], "isError": errore}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"metodo sconosciuto: {metodo}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": risultato}


def main() -> int:
    if os.name == "nt":
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    app = App()
    for riga in sys.stdin:
        if not riga.strip():
            continue
        try:
            messaggio = json.loads(riga)
        except ValueError:
            risposta = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON non valido"}}
        else:
            risposta = rispondi(app, messaggio) if isinstance(messaggio, dict) else None
        if risposta is not None:
            sys.stdout.write(json.dumps(risposta, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


def configurazione() -> dict:
    """Comando con cui un agente avvia il collegamento su questo computer (per la pagina delle impostazioni)."""
    if getattr(sys, "frozen", False):
        comando, argomenti = sys.executable, ["--mcp"]
    else:  # lo script aggiunge da solo la cartella del codice: non serve indicare la cartella di lavoro
        comando, argomenti = sys.executable, [str(percorsi.CODICE / "mcp_cantierelink.py")]
    return {
        "comando": comando,
        "argomenti": argomenti,
        "json": {"mcpServers": {"cantierelink": {"command": comando, "args": argomenti}}},
        "claude_code": " ".join(
            f'"{x}"' if " " in x else x for x in ["claude", "mcp", "add", "cantierelink", "--", comando, *argomenti]
        ),
    }
