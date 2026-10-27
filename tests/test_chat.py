import json

from test_flusso import _crea_lavoro, _leggi_tutto

from traccia import chat, cli


def test_domanda_in_coda_ha_la_precedenza_e_risposta_con_fonti(radice, capsys):
    cartella, schede = _crea_lavoro(radice)
    pagine = _leggi_tutto(cartella, schede)
    d = chat.chiedi(cartella, "Che colata ha la HEB 180?")
    assert [m["id"] for m in chat.in_attesa(cartella)] == [d["id"]]
    capsys.readouterr()
    assert cli._prossima_domanda()["domanda"] == d["id"]  # prima della composizione

    trovate = chat.cerca(cartella, "colata HEB 180 H1001")
    assert trovate and trovate[0]["file"].endswith("cert777.pdf")
    pid = trovate[0]["pid"]

    errori = chat.rispondi(cartella, d["id"], {"testo": "H1001", "fonti": [{"pid": pid, "cit": "frase inventata"}]})
    assert errori and "non si trova" in errori[0]
    assert (
        chat.rispondi(cartella, d["id"], {"testo": "La colata è H1001.", "fonti": [{"pid": pid, "cit": "H1001"}]}) == []
    )
    assert chat.in_attesa(cartella) == []
    risposta = chat.messaggi(cartella)[-1]
    assert risposta["ruolo"] == "claude" and risposta["fonti"][0]["file"].endswith("cert777.pdf")
    assert len(pagine) > 1


def test_comandi_domanda_e_rispondi(radice, capsys):
    cartella, schede = _crea_lavoro(radice)
    _leggi_tutto(cartella, schede)
    d = chat.chiedi(cartella, "Quali certificati mancano?")
    capsys.readouterr()
    assert cli.domanda("prova", d["id"]) == 0
    dove = json.loads(capsys.readouterr().out)["scrivi_la_risposta_in"]
    with open(dove, "w", encoding="utf-8") as f:
        json.dump({"testo": "Non l'ho trovato nelle pagine lette.", "fonti": []}, f)
    assert cli.rispondi("prova", d["id"]) == 0
    assert chat.in_attesa(cartella) == []
