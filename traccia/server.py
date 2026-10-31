"""Piattaforma locale (solo 127.0.0.1): caricamento, stato in tempo reale, immagini, download.

Il servizio locale collega il browser all’agente ChatGPT e conserva originali e risultati sul computer.
"""

import hashlib
import io
import json
import os
import re
import secrets
import shutil
import threading
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from PIL import Image
from pydantic import BaseModel, Field

from . import agente, aggiornamenti, cestino, chatgpt, configurazione, consumi, demo_cantiere, ocr, percorsi
from . import lavoro as lv
from .preparazione import prepara


@asynccontextmanager
async def lifecycle(_app):
    stop_checks = threading.Event()

    def update_checks():
        while not stop_checks.is_set():
            try:
                aggiornamenti.check()
            except Exception:
                pass
            stop_checks.wait(3600)

    threading.Thread(target=update_checks, daemon=True).start()
    yield
    stop_checks.set()
    agente.stop()


app = FastAPI(title="CantiereLink", docs_url=None, redoc_url=None, lifespan=lifecycle)
_PREPARING = set()
_ANCORA = set()  # cantieri con file arrivati mentre la preparazione era già in corso: si ripassa
_PREPARAZIONE: dict[str, dict] = {}  # avanzamento della preparazione: {"n": file fatti, "totale": file da fare}
_ESTENSIONI = {".pdf", ".zip", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
_MAX_BYTE = 500 * 1024 * 1024
_TOKEN = secrets.token_urlsafe(32)


@app.middleware("http")
async def locale(request: Request, call_next):
    host = request.url.hostname
    if host not in ("127.0.0.1", "localhost") and not (host == "testserver" and request.client.host == "testclient"):
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
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(chatgpt.AgentError)
async def agent_error(_request: Request, exc: chatgpt.AgentError):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.get("/api/sessione")
def sessione():
    return {"token": _TOKEN}


@app.get("/api/impostazioni")
def impostazioni():
    prefs = configurazione.leggi()
    return {k: prefs[k] for k in ("model", "reasoning", "theme")} | {"cartella": str(percorsi.RADICE)}


class Preferenze(BaseModel):
    model: str = Field(default="", max_length=150)
    reasoning: str = "low"
    theme: str = "system"


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
    agente.avvia(cartella, poi=lambda riuscita: _ancora_da_fare(id_lavoro, riuscita))
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
        raise chatgpt.AgentError("Attendi il completamento della preparazione delle pagine.")
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


@app.put("/api/aggiornamenti/preferenze")
def update_preferences(choice: UpdatePreferences):
    configurazione.aggiorna({"update_checks": choice.automatic, "dismissed_update": choice.dismissed})
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
    return {"ok": True, "application": "tracciabilita-materiali"}


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
        except OSError:
            # Una cartella non leggibile (permessi) non deve nascondere tutti gli altri cantieri.
            continue
        voce = {k: s[k] for k in ("lavoro", "nome", "creato", "fase", "pagine_totali", "percentuale", "consumo")}
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
        with destinazione.open("xb") as output:
            while dati := await f.read(1024 * 1024):
                totale += len(dati)
                if totale > _MAX_BYTE:
                    raise HTTPException(413, "Caricamento troppo grande. Suddividi i file in fascicoli più piccoli.")
                output.write(dati)
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
            lv.evento(
                cartella, tipo="errore", testo="Preparazione non riuscita: controlla formato e dimensioni dei file."
            )
        finally:
            _PREPARING.discard(id_lavoro)
            _PREPARAZIONE.pop(id_lavoro, None)
        _avvia_se_serve(id_lavoro)

    threading.Thread(target=prepare_job, daemon=True).start()


@app.post("/api/lavori")
async def carica(file: list[UploadFile], nome: str = Form("")):
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
    (cartella / "info.json").write_text(
        json.dumps(
            {
                "nome": nome or id_lavoro,
                "creato": time.strftime("%d/%m/%Y %H:%M"),
                "file": accettati,
                "scartati": scartati,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    lv.evento(cartella, tipo="ricevuti", testo=f"{len(accettati)} file ricevuti", file=accettati, scartati=scartati)
    _prepara_in_sfondo(id_lavoro, cartella)
    return {"lavoro": id_lavoro, "accettati": accettati, "scartati": scartati}


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
    info_file.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
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
    return lv.stato(cartella) | {
        "preparing": id_lavoro in _PREPARING,
        "preparazione": _PREPARAZIONE.get(id_lavoro),
        "fermato": _fermato(cartella),
    }


@app.get("/api/lavori/{id_lavoro}/eventi")
def eventi(id_lavoro: str, da: int = 0):
    return lv.eventi(_cartella(id_lavoro), da)


@app.get("/api/lavori/{id_lavoro}/pagine/{pid}.png")
def immagine(id_lavoro: str, pid: str):
    return FileResponse(_dentro(_cartella(id_lavoro) / "pagine", f"{pid}.png"))


@app.get("/api/lavori/{id_lavoro}/miniature/{pid}.png")
def miniatura(id_lavoro: str, pid: str):
    """Miniatura della pagina (160 px), creata una volta e poi riusata."""
    c = _cartella(id_lavoro)
    originale = _dentro(c / "pagine", f"{pid}.png")
    f = c / "miniature" / f"{pid}.png"
    if not f.exists():
        f.parent.mkdir(exist_ok=True)
        with Image.open(originale) as img:
            img.thumbnail((160, 160))
            img.save(f, format="PNG")
    return FileResponse(f)


@app.get("/api/lavori/{id_lavoro}/pagine/{pid}")
def scheda(id_lavoro: str, pid: str):
    c = _cartella(id_lavoro)
    info = next((p for p in lv.pagine(c) if p["pid"] == pid), None)
    if not info:
        raise HTTPException(404, "pagina non trovata")
    return {"pagina": info, "scheda": lv.scheda_pagina(info)}


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


def _zip(base: Path, escludi: str | None = None, solo: str | None = None) -> StreamingResponse:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(base.rglob("*")):
            rel = f.relative_to(base).as_posix()
            if (
                f.is_file()
                and not rel.endswith(".json")
                and (not escludi or not rel.startswith(escludi))
                and (not solo or rel.startswith(solo))
            ):
                z.write(f, rel[len(solo) + 1 :] if solo else rel)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip")


@app.get("/api/lavori/{id_lavoro}/scarica")
def scarica(id_lavoro: str):
    uscita = _cartella(id_lavoro) / "uscita"
    if not (uscita / "tracciabilita.xlsx").exists():
        raise HTTPException(404, "Excel non ancora pronto")
    risposta = _zip(uscita, escludi="fascicolo_ordinato")
    risposta.headers["Content-Disposition"] = f'attachment; filename="tracciabilita_{id_lavoro}_tracciabilita.zip"'
    return risposta


@app.get("/api/lavori/{id_lavoro}/fascicolo-ordinato")
def fascicolo_ordinato(id_lavoro: str):
    uscita = _cartella(id_lavoro) / "uscita"
    if not (uscita / "fascicolo_ordinato").exists():
        raise HTTPException(404, "fascicolo ordinato non ancora pronto")
    risposta = _zip(uscita, solo="fascicolo_ordinato")
    risposta.headers["Content-Disposition"] = f'attachment; filename="tracciabilita_{id_lavoro}_fascicolo_ordinato.zip"'
    return risposta
