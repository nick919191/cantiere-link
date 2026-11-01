"""Interfaccia 0.7: rinomina, pagine raddrizzate, tabella leggera, ZIP unico, prezzi stimati."""

import io
import zipfile

from fastapi.testclient import TestClient
from PIL import Image
from test_flusso import _crea_lavoro, _leggi_tutto

from traccia import cli, configurazione, server


def _pronto(radice, capsys):
    cartella, schede = _crea_lavoro(radice)
    _leggi_tutto(cartella, schede)
    assert cli.componi("prova") == 0
    capsys.readouterr()
    return TestClient(server.app), {"X-Traccia-Token": server._TOKEN}


def test_rinomina_cantiere_anche_dopo_la_creazione(radice, capsys):
    client, testata = _pronto(radice, capsys)
    r = client.put("/api/lavori/prova/nome", json={"nome": "  Palestra   Codogno "}, headers=testata)
    assert r.status_code == 200 and r.json()["nome"] == "Palestra Codogno"
    assert client.get("/api/lavori/prova/stato").json()["nome"] == "Palestra Codogno"
    assert next(c for c in client.get("/api/lavori").json() if c["lavoro"] == "prova")["nome"] == "Palestra Codogno"
    assert client.put("/api/lavori/prova/nome", json={"nome": "   "}, headers=testata).status_code == 400
    assert client.put("/api/lavori/prova/nome", json={"nome": "x"}).status_code == 403  # senza token


def test_pagina_dritta_e_rotazione_manuale(radice, capsys):
    client, testata = _pronto(radice, capsys)
    t = client.get("/api/lavori/prova/tabella").json()
    assert "rotazioni" in t
    pid = next(d["pid"] for v in t["voci"] for c in v["celle"].values() for d in c["documenti"])
    originale = Image.open(io.BytesIO(client.get(f"/api/lavori/prova/pagine/{pid}.png").content)).size
    assert Image.open(io.BytesIO(client.get(f"/api/lavori/prova/pagine/{pid}.png?dritta=1").content)).size == originale
    r = client.post(f"/api/lavori/prova/pagine/{pid}/ruota", json={"gradi": 90}, headers=testata)
    assert r.status_code == 200 and r.json()["gradi"] == 90
    girata = Image.open(io.BytesIO(client.get(f"/api/lavori/prova/pagine/{pid}.png?dritta=1").content)).size
    assert girata == (originale[1], originale[0])  # larghezza e altezza scambiate
    assert client.get("/api/lavori/prova/rotazioni").json() == {pid: 90}
    assert client.get("/api/lavori/prova/tabella").json()["rotazioni"] == {pid: 90}
    for _ in range(3):
        client.post(f"/api/lavori/prova/pagine/{pid}/ruota", json={"gradi": 90}, headers=testata)
    assert client.get("/api/lavori/prova/rotazioni").json() == {}  # quattro quarti di giro: torna dritta
    assert client.post(f"/api/lavori/prova/pagine/{pid}/ruota", json={"gradi": 45}, headers=testata).status_code == 400


def test_tabella_limita_i_documenti_per_cella(radice, capsys):
    client, _ = _pronto(radice, capsys)
    t = client.get("/api/lavori/prova/tabella").json()
    for v in t["voci"]:
        for c in v["celle"].values():
            assert len(c["documenti"]) <= server.MAX_DOCUMENTI_CELLA and c["altri"] >= 0


def test_zip_unico_con_excel_prove_e_fascicolo_ordinato(radice, capsys):
    client, _ = _pronto(radice, capsys)
    r = client.get("/api/lavori/prova/tutto")
    assert r.status_code == 200 and "completo.zip" in r.headers["content-disposition"]
    nomi = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "tracciabilita.xlsx" in nomi
    assert any(n.startswith("prove/") for n in nomi) and any(n.startswith("fascicolo_ordinato/") for n in nomi)
    assert not any(n.endswith(".json") for n in nomi)


def test_prezzi_stimati_nelle_impostazioni(radice):
    client = TestClient(server.app)
    testata = {"X-Traccia-Token": server._TOKEN}
    i = client.get("/api/impostazioni", headers=testata).json()
    assert i["prezzo_ingresso"] == 1.15 and i["prezzo_uscita"] == 9.2
    r = client.put("/api/impostazioni", json={**i, "prezzo_ingresso": 2, "prezzo_uscita": 0}, headers=testata)
    assert r.status_code == 200 and r.json()["prezzo_ingresso"] == 2.0 and r.json()["prezzo_uscita"] == 0.0
    assert configurazione.leggi()["prezzo_ingresso"] == 2.0
    assert client.put("/api/impostazioni", json={**i, "prezzo_uscita": -1}, headers=testata).status_code == 422
