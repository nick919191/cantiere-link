"""L'app ChatGPT non nomina più "Claude" nei testi per l'utente: Excel, pagine di prova, eventi, interfaccia."""

from openpyxl import load_workbook
from test_flusso import _crea_lavoro, _leggi_tutto

from traccia import cli, percorsi
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
    prove = list((uscita / "prove").glob("*.html"))
    assert prove and not any("Claude" in p.read_text(encoding="utf-8") for p in prove)


def test_eventi_senza_claude(radice):
    cartella, _ = _crea_lavoro(radice)
    cli.prepara_lavoro("prova")
    lv.prossimo_lavoro()
    eventi = (cartella / "eventi.jsonl").read_text(encoding="utf-8")
    assert "Claude" not in eventi and "agente legge" in eventi


def test_interfaccia_senza_claude():
    for nome in ("index.html", "cantiere.js"):
        assert "Claude" not in (percorsi.WEB / nome).read_text(encoding="utf-8"), nome
    # in app.js Claude si nomina solo nella pagina «Collega un agente», dove è uno degli agenti che si possono collegare
    app = (percorsi.WEB / "app.js").read_text(encoding="utf-8")
    assert "Claude" not in app.split("function agenteContent")[0]
