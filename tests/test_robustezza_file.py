"""File di stato corrotti o del tipo sbagliato: l'app parte, la home resta piena, i file si scrivono in modo atomico."""

from fastapi.testclient import TestClient
from pdf_minimo import pdf_con_testo

from traccia import cestino, configurazione, consumi, server
from traccia import lavoro as lv


def _client():
    client = TestClient(server.app)
    client.headers["X-Traccia-Token"] = client.get("/api/sessione").json()["token"]
    return client


def _cantiere(radice, nome, info='{"nome": "ok"}'):
    cartella = radice / "lavori" / nome
    cartella.mkdir(parents=True)
    (cartella / "info.json").write_text(info, encoding="utf-8")
    return cartella


def test_chat_di_una_versione_precedente_non_impedisce_l_avvio(radice):
    rotto = _cantiere(radice, "20260101-000000-rotto")
    (rotto / "chat.jsonl").write_text('{"id": "d1", "ruolo": "utente", "testo": "ciao"}\n{"id": "d2", "ruo', "utf-8")
    buono = _cantiere(radice, "20260101-000001-buono")
    (buono / "pagine.json").write_text("[]", encoding="utf-8")
    with TestClient(server.app) as client:  # il blocco with esegue il lifespan (A1)
        lavori = [j["lavoro"] for j in client.get("/api/lavori").json()]
    assert buono.name in lavori


def test_json_corrotto_di_un_cantiere_non_svuota_la_home(radice):
    client = _client()
    pdf = pdf_con_testo(["x"])
    buono = client.post("/api/lavori", files=[("file", ("b.pdf", pdf, "application/pdf"))]).json()["lavoro"]
    rotto = _cantiere(radice, "20260101-000000-rotto")
    (rotto / "pagine.json").write_text("[{", encoding="utf-8")
    assert [j["lavoro"] for j in client.get("/api/lavori").json()] == [buono]
    # info.json e tentativi.json corrotti non fermano nemmeno lo stato del cantiere stesso
    mezzo = _cantiere(radice, "20260101-000002-mezzo", info="non json")
    (mezzo / "pagine.json").write_text("[]", encoding="utf-8")
    (mezzo / "tentativi.json").write_text('["lista"]', encoding="utf-8")
    assert client.get(f"/api/lavori/{mezzo.name}/stato").json()["nome"] == mezzo.name
    assert lv.tentativi(mezzo) == {}


def test_preferenze_corrotte_tornano_ai_valori_predefiniti(radice):
    path = configurazione.directory() / "preferenze.json"
    path.write_text('"testo"', encoding="utf-8")
    prefs = configurazione.leggi()
    assert prefs["theme"] == "system" and prefs["modello_mistral"] == "" and prefs["host_id"].startswith("urn:uuid:")
    path.write_text('{"theme": 5, "modello_mistral": 7, "reasoning": "x", "model": null, "host_id": 1}', "utf-8")
    prefs = configurazione.leggi()
    assert (prefs["theme"], prefs["modello_mistral"], prefs["reasoning"], prefs["model"]) == ("system", "", "low", "")
    assert isinstance(prefs["host_id"], str)
    path.write_text("{ rotto", encoding="utf-8")
    assert _client().get("/api/impostazioni").status_code == 200


def test_consumi_e_cestino_tollerano_file_corrotti(radice):
    (radice / "consumi.json").write_text("[]", encoding="utf-8")
    assert consumi.totale() == consumi.VUOTO
    (radice / "consumi.json").write_text('{"chiamate": "tre", "ingresso": 7}', encoding="utf-8")
    assert consumi.totale() == {"chiamate": 0, "ingresso": 7, "uscita": 0}
    corrotta = cestino.directory() / "20260101-000000-aaaaaaaaaaaa"
    (corrotta / "contenuto").mkdir(parents=True)
    (corrotta / "voce.json").write_text("{", encoding="utf-8")
    assert cestino.elenco() == []
    assert _client().get("/api/cestino").status_code == 200


def test_tentativi_e_info_scritti_in_modo_atomico(radice, monkeypatch):
    cartella = _cantiere(radice, "20260101-000000-atomico")
    scritture = []
    vero = configurazione.scrivi_json

    def spia(path, value):
        scritture.append(path.name)
        vero(path, value)

    monkeypatch.setattr(lv.configurazione, "scrivi_json", spia)
    lv.segna_tentativi(cartella, ["p0001", "p0001"])
    assert scritture == ["tentativi.json"] and lv.tentativi(cartella) == {"p0001": 2}
    assert not list(cartella.glob("*.tmp"))
