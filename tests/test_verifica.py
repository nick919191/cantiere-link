"""Verifica finale: si ripassano solo le pagine delle voci DA CONFERMARE e MANCANTE, le correzioni passano dal
controllo Python e gli stati li decide di nuovo il motore. Modello finto: nessuna chiamata."""

import json

import pytest
from fascicolo_inventato import certificato, timbro
from fastapi.testclient import TestClient
from test_flusso import _crea_lavoro, _leggi_tutto

from traccia import agente, chatgpt, cli, server, verifica
from traccia import lavoro as lv

CERT_DA_CONFERMARE = "cert5503.pdf"  # due colate per LAMIERA 8: la voce PL8*120/180 è DA CONFERMARE
PROVATE_O_DEDOTTE = {
    "cert777.pdf",
    "cert5502.pdf",
    "cert5505.pdf",
    "cert5506.pdf",
    "ddt200.pdf",
    "ddt500.pdf",
    "ddt600.pdf",
}


def _pronto(radice):
    cartella, schede = _crea_lavoro(radice)
    pagine = _leggi_tutto(cartella, schede)
    cli.componi("prova")
    return cartella, {p["file"].rsplit("/", 1)[-1]: p for p in pagine}


def _risultato(cartella):
    return json.loads((cartella / "uscita" / "risultato.json").read_text(encoding="utf-8"))


def _voce(cartella, nome):
    return next(v for v in _risultato(cartella)["voci"] if v["voce"].startswith(nome))


class Finto:
    """Al posto di chatgpt.response: registra le pagine ricevute e risponde con le correzioni assegnate per pid."""

    def __init__(self, risposte=None):
        self.risposte = risposte or {}
        self.chiamate = []

    def __call__(self, instructions, inputs, model, reasoning, cancelled, consumo=None):
        blocchi = inputs[0]["content"]
        pids = []
        for b in blocchi:
            if b["type"] == "input_text" and b["text"].startswith("{"):
                d = json.loads(b["text"])
                if "pid" in d:
                    pids.append(d["pid"])
        self.chiamate.append(
            {
                "pids": pids,
                "immagini": sum(1 for b in blocchi if b["type"] == "input_image"),
                "istruzioni": instructions,
            }
        )
        if consumo is not None:
            consumo.update(chiamata=True, ingresso=1000, uscita=100)
        return json.dumps({"pagine": {pid: self.risposte.get(pid, {"campi": []}) for pid in pids}})


@pytest.fixture
def modello(monkeypatch):
    finto = Finto()
    monkeypatch.setattr(chatgpt, "response", finto)
    return finto


def test_candidati_solo_pagine_delle_voci_da_confermare_e_mancante(radice):
    cartella, per_file = _pronto(radice)
    r = _risultato(cartella)
    assert r["conteggio"] == {"PROVATO": 1, "DEDOTTO": 3, "DA CONFERMARE": 1, "MANCANTE": 1}
    voci = verifica.candidati(cartella, r, json.loads((cartella / "uscita" / "prove.json").read_text("utf-8")))
    assert {v["stato"] for v in voci} == {"DA CONFERMARE", "MANCANTE"}
    pid_file = {p["pid"]: f for f, p in per_file.items()}
    inviate = {pid_file[pid] for v in voci for pid in v["pagine"]}
    assert inviate == {CERT_DA_CONFERMARE, "ddt300.pdf", "tabella.pdf"}
    assert not inviate & PROVATE_O_DEDOTTE
    assert all(len(v["pagine"]) <= verifica.PAGINE_PER_VOCE for v in voci)
    assert voci[0]["riga"]["motivi"]  # la riga del risultato va al modello: dice già che cosa manca


def test_correzione_accettata_cambia_lo_stato_deciso_dal_motore(radice, modello):
    cartella, per_file = _pronto(radice)
    pid = per_file[CERT_DA_CONFERMARE]["pid"]
    lettura_prima = lv.leggi_lettura(per_file[CERT_DA_CONFERMARE]["impronta"])
    modello.risposte[pid] = {
        "campi": [
            {
                "campo": "testata.numero",
                "esito": "confermato",
                "dopo": "5503",
                "cit": "5503",
                "zona": [10, 10, 100, 30],
            },
            {
                "campo": "righe[1].profilo",
                "esito": "corretto",
                "dopo": "LAMIERA 10x2000x6000",
                "cit": "LAMIERA 10x2000x6000",
                "zona": [100, 500, 400, 520],
                "motivo": "sulla riga 2 lo spessore è 10, non 8",
            },
        ],
        "timbri": [dict(timbro("300"), zona=[600, 50, 950, 120])],
        "aggiunte": "LAMIERA 10x2000x6000\nFORNITORE 001 COPIA CONFORME Rif. Ns. ddt n. 300",
    }
    esito = verifica.esegui(cartella, "modello-test", "")
    assert esito["stato"] == "fatta" and esito["pagine"] == 3 and esito["chiamate"] >= 1
    assert esito["token"] == {"ingresso": 1000 * esito["chiamate"], "uscita": 100 * esito["chiamate"]}
    # al modello vanno solo le pagine candidate, mai quelle PROVATO/DEDOTTO; ogni pagina con la sua immagine
    pid_file = {p["pid"]: f for f, p in per_file.items()}
    ricevute = {pid_file[x] for c in modello.chiamate for x in c["pids"]}
    assert ricevute == {CERT_DA_CONFERMARE, "ddt300.pdf", "tabella.pdf"}
    assert all(c["immagini"] >= len(c["pids"]) for c in modello.chiamate)
    assert all("non decidi lo stato" in c["istruzioni"].lower() for c in modello.chiamate)
    # gli stati li ha rifatti il motore: la voce con il certificato corretto e timbrato è PROVATO
    r = _risultato(cartella)
    assert _voce(cartella, "PL8")["stato"] == "PROVATO"
    assert r["conteggio"] == {"PROVATO": 2, "DEDOTTO": 3, "DA CONFERMARE": 0, "MANCANTE": 1}
    assert esito["conteggio_prima"]["DA CONFERMARE"] == 1 and esito["conteggio_dopo"] == r["conteggio"]
    # prima / dopo per campo, con pagina e citazione
    campo = next(c for c in esito["campi"] if c["campo"] == "righe[1].profilo")
    assert campo["prima"] == "LAMIERA 8x2000x6000" and campo["dopo"] == "LAMIERA 10x2000x6000"
    assert campo["esito"] == "corretto" and campo["pid"] == pid and campo["file"].endswith(CERT_DA_CONFERMARE)
    assert any(c["campo"] == "timbri" and c["esito"] == "corretto" for c in esito["campi"])
    # la lettura originale è intatta; la scheda della pagina è quella verificata, con le prove che la citano
    assert lv.leggi_lettura(per_file[CERT_DA_CONFERMARE]["impronta"]) == lettura_prima
    s = lv.scheda_pagina(per_file[CERT_DA_CONFERMARE])
    assert s["verifica"]["campi"] and s["righe"][1]["profilo"]["v"] == "LAMIERA 10x2000x6000"
    assert s["timbri"][0]["ddt_citato"] == "300" and s["agente"].startswith("ChatGPT · verifica")
    prove = json.loads((cartella / "uscita" / "prove.json").read_text(encoding="utf-8"))
    assert any(
        f["pid"] == pid and "ddt n. 300" in f["valore"] for f in prove["fonti"].values()
    )  # il timbro Ã¨ una prova
    assert (cartella / "verifica.json").exists() and lv.stato(cartella)["fase"] == "pronto"
    assert list((radice / "archivio" / "verifiche").glob("*.json"))


def test_seconda_passata_senza_chiamate(radice, modello):
    cartella, _ = _pronto(radice)
    primo = verifica.esegui(cartella, "modello-test", "")
    assert primo["pagine"] == 3 and modello.chiamate
    modello.chiamate.clear()
    secondo = verifica.esegui(cartella, "modello-test", "")
    assert secondo["pagine"] == 0 and secondo["pagine_gia_verificate"] == 3 and not modello.chiamate
    assert lv.stato(cartella)["fase"] == "pronto"


def test_correzione_senza_citazione_sulla_pagina_viene_scartata(radice, modello):
    cartella, per_file = _pronto(radice)
    pid = per_file[CERT_DA_CONFERMARE]["pid"]
    modello.risposte[pid] = {
        "campi": [{"campo": "righe[0].colata", "esito": "corretto", "dopo": "H9999", "cit": "H9999", "zona": []}]
    }
    esito = verifica.esegui(cartella, "modello-test", "")
    campo = next(c for c in esito["campi"] if c["campo"] == "righe[0].colata")
    assert campo["esito"] == "scartata dal controllo"
    s = lv.scheda_pagina(per_file[CERT_DA_CONFERMARE])
    assert s["righe"][0]["colata"]["v"] == "H3003" and any("controllo" in a for a in s["avvisi"])
    assert _voce(cartella, "PL8")["stato"] == "DA CONFERMARE"


def test_valore_inventato_dalla_lettura_si_toglie(radice, modello):
    cartella, per_file = _pronto(radice)
    pid = per_file[CERT_DA_CONFERMARE]["pid"]
    modello.risposte[pid] = {"campi": [{"campo": "righe[1].colata", "esito": "assente", "dopo": "", "cit": ""}]}
    verifica.esegui(cartella, "modello-test", "")
    s = lv.scheda_pagina(per_file[CERT_DA_CONFERMARE])
    assert s["righe"][1]["colata"]["v"] == "" and s["righe"][0]["colata"]["v"] == "H3003"
    assert _voce(cartella, "PL8")["stato"] == "DEDOTTO"  # una colata sola, senza timbro


def test_pagina_non_letta_riceve_una_scheda_intera(radice, modello):
    cartella, schede = _crea_lavoro(radice)
    cli.prepara_lavoro("prova")
    pagine = lv.pagine(cartella)
    da_saltare = next(p for p in pagine if p["file"].endswith(CERT_DA_CONFERMARE))
    for p in pagine:
        if p["pid"] == da_saltare["pid"]:
            continue
        nome = p["file"].rsplit("/", 1)[-1]
        s = next(
            s
            for (file, _, _s), s in zip(__import__("fascicolo_inventato").fascicolo(), schede, strict=True)
            if file == nome
        )
        lv.salva_lettura(p["impronta"], s)
    lv.segna_tentativi(cartella, [da_saltare["pid"]] * lv.MAX_TENTATIVI)
    assert lv.stato(cartella)["non_lette"] == [da_saltare["pid"]]
    cli.componi("prova")
    modello.risposte[da_saltare["pid"]] = {
        "scheda": certificato("5503", [("LAMIERA 8x2000x6000", "S355J2+N", "H3003")], [timbro("300")])
    }
    esito = verifica.esegui(cartella, "modello-test", "")
    assert da_saltare["pid"] in {x for c in modello.chiamate for x in c["pids"]}
    assert lv.stato(cartella)["non_lette"] == [] and lv.stato(cartella)["lette"] == len(pagine)
    assert _voce(cartella, "PL8")["stato"] == "PROVATO"
    assert any(c["pid"] == da_saltare["pid"] and c["campo"] == "scheda" for c in esito["campi"])


def test_cantiere_demo_senza_chiamate_non_si_verifica(radice, modello):
    cartella, _ = _pronto(radice)
    info = json.loads((cartella / "info.json").read_text(encoding="utf-8")) if (cartella / "info.json").exists() else {}
    (cartella / "info.json").write_text(json.dumps(info | {"demo_locale": True}), encoding="utf-8")
    assert verifica.esegui(cartella, "modello-test", "") is None and not modello.chiamate


def test_ferma_interrompe_senza_salvare_altro(radice, modello):
    cartella, _ = _pronto(radice)
    agente._cancel.set()
    try:
        with pytest.raises(chatgpt.AgentError):
            verifica.esegui(cartella, "modello-test", "")
    finally:
        agente._cancel.clear()
    assert not modello.chiamate
    assert json.loads((cartella / "verifica.json").read_text(encoding="utf-8"))["stato"] == "interrotta"


def test_endpoint_e_stato(radice, modello):
    cartella, _ = _pronto(radice)
    client = TestClient(server.app)
    assert client.get("/api/lavori/prova/verifica").status_code == 404
    prima = client.get("/api/lavori/prova/stato").json()["verifica"]
    assert prima["stato"] == "" and prima["da_fare"] is True
    verifica.esegui(cartella, "modello-test", "")
    r = client.get("/api/lavori/prova/verifica").json()
    assert r["stato"] == "fatta" and r["pagine"] == 3 and "campi" in r and "conteggio_dopo" in r
    s = client.get("/api/lavori/prova/stato").json()["verifica"]
    assert s["stato"] == "fatta" and s["da_fare"] is False and s["pagine"] == 3


def test_la_verifica_parte_dopo_una_lettura_o_su_richiesta_non_a_una_ricomposizione(radice, monkeypatch):
    """Un cantiere già pronto ricomposto (motore nuovo) non spende: la verifica parte solo con il pulsante."""
    cartella, _ = _pronto(radice)
    chiamate = []
    monkeypatch.setattr(verifica, "esegui", lambda c, m, e: chiamate.append(c.name))
    monkeypatch.setattr(chatgpt, "response", Finto())
    agente._cancel.clear()
    agente.analizza(cartella, "modello-test", "")  # niente da leggere, nessuna richiesta esplicita
    assert chiamate == []
    agente.analizza(cartella, "modello-test", "", verifica=True)  # pulsante «Verifica finale»
    assert chiamate == ["prova"]
