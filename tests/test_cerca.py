from test_flusso import _crea_lavoro, _leggi_tutto

from traccia import cerca


def test_cerca_trova_le_pagine_lette_con_le_parole(radice):
    cartella, schede = _crea_lavoro(radice)
    _leggi_tutto(cartella, schede)
    trovate = cerca.cerca(cartella, "colata HEB 180 H1001")
    assert trovate and trovate[0]["file"].endswith("cert777.pdf")
    assert "h1001" in trovate[0]["parole_trovate"] and trovate[0]["estratto"]
