"""Riconoscimento DeepSeek (mappa.py) e suo uso nella lettura veloce, senza chiamate vere."""

import json

import httpx
from PIL import Image

from traccia import mappa, veloce


def test_ricavati_dal_markdown():
    md = "| Pos | Profilo | Cert |\n| 1 | HEA 200 | EN 10204 3.1 |\n|  |  |  |\n| 2 | IPE 240 | EN10204 3.1 |"
    pulito = mappa.pulisci_md(md)
    assert "|  |  |  |" not in pulito
    assert mappa.righe_materiale_md(pulito, "packing_costruttore", False) == 2
    assert mappa.righe_materiale_md(pulito, "packing_costruttore", True) is None  # troncato: non affidabile
    assert mappa.righe_materiale_md(pulito, "ddt", False) is None
    assert mappa.timbro_md("Certificato\n[timbro] DDT N. 1663 del 02/7/21", "certificato_31").startswith("[timbro] DDT")
    assert mappa.timbro_md("DDT N. 1663", "ddt") is None


class _Client:
    def __init__(self, risposte):
        self.risposte, self.corpi = list(risposte), []

    def post(self, url, json):
        self.corpi.append(json)
        return httpx.Response(200, json=self.risposte.pop(0))


def _risposta(contenuto, fine="stop"):
    return {"choices": [{"message": {"content": contenuto}, "finish_reason": fine}], "usage": {"prompt_tokens": 1000}}


def test_riconosci_usa_l_archivio_e_salta_il_markdown_dei_ddt(radice, tmp_path):
    png = tmp_path / "p.png"
    Image.new("RGB", (100, 140), "white").save(png)
    tipo = {"famiglia": "ddt", "sicurezza": 0.95, "verso": "dritto", "motivo": "DDT", "timbro": False}
    client = _Client([_risposta(json.dumps(tipo))])
    r = mappa.riconosci(png, "imp1", client)
    assert r["famiglia"] == "ddt" and not r["da_guardare"] and r["markdown"] == ""
    assert len(client.corpi) == 1  # niente Markdown per i DDT
    assert mappa.riconosci(png, "imp1", _Client([]))["famiglia"] == "ddt"  # dall'archivio: nessuna chiamata

    cert = {"famiglia": "certificato_31", "sicurezza": 0.6, "verso": "dritto", "timbro": True}
    client = _Client([_risposta(json.dumps(cert)), _risposta("[timbro] DDT N. 1663 del 02/7/21")])
    r = mappa.riconosci(png, "imp2", client)
    assert r["da_guardare"]  # sicurezza sotto 0,8
    assert r["timbro"] and r["timbro_md"]


def _lavoro_due_pagine(radice):
    from traccia import percorsi

    cartella = percorsi.lavori() / "mappa-prova"
    (cartella / "pagine").mkdir(parents=True)
    elenco = []
    for i, file in ((1, "cert.pdf"), (2, "pubblicita.pdf")):
        pid = f"p000{i}"
        Image.new("RGB", (100, 140), "white").save(cartella / "pagine" / f"{pid}.png")
        info = {
            "pid": pid,
            "file": file,
            "pagina": 1,
            "pagine_file": 1,
            "impronta": f"imp{i}",
            "bianca": False,
            "larghezza": 100,
            "altezza": 140,
            "testo_nativo": "",
            "parole": [],
        }
        (cartella / "pagine" / f"{pid}.json").write_text(json.dumps(info), encoding="utf-8")
        elenco.append({k: info[k] for k in ("pid", "file", "pagina", "pagine_file", "impronta", "bianca")})
    (cartella / "pagine.json").write_text(json.dumps(elenco), encoding="utf-8")
    return cartella


def test_lettura_con_mappa_salta_le_escluse_e_rilegge_i_timbri_con_l_immagine(radice, monkeypatch):
    from traccia import agente, ocr
    from traccia import lavoro as lv

    cartella = _lavoro_due_pagine(radice)
    base = {"sicurezza": 0.95, "verso": "dritto", "da_guardare": False, "modello": "deepseek-flash"}
    mappe = {
        "p0001": {
            **base,
            "famiglia": "certificato_31",
            "motivo": "3.1",
            "timbro": True,
            "timbro_md": None,
            "righe_materiale_md": None,
            "costo_dollari": 0.001,
        },
        "p0002": {
            **base,
            "famiglia": "da_escludere",
            "motivo": "pubblicità",
            "timbro": False,
            "timbro_md": None,
            "righe_materiale_md": None,
            "costo_dollari": 0.001,
        },
    }
    monkeypatch.setattr(mappa, "attiva", lambda: True)
    monkeypatch.setattr(mappa, "riconosci_tutte", lambda c, pagine, avanza=None: mappe)
    letti = []

    def leggi(png, impronta, client):
        letti.append(impronta)
        return {"testo": "INSPECTION CERTIFICATE EN 10204 3.1\nN. 7731\nHEA 200 S275JR", "incerte": [], "blocchi": []}

    monkeypatch.setattr(ocr, "client", lambda: _Nulla())
    monkeypatch.setattr(ocr, "leggi", leggi)
    scheda = {"famiglia": "certificato_31", "motivo": "3.1", "testata": {"numero": "7731"}, "righe": []}
    chiamate = []

    def chiama(cartella, istruzioni, messaggi, model, effort):
        chiamate.append((istruzioni, messaggi))
        return json.dumps({"schede": {"p0001": scheda}})

    monkeypatch.setattr(agente, "_chiama", chiama)
    monkeypatch.setattr(veloce.agente, "componi", lambda c: None)
    agente._cancel.clear()
    veloce.analizza(cartella, "modello", "low")

    assert letti == ["imp1"]  # la pagina esclusa non passa dall'OCR
    esclusa = lv.scheda_pagina(lv.pagine(cartella)[1])
    assert esclusa["famiglia"] == "da_escludere" and "DeepSeek" in esclusa["agente"]
    assert len(chiamate) == 2  # lettura + verifica del timbro
    verifica = chiamate[1][1][0]["content"]
    assert any("timbro" in c.get("text", "") for c in verifica)
    assert any(c.get("type") == "input_image" for c in verifica)  # pagina intera, non un ritaglio
    assert "certificato_31" in chiamate[0][0]  # istruzioni del tipo riconosciuto


class _Nulla:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_riconoscimento_chiede_e_riporta_il_segno_a_mano(radice, tmp_path):
    assert "segno_a_mano" in mappa.prompt_tipo()
    png = tmp_path / "p.png"
    Image.new("RGB", (100, 140), "white").save(png)
    tipo = {"famiglia": "certificato_31", "sicurezza": 0.95, "verso": "dritto", "timbro": False, "segno_a_mano": True}
    r = mappa.riconosci(png, "imp9", _Client([_risposta(json.dumps(tipo)), _risposta("| HEA 160 | 150890 |")]))
    assert r["segno_a_mano"] is True
    tipo["segno_a_mano"] = "forse"
    assert (
        mappa.riconosci(png, "imp10", _Client([_risposta(json.dumps(tipo)), _risposta("x")]))["segno_a_mano"] is False
    )
