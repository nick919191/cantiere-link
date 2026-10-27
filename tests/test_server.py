import time

from fastapi.testclient import TestClient
from pdf_minimo import pdf_con_testo

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
