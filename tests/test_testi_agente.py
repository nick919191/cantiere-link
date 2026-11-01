"""L'app ChatGPT non nomina più "Claude" nei testi per l'utente: Excel, pagine di prova, eventi, chat, interfaccia."""

import json

from openpyxl import load_workbook
from test_flusso import _crea_lavoro, _leggi_tutto

from traccia import chat, cli, percorsi
from traccia import lavoro as lv


def test_excel_e_prove_senza_claude(radice):
    cartella, schede = _crea_lavoro(radice)
    _leggi_tutto(cartella, schede)
    cli.componi("prova")
    uscita = cartella / "uscita"
    wb = load_workbook(uscita / "tracciabilita.xlsx")
    for nome in ("Metodo", "Provenienza"):
        celle = [str(c.value) for r in wb[nome].iter_rows() for c in r if c.value is not None]
        assert not any("Claude" in c for c in celle), nome
        assert nome != "Metodo" or any("ChatGPT" in c for c in celle)
    prove = list((uscita / "prove").glob("*.html"))
    assert prove and not any("Claude" in p.read_text(encoding="utf-8") for p in prove)


def test_eventi_e_chat_senza_claude(radice):
    cartella, _ = _crea_lavoro(radice)
    cli.prepara_lavoro("prova")
    lv.prossimo_lavoro()
    eventi = (cartella / "eventi.jsonl").read_text(encoding="utf-8")
    assert "Claude" not in eventi and "agente legge" in eventi
    # la risposta si scrive con ruolo "assistente"; gli storici con ruolo "claude" restano risposte valide
    cartella2, schede = _crea_lavoro(radice, "bis")
    pagine = _leggi_tutto(cartella2, schede)
    d = chat.chiedi(cartella2, "colata?")
    assert chat.rispondi(cartella2, d["id"], {"testo": "H1001", "fonti": [{"pid": pagine[0]["pid"], "cit": "a"}]}) == []
    assert chat.messaggi(cartella2)[-1]["ruolo"] == "assistente"
    vecchia = {"id": "r1", "ruolo": "claude", "domanda": d["id"], "testo": "x", "fonti": [], "ora": "10:00"}
    with (cartella2 / "chat.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(vecchia) + "\n")
    assert chat.in_attesa(cartella2) == []
    assert chat.RUOLO_RISPOSTA == "assistente" and "claude" in chat.RUOLI_RISPOSTA


def test_interfaccia_senza_claude():
    for nome in ("index.html", "app.js", "cantiere.js"):
        assert "Claude" not in (percorsi.WEB / nome).read_text(encoding="utf-8"), nome
