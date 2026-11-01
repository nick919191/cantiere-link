"""Correzioni di gravità bassa: B2, B3, B5, B6, B7, B9, S7, S10, S11 e i test mancanti su chat e Excel."""

import copy
import json
import time

import pytest
from fascicolo_inventato import fascicolo, scheda
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pdf_minimo import pdf_con_testo
from PIL import Image
from test_flusso import _crea_lavoro, _leggi_tutto
from test_motore import _risultato, _voce

from traccia import agente, chat, chatgpt, cli, riordino, server
from traccia import lavoro as lv
from traccia.controlli import valida
from traccia.motore import Motore, elabora


def _client():
    client = TestClient(server.app)
    client.headers["X-Traccia-Token"] = client.get("/api/sessione").json()["token"]
    return client


def _respond_con(records, salta=None, prima=None):
    def respond(_instructions, inputs, *_args):
        if prima:
            prima()
        schede = {}
        for item in inputs[0]["content"]:
            if item["type"] == "input_text":
                context = json.loads(item["text"])
                name = context["file"].rsplit("/", 1)[-1]
                if name != salta:
                    schede[context["pid"]] = copy.deepcopy(records[name])
        return json.dumps({"schede": schede})

    return respond


def test_b2_stato_deciso_dal_flag_ambiguo_non_dal_testo(monkeypatch):
    prove, _ = _risultato()
    monkeypatch.setattr(
        Motore,
        "_cerca_per_profilo",
        lambda self, voce, doc_ddt, riga_ddt, classe_ddt, scartati, motivi: (
            motivi.append("certificati possibili: A, B") or (None, [], False, True)
        ),
    )
    for riga in prove["packing"]:
        riga["certificato"] = ""  # senza certificato dichiarato si passa dalla ricerca per profilo
    assert _voce(elabora(prove), "PL10*60")["stato"] == "DA CONFERMARE"


def test_b3_miniatura_scritta_su_temporaneo_poi_rinominata(radice, monkeypatch):
    client = _client()
    lavoro = client.post("/api/lavori", files=[("file", ("a.pdf", pdf_con_testo(["x"]), "application/pdf"))]).json()
    for _ in range(100):
        stato = client.get(f"/api/lavori/{lavoro['lavoro']}/stato").json()
        if stato["fase"] != "preparazione" and not stato["preparing"]:
            break
        time.sleep(0.1)
    destinazioni = []
    salva = Image.Image.save

    def spia(self, fp, *args, **kwargs):
        destinazioni.append(str(fp))
        return salva(self, fp, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "save", spia)
    r = client.get(f"/api/lavori/{lavoro['lavoro']}/miniature/p0001.png")
    assert r.status_code == 200 and destinazioni and destinazioni[0].endswith(".tmp")
    miniature = radice / "lavori" / lavoro["lavoro"] / "miniature"
    assert [p.name for p in miniature.iterdir()] == ["p0001.png"]


def test_b5_risposta_ricevuta_dopo_interrompi_viene_salvata(radice, monkeypatch):
    directory, _ = _crea_lavoro(radice)
    records = {name: schema for name, _, schema in fascicolo()}
    monkeypatch.setattr(chatgpt, "response", _respond_con(records, prima=agente.stop))
    monkeypatch.setattr(agente, "_state", {**agente._state, "busy": True})
    agente._cancel.clear()
    agente._stop_richiesto.clear()
    with pytest.raises(chatgpt.AgentError, match="interrotta"):
        agente.analizza(directory, "test-model", "")
    assert lv.stato(directory)["lette"] >= agente.PAGINE_PER_LOTTO


def test_b6_host_di_test_ammesso_solo_dalla_fixture(radice, monkeypatch):
    monkeypatch.setattr(server, "HOST_CONSENTITI", {"127.0.0.1", "localhost"})
    assert TestClient(server.app).get("/api/salute").status_code == 403
    assert TestClient(server.app, base_url="http://127.0.0.1").get("/api/salute").status_code == 200


def test_b7_agente_rispondi_con_mock_esclude_i_messaggi_di_stato(radice, monkeypatch):
    directory, schede = _crea_lavoro(radice)
    pagine = _leggi_tutto(directory, schede)
    cli.componi("prova")
    q1 = chat.chiedi(directory, "prima domanda")
    chat.fallita(directory, q1["id"], "Sessione interrotta.")
    q2 = chat.chiedi(directory, "Che colata ha la HEB 180?")
    pid = next(p["pid"] for p in pagine if p["file"].endswith("cert777.pdf"))
    payload = {}

    def respond(_instructions, inputs, *_args):
        payload.update(json.loads(inputs[0]["content"]))
        return json.dumps({"testo": "La colata è H1001.", "fonti": [{"pid": pid, "cit": "H1001"}]})

    monkeypatch.setattr(chatgpt, "response", respond)
    agente._cancel.clear()
    agente.rispondi(directory, q2["id"], "test-model", "")
    assert {m["ruolo"] for m in payload["storico"]} <= {"utente", "assistente"}
    assert payload["domanda"] == q2["testo"] and any(p["pid"] == pid for p in payload["pagine"])
    risposta = chat.messaggi(directory)[-1]
    assert risposta["ruolo"] == "assistente" and risposta["fonti"][0]["pid"] == pid
    assert chat.in_attesa(directory) == []


def test_b9_messaggio_di_avanzamento_non_conta_le_schede_rifiutate(radice, monkeypatch):
    directory, _ = _crea_lavoro(radice)
    records = {name: schema for name, _, schema in fascicolo()}
    monkeypatch.setattr(chatgpt, "response", _respond_con(records, salta="ddt300.pdf"))
    monkeypatch.setattr(agente, "GIRI_AUTOMATICI", 1)
    messaggi = []

    class Registra(dict):
        def update(self, *args, **kwargs):
            messaggi.append(kwargs.get("message", ""))
            super().update(*args, **kwargs)

    monkeypatch.setattr(agente, "_state", Registra(agente._state))
    agente._cancel.clear()
    agente._stop_richiesto.clear()
    with pytest.raises(chatgpt.AgentError):
        agente.analizza(directory, "test-model", "")
    assert any(m.startswith("Lette 11 di 12 pagine, 1 da rileggere") for m in messaggi), messaggi


def test_s7_nome_del_cantiere_limitato(radice):
    client = _client()
    r = client.post(
        "/api/lavori", files=[("file", ("a.pdf", pdf_con_testo(["x"]), "application/pdf"))], data={"nome": "n" * 201}
    )
    assert r.status_code == 422


def test_s10_enum_in_whitelist_e_lunghezze_limitate():
    s = scheda("ddt")
    s["testata"]["tipo_proposto"] = {"v": "forse", "cit": "", "zona": []}
    assert any("tipo_proposto" in e and "non ammesso" in e for e in valida(s))
    s = scheda("ddt")
    s["testata"]["tipo_proposto"] = {"v": "costruttore_cliente", "cit": "", "zona": []}
    assert not any("tipo_proposto" in e for e in valida(s))
    s = scheda("ddt")
    s["trascrizione"] = "x" * 100_001
    assert any("trascrizione" in e for e in valida(s))
    s = scheda("ddt")
    s["avvisi"] = ["a"] * 21
    assert any("avvisi" in e for e in valida(s))
    s = scheda("ddt")
    s["segni"] = [{"tipo": "freccia", "riga": 1, "testo": "x", "zona": [1, 2, 3]}]
    assert any("segni[0]" in e for e in valida(s))


def test_s11_ritagli_solo_nomi_di_file_e_indice_senza_formule(radice):
    directory, schede = _crea_lavoro(radice)
    pagine = _leggi_tutto(directory, schede)
    ritagli = lv.cartella_ritagli()
    ritagli.mkdir(parents=True, exist_ok=True)
    (ritagli / "buono.png").write_bytes(b"png")
    (radice / "fuori.png").write_bytes(b"segreto")
    impronta = pagine[0]["impronta"]
    lettura = lv.file_lettura(impronta)
    s = json.loads(lettura.read_text(encoding="utf-8"))
    s["ritagli"] = [{"file": "buono.png"}, {"file": "../fuori.png"}, {"file": str(radice / "fuori.png")}]
    lettura.write_text(json.dumps(s), encoding="utf-8")
    cli.componi("prova")
    copiati = sorted(p.name for p in (directory / "uscita" / "prove" / "ritagli").iterdir())
    assert copiati == ["buono.png"]

    cartella = radice / "lavori" / "formula"
    (cartella / "ingresso").mkdir(parents=True)
    (cartella / "ingresso" / "=1+1.pdf").write_bytes(pdf_con_testo(["DDT 1"]))
    pagina = [{"pid": "p0001", "file": "=1+1.pdf", "pagina": 1}]
    riordino.crea(cartella, pagina, {"p0001": scheda("ddt")}, cartella / "ordinato")
    ws = load_workbook(cartella / "ordinato" / "INDICE.xlsx")["Indice"]
    assert ws["B2"].value == "=1+1.pdf" and ws["B2"].data_type == "s"


def test_post_chat_endpoint(radice, monkeypatch):
    directory, _ = _crea_lavoro(radice)
    cli.prepara_lavoro("prova")
    client = _client()
    monkeypatch.setattr(chatgpt, "status", lambda: {"plan_enabled": True})
    avviati = []
    monkeypatch.setattr(server.agente, "avvia", lambda c, qid=None: avviati.append(qid))
    r = client.post("/api/lavori/prova/chat", json={"testo": "Quali documenti mancano?", "pagine": ["p0001"]})
    assert r.status_code == 200 and avviati == [r.json()["id"]]
    assert client.get("/api/lavori/prova/chat").json()["in_attesa"] == [r.json()["id"]]
    assert client.get("/api/lavori/prova/conversazioni").json()[0]["title"].startswith("Quali documenti")
    assert client.post("/api/lavori/prova/chat", json={"testo": "x", "pagine": ["p9999"]}).status_code == 400
    assert client.post("/api/lavori/prova/chat", json={"testo": ""}).status_code == 422
    monkeypatch.setattr(chatgpt, "status", lambda: {"plan_enabled": False})
    assert client.post("/api/lavori/prova/chat", json={"testo": "y"}).status_code == 409


def test_contenuto_dei_fogli_excel(radice):
    directory, schede = _crea_lavoro(radice)
    _leggi_tutto(directory, schede)
    cli.componi("prova")
    wb = load_workbook(directory / "uscita" / "tracciabilita.xlsx")
    ws = wb["Tracciabilità"]
    intestazione = [c.value for c in ws[1]]
    assert intestazione[:2] == ["PRODUTTORE", "COLATA"] and "STATO" in intestazione and "PARTE D'OPERA" in intestazione
    righe = list(ws.iter_rows(min_row=2, values_only=True))
    stati = {r[intestazione.index("STATO")] for r in righe}
    assert righe and stati <= {"PROVATO", "DEDOTTO", "DA CONFERMARE", "MANCANTE"} and "MANCANTE" in stati
    assert all(c.data_type == "s" for r in ws.iter_rows(min_row=2) for c in r if c.value is not None)
    richieste = list(wb["Richieste ai fornitori"].iter_rows(min_row=2, values_only=True))
    assert any("5504" in " ".join(str(v) for v in r if v) for r in richieste)
