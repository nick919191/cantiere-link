"""Controlli sulla scheda: errori bloccanti contro errori di campo (C3)."""

from fascicolo_inventato import V, certificato, ddt, scheda, timbro

from traccia.controlli import valida
from traccia.famiglie import FAMIGLIE


def _ddt_con_riferimenti():
    s = ddt("4563", ["HEA 140"])
    s["trascrizione"] += "\nCUP: D75E23000000001 CIG: 847FA79341 ORDINE 12"
    s["riferimenti"] = [
        {"tipo": "cup", "v": "D75E23000000001", "cit": "CUP: D75E23000000001", "zona": []},
        {"tipo": "ordine", "v": "12", "cit": "ORDINE 12", "zona": []},
    ]
    return s


def test_riferimento_con_tipo_fuori_elenco_diventa_altro_senza_errore():
    s = _ddt_con_riferimenti()
    assert valida(s) == []
    assert [r["tipo"] for r in s["riferimenti"]] == ["altro", "ordine"]
    assert len(s["avvisi"]) == 1 and "altro" in s["avvisi"][0]


def test_senza_correzione_gli_errori_di_campo_restano_bloccanti():
    s = certificato("7001", [("HEA 200", "S275JR", "K100")])
    s["testata"]["numero"] = V("7001", "numero inventato non sulla pagina")
    assert any("citazione" in e for e in valida(s))
    s = _ddt_con_riferimenti()
    s["riferimenti"].append({"tipo": "ddt", "v": "1"})  # malformato
    assert any("riferimenti[2]" in e for e in valida(s))


def test_con_correzione_il_campo_si_svuota_e_il_riferimento_malformato_si_toglie():
    s = certificato("7001", [("HEA 200", "S275JR", "K100")], [timbro("300")])
    s["testata"]["numero"] = V("7001", "numero inventato non sulla pagina")
    s["righe"][0]["colata"] = V("K100", "colata non nel testo")
    s["riferimenti"] = [{"tipo": "ddt", "v": "1"}, {"tipo": "cig", "v": "300", "cit": "300", "zona": []}]
    s["timbri"].append({"chi": "X"})  # timbro malformato
    s["segni"] = [{"tipo": "freccia", "riga": "zero", "testo": "", "zona": []}]
    assert valida(s, correggi=True) == []
    assert s["testata"]["numero"]["v"] == "" and s["righe"][0]["colata"]["v"] == ""
    assert s["testata"]["produttore"]["v"] == "PRODUTTORE 001 SPA"  # gli altri campi restano
    assert [r["tipo"] for r in s["riferimenti"]] == ["altro"]
    assert len(s["timbri"]) == 1 and s["timbri"][0]["ddt_citato"] == "300"
    assert s["segni"] == []
    scartati = [a for a in s["avvisi"] if a.startswith("valore scartato")]
    assert len(scartati) == 5  # numero, colata, riferimento, timbro, segno


def test_con_correzione_restano_bloccanti_famiglia_testata_e_righe():
    s = scheda("ddt")
    s["famiglia"] = "fattura"
    assert valida(s, correggi=True) == ["famiglia 'fattura' non valida: una tra " + ", ".join(FAMIGLIE)]
    s = ddt("1", ["HEA 100"])
    s["testata"].pop("numero")
    assert any(e.startswith("testata:") for e in valida(s, correggi=True))
    s = ddt("1", ["HEA 100"])
    s["righe"][0] = {"descrizione": V("x")}
    assert any(e.startswith("righe[0]") for e in valida(s, correggi=True))
