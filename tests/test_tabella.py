from fastapi.testclient import TestClient
from test_flusso import _crea_lavoro, _leggi_tutto

from traccia import cli, server


def test_tabella_ha_valore_perche_e_documento_per_cella(radice, capsys):
    cartella, schede = _crea_lavoro(radice)
    _leggi_tutto(cartella, schede)
    assert cli.componi("prova") == 0
    capsys.readouterr()
    client = TestClient(server.app)
    t = client.get("/api/lavori/prova/tabella").json()
    assert "COLATA" in t["colonne"] and t["voci"]
    celle = [c for v in t["voci"] for c in v["celle"].values()]
    assert all(c["perche"] for c in celle)  # ogni cella dice perché c'è quel dato (o perché manca)
    con_doc = [c for c in celle if c["documenti"]]
    assert con_doc and all(d["pid"] and d["file"] and d["pagina"] for c in con_doc for d in c["documenti"])
    pid = con_doc[0]["documenti"][0]["pid"]
    r = client.get(f"/api/lavori/prova/originale/{pid}")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert client.get("/api/lavori/prova/originale/p9999").status_code == 404
