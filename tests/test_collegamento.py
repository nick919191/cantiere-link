"""Collegamento MCP per agenti: protocollo e strumenti, contro il servizio dell'app in memoria."""

import json

from fastapi.testclient import TestClient
from test_flusso import _crea_lavoro, _leggi_tutto

from traccia import cli, collegamento, server


class AppInMemoria(collegamento.App):
    """Come App, ma il servizio è quello dei test (nessuna porta, nessuna finestra)."""

    def __init__(self):
        super().__init__()
        self.client = TestClient(server.app)
        self.token = self.client.get("/api/sessione").json()["token"]

    def chiama(self, metodo, percorso, **kw):
        r = self.client.request(metodo, percorso, headers={"X-Traccia-Token": self.token}, **kw)
        if not r.is_success:
            raise RuntimeError(r.json().get("detail"))
        return r.json()


def _chiedi(app, metodo, params=None, mid=1):
    return collegamento.rispondi(app, {"jsonrpc": "2.0", "id": mid, "method": metodo, "params": params or {}})


def test_protocollo_initialize_e_strumenti(radice):
    app = AppInMemoria()
    r = _chiedi(app, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
    assert r["result"]["protocolVersion"] == "2025-06-18" and "tools" in r["result"]["capabilities"]
    assert collegamento.rispondi(app, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    nomi = {t["name"] for t in _chiedi(app, "tools/list")["result"]["tools"]}
    assert {"elenco_cantieri", "crea_cantiere", "avvia_analisi", "ferma_analisi", "tabella", "salva_excel"} <= nomi
    assert _chiedi(app, "metodo/inventato")["error"]["code"] == -32601
    errore = _chiedi(app, "tools/call", {"name": "stato_cantiere", "arguments": {"cantiere": "nessuno"}})["result"]
    assert errore["isError"] and errore["content"][0]["text"].startswith("Errore")


def test_strumenti_su_un_cantiere_composto(radice, capsys, tmp_path):
    cartella, schede = _crea_lavoro(radice)
    _leggi_tutto(cartella, schede)
    (cartella / "info.json").write_text(json.dumps({"nome": "Prova agente"}), encoding="utf-8")
    assert cli.componi("prova") == 0
    capsys.readouterr()
    app = AppInMemoria()

    def strumento(nome, **argomenti):
        r = _chiedi(app, "tools/call", {"name": nome, "arguments": argomenti})["result"]
        assert not r["isError"], r["content"][0]["text"]
        return json.loads(r["content"][0]["text"])

    assert any(c["lavoro"] == "prova" for c in strumento("elenco_cantieri"))
    assert strumento("stato_cantiere", cantiere="prova")["fase"] == "pronto"
    t = strumento("tabella", cantiere="prova")
    assert t["voci"] and all(isinstance(d, str) for v in t["voci"] for c in v["celle"].values() for d in c["documenti"])
    assert strumento("cerca", cantiere="prova", parole="H1001")
    assert "fornitori" in strumento("richieste_fornitori", cantiere="prova")
    salvato = strumento("salva_excel", cantiere="prova", cartella=str(tmp_path))
    assert salvato["excel"].endswith("tracciabilita_Prova agente.xlsx")


def test_crea_cantiere_da_file_sul_computer(radice, tmp_path):
    from pdf_minimo import pdf_con_testo

    pdf = tmp_path / "ddt.pdf"
    pdf.write_bytes(pdf_con_testo(["DDT 1458"]))
    app = AppInMemoria()
    r = _chiedi(app, "tools/call", {"name": "crea_cantiere", "arguments": {"nome": "Da agente", "file": [str(pdf)]}})
    dati = json.loads(r["result"]["content"][0]["text"])
    assert dati["accettati"] == ["ddt.pdf"] and dati["lavoro"]
    r = _chiedi(app, "tools/call", {"name": "crea_cantiere", "arguments": {"file": [str(tmp_path / "manca.pdf")]}})
    assert r["result"]["isError"] and "non trovato" in r["result"]["content"][0]["text"]
