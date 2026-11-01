import collections
import copy
import io
import json
import zipfile
from pathlib import Path

import pytest
from fascicolo_inventato import fascicolo, scheda, timbro
from fastapi.testclient import TestClient
from pdf_minimo import pdf_con_testo
from test_flusso import _crea_lavoro

from traccia import agente, chatgpt, normalizza, server
from traccia import lavoro as lv
from traccia.controlli import valida
from traccia.motore import elabora
from traccia.preparazione import _estrai_zip
from traccia.prove import costruisci


def test_aziende_con_prima_parola_comune_non_coincidono():
    assert not normalizza.aziende("Costruzioni 001 SRL") & normalizza.aziende("Costruzioni 002 SRL")
    assert normalizza.aziende("Produttore 001 S.p.A.") == normalizza.aziende("PRODUTTORE 001 SPA")


def test_timbro_senza_riscontro_non_valido():
    s = scheda("certificato_31")
    s["timbri"] = [timbro("12345")]
    assert any("trascrizione" in e for e in valida(s))


def test_lettura_incompleta_non_dichiara_assenze():
    items = fascicolo()
    pages = [{"pid": f"p{i:04}", "file": name, "pagina": n} for i, (name, n, _) in enumerate(items, 1)]
    schemas = {p["pid"]: s for p, (_, _, s) in zip(pages, items, strict=True)}
    missing = next(p["pid"] for p in pages if "cert777" in p["file"])
    del schemas[missing]
    result = elabora(costruisci(pages, schemas))
    assert result["voci"] and all(v["stato"] == "DA CONFERMARE" for v in result["voci"])


def test_origine_e_token_locale_obbligatori(radice):
    client = TestClient(server.app)
    assert client.post("/api/agente/interrompi").status_code == 403
    token = client.get("/api/sessione").json()["token"]
    assert (
        client.post(
            "/api/agente/interrompi", headers={"X-Traccia-Token": token, "Origin": "https://other.invalid"}
        ).status_code
        == 403
    )
    assert client.get("/api/sessione", headers={"Host": "other.invalid"}).status_code == 403
    assert client.post("/api/agente/interrompi", headers={"X-Traccia-Token": token}).status_code == 200


def test_upload_nomi_duplicati_non_sovrascrive(radice, monkeypatch):
    monkeypatch.setattr(server, "prepara", lambda *_args, **_kwargs: [])
    client = TestClient(server.app)
    client.headers["X-Traccia-Token"] = client.get("/api/sessione").json()["token"]
    pdf = pdf_con_testo(["esempio"])
    response = client.post("/api/lavori", files=[("file", ("a.pdf", pdf)), ("file", ("a.pdf", pdf + b"\n"))])
    assert response.status_code == 200
    data = response.json()
    assert len(set(data["accettati"])) == 2
    assert len(list((radice / "lavori" / data["lavoro"] / "ingresso").iterdir())) == 2


def test_zip_limiti_e_percorsi(tmp_path, monkeypatch):
    from traccia import preparazione

    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../escape.pdf", b"x")
        z.writestr("ok.pdf", b"12345")
    _estrai_zip(archive, tmp_path / "out")
    assert not (tmp_path / "escape.pdf").exists()
    monkeypatch.setattr(preparazione, "MAX_BYTE_ZIP", 2)
    with pytest.raises(ValueError, match="limiti"):
        _estrai_zip(archive, tmp_path / "small")
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w") as z:
        z.writestr("a.pdf", b"x")
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("nested.zip", nested.getvalue())
    monkeypatch.setattr(preparazione, "MAX_BYTE_ZIP", 1_000_000)
    monkeypatch.setattr(preparazione, "MAX_PROFONDITA_ZIP", 0)
    with pytest.raises(ValueError, match="annidati"):
        _estrai_zip(archive, tmp_path / "deep")


def test_agente_pipeline_senza_chiamate_reali(radice, monkeypatch):
    directory, _ = _crea_lavoro(radice)
    records = {name: schema for name, _, schema in fascicolo()}
    calls = []

    def respond(instructions, inputs, *_args):
        assert "schede" in instructions
        schede = {}
        for item in inputs[0]["content"]:
            if item["type"] == "input_text":
                context = json.loads(item["text"])
                name = context["file"].rsplit("/", 1)[-1]
                calls.append(name)
                schede[context["pid"]] = copy.deepcopy(records[name])
        return json.dumps({"schede": schede})

    monkeypatch.setattr(chatgpt, "response", respond)
    agente._cancel.clear()
    agente.analizza(directory, "test-model", "")
    assert sorted(calls) == sorted(records)
    assert (directory / "uscita" / "tracciabilita.xlsx").exists()
    agente.analizza(directory, "test-model", "")
    assert len(calls) == len(records), "accepted pages must not be requested again"
    assert len(list((directory / "versioni").iterdir())) == 1


def test_lotto_con_scheda_mancante_segnala_solo_quella_pagina(radice, monkeypatch):
    directory, _ = _crea_lavoro(radice)
    records = {name: schema for name, _, schema in fascicolo()}
    richieste = []

    def respond(_instructions, inputs, *_args):
        schede = {}
        for item in inputs[0]["content"]:
            if item["type"] == "input_text":
                context = json.loads(item["text"])
                name = context["file"].rsplit("/", 1)[-1]
                richieste.append(name)
                if name != "ddt300.pdf":
                    schede[context["pid"]] = copy.deepcopy(records[name])
        return json.dumps({"schede": schede})

    monkeypatch.setattr(chatgpt, "response", respond)
    agente._cancel.clear()
    with pytest.raises(chatgpt.AgentError, match=r"Lette 11 pagine su 12.*1 da rileggere \(ddt300\.pdf\)"):
        agente.analizza(directory, "test-model", "")
    stato = lv.stato(directory)
    assert stato["lette"] == len(records) - 1 and stato["da_leggere"] == 1
    # secondo tentativo automatico: solo la pagina rifiutata viene richiesta di nuovo
    assert richieste.count("ddt300.pdf") == 2 and richieste.count("ddt200.pdf") == 1
    assert json.loads((directory / "tentativi.json").read_text(encoding="utf-8"))["p0007"] == 2


def test_secondo_tentativo_recupera_la_pagina(radice, monkeypatch):
    directory, _ = _crea_lavoro(radice)
    records = {name: schema for name, _, schema in fascicolo()}
    visti = collections.Counter()

    def respond(_instructions, inputs, *_args):
        schede = {}
        for item in inputs[0]["content"]:
            if item["type"] == "input_text":
                context = json.loads(item["text"])
                name = context["file"].rsplit("/", 1)[-1]
                visti[name] += 1
                if name == "ddt300.pdf" and visti[name] == 1:
                    continue  # la prima volta la scheda manca
                schede[context["pid"]] = copy.deepcopy(records[name])
        return json.dumps({"schede": schede})

    monkeypatch.setattr(chatgpt, "response", respond)
    agente._cancel.clear()
    agente.analizza(directory, "test-model", "")
    assert lv.stato(directory)["fase"] == "pronto" and visti["ddt300.pdf"] == 2


def test_agente_legge_le_pagine_in_parallelo(radice, monkeypatch):
    import threading
    import time

    directory, _ = _crea_lavoro(radice)
    records = {name: schema for name, _, schema in fascicolo()}
    attivi, picco, lock = [0], [0], threading.Lock()

    def respond(_instructions, inputs, *_args):
        with lock:
            attivi[0] += 1
            picco[0] = max(picco[0], attivi[0])
        time.sleep(0.6)  # più del tempo per preparare un lotto anche a computer carico
        with lock:
            attivi[0] -= 1
        schede = {}
        for item in inputs[0]["content"]:
            if item["type"] == "input_text":
                context = json.loads(item["text"])
                schede[context["pid"]] = copy.deepcopy(records[context["file"].rsplit("/", 1)[-1]])
        return json.dumps({"schede": schede})

    monkeypatch.setattr(agente, "PAGINE_PER_LOTTO", 2)
    monkeypatch.setattr(chatgpt, "response", respond)
    agente._cancel.clear()
    agente.analizza(directory, "test-model", "")
    assert picco[0] == min(agente.PAGINE_IN_PARALLELO, -(-len(records) // 2))
    assert lv.stato(directory)["fase"] == "pronto"
    tentativi = json.loads((directory / "tentativi.json").read_text(encoding="utf-8"))
    assert len(tentativi) == len(records) and set(tentativi.values()) == {1}


def test_interruzione_ferma_le_pagine_non_iniziate(radice, monkeypatch):
    directory, _ = _crea_lavoro(radice)
    calls = []

    def respond(*_args):
        calls.append(1)
        agente._cancel.set()
        raise chatgpt.AgentError("Operazione interrotta.")

    monkeypatch.setattr(chatgpt, "response", respond)
    agente._cancel.clear()
    with pytest.raises(chatgpt.AgentError):
        agente.analizza(directory, "test-model", "")
    assert len(calls) <= agente.PAGINE_IN_PARALLELO


def test_same_number_documents_require_unambiguous_identity():
    from test_motore import _risultato, _voce

    from traccia.motore import Motore

    proofs, _ = _risultato()
    engine = Motore(proofs)
    doc = proofs["ddt"][0]
    voice = {"ddt": doc["numero"], "fornito_da": "FORNITORE 999 SRL"}
    assert engine.ddt_di(voice) is None
    voice["fornito_da"] = doc["emittente"]
    proofs["ddt"].append(copy.deepcopy(doc))
    assert Motore(proofs).ddt_di(voice) is None
    proofs, _ = _risultato()
    certificate = next(c for c in proofs["certificati"] if c["numero"] == "99-777")
    proofs["certificati"].append(copy.deepcopy(certificate) | {"emittente": "PRODUTTORE 999 SPA"})
    assert _voce(elabora(proofs), "HEB 180")["stato"] == "DA CONFERMARE"


def test_letter_same_file_requires_explicit_certificate_reference():
    from test_motore import _risultato

    from traccia.motore import Motore

    proofs, _ = _risultato()
    certificate = next(c for c in proofs["certificati"] if c["numero"] == "99-777")
    certificate["timbri"] = []
    pid = certificate["pagine"][0]
    proofs["lettere"] = [{"ddt_citato": "200", "pid": pid, "certificati": ["unrelated"]}]
    assert Motore(proofs).ponti(certificate, "200") == []
    proofs["lettere"][0]["certificati"] = ["99-777"]
    assert len(Motore(proofs).ponti(certificate, "200")) == 1


# ---------- fascicolo reale anonimizzato (Codogno, letture 0.5.1) ----------
def _codogno(con_non_lette=True):
    """Prove del fascicolo reale: le 10 pagine non lette dall'app (DDT, lettera, lista, DoP, albaranes) restano non
    lette come nel lavoro vero; con `con_non_lette=False` si tolgono dall'elenco, come se la lettura fosse completa."""
    dati = json.loads((Path(__file__).parent / "dati" / "codogno.json").read_text(encoding="utf-8"))
    pagine = [p for p in dati["pagine"] if con_non_lette or p["pid"] in dati["schede"]]
    prove = costruisci(pagine, dati["schede"], dati["mappe"])
    return prove, elabora(prove)


def test_codogno_ruoli_e_perimetro_dei_ddt():
    prove, _ = _codogno()
    assert "COSTR" in prove["costruttore"].upper()
    tipi = {d["numero"]: d["tipo"] for d in prove["ddt"]}
    assert tipi["8027"] == tipi["602"] == tipi["2902"] == tipi["G02 / 51159"] == "commerciante_costruttore"
    assert tipi["0000587"] == "costruttore_terzista" and tipi["5.877"] == "terzista_cantiere"
    assert len(prove["ddt"]) == 6  # le due copie del DDT 2902 ('LAMIX S.P.A.' e 'LAMIXS.P.A.') sono un DDT solo
    ddt_2902 = next(d for d in prove["ddt"] if d["numero"] == "2902")
    assert ddt_2902["copie"] == 2 and len(ddt_2902["pagine"]) == 2
    ddt_8027 = next(d for d in prove["ddt"] if d["numero"] == "8027")
    assert "p0003" in ddt_8027["pagine"]  # pagina 2 letta '2027': stesso DDT, con avviso
    assert any("2027" in a for a in ddt_8027["avvisi"])
    assert [d["numero_dop"] for d in prove["dop_fornitore_intermedio"]] == ["9588 .25"]


def test_codogno_voci_con_certificato_e_colata():
    _, r = _codogno()
    voci = r["voci"]
    con_colata = [v for v in voci if v["colonne"]["COLATA"]["v"]]
    con_cert = [v for v in voci if "del" in v["colonne"]["CERT 3.1 ACCIAIERIA"]["v"]]
    assert len(con_cert) >= 9 and len(con_colata) >= 9
    assert not [v for v in voci if "TUBO 12x2450" in v["voce"]]
    assert not [v for v in voci if "5.877" in v["colonne"]["DDT COMMERCIANTE"]["v"]]  # niente voci dal reso
    assert not [v for v in voci if "ZINCOLUX" in v["colonne"]["COMMERCIANTE / CENTRO TRASF."]["v"].upper()]
    ddt_usati = {v["colonne"]["DDT COMMERCIANTE"]["v"].split(" del")[0] for v in voci}
    assert {"DDT n. 602", "DDT n. 2902", "DDT n. G02 / 51159", "DDT n. 8027"} <= ddt_usati
    # lamiere con la colata dichiarata sul DDT, una voce per colata, placche in nota
    lamiere = [v for v in voci if v["voce"].startswith("LAMIERA 15 · colata")]
    assert {v["colonne"]["COLATA"]["v"] for v in lamiere} == {"143343", "442770", "339044"}
    assert all(any("Placche dichiarate" in n for n in v["note"]) for v in lamiere)
    # DDT COSTRUTTORE: al terzista (zincatura) e reso al cantiere
    colonna = voci[0]["colonne"]["DDT COSTRUTTORE"]["v"]
    assert "DDT n. 0000587" in colonna and "tramite" in colonna and "5.877" in colonna
    # DoP EN 1090 del fornitore intermedio nelle voci del suo DDT
    hea = next(v for v in voci if v["voce"] == "HEA 160")
    assert hea["colonne"]["CE/DoP CENTRO"]["v"].startswith("DoP EN 1090 9588")
    # certificato con timbro che cita un DDT assente: voce da confermare con la richiesta del DDT
    tubo = next(v for v in voci if v["voce"].startswith("TUBO 219.1"))
    assert tubo["stato"] == "DA CONFERMARE" and tubo["richieste"] == ["DDT 6559 di F.LLI MONTANI s.p.a."]


def test_codogno_tetto_non_letto_solo_finche_restano_pagine_della_catena():
    _, r = _codogno()
    assert r["conteggio"]["PROVATO"] == 0  # un DDT e una lista non letti nello stesso file: esito provvisorio
    assert all(any("non letto completamente" in a for a in v["avvisi"]) for v in r["voci"])
    _, r = _codogno(con_non_lette=False)
    assert r["conteggio"]["PROVATO"] >= 9  # senza il tetto: le lamiere con colata e timbro sono provate
    per_stato = {v["voce"]: v["stato"] for v in r["voci"]}
    assert per_stato["LAMIERA 12 · colata 2458653"] == "PROVATO"
    assert per_stato["HEA 160"] == "DA CONFERMARE"  # due colate, segno a mano non letto nella 0.5.1
