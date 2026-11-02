"""Piattaforma locale (solo 127.0.0.1): caricamento, stato in tempo reale, immagini, download.

Il servizio locale collega il browser all’agente ChatGPT e conserva originali e risultati sul computer.
"""

import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from PIL import Image
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from . import (
    agente,
    aggiornamenti,
    cestino,
    chatgpt,
    chiavi,
    collegamento,
    configurazione,
    consumi,
    demo_cantiere,
    ocr,
    percorsi,
    registro,
    verifica,
)
from . import cerca as ricerca
from . import lavoro as lv
from .motore import COLONNE
from .preparazione import info_pagina, prepara

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifecycle(_app):
    registro.configura()
    stop_checks = threading.Event()

    def update_checks():
        while not stop_checks.is_set():
            try:
                aggiornamenti.check()
            except Exception:
                log.exception("Controllo aggiornamenti non riuscito")
            stop_checks.wait(3600)

    threading.Thread(target=update_checks, daemon=True).start()
    yield
    stop_checks.set()
    agente.stop()


app = FastAPI(title="CantiereLink", docs_url=None, redoc_url=None, lifespan=lifecycle)
_PREPARING = set()
_ANCORA = set()  # cantieri con file arrivati mentre la preparazione era già in corso: si ripassa
_PREPARAZIONE: dict[str, dict] = {}  # avanzamento della preparazione: {"n": file fatti, "totale": file da fare}
HOST_CONSENTITI = {"127.0.0.1", "localhost"}  # i test aggiungono "testserver" dalla fixture, non il codice
_ESTENSIONI = {".pdf", ".zip", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
MAX_DOCUMENTI_CELLA = 6
_MAX_BYTE = 500 * 1024 * 1024
_TOKEN = secrets.token_urlsafe(32)
_TOKEN_DALLA_FINESTRA = False  # True quando desktop.py ha generato il token e lo consegna nel frammento dell'URL


def imposta_token(token: str) -> None:
    """Token scelto da desktop.py prima dell'avvio: /api/sessione si spegne e nessun altro processo locale lo legge."""
    global _TOKEN, _TOKEN_DALLA_FINESTRA
    _TOKEN, _TOKEN_DALLA_FINESTRA = token, True


def impronta_istanza() -> str:
    """Identifica questa istanza in /api/salute senza esporre il token."""
    return hashlib.sha256(_TOKEN.encode()).hexdigest()[:16]


# Nessuno script o handler inline nell'app: la CSP fa da rete di sicurezza all'escaping. Gli stili inline restano
# (attributi style nell'interfaccia e nelle pagine di prova). La demo statica in demo/ ha ancora script inline.
_CSP = "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'"
_CSP_DEMO = _CSP + "; script-src 'self' 'unsafe-inline'"


@app.middleware("http")
async def locale(request: Request, call_next):
    host = request.url.hostname
    if host not in HOST_CONSENTITI:
        return JSONResponse({"detail": "Host non autorizzato"}, status_code=403)
    origin = request.headers.get("origin")
    if origin and (urlsplit(origin).netloc != request.headers.get("host") or urlsplit(origin).scheme != "http"):
        return JSONResponse({"detail": "Origine non autorizzata"}, status_code=403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not secrets.compare_digest(request.headers.get("x-traccia-token", ""), _TOKEN):
            return JSONResponse({"detail": "Ricarica la pagina per ripristinare la sessione locale"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Content-Security-Policy"] = _CSP_DEMO if request.url.path.startswith("/demo/") else _CSP
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(Exception)
async def errore_interno(request: Request, exc: Exception):
    """Qualunque errore inatteso arriva al browser come JSON con `detail`, mai come testo grezzo."""
    log.error("Errore interno su %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        {"detail": "Errore interno dell’applicazione. Riprova; se il problema resta, chiudi e riapri l’app."},
        status_code=500,
    )


@app.exception_handler(chatgpt.AgentError)
async def agent_error(_request: Request, exc: chatgpt.AgentError):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.get("/api/sessione")
def sessione():
    if _TOKEN_DALLA_FINESTRA:
        raise HTTPException(404, "La sessione si apre soltanto dalla finestra dell’app.")
    return {"token": _TOKEN}


@app.get("/api/impostazioni")
def impostazioni():
    prefs = configurazione.leggi()
    return {k: prefs[k] for k in ("model", "reasoning", "theme", "prezzo_ingresso", "prezzo_uscita")} | {
        "cartella": str(percorsi.RADICE),
        "registro": str(registro.percorso()),
    }


class Preferenze(BaseModel):
    model: str = Field(default="", max_length=150)
    reasoning: str = "low"
    theme: str = "system"
    prezzo_ingresso: float = Field(default=1.15, ge=0, le=1000)
    prezzo_uscita: float = Field(default=9.2, ge=0, le=1000)


@app.put("/api/impostazioni")
def preferenze(value: Preferenze):
    try:
        configurazione.aggiorna(value.model_dump())
        return impostazioni()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _idle():
    if aggiornamenti.status()["busy"]:
        raise chatgpt.AgentError("Attendi il completamento dell’aggiornamento prima di avviare altre operazioni.")
    if agente.stato()["busy"]:
        raise chatgpt.AgentError("L’agente sta lavorando: attendi la fine dell’operazione o premi «Interrompi».")


@app.get("/api/account")
def account():
    return chatgpt.status()


class Account(BaseModel):
    profile: str | None = Field(default=None, max_length=200)


@app.post("/api/account/collega")
def collega(value: Account):
    _idle()
    return chatgpt.start(value.profile)


@app.post("/api/account/seleziona")
def seleziona(value: Account):
    _idle()
    chatgpt.select(value.profile)
    return chatgpt.status()


@app.post("/api/account/scollega")
def scollega():
    _idle()
    return chatgpt.logout()


@app.get("/api/mistral")
def mistral_stato():
    return ocr.stato()


class ChiaveMistral(BaseModel):
    chiave: str = Field(min_length=1, max_length=200)


@app.post("/api/mistral")
def mistral_salva(value: ChiaveMistral):
    _idle()
    return ocr.salva(value.chiave)


@app.delete("/api/mistral")
def mistral_rimuovi():
    _idle()
    return ocr.rimuovi()


@app.get("/api/chiavi")
def chiavi_stato():
    return {s: chiavi.stato(s) for s in chiavi.SERVIZI}


class Chiave(BaseModel):
    chiave: str = Field(min_length=1, max_length=300)


class Modello(BaseModel):
    modello: str = Field(default="", max_length=100)


@app.post("/api/chiavi/{servizio}")
def chiave_salva(servizio: str, value: Chiave):
    _idle()
    return chiavi.salva(servizio, value.chiave)


@app.delete("/api/chiavi/{servizio}")
def chiave_rimuovi(servizio: str):
    _idle()
    return chiavi.rimuovi(servizio)


@app.post("/api/chiavi/{servizio}/prova")
def chiave_prova(servizio: str):
    return chiavi.prova(servizio)


@app.put("/api/chiavi/{servizio}/modello")
def chiave_modello(servizio: str, value: Modello):
    return chiavi.imposta_modello(servizio, value.modello)


@app.get("/api/modelli")
def modelli():
    return chatgpt.models()


@app.get("/api/agente")
def stato_agente():
    return agente.stato()


@app.post("/api/agente/interrompi")
def interrompi():
    job = agente.stato().get("job")
    if agente.stato()["busy"] and job and percorsi.lavoro(job).is_dir():
        _segna_fermato(percorsi.lavoro(job), True)  # fermato dall'utente: non ripartire da solo
    return agente.stop()


@app.post("/api/lavori/{id_lavoro}/analizza")
def analizza(id_lavoro: str):
    """Riprendi: toglie il fermo e riparte dalle pagine rimaste (quelle già lette non si rileggono)."""
    _idle()
    cartella = _cartella(id_lavoro)
    _segna_fermato(cartella, False)
    if id_lavoro in _PREPARING:
        return {"started": False, "attesa": "preparazione"}  # partirà da solo a preparazione finita
    # cantiere già pronto: il pulsante è «Verifica finale» e la verifica parte anche senza pagine da leggere
    esplicita = lv.stato(cartella, leggero=True)["fase"] == "pronto"
    agente.avvia(cartella, poi=lambda riuscita: _ancora_da_fare(id_lavoro, riuscita), verifica=esplicita)
    return {"started": True}


# ---------- analisi automatica ----------
def _segna_fermato(cartella: Path, fermo: bool) -> None:
    segno = cartella / "fermato"
    if fermo:
        segno.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        lv.evento(cartella, tipo="fermata", testo="Analisi fermata: le pagine già lette restano salvate")
    elif segno.exists():
        segno.unlink()
        lv.evento(cartella, tipo="ripresa", testo="Analisi ripresa dalle pagine rimaste")


def _fermato(cartella: Path) -> bool:
    return (cartella / "fermato").exists()


def _avvia_se_serve(id_lavoro: str) -> None:
    """Parte da sola se ci sono pagine da leggere o un Excel da rifare, ChatGPT è collegato e il cantiere non è
    stato fermato. Si chiama a fine preparazione e a fine analisi (pagine aggiunte nel frattempo)."""
    try:
        cartella = percorsi.lavoro(id_lavoro)
        if id_lavoro in _PREPARING or _fermato(cartella) or agente.stato()["busy"]:
            return
        if aggiornamenti.status()["busy"] or not chatgpt.status().get("plan_enabled"):
            return
        if lv.stato(cartella, leggero=True)["fase"] not in ("lettura", "composizione"):
            return
        agente.avvia(cartella, poi=lambda riuscita: _ancora_da_fare(id_lavoro, riuscita))
    except Exception:  # l'avvio automatico non deve mai rompere caricamento o preparazione
        pass


def _ancora_da_fare(id_lavoro: str, riuscita: bool) -> None:
    """Fine analisi: se è andata bene e nel frattempo sono arrivate pagine nuove, riparte su quelle sole.
    Dopo un errore non riparte da sola, per non ripetere all'infinito una chiamata che fallisce."""
    if riuscita:
        _avvia_se_serve(id_lavoro)


@app.exception_handler(aggiornamenti.UpdateError)
async def update_error(_request: Request, exc: aggiornamenti.UpdateError):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.get("/api/aggiornamenti")
def update_status():
    return aggiornamenti.status()


@app.post("/api/aggiornamenti/controlla")
def update_check():
    return aggiornamenti.check(force=True)


class UpdateChoice(BaseModel):
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


@app.post("/api/aggiornamenti/installa")
def update_install(choice: UpdateChoice):
    _idle()
    if _PREPARING or chatgpt.status().get("pending"):
        raise aggiornamenti.UpdateError("Attendi il caricamento dei documenti o il completamento dell’accesso.")
    return aggiornamenti.install(choice.version)


@app.post("/api/aggiornamenti/ripristina")
def update_rollback():
    _idle()
    return aggiornamenti.rollback()


@app.post("/api/aggiornamenti/apri-installer")
def update_open_installer():
    _idle()
    if _PREPARING:
        raise aggiornamenti.UpdateError("Attendi il completamento del caricamento.")
    aggiornamenti.open_installer()
    _shutdown()
    return {"ok": True}


def _shutdown():
    callback = getattr(app.state, "shutdown", None)
    if callback:
        threading.Timer(1, callback).start()


@app.post("/api/chiudi")
def close_app():
    _idle()
    if _PREPARING:
        raise chatgpt.AgentError("Attendi il completamento del caricamento.")
    if not getattr(app.state, "shutdown", None):
        raise chatgpt.AgentError("Chiudi il terminale con Ctrl+C per arrestare questa sessione di sviluppo.")
    _shutdown()
    return {"ok": True}


@app.get("/api/cestino")
def trash_list():
    return cestino.elenco()


@app.get("/api/consumi")
def consumi_totali():
    return consumi.totale()


@app.delete("/api/lavori/{id_lavoro}")
def trash_job(id_lavoro: str):
    if aggiornamenti.status()["busy"]:
        raise chatgpt.AgentError("Attendi il completamento dell’aggiornamento prima di eliminare un cantiere.")
    agent = agente.stato()
    if agent["busy"] and agent.get("job") == id_lavoro:
        raise chatgpt.AgentError("L’agente sta analizzando questo cantiere: premi «Interrompi», poi elimina.")
    if id_lavoro in _PREPARING:
        raise chatgpt.AgentError("Attendi il completamento del caricamento o della preparazione delle pagine.")
    try:
        return cestino.sposta(id_lavoro)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/cestino/{key}/ripristina")
def restore_job(key: str):
    _idle()
    try:
        return cestino.ripristina(key)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


class UpdatePreferences(BaseModel):
    automatic: bool
    dismissed: str = Field(default="", max_length=40)
    prova: bool | None = None  # anche le versioni di prova; None = lascia com'è


@app.put("/api/aggiornamenti/preferenze")
def update_preferences(choice: UpdatePreferences):
    prima = aggiornamenti.anteprime()
    valori = {"update_checks": choice.automatic, "dismissed_update": choice.dismissed}
    if choice.prova is not None:
        valori["update_prerelease"] = choice.prova
    configurazione.aggiorna(valori)
    if choice.prova is not None and choice.prova != prima:
        threading.Thread(target=lambda: aggiornamenti.check(force=True), daemon=True).start()
    return aggiornamenti.status()


@app.get("/guida/", response_class=HTMLResponse)
def guida():
    return (percorsi.CODICE / "docs/index.html").read_text(encoding="utf-8")


@app.get("/guida/{path:path}")
def guida_asset(path: str):
    return FileResponse(_dentro(percorsi.CODICE / "docs", path))


@app.get("/demo/{path:path}")
def demo_asset(path: str):
    return FileResponse(_dentro(percorsi.CODICE / "demo", path))


@app.get("/LICENSE")
def license_file():
    return FileResponse(percorsi.CODICE / "LICENSE", media_type="text/plain")


def _cartella(id_lavoro: str) -> Path:
    try:
        c = percorsi.lavoro(id_lavoro)
    except ValueError as e:
        raise HTTPException(400, "lavoro non valido") from e
    if not c.exists():
        raise HTTPException(404, "lavoro non trovato")
    if not os.access(c, os.R_OK | os.W_OK):
        raise HTTPException(409, "Cartella del cantiere non accessibile: controlla i permessi nella cartella dati.")
    return c


def _dentro(base: Path, relativo: str) -> Path:
    f = (base / relativo).resolve()
    if not f.is_relative_to(base.resolve()) or not f.is_file():
        raise HTTPException(404, "file non trovato")
    return f


@app.get("/api/salute")
def salute():
    return {"ok": True, "application": "tracciabilita-materiali", "istanza": impronta_istanza()}


@app.get("/", response_class=HTMLResponse)
def pagina():
    return (percorsi.WEB / "index.html").read_text(encoding="utf-8")


@app.get("/web/{nome}")
def statico(nome: str):
    return FileResponse(_dentro(percorsi.WEB, nome))


@app.get("/api/lavori")
def elenco():
    radice = percorsi.lavori()
    if not radice.exists():
        return []
    voci = []
    for c in sorted(radice.iterdir(), reverse=True):
        if c.name.startswith(".") or not c.is_dir():
            continue
        try:
            if not (c / "info.json").exists():
                continue
            s = lv.stato(c, leggero=True)
        except (OSError, ValueError):
            # Una cartella non leggibile (permessi) o un JSON corrotto non devono nascondere gli altri cantieri.
            continue
        chiavi_voce = ("lavoro", "nome", "creato", "fase", "motivo", "pagine_totali", "percentuale", "consumo")
        voce = {k: s[k] for k in chiavi_voce}
        # Conteggi per stato solo se l'Excel corrisponde alle letture attuali: la home li mostra sulla scheda.
        voce["conteggio"] = (s["riepilogo"] or {}).get("conteggio") if s["fase"] == "pronto" else None
        voci.append(voce)
    return voci


async def _ricevi(file: list[UploadFile], ingresso: Path) -> tuple[list[str], list[str]]:
    """Salva i file caricati in `ingresso` con nomi sicuri. Ritorna (accettati, scartati)."""
    accettati, scartati, totale = [], [], 0
    for f in file:
        nome_file = Path((f.filename or "").replace("\\", "/")).name[:180]
        if Path(nome_file).suffix.lower() not in _ESTENSIONI:
            scartati.append(nome_file)
            continue
        destinazione = ingresso / re.sub(r"[^\w.\- ]", "_", nome_file)
        if destinazione.stem.upper() in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *[f"COM{i}" for i in range(10)],
            *[f"LPT{i}" for i in range(10)],
        }:
            destinazione = ingresso / ("documento_" + destinazione.name)
        if destinazione.exists():
            destinazione = destinazione.with_name(uuid.uuid4().hex[:8] + "_" + destinazione.name)
        # Un .part non è visibile alla preparazione, che può girare mentre arriva un file aggiunto.
        parziale = destinazione.with_name(destinazione.name + ".part")
        try:
            with parziale.open("xb") as output:
                while dati := await f.read(1024 * 1024):
                    totale += len(dati)
                    if totale > _MAX_BYTE:
                        raise HTTPException(
                            413, "Caricamento troppo grande. Suddividi i file in fascicoli più piccoli."
                        )
                    output.write(dati)
            parziale.replace(destinazione)
        finally:
            parziale.unlink(missing_ok=True)
        await f.close()
        accettati.append(destinazione.name)
    if not accettati:
        raise HTTPException(400, "Nessun PDF o immagine supportata nel caricamento")
    return accettati, scartati


def _prepara_in_sfondo(id_lavoro: str, cartella: Path) -> None:
    """Prepara le pagine in un thread, poi avvia l'analisi da sola. File arrivati durante la preparazione: si ripassa
    alla fine (prepara salta i file già fatti)."""
    if id_lavoro in _PREPARING:
        _ANCORA.add(id_lavoro)
        return
    _PREPARING.add(id_lavoro)

    def avviso(**d):
        if d.get("tipo") == "file":
            _PREPARAZIONE[id_lavoro] = {"n": d["n"], "totale": d["totale"]}
        lv.evento(cartella, **d)

    def prepare_job():
        try:
            while True:
                _ANCORA.discard(id_lavoro)
                _PREPARAZIONE[id_lavoro] = {"n": 0, "totale": 0}
                prepara(cartella, avviso=avviso)
                if id_lavoro not in _ANCORA:
                    break
            lv.evento(cartella, tipo="preparate", testo=f"{len(lv.pagine(cartella))} pagine pronte")
        except Exception:
            log.exception("Preparazione del cantiere %s non riuscita", id_lavoro)
            lv.evento(
                cartella, tipo="errore", testo="Preparazione non riuscita: controlla formato e dimensioni dei file."
            )
        finally:
            _PREPARING.discard(id_lavoro)
            _PREPARAZIONE.pop(id_lavoro, None)
        _avvia_se_serve(id_lavoro)

    threading.Thread(target=prepare_job, daemon=True).start()


@app.post("/api/lavori")
async def carica(file: list[UploadFile], nome: str = Form("", max_length=200)):
    id_lavoro = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    cartella = percorsi.lavoro(id_lavoro)
    percorsi.lavori().mkdir(parents=True, exist_ok=True)
    # Cartella provvisoria creata con mkdir normale: tempfile.mkdtemp su Windows (Python 3.12) applica permessi
    # ristretti al solo proprietario e, se l'app è stata avviata come amministratore, l'utente non la legge più.
    temporary = percorsi.lavori() / (".caricamento-" + id_lavoro)
    try:
        ingresso = temporary / "ingresso"
        ingresso.mkdir(parents=True)
        accettati, scartati = await _ricevi(file, ingresso)
        temporary.rename(cartella)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    configurazione.scrivi_json(
        cartella / "info.json",
        {"nome": nome or id_lavoro, "creato": time.strftime("%d/%m/%Y %H:%M"), "file": accettati, "scartati": scartati},
    )
    lv.evento(cartella, tipo="ricevuti", testo=f"{len(accettati)} file ricevuti", file=accettati, scartati=scartati)
    _prepara_in_sfondo(id_lavoro, cartella)
    return {"lavoro": id_lavoro, "accettati": accettati, "scartati": scartati}


class Nome(BaseModel):
    nome: str = Field(default="", max_length=200)


@app.put("/api/lavori/{id_lavoro}/nome")
def rinomina(id_lavoro: str, value: Nome):
    """Cambia il nome del cantiere anche dopo la creazione: tocca solo info.json."""
    cartella = _cartella(id_lavoro)
    nome = " ".join(value.nome.split())
    if not nome:
        raise HTTPException(400, "Il nome non può essere vuoto.")
    info = lv._json_tollerante(cartella / "info.json", {})
    info["nome"] = nome
    configurazione.scrivi_json(cartella / "info.json", info)
    return {"lavoro": id_lavoro, "nome": nome}


@app.post("/api/lavori/prova")
def crea_prova():
    """Cantiere di prova con 30 documenti inventati, pronto da analizzare."""
    percorsi.lavori().mkdir(parents=True, exist_ok=True)
    id_lavoro, cartella = demo_cantiere.crea()
    lv.evento(cartella, tipo="ricevuti", testo="30 documenti di prova generati", file=[], scartati=[])
    _prepara_in_sfondo(id_lavoro, cartella)
    return {"lavoro": id_lavoro}


@app.post("/api/lavori/{id_lavoro}/file")
async def aggiungi_file(id_lavoro: str, file: list[UploadFile]):
    """Aggiunge documenti a un cantiere esistente, anche mentre l'analisi è in corso: i nuovi entrano in coda.

    Un file identico a uno già caricato (stesso contenuto, anche con un altro nome) non si aggiunge. Le pagine già
    lette non si rileggono comunque: la lettura è in archivio per impronta della pagina.
    """
    cartella = _cartella(id_lavoro)
    ingresso = cartella / "ingresso"
    ingresso.mkdir(exist_ok=True)
    gia = {_impronta_file(f) for f in ingresso.rglob("*") if f.is_file()}
    accettati, scartati = await _ricevi(file, ingresso)
    doppi = []
    for nome_file in list(accettati):
        f = ingresso / nome_file
        impronta = _impronta_file(f)
        if impronta in gia:
            f.unlink()
            accettati.remove(nome_file)
            doppi.append(nome_file)
        gia.add(impronta)
    if not accettati:
        return {"lavoro": id_lavoro, "accettati": [], "scartati": scartati, "doppi": doppi}
    info_file = cartella / "info.json"
    info = json.loads(info_file.read_text(encoding="utf-8"))
    info["file"] = info.get("file", []) + accettati
    info["scartati"] = info.get("scartati", []) + scartati
    configurazione.scrivi_json(info_file, info)
    lv.evento(cartella, tipo="ricevuti", testo=f"{len(accettati)} file aggiunti", file=accettati, scartati=scartati)
    _prepara_in_sfondo(id_lavoro, cartella)
    return {"lavoro": id_lavoro, "accettati": accettati, "scartati": scartati, "doppi": doppi}


def _impronta_file(f: Path) -> str:
    h = hashlib.sha256()
    with f.open("rb") as fh:
        while blocco := fh.read(1024 * 1024):
            h.update(blocco)
    return h.hexdigest()


@app.get("/api/lavori/{id_lavoro}/stato")
def stato(id_lavoro: str):
    cartella = _cartella(id_lavoro)
    s = lv.stato(cartella)
    return s | {
        "preparing": id_lavoro in _PREPARING,
        "preparazione": _PREPARAZIONE.get(id_lavoro),
        "fermato": _fermato(cartella),
        "verifica": verifica.riassunto(cartella, s),
    }


@app.get("/api/lavori/{id_lavoro}/verifica")
def esito_verifica(id_lavoro: str):
    """Esito della Verifica finale: pagine ripassate, token, campi prima/dopo, conteggio degli stati prima e dopo."""
    f = _cartella(id_lavoro) / "verifica.json"
    if not f.exists():
        raise HTTPException(404, "verifica finale non ancora fatta")
    return json.loads(f.read_text(encoding="utf-8"))


@app.get("/api/lavori/{id_lavoro}/eventi")
def eventi(id_lavoro: str, da: int = 0):
    return lv.eventi(_cartella(id_lavoro), da)


def _rotazioni(c: Path) -> dict[str, int]:
    """Rotazioni scelte a mano dall'utente (pid -> gradi), in aggiunta a quella letta dal motore."""
    v = lv._json_tollerante(c / "rotazioni.json", {})
    if not isinstance(v, dict):
        return {}
    return {k: int(g) for k, g in v.items() if isinstance(k, str) and g in (0, 90, 180, 270)}


_VERSO_OCR: dict[tuple[str, str], int] = {}  # (cartella, pid) -> gradi stimati dalle righe dell'OCR


def _verso_ocr(c: Path, pid: str) -> int:
    """Pagina girata di lato secondo l'OCR: righe di testo alte e strette invece che larghe e basse.

    L'OCR non dice da che parte è girata: si prova 90° (il caso più comune nei fascicoli visti); «Ruota» corregge.
    """
    chiave = (str(c), pid)
    if chiave in _VERSO_OCR:
        return _VERSO_OCR[chiave]
    gradi = 0
    try:
        riquadri = _riquadri(c, pid)[1]
        # contano solo i blocchi allungati: quelli quasi quadrati (loghi, timbri, celle) non dicono il verso
        alti = sum(1 for x0, y0, x1, y1 in riquadri if (y1 - y0) > 1.5 * max(x1 - x0, 1))
        larghi = sum(1 for x0, y0, x1, y1 in riquadri if (x1 - x0) > 1.5 * max(y1 - y0, 1))
        if alti >= 2 and alti > 2 * larghi:
            gradi = 90
    except (OSError, ValueError, KeyError, TypeError):
        gradi = 0
    _VERSO_OCR[chiave] = gradi
    return gradi


def _gradi(c: Path, p: dict, manuale: int) -> int:
    """Verso letto dal motore, altrimenti stimato dall'OCR, più la correzione manuale."""
    auto = (lv.scheda_pagina(p) or {}).get("orientamento", 0)
    auto = auto if auto in (90, 180, 270) else _verso_ocr(c, p["pid"])
    return (auto + manuale) % 360


def _gradi_pagina(c: Path, pid: str, manuali: dict[str, int] | None = None) -> int:
    """Gradi totali (orari) per vedere la pagina dritta."""
    info = next((p for p in lv.pagine(c) if p["pid"] == pid), None)
    if not info:
        raise HTTPException(404, "pagina non trovata")
    manuali = _rotazioni(c) if manuali is None else manuali
    return _gradi(c, info, manuali.get(pid, 0))


def _gradi_tutte(c: Path) -> dict[str, int]:
    """pid -> gradi orari, solo per le pagine da girare."""
    manuali = _rotazioni(c)
    gradi = {p["pid"]: _gradi(c, p, manuali.get(p["pid"], 0)) for p in lv.pagine(c)}
    return {pid: g for pid, g in gradi.items() if g}


@app.get("/api/lavori/{id_lavoro}/pagine/{pid}.png")
def immagine(id_lavoro: str, pid: str, dritta: int = 0):
    """La pagina come PNG. Con `dritta=1` è raddrizzata (verso letto dal motore + correzione manuale)."""
    c = _cartella(id_lavoro)
    originale = _dentro(c / "pagine", f"{pid}.png")
    gradi = _gradi_pagina(c, pid) if dritta else 0
    if not gradi:
        return FileResponse(originale)
    f = c / "pagine_dritte" / f"{pid}.{gradi}.png"
    if not f.exists():
        f.parent.mkdir(exist_ok=True)
        temporaneo = f.with_name(f"{pid}.{uuid.uuid4().hex}.tmp")
        with Image.open(originale) as img:
            img.rotate(-gradi, expand=True).save(temporaneo, format="PNG")
        try:
            temporaneo.replace(f)
        except OSError:
            temporaneo.unlink(missing_ok=True)
    return FileResponse(f)


class Rotazione(BaseModel):
    gradi: int = 90


@app.post("/api/lavori/{id_lavoro}/pagine/{pid}/ruota")
def ruota(id_lavoro: str, pid: str, value: Rotazione):
    """Gira la pagina di altri 90° (o quanto indicato) quando il verso letto dal motore è sbagliato; resta salvato."""
    if value.gradi not in (90, 180, 270, -90):
        raise HTTPException(400, "gradi non validi")
    c = _cartella(id_lavoro)
    manuali = _rotazioni(c)
    manuali[pid] = (manuali.get(pid, 0) + value.gradi) % 360
    configurazione.scrivi_json(c / "rotazioni.json", manuali)
    return {"pid": pid, "gradi": _gradi_pagina(c, pid, manuali)}


@app.get("/api/lavori/{id_lavoro}/rotazioni")
def rotazioni(id_lavoro: str):
    return _gradi_tutte(_cartella(id_lavoro))


@app.get("/api/lavori/{id_lavoro}/miniature/{pid}.png")
def miniatura(id_lavoro: str, pid: str):
    """Miniatura della pagina (160 px), creata una volta e poi riusata."""
    c = _cartella(id_lavoro)
    originale = _dentro(c / "pagine", f"{pid}.png")
    f = c / "miniature" / f"{pid}.png"
    if not f.exists():
        f.parent.mkdir(exist_ok=True)
        temporaneo = f.with_name(f"{pid}.{uuid.uuid4().hex}.tmp")  # mai una PNG a metà servita a un'altra richiesta
        with Image.open(originale) as img:
            img.thumbnail((160, 160))
            img.save(temporaneo, format="PNG")
        try:
            temporaneo.replace(f)
        except OSError:
            temporaneo.unlink(missing_ok=True)
    return FileResponse(f)


@app.get("/api/lavori/{id_lavoro}/pagine/{pid}")
def scheda(id_lavoro: str, pid: str):
    c = _cartella(id_lavoro)
    info = next((p for p in lv.pagine(c) if p["pid"] == pid), None)
    if not info:
        raise HTTPException(404, "pagina non trovata")
    return {"pagina": info, "scheda": lv.scheda_pagina(info)}


@app.get("/api/lavori/{id_lavoro}/tabella")
def tabella(id_lavoro: str):
    """Risultato in forma di tabella: per ogni cella valore, perché e documenti da cui viene (pagina e zona)."""
    uscita = _cartella(id_lavoro) / "uscita"
    if not (uscita / "risultato.json").exists() or not (uscita / "prove.json").exists():
        raise HTTPException(404, "risultato non ancora pronto")
    risultato = json.loads((uscita / "risultato.json").read_text(encoding="utf-8"))
    fonti = json.loads((uscita / "prove.json").read_text(encoding="utf-8")).get("fonti", {})
    voci = []
    for v in risultato.get("voci", []):
        celle = {}
        for col, cella in v["colonne"].items():
            documenti = []
            for fid in cella.get("fonti", []):
                f = fonti.get(fid)
                if f and f.get("pid"):
                    documenti.append({k: f.get(k) for k in ("pid", "file", "pagina", "cit", "zona")})
            # Pochi documenti per cella: una packing list di 600 pagine rendeva la tabella pesantissima (Viollier).
            celle[col] = {
                "v": cella.get("v", ""),
                "perche": cella.get("perche", ""),
                "documenti": documenti[:MAX_DOCUMENTI_CELLA],
                "altri": max(0, len(documenti) - MAX_DOCUMENTI_CELLA),
            }
        voci.append(
            {
                "n": v["n"],
                "voce": v["voce"],
                "stato": v["stato"],
                "note": v.get("note", []),
                "celle": celle,
            }
        )
    return {"colonne": COLONNE, "voci": voci, "rotazioni": _gradi_tutte(_cartella(id_lavoro))}


@app.get("/api/lavori/{id_lavoro}/originale/{pid}")
def originale(id_lavoro: str, pid: str):
    """Il file originale (PDF o immagine) da cui viene la pagina, senza modifiche."""
    c = _cartella(id_lavoro)
    info = next((p for p in lv.pagine(c) if p["pid"] == pid), None)
    if not info:
        raise HTTPException(404, "pagina non trovata")
    f = _dentro(c / "ingresso", info["file"])
    tipo = "application/pdf" if f.suffix.lower() == ".pdf" else None
    return FileResponse(f, media_type=tipo, content_disposition_type="inline", filename=f.name)


@app.get("/api/lavori/{id_lavoro}/cerca")
def cerca_nelle_pagine(id_lavoro: str, q: str = ""):
    """Pagine lette che contengono le parole cercate, con estratti (per il collegamento agenti)."""
    return ricerca.cerca(_cartella(id_lavoro), q[:300])


@app.get("/api/collegamento")
def collegamento_config():
    """Comando con cui un agente (Claude, ChatGPT...) avvia il collegamento MCP su questo computer."""
    return collegamento.configurazione()


MAX_PAROLE = 400  # riquadri mostrati sulla pagina: oltre non si vede differenza e la pagina si appesantisce


def _riquadri(c: Path, pid: str) -> tuple[str, list[list[int]]]:
    """(origine, riquadri 0-1000) del testo della pagina: parole del PDF, oppure blocchi dell'OCR se già fatto."""
    info = info_pagina(c, pid)
    riquadri = [r[:4] for r in info.get("parole", [])]
    if riquadri:
        return "testo", riquadri
    f = ocr.file_cache(info["impronta"])
    w, h = info.get("larghezza") or 0, info.get("altezza") or 0
    if f.exists() and w and h:
        for b in json.loads(f.read_text(encoding="utf-8")).get("blocchi", []):
            try:
                riquadri.append(
                    [
                        round(1000 * b["top_left_x"] / w),
                        round(1000 * b["top_left_y"] / h),
                        round(1000 * b["bottom_right_x"] / w),
                        round(1000 * b["bottom_right_y"] / h),
                    ]
                )
            except (KeyError, TypeError):
                continue
    return ("ocr" if riquadri else ""), riquadri


@app.get("/api/lavori/{id_lavoro}/pagine/{pid}/parole")
def parole(id_lavoro: str, pid: str):
    """Riquadri del testo riconosciuto (0-1000 sull'immagine), per l'animazione della lettura nel documento in esame.

    Testo nativo del PDF: le parole. Scansioni: i blocchi dell'OCR Mistral, se la pagina è già passata dall'OCR.
    """
    c = _cartella(id_lavoro)
    if not any(p["pid"] == pid for p in lv.pagine(c)):
        raise HTTPException(404, "pagina non trovata")
    origine, riquadri = _riquadri(c, pid)
    if len(riquadri) > MAX_PAROLE:
        passo = len(riquadri) / MAX_PAROLE
        riquadri = [riquadri[int(i * passo)] for i in range(MAX_PAROLE)]
    return {"origine": origine, "riquadri": riquadri}


@app.get("/api/ritagli/{nome}")
def ritaglio(nome: str):
    return FileResponse(_dentro(lv.cartella_ritagli(), nome))


@app.get("/api/lavori/{id_lavoro}/risultato")
def risultato(id_lavoro: str):
    f = _cartella(id_lavoro) / "uscita" / "risultato.json"
    if not f.exists():
        raise HTTPException(404, "uscita non ancora pronta")
    return json.loads(f.read_text(encoding="utf-8"))


@app.get("/api/lavori/{id_lavoro}/uscita/{relativo:path}")
def file_uscita(id_lavoro: str, relativo: str):
    return FileResponse(_dentro(_cartella(id_lavoro) / "uscita", relativo))


def _zip(base: Path, escludi: str | None = None, solo: str | None = None) -> FileResponse:
    """Zip su file temporaneo, non in RAM: FileResponse lo invia a pezzi e lo cancella a fine risposta."""
    fd, percorso = tempfile.mkstemp(prefix="cantierelink-", suffix=".zip")
    os.close(fd)
    try:
        with zipfile.ZipFile(percorso, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(base.rglob("*")):
                rel = f.relative_to(base).as_posix()
                if (
                    f.is_file()
                    and not rel.endswith(".json")
                    and (not escludi or not rel.startswith(escludi))
                    and (not solo or rel.startswith(solo))
                ):
                    z.write(f, rel[len(solo) + 1 :] if solo else rel)
    except BaseException:
        os.remove(percorso)
        raise
    return FileResponse(percorso, media_type="application/zip", background=BackgroundTask(os.remove, percorso))


@app.get("/api/lavori/{id_lavoro}/scarica")
def scarica(id_lavoro: str):
    uscita = _cartella(id_lavoro) / "uscita"
    if not (uscita / "tracciabilita.xlsx").exists():
        raise HTTPException(404, "Excel non ancora pronto")
    risposta = _zip(uscita, escludi="fascicolo_ordinato")
    risposta.headers["Content-Disposition"] = f'attachment; filename="tracciabilita_{id_lavoro}_tracciabilita.zip"'
    return risposta


@app.get("/api/lavori/{id_lavoro}/tutto")
def scarica_tutto(id_lavoro: str):
    """Un solo ZIP: Excel, prove e la cartella fascicolo_ordinato con i documenti in ordine di catena."""
    uscita = _cartella(id_lavoro) / "uscita"
    if not (uscita / "tracciabilita.xlsx").exists():
        raise HTTPException(404, "Excel non ancora pronto")
    risposta = _zip(uscita)
    risposta.headers["Content-Disposition"] = f'attachment; filename="tracciabilita_{id_lavoro}_completo.zip"'
    return risposta


@app.get("/api/lavori/{id_lavoro}/fascicolo-ordinato")
def fascicolo_ordinato(id_lavoro: str):
    uscita = _cartella(id_lavoro) / "uscita"
    if not (uscita / "fascicolo_ordinato").exists():
        raise HTTPException(404, "fascicolo ordinato non ancora pronto")
    risposta = _zip(uscita, solo="fascicolo_ordinato")
    risposta.headers["Content-Disposition"] = f'attachment; filename="tracciabilita_{id_lavoro}_fascicolo_ordinato.zip"'
    return risposta
