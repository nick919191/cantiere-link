"""Endpoint del risultato: /risultato, /scarica (zip su file temporaneo), /fascicolo-ordinato; cache della versione."""

import io
import tempfile
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from test_flusso import _crea_lavoro, _leggi_tutto

from traccia import cli, percorsi, server


def _pronto(radice):
    cartella, schede = _crea_lavoro(radice)
    _leggi_tutto(cartella, schede)
    cli.componi("prova")
    client = TestClient(server.app)
    client.headers["X-Traccia-Token"] = client.get("/api/sessione").json()["token"]
    return cartella, client


def _temporanei():
    return set(Path(tempfile.gettempdir()).glob("cantierelink-*.zip"))


def test_scarica_e_fascicolo_ordinato_senza_zip_in_memoria(radice, monkeypatch):
    _cartella, client = _pronto(radice)
    creati = []
    mkstemp = tempfile.mkstemp

    def spia(**kwargs):
        fd, percorso = mkstemp(**kwargs)
        creati.append(Path(percorso))
        return fd, percorso

    monkeypatch.setattr(server.tempfile, "mkstemp", spia)
    assert client.get("/api/lavori/prova/risultato").json()["voci"]
    assert client.get("/api/lavori/assente/risultato").status_code == 404
    prima = _temporanei()
    r = client.get("/api/lavori/prova/scarica")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert 'filename="tracciabilita_prova_tracciabilita.zip"' in r.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        nomi = z.namelist()
    assert "tracciabilita.xlsx" in nomi and any(n.startswith("prove/") for n in nomi)
    assert not any(n.startswith("fascicolo_ordinato") or n.endswith(".json") for n in nomi)
    r = client.get("/api/lavori/prova/fascicolo-ordinato")
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert "INDICE.xlsx" in z.namelist()
    # zip su file temporaneo, cancellato a fine risposta
    assert len(creati) == 2 and not any(p.exists() for p in creati)
    assert _temporanei() == prima
    assert client.get("/api/lavori/prova/uscita/../info.json").status_code == 404


def test_versione_lettura_calcolata_una_volta(monkeypatch):
    percorsi.versione_lettura.cache_clear()
    valore = percorsi.versione_lettura()
    letture = []
    monkeypatch.setattr(percorsi.Path, "read_bytes", lambda self: letture.append(self) or b"")
    assert percorsi.versione_lettura() == valore and letture == []
    assert percorsi.versione_lettura.cache_info().hits >= 1
