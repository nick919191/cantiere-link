"""Cantiere di prova, aggiunta di file senza rileggere, conteggio token, stato dell'interruzione."""

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient
from pdf_minimo import pdf_con_testo

from traccia import agente, chatgpt, consumi, demo_cantiere, server
from traccia import lavoro as lv
from traccia.preparazione import prepara


def _client():
    client = TestClient(server.app)
    client.headers["X-Traccia-Token"] = client.get("/api/sessione").json()["token"]
    return client


def _attendi_preparazione(client, lavoro):
    for _ in range(100):
        stato = client.get(f"/api/lavori/{lavoro}/stato").json()
        if not stato["preparing"] and stato["fase"] != "preparazione":
            return stato
        time.sleep(0.1)
    pytest.fail("preparazione non terminata")


def test_cantiere_di_prova_ha_30_documenti_leggibili(radice):
    assert len(demo_cantiere.documenti()) == 30
    assert len({nome for nome, _ in demo_cantiere.documenti()}) == 30
    _id, cartella = demo_cantiere.crea()
    pagine = prepara(cartella)
    assert len(pagine) == 30 and all(p["pid"] for p in pagine)
    testi = [json.loads((cartella / "pagine" / f"{p['pid']}.json").read_text(encoding="utf-8")) for p in pagine]
    assert all(t["testo_nativo"] and t["larghezza"] < 1000 for t in testi)  # A5: immagini piccole
    assert any("TABELLA DI TRACCIABILITA" in t["testo_nativo"] for t in testi)
    assert sum("CERTIFICATO DI COLLAUDO 3.1" in t["testo_nativo"] for t in testi) == 16
    assert lv.stato(cartella)["fase"] == "lettura"


def test_api_crea_cantiere_di_prova(radice):
    client = _client()
    r = client.post("/api/lavori/prova")
    assert r.status_code == 200
    stato = _attendi_preparazione(client, r.json()["lavoro"])
    assert stato["pagine_totali"] == 30 and stato["nome"] == demo_cantiere.NOME
    assert client.get("/api/lavori").json()[0]["lavoro"] == r.json()["lavoro"]


def test_aggiunta_file_conserva_pid_e_letture(radice):
    client = _client()
    r = client.post(
        "/api/lavori",
        files=[("file", ("b.pdf", pdf_con_testo(["pagina B"]), "application/pdf"))],
        data={"nome": "incrementale"},
    )
    lavoro = r.json()["lavoro"]
    prima = _attendi_preparazione(client, lavoro)
    assert [p["pid"] for p in prima["pagine"]] == ["p0001"]
    cartella = radice / "lavori" / lavoro
    impronta = lv.pagine(cartella)[0]["impronta"]
    lv.salva_lettura(impronta, {"famiglia": "da_escludere", "utile": False, "motivo": "test", "righe": []})
    assert lv.stato(cartella)["fase"] == "composizione"

    # "a.pdf" verrebbe prima di "b.pdf" in ordine alfabetico: il pid di b.pdf non deve cambiare
    r = client.post(
        f"/api/lavori/{lavoro}/file", files=[("file", ("a.pdf", pdf_con_testo(["pagina A"]), "application/pdf"))]
    )
    assert r.status_code == 200 and r.json()["accettati"] == ["a.pdf"]
    dopo = _attendi_preparazione(client, lavoro)
    assert {(p["pid"], p["file"]) for p in dopo["pagine"]} == {("p0001", "b.pdf"), ("p0002", "a.pdf")}
    assert dopo["lette"] == 1 and dopo["da_leggere"] == 1 and dopo["fase"] == "lettura"
    assert json.loads((cartella / "info.json").read_text(encoding="utf-8"))["file"] == ["b.pdf", "a.pdf"]


def test_aggiunta_file_rifiutata_mentre_agente_legge_quel_cantiere(radice, monkeypatch):
    client = _client()
    r = client.post("/api/lavori", files=[("file", ("b.pdf", pdf_con_testo(["x"]), "application/pdf"))])
    lavoro = r.json()["lavoro"]
    _attendi_preparazione(client, lavoro)
    monkeypatch.setattr(server.agente, "stato", lambda: {"busy": True, "job": lavoro})
    r = client.post(f"/api/lavori/{lavoro}/file", files=[("file", ("a.pdf", pdf_con_testo(["y"]), "application/pdf"))])
    assert r.status_code == 409 and "Interrompi" in r.json()["detail"]


def test_token_dichiarati_dal_servizio_vengono_contati(radice, monkeypatch):
    events = [
        {"type": "response.output_text.delta", "delta": "{}"},
        {"type": "response.completed", "response": {"usage": {"input_tokens": 1200, "output_tokens": 34}}},
    ]

    class Stream:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def iter_lines(self):
            return iter("data: " + json.dumps(e) for e in events)

    monkeypatch.setattr(chatgpt, "access_token", lambda: "fake-token")
    monkeypatch.setattr(chatgpt.httpx, "stream", lambda *a, **k: Stream())
    consumo = {}
    assert chatgpt.response("i", [], "model", "", threading.Event(), consumo) == "{}"
    assert consumo == {"chiamata": True, "ingresso": 1200, "uscita": 34}

    cartella = radice / "lavori" / "c1"
    cartella.mkdir(parents=True)
    consumi.registra(cartella, consumo)
    consumi.registra(cartella, consumo)
    consumi.registra(cartella, {})  # chiamata fallita prima della risposta: non conta
    assert consumi.cantiere(cartella) == {"chiamate": 2, "ingresso": 2400, "uscita": 68}
    assert consumi.totale() == {"chiamate": 2, "ingresso": 2400, "uscita": 68}
    assert client_consumi(_client()) == {"chiamate": 2, "ingresso": 2400, "uscita": 68}


def client_consumi(client):
    return client.get("/api/consumi").json()


def test_cartella_non_leggibile_non_blocca_gli_altri_cantieri(radice, monkeypatch):
    client = _client()
    buono = client.post("/api/lavori", files=[("file", ("b.pdf", pdf_con_testo(["x"]), "application/pdf"))]).json()
    _attendi_preparazione(client, buono["lavoro"])
    rotto = radice / "lavori" / "20260101-000000-rotto"
    rotto.mkdir()
    (rotto / "info.json").write_text("{}", encoding="utf-8")
    stato_vero = lv.stato

    def stato_finto(cartella):
        if cartella.name.endswith("rotto"):
            raise PermissionError("accesso negato")
        return stato_vero(cartella)

    monkeypatch.setattr(server.lv, "stato", stato_finto)
    assert [j["lavoro"] for j in client.get("/api/lavori").json()] == [buono["lavoro"]]
    assert not list((radice / "lavori").glob(".caricamento-*"))  # nessuna cartella provvisoria lasciata indietro


def test_immagine_per_modello_ridotta_in_jpeg(tmp_path):
    import base64
    import io

    from PIL import Image

    png = tmp_path / "a0.png"
    Image.new("RGB", (7382, 5315), "white").save(png)
    blocco = agente.immagine_per_modello(png)
    assert blocco["type"] == "input_image" and blocco["image_url"].startswith("data:image/jpeg;base64,")
    dati = base64.b64decode(blocco["image_url"].split(",", 1)[1])
    with Image.open(io.BytesIO(dati)) as img:
        assert max(img.size) == agente.LATO_MASSIMO and img.format == "JPEG"
    assert len(dati) < 500_000


def test_rifiuto_di_chatgpt_mostra_codice_e_motivo(monkeypatch):
    class Stream:
        status_code = 400
        text = json.dumps({"error": {"message": "Invalid image: too  large"}})

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            pass

    monkeypatch.setattr(chatgpt, "access_token", lambda: "fake-token")
    monkeypatch.setattr(chatgpt.httpx, "stream", lambda *a, **k: Stream())
    with pytest.raises(chatgpt.AgentError, match=r"codice 400\): Invalid image: too large"):
        chatgpt.response("i", [], "model", "", threading.Event())


def test_interruzione_segnala_lo_stato(monkeypatch):
    monkeypatch.setattr(agente, "_state", {**agente._state, "busy": False, "stopping": False})
    assert "Nessuna" in agente.stop()["message"]
    monkeypatch.setattr(agente, "_state", {**agente._state, "busy": True, "stopping": False})
    agente._cancel.clear()
    assert "riprendi" in agente.stop()["message"]
    assert agente.stato()["stopping"] and agente._cancel.is_set()
    agente._cancel.clear()
