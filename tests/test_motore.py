from fascicolo_inventato import fascicolo

from traccia.motore import elabora
from traccia.prove import costruisci


def _risultato():
    pagine, schede = [], {}
    for i, (file, pagina, s) in enumerate(fascicolo(), 1):
        pid = f"p{i:04d}"
        pagine.append({"pid": pid, "file": file, "pagina": pagina})
        schede[pid] = s
    prove = costruisci(pagine, schede)
    return prove, elabora(prove)


def _voce(risultato, inizio):
    return next(v for v in risultato["voci"] if v["voce"].startswith(inizio))


def test_ruoli_dal_fascicolo():
    prove, _ = _risultato()
    assert prove["costruttore"] == "COSTRUTTORE 001 SRL"
    assert {d["tipo"] for d in prove["ddt"]} == {"commerciante_costruttore"}


def test_provato_con_timbro_e_numero_con_prefisso():
    _, r = _risultato()
    v = _voce(r, "HEB 180")
    assert v["stato"] == "PROVATO"
    assert v["colonne"]["COLATA"]["v"] == "H1001"
    assert any("99-777" in a for a in v["avvisi"])


def test_dedotto_senza_timbro():
    _, r = _risultato()
    assert _voce(r, "PL10*60")["stato"] == "DEDOTTO"


def test_piu_colate_da_confermare_senza_colata():
    _, r = _risultato()
    v = _voce(r, "PL8*120/180")
    assert v["stato"] == "DA CONFERMARE"
    assert v["colonne"]["COLATA"]["v"] == ""
    assert v["colate_possibili"] == ["H3003", "H3004"]


def test_mancante_con_numero_dichiarato_e_fornitore():
    _, r = _risultato()
    v = _voce(r, "PL10*90")
    assert v["stato"] == "MANCANTE"
    assert v["colonne"]["CERT 3.1 ACCIAIERIA"]["v"].startswith("5504")
    assert "non nel fascicolo" in v["colonne"]["CERT 3.1 ACCIAIERIA"]["v"]
    assert "FORNITORE 001 SRL" in " ".join(v["note"])
    assert "certificato 5504" in v["richieste"] and "DDT 400" in v["richieste"]


def test_ricavato_da_profilo_piu_largo_al_massimo_dedotto():
    _, r = _risultato()
    v = _voce(r, "PL10*155")
    assert v["stato"] == "DEDOTTO"
    assert v["colonne"]["COLATA"]["v"] == "H5005"


def test_timbro_a_penna_al_massimo_da_confermare():
    _, r = _risultato()
    assert _voce(r, "HEA 140")["stato"] == "DA CONFERMARE"


def test_ogni_valore_ha_la_sua_fonte():
    prove, r = _risultato()
    v = _voce(r, "HEB 180")
    fid = v["colonne"]["COLATA"]["fonti"][0]
    assert prove["fonti"][fid]["file"] == "cert777.pdf"
    assert prove["fonti"][fid]["valore"] == "H1001"


def test_stesse_prove_stesso_risultato():
    _, a = _risultato()
    _, b = _risultato()
    assert a == b


def test_piatti_divisi_per_profilo_di_origine():
    from fascicolo_inventato import V, certificato, ddt, riga_tabella, scheda

    tab = scheda(
        "packing_costruttore",
        {"titolo": V("Telai")},
        [riga_tabella("PL10*90", "7001", "800"), riga_tabella("PL10*155", "7001", "800/1")],
    )
    cert = certificato("7001", [("FLAT 100X10", "S275JR", "K100"), ("FLAT 160X10", "S275JR", "K160")])
    cert["testata"]["ddt_produttore"] = V("PA/55")
    cert["trascrizione"] += "\nPA/55"
    dop = scheda("dop_ce_prodotto", {"fabbricante": V("PRODUTTORE 001 SPA"), "ddt_citato": V("PA/55")})
    fogli = [
        ("t.pdf", tab),
        ("d.pdf", ddt("800/1", ["PIATTO LT=100 SP=10", "LARGHI PIATTI LA=160 SP=10"])),
        ("c.pdf", cert),
        ("dop.pdf", dop),
    ]
    pagine = [{"pid": f"p{i}", "file": f, "pagina": 1} for i, (f, _) in enumerate(fogli)]
    r = elabora(costruisci(pagine, {f"p{i}": s for i, (_, s) in enumerate(fogli)}))
    per_voce = {v["voce"]: v for v in r["voci"]}
    assert set(per_voce) == {"PL10*90", "PL10*155"}
    assert per_voce["PL10*90"]["colonne"]["COLATA"]["v"] == "K100"
    assert per_voce["PL10*155"]["colonne"]["COLATA"]["v"] == "K160"
    assert any("800/1" in a for a in per_voce["PL10*90"]["avvisi"])  # suffisso di serie: stesso DDT, con avviso
    assert "PA/55" in per_voce["PL10*90"]["colonne"]["CE/DoP ACCIAIERIA"]["v"]  # DoP collegata con prova P2


def test_packing_assente_al_massimo_dedotto():
    pagine, schede = [], {}
    for i, (file, pagina, s) in enumerate(fascicolo(), 1):
        if s["famiglia"] == "packing_costruttore":
            continue
        pid = f"p{i:04d}"
        pagine.append({"pid": pid, "file": file, "pagina": pagina})
        schede[pid] = s
    r = elabora(costruisci(pagine, schede))
    assert r["avviso_packing"]
    assert all(v["stato"] != "PROVATO" for v in r["voci"])
    assert any(v["voce"] == "HEB 180" and v["stato"] == "DEDOTTO" for v in r["voci"])
