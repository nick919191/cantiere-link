"""Pagine identiche (stessa impronta): una sola chiamata al modello e nessuna race in salva_lettura (A2)."""

import copy
import json
import threading

from fascicolo_inventato import fascicolo
from pdf_minimo import pdf_con_testo

from traccia import agente, chatgpt
from traccia import lavoro as lv
from traccia.preparazione import prepara


def test_salva_lettura_da_due_thread_senza_errori(radice):
    errori, barriera = [], threading.Barrier(8)
    scheda = {"famiglia": "da_escludere", "motivo": "x"}

    def salva():
        try:
            barriera.wait()
            for _ in range(20):
                lv.salva_lettura("impronta-condivisa", scheda)
        except Exception as exc:  # noqa: BLE001
            errori.append(exc)

    thread = [threading.Thread(target=salva) for _ in range(8)]
    for t in thread:
        t.start()
    for t in thread:
        t.join()
    assert errori == []
    letture = radice / "archivio" / "letture"
    assert [p.name for p in letture.iterdir()] == [lv.file_lettura("impronta-condivisa").name]
    assert lv.leggi_lettura("impronta-condivisa") == scheda


def test_pagine_identiche_una_sola_chiamata(radice, monkeypatch):
    cartella = radice / "lavori" / "doppie"
    ingresso = cartella / "ingresso"
    ingresso.mkdir(parents=True)
    records = {name: schema for name, _, schema in fascicolo()}
    pdf = pdf_con_testo((records["cert777.pdf"]["trascrizione"] or "pagina").splitlines())
    (ingresso / "cert777.pdf").write_bytes(pdf)
    (ingresso / "copia_cert777.pdf").write_bytes(pdf)  # stesso certificato scansionato due volte
    pagine = prepara(cartella)
    assert len(pagine) == 2 and len({p["impronta"] for p in pagine}) == 1
    richieste = []

    def respond(_instructions, inputs, *_args):
        schede = {}
        for item in inputs[0]["content"]:
            if item["type"] == "input_text":
                context = json.loads(item["text"])
                richieste.append(context["pid"])
                schede[context["pid"]] = copy.deepcopy(records["cert777.pdf"])
        return json.dumps({"schede": schede})

    monkeypatch.setattr(chatgpt, "response", respond)
    agente._cancel.clear()
    agente._stop_richiesto.clear()
    agente.analizza(cartella, "test-model", "")
    assert richieste == ["p0001"]
    stato = lv.stato(cartella)
    assert stato["lette"] == 2 and stato["fase"] == "pronto"
