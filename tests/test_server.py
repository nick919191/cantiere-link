import time

from fastapi.testclient import TestClient
from pdf_minimo import pdf_con_testo

from traccia import server
from traccia.server import app


def test_carica_e_prepara(radice):
    pdf = pdf_con_testo(["DOCUMENTO DI TRASPORTO numero 1"])
    client = TestClient(app)
    client.headers["X-Traccia-Token"] = client.get("/api/sessione").json()["token"]
    r = client.post(
        "/api/lavori", files=[("file", ("ddt.pdf", pdf, "application/pdf")), ("file", ("note.txt", b"x", "text/plain"))]
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["accettati"] == ["ddt.pdf"] and corpo["scartati"] == ["note.txt"]
    for _ in range(50):
        stato = client.get(f"/api/lavori/{corpo['lavoro']}/stato").json()
        if stato["fase"] != "preparazione":
            break
        time.sleep(0.1)
    assert stato["fase"] == "lettura" and stato["pagine_totali"] == 1
    assert client.get(f"/api/lavori/{corpo['lavoro']}/pagine/p0001.png").status_code == 200
    assert client.get(f"/api/lavori/{corpo['lavoro']}/uscita/../info.json").status_code == 404
    assert client.get("/api/lavori/..%2f..%2fx/stato").status_code in (400, 404)


def test_csp_presente_e_errori_interni_in_json(radice, monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)
    csp = client.get("/").headers["Content-Security-Policy"]
    assert csp.startswith("default-src 'self'") and "script-src" not in csp
    assert client.get("/web/app.js").headers["Content-Security-Policy"] == csp
    assert "script-src 'self' 'unsafe-inline'" in client.get("/demo/shell.html").headers["Content-Security-Policy"]

    def rotto(_cartella):
        raise RuntimeError("imprevisto")

    monkeypatch.setattr(server.lv, "stato", rotto)
    client.post("/api/lavori/prova", headers={"X-Traccia-Token": client.get("/api/sessione").json()["token"]})
    lavoro = next(c.name for c in (radice / "lavori").iterdir())
    r = client.get(f"/api/lavori/{lavoro}/stato")
    assert r.status_code == 500 and r.headers["content-type"].startswith("application/json")
    assert "detail" in r.json() and "imprevisto" not in r.text


def test_zero_pagine_leggibili_da_fase_errore(radice):
    client = TestClient(app)
    client.headers["X-Traccia-Token"] = client.get("/api/sessione").json()["token"]
    r = client.post("/api/lavori", files=[("file", ("finto.pdf", b"non sono un pdf", "application/pdf"))])
    lavoro = r.json()["lavoro"]
    for _ in range(100):
        stato = client.get(f"/api/lavori/{lavoro}/stato").json()
        if not stato["preparing"] and stato["fase"] != "preparazione":
            break
        time.sleep(0.1)
    assert stato["fase"] == "errore" and stato["pagine_totali"] == 0 and "leggibile" in stato["motivo"]
    voce = client.get("/api/lavori").json()[0]
    assert voce["fase"] == "errore" and voce["motivo"] == stato["motivo"]
