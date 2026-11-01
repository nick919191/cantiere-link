"""Lettura veloce: coltellino, scheda compatta, qualità, campi chiave, flusso con ChatGPT e Mistral finti."""

import json

from traccia import coltellino, veloce
from traccia.controlli import valida


def test_coltellino_toglie_il_modulo_e_tiene_i_valori():
    testo = "\n".join(
        [
            "Tel. +39 045 7900911 - fax 045 6300376",
            "CONDIZIONI DI VENDITA il materiale fornito prima di essere lavorato deve essere controllato dal "
            "ricevente sotto la propria responsabilita e non si accettano reclami dopo la lavorazione del materiale "
            "ne per differenze di peso se non contestate al trasportatore al momento della consegna",
            "| HEA 120 | S275J0 +AR | 148423A | 0,08 | 0,63 | 0,010 | 7.110 |",
            "| HEA 120 | S275J0 +AR | 148423A | 0,08 | 0,63 | 0,010 | 7.110 |",
            "1. 2. 3. 4. 5. 6. 7. 8. 9. 10.",
            "Norma armonizzata EN 10025-1:2004",
        ]
    )
    tagliato = coltellino.taglia(testo, "certificato_31")
    assert "Tel." not in tagliato and "CONDIZIONI" not in tagliato and "1. 2. 3." not in tagliato
    assert "0,08" not in tagliato and "0,010" not in tagliato
    assert tagliato.count("148423A") == 2  # righe di prodotto uguali restano due righe
    assert "7.110" in tagliato and "EN 10025-1" in tagliato


def test_coltellino_annotazioni_ripetute_una_volta():
    caption = '{"box_2d": [1, 2, 3, 4], "label": "text", "caption": "DDT n. 4563 del 20/05/2026"}'
    tagliato = coltellino.taglia("| FIRMA |[" + ", ".join([caption] * 50) + "]", "ddt")
    assert tagliato.count("4563") == 1


def test_coltellino_impara_solo_frasi_senza_valori(radice):
    frase = "La prestazione del prodotto sopra identificato è conforme alle prestazioni dichiarate"
    pagine = [
        {"testo": f"{frase}\nMarchio Acme", "documento": f"d{i}", "emittente": f"e{i % 2}", "valori": ["X1"]}
        for i in range(4)
    ]
    coltellino.impara(pagine)
    diz = coltellino.dizionario()
    assert coltellino.forma(frase) in diz
    assert coltellino.forma("Marchio Acme") not in diz  # riga breve: resta


def test_scheda_compatta_si_espande_e_passa_i_controlli():
    testo = "INSPECTION CERTIFICATE 3.1\nNumero: 9279 del 5/12/24\n| HEA 120 | S275JO +AR | No. 148423A |"
    compatta = {
        "famiglia": "certificato_31",
        "motivo": "certificato 3.1",
        "testata": {"numero": "9279", "data": "5/12/24", "tipo_materiale": "profilati_lamiere_tubi"},
        "righe": [{"profilo": "HEA 120", "qualita": "S275JO +AR", "colata": ["148423A", "No. 148423A"]}],
    }
    s = veloce.espandi(compatta)
    assert s["righe"][0]["qualita"]["v"] == "S275J0 +AR"  # O/0 corretto dal programma, con avviso
    assert any("qualità corretta" in a for a in s["avvisi"])
    s["trascrizione"] = (testo + "\n" + s["trascrizione"]).strip()
    assert valida(s, "") == []
    assert veloce.mancanti(s, prima_del_file=True) == ["testata.produttore"]


def test_qualita_5_e_o():
    assert veloce._qualita_corretta("5275") == "S275"
    assert veloce._qualita_corretta("S275 grado: JR,JO,J2") == "S275 grado: JR,J0,J2"
    assert veloce._qualita_corretta("1.5275") == "1.5275"


def test_famiglia_probabile():
    assert veloce.famiglia_probabile("INSPECTION CERTIFICATE EN 10204 3.1 heat") == "certificato_31"
    assert veloce.famiglia_probabile("Documento di trasporto D.P.R. 472/96 causale vettore") == "ddt"
    assert veloce.famiglia_probabile("testo qualsiasi") is None


def test_zone_dai_blocchi():
    s = veloce.espandi({"famiglia": "ddt", "testata": {"numero": "4563"}})
    blocchi = [
        {
            "content": "tutta la pagina DDT 4563",
            "top_left_x": 0,
            "top_left_y": 0,
            "bottom_right_x": 1000,
            "bottom_right_y": 1000,
        },
        {"content": "DDT n. 4563", "top_left_x": 100, "top_left_y": 50, "bottom_right_x": 300, "bottom_right_y": 80},
    ]
    veloce.zone_dai_blocchi(s, blocchi, 1000, 1000)
    assert s["testata"]["numero"]["zona"] == [100, 50, 300, 80]  # il blocco più piccolo


def test_flusso_veloce_con_servizi_finti(radice, monkeypatch):
    """Una pagina scansionata: OCR finto, una lettura dal testo, nessun dubbio, scheda salvata in archivio."""
    from PIL import Image

    from traccia import agente, ocr, percorsi
    from traccia import lavoro as lv

    cartella = percorsi.lavori() / "veloce-prova"
    (cartella / "pagine").mkdir(parents=True)
    Image.new("RGB", (100, 140), "white").save(cartella / "pagine" / "p0001.png")
    info = {
        "pid": "p0001",
        "file": "ddt.pdf",
        "pagina": 1,
        "pagine_file": 1,
        "impronta": "abc123",
        "bianca": False,
        "larghezza": 100,
        "altezza": 140,
        "testo_nativo": "",
        "parole": [],
    }
    (cartella / "pagine" / "p0001.json").write_text(json.dumps(info), encoding="utf-8")
    (cartella / "pagine.json").write_text(
        json.dumps([{k: info[k] for k in ("pid", "file", "pagina", "pagine_file", "impronta", "bianca")}]),
        encoding="utf-8",
    )
    testo = (
        "DOCUMENTO DI TRASPORTO D.P.R. 472/96 causale vendita vettore\nEmittente: ACME SPA\n"
        "DDT n. 4563 del 20/05/2026\n| TRAVE HEA 140 | S275J0 | 120 KG |\n"
        + "".join(f"| ARTICOLO {i} | TUBO 40x40x{i} | S235JR | {i}0 KG |\n" for i in range(2, 9))
    )
    monkeypatch.setattr(ocr, "client", lambda: _Nulla())
    monkeypatch.setattr(ocr, "leggi", lambda png, impronta, client: {"testo": testo, "incerte": [], "blocchi": []})
    risposta = {
        "schede": {
            "p0001": {
                "famiglia": "ddt",
                "motivo": "DDT",
                "testata": {
                    "emittente": "ACME SPA",
                    "numero": "4563",
                    "data": "20/05/2026",
                    "tipo_proposto": "commerciante_costruttore",
                },
                "righe": [
                    {"descrizione": "TRAVE HEA 140", "profilo": "HEA 140", "qualita": "S275J0", "servizio": "no"}
                ],
            }
        }
    }
    chiamate = []
    monkeypatch.setattr(agente, "_chiama", lambda *a: chiamate.append(a) or json.dumps(risposta))
    monkeypatch.setattr(veloce.agente, "componi", lambda c: None)
    agente._cancel.clear()
    veloce.analizza(cartella, "modello", "low")
    scheda = lv.scheda_pagina(lv.pagine(cartella)[0])
    assert scheda and scheda["testata"]["numero"]["v"] == "4563"
    assert len(chiamate) == 1  # nessun dubbio: nessuna verifica con immagine
    assert "DOCUMENTO DI TRASPORTO" in scheda["trascrizione"]  # la ricerca ritrova il testo della pagina


class _Nulla:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _lavoro_una_pagina(radice, testo_nativo=""):
    from PIL import Image

    from traccia import percorsi

    cartella = percorsi.lavori() / "veloce-prova"
    (cartella / "pagine").mkdir(parents=True)
    Image.new("RGB", (100, 140), "white").save(cartella / "pagine" / "p0001.png")
    info = {
        "pid": "p0001",
        "file": "ddt.pdf",
        "pagina": 1,
        "pagine_file": 1,
        "impronta": "abc123",
        "bianca": False,
        "larghezza": 100,
        "altezza": 140,
        "testo_nativo": testo_nativo,
        "parole": [],
    }
    (cartella / "pagine" / "p0001.json").write_text(json.dumps(info), encoding="utf-8")
    (cartella / "pagine.json").write_text(
        json.dumps([{k: info[k] for k in ("pid", "file", "pagina", "pagine_file", "impronta", "bianca")}]),
        encoding="utf-8",
    )
    return cartella


_TESTO_DDT = (
    "DOCUMENTO DI TRASPORTO D.P.R. 472/96 causale vendita vettore\nEmittente: ACME SPA\n"
    "DDT n. 4563 del 20/05/2026\nCUP: D75E23000000001\n| TRAVE HEA 140 | S275J0 | 120 KG |\n"
    + "".join(f"| ARTICOLO {i} | TUBO 40x40x{i} | S235JR | {i}0 KG |\n" for i in range(2, 9))
)
_SCHEDA_DDT = {
    "famiglia": "ddt",
    "motivo": "DDT",
    "testata": {
        "emittente": "ACME SPA",
        "numero": "4563",
        "data": "20/05/2026",
        "tipo_proposto": "commerciante_costruttore",
    },
    "righe": [{"descrizione": "TRAVE HEA 140", "profilo": "HEA 140", "qualita": "S275J0", "servizio": "no"}],
}


def _servizi_finti(monkeypatch, risposte):
    from traccia import agente, ocr

    monkeypatch.setattr(ocr, "client", lambda: _Nulla())
    monkeypatch.setattr(ocr, "leggi", lambda png, impronta, client: {"testo": _TESTO_DDT, "incerte": [], "blocchi": []})
    chiamate = []

    def chiama(cartella, istruzioni, messaggi, model, effort):
        chiamate.append((istruzioni, messaggi))
        return json.dumps(risposte[min(len(chiamate), len(risposte)) - 1])

    monkeypatch.setattr(agente, "_chiama", chiama)
    monkeypatch.setattr(veloce.agente, "componi", lambda c: None)
    agente._cancel.clear()
    return chiamate


def test_riferimento_con_tipo_sconosciuto_non_fa_scartare_la_pagina(radice, monkeypatch):
    """C3: prima la pagina era rifiutata 4 volte per `riferimenti[0].tipo = "cup"`; ora entra con un avviso."""
    from traccia import lavoro as lv

    cartella = _lavoro_una_pagina(radice)
    risposta = {"schede": {"p0001": {**_SCHEDA_DDT, "riferimenti": [["cup", "D75E23000000001"]]}}}
    chiamate = _servizi_finti(monkeypatch, [risposta])
    veloce.analizza(cartella, "modello", "low")
    scheda = lv.scheda_pagina(lv.pagine(cartella)[0])
    assert scheda and scheda["testata"]["numero"]["v"] == "4563" and not scheda.get("parziale")
    assert [r["tipo"] for r in scheda["riferimenti"]] == ["altro"]
    assert sum("altro" in a for a in scheda["avvisi"]) == 1
    assert len(chiamate) == 1  # nessuna verifica con immagine: il tipo sconosciuto non è un errore


def test_citazione_non_trovata_svuota_il_campo_e_la_pagina_resta(radice, monkeypatch):
    from traccia import lavoro as lv

    cartella = _lavoro_una_pagina(radice)
    sbagliata = {**_SCHEDA_DDT, "testata": {**_SCHEDA_DDT["testata"], "ordine": ["77", "ordine inventato 77"]}}
    chiamate = _servizi_finti(monkeypatch, [{"schede": {"p0001": sbagliata}}, {"correzioni": {}}])
    veloce.analizza(cartella, "modello", "low")
    scheda = lv.scheda_pagina(lv.pagine(cartella)[0])
    assert len(chiamate) == 2  # l'errore di campo va prima alla verifica con immagine
    assert scheda["testata"]["numero"]["v"] == "4563" and scheda["testata"]["ordine"]["v"] == ""
    assert any(a.startswith("valore scartato") and "ordine" in a for a in scheda["avvisi"])


def test_terzo_tentativo_pagina_intera_con_le_istruzioni_della_famiglia(radice, monkeypatch):
    from traccia import lavoro as lv

    cartella = _lavoro_una_pagina(radice)
    (cartella / "tentativi.json").write_text(json.dumps({"p0001": 2}), encoding="utf-8")
    chiamate = _servizi_finti(monkeypatch, [{"schede": {"p0001": _SCHEDA_DDT}}, {"schede": {"p0001": _SCHEDA_DDT}}])
    veloce.analizza(cartella, "modello", "low")
    assert len(chiamate) == 2
    istruzioni, messaggi = chiamate[1]
    contenuto = messaggi[0]["content"]
    testo = json.loads(contenuto[0]["text"])
    assert testo["rileggi"] is True and any("tutta la pagina" in m for _, _, m in testo["dubbi"])
    assert contenuto[1]["type"] == "input_image"
    assert "# ddt" in istruzioni and "# certificato_31" not in istruzioni  # solo la famiglia letta finora
    assert lv.scheda_pagina(lv.pagine(cartella)[0])["testata"]["numero"]["v"] == "4563"


def test_scheda_parziale_vale_finche_non_arriva_quella_completa(radice):
    from traccia import lavoro as lv

    cartella = _lavoro_una_pagina(radice)
    pagina = lv.pagine(cartella)[0]
    letta = {**veloce.espandi(_SCHEDA_DDT), "trascrizione": _TESTO_DDT}
    p = veloce.parziale(letta, ["righe[0]: servono esattamente i campi"])
    assert p["parziale"] is True and p["righe"] == [] and p["testata"]["numero"]["v"] == "4563"
    assert any(a.startswith("scheda parziale") for a in p["avvisi"])
    assert veloce.parziale({"famiglia": "fattura"}, ["x"]) is None

    lv.salva_lettura(pagina["impronta"], p)
    assert lv.scheda_pagina(pagina)["parziale"] and not lv.completa(pagina)
    stato = lv.stato(cartella)
    assert stato["da_leggere"] == 1 and stato["lette"] == 0  # si ritenta finché ci sono tentativi
    impronta_prima = lv.impronta_letture(cartella)
    (cartella / "tentativi.json").write_text(json.dumps({"p0001": lv.MAX_TENTATIVI}), encoding="utf-8")
    stato = lv.stato(cartella)
    assert stato["lette"] == 1 and stato["pagine"][0]["parziale"] is True and not stato["non_lette"]
    (cartella / "tentativi.json").unlink()
    lv.salva_lettura(pagina["impronta"], veloce.espandi(_SCHEDA_DDT))
    assert lv.completa(pagina) and not lv.scheda_pagina(pagina).get("parziale")
    assert lv.impronta_letture(cartella) != impronta_prima
    assert lv.stato(cartella)["lette"] == 1


def test_piu_colate_per_profilo_chiede_i_segni_con_la_pagina_intera(radice, monkeypatch):
    """C7: certificato con due colate dello stesso profilo -> dubbio «segni» con l'immagine intera; la risposta
    con i segni entra nella scheda."""
    from traccia import lavoro as lv

    cartella = _lavoro_una_pagina(radice)
    testo = (
        "INSPECTION CERTIFICATE EN 10204 3.1\nNumero: 6577 del 2/09/25\nT.P.P. s.p.a.\n"
        "| HEA 160 | S355J2 +AR | 150890 |\n| HEA 160 | S355J2 +AR | 152590 |"
    )
    monkeypatch.setattr(
        veloce.ocr, "leggi", lambda png, impronta, client: {"testo": testo, "incerte": [], "blocchi": []}
    )
    scheda = {
        "famiglia": "certificato_31",
        "motivo": "3.1",
        "testata": {"numero": "6577", "data": "2/09/25", "produttore": "T.P.P. s.p.a."},
        "righe": [
            {"profilo": "HEA 160", "qualita": "S355J2 +AR", "colata": "150890"},
            {"profilo": "HEA 160", "qualita": "S355J2 +AR", "colata": "152590"},
        ],
    }
    risposte = [
        {"schede": {"p0001": scheda}},
        {"correzioni": {"p0001": {"segni": [{"tipo": "freccia", "riga": 0, "testo": ""}]}}},
    ]
    chiamate = _servizi_finti(monkeypatch, risposte)
    monkeypatch.setattr(
        veloce.ocr, "leggi", lambda png, impronta, client: {"testo": testo, "incerte": [], "blocchi": []}
    )
    veloce.analizza(cartella, "modello", "low")
    assert len(chiamate) == 2
    contenuto = chiamate[1][1][0]["content"]
    dubbi = json.loads(contenuto[0]["text"])["dubbi"]
    assert any(c == "segni" and "più colate" in m for c, _, m in dubbi)
    assert contenuto[1]["type"] == "input_image"
    s = lv.scheda_pagina(lv.pagine(cartella)[0])
    assert s["segni"] == [{"tipo": "freccia", "riga": 0, "testo": "", "zona": []}]
    assert veloce.piu_colate_per_profilo(s) and not veloce.piu_colate_per_profilo(veloce.espandi(_SCHEDA_DDT))
