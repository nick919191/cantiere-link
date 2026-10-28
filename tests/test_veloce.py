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
    assert "DOCUMENTO DI TRASPORTO" in scheda["trascrizione"]  # la chat ritrova il testo della pagina


class _Nulla:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False
