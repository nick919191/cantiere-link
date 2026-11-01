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


def test_timbro_a_penna_dedotto_con_avviso():
    _, r = _risultato()
    v = _voce(r, "HEA 140")
    assert v["stato"] == "DEDOTTO"
    assert any("penna" in a for a in v["avvisi"])


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


def test_packing_assente_nessun_tetto_ma_avviso_e_dicitura_dai_ddt():
    """Decisione 2 (0.7.0): la packing mancante rende incerto il perimetro, non la prova della singola catena."""
    pagine, schede = [], {}
    for i, (file, pagina, s) in enumerate(fascicolo(), 1):
        if s["famiglia"] == "packing_costruttore":
            continue
        pid = f"p{i:04d}"
        pagine.append({"pid": pid, "file": file, "pagina": pagina})
        schede[pid] = s
    r = elabora(costruisci(pagine, schede))
    assert r["avviso_packing"]
    heb = next(v for v in r["voci"] if v["voce"] == "HEB 180")
    assert heb["stato"] == "PROVATO" and heb["colonne"]["PARTE D'OPERA"]["v"] == "HEB 180 (dai DDT)"
    assert next(v for v in r["voci"] if v["voce"] == "PIATTO 60x10")["stato"] == "DEDOTTO"


def test_righe_packing_senza_materiale_ne_certificato_segnalate():
    from fascicolo_inventato import V, riga_tabella, scheda

    vuota = {**riga_tabella("", "", ""), "qualita": V("S275JR")}
    tab = scheda("packing_costruttore", {"titolo": V("Telai")}, [riga_tabella("HEB 180", "777", "200"), vuota])
    prove = costruisci([{"pid": "p1", "file": "t.pdf", "pagina": 1}], {"p1": tab})
    assert len(prove["packing"]) == 1
    assert prove["packing_scartate"] == [{"pid": "p1", "indice": 1}]


def test_pagina_non_letta_abbassa_lo_stato_solo_se_puo_riguardare_la_voce():
    """C4: il tetto "fascicolo non letto completamente" vale solo per le pagine non lette senza riconoscimento o
    riconosciute come DDT, certificato, packing o lettera nello stesso file dei documenti della voce."""
    prove, _ = _risultato()
    assert _voce(elabora(prove), "HEB 180")["stato"] == "PROVATO"
    prove["non_lette"] = ["p0099"]

    def stato(famiglia, file):
        prove["non_lette_dettagli"] = [{"pid": "p0099", "file": file, "pagina": 9, "famiglia": famiglia}]
        return _voce(elabora(prove), "HEB 180")["stato"]

    assert stato("da_escludere", "cert777.pdf") == "PROVATO"
    assert stato("dop_ce_prodotto", "cert777.pdf") == "PROVATO"
    assert stato("ddt", "altro.pdf") == "PROVATO"  # DDT non letto, ma in un altro file
    assert stato("ddt", "cert777.pdf") == "DA CONFERMARE"  # nello stesso file del certificato della voce
    assert stato("certificato_31", "ddt200.pdf") == "DA CONFERMARE"
    assert stato(None, "altro.pdf") == "DA CONFERMARE"  # senza riconoscimento: contenuto ignoto
    prove.pop("non_lette_dettagli")
    assert _voce(elabora(prove), "HEB 180")["stato"] == "DA CONFERMARE"  # prove senza dettagli: come prima


def test_documento_letto_a_meta_rende_la_voce_da_confermare():
    prove, _ = _risultato()
    doc = next(d for d in prove["ddt"] if d["numero"] == "200")
    prove["parziali"] = [doc["pagine"][0]]
    v = _voce(elabora(prove), "HEB 180")
    assert v["stato"] == "DA CONFERMARE" and any("letto solo in parte" in m for m in v["motivi"])


def _senza_packing(fogli):
    pagine = [{"pid": f"p{i:04d}", "file": f, "pagina": n} for i, (f, n, _) in enumerate(fogli, 1)]
    return elabora(costruisci(pagine, {p["pid"]: s for p, (_, _, s) in zip(pagine, fogli, strict=True)}))


def test_colata_dichiarata_sul_ddt_sceglie_tra_piu_colate_del_certificato():
    """C5: il DDT stampa la colata; il certificato ha due colate dello stesso profilo: nessuna ambiguità."""
    from fascicolo_inventato import certificato, ddt, timbro

    fogli = [
        ("ddt.pdf", 1, ddt("2902", ["LAMIERE S355J2+N SP.012X2450X6000 Placca: 24G6302(A) Colata: 2458653"])),
        ("ddt2.pdf", 1, ddt("77", ["HEA 200 S275JR"], emittente="FORNITORE 002 SRL")),
        (
            "cert.pdf",
            1,
            certificato(
                "16524497809",
                [
                    ("Hot Rolled Heavy Plates 12,00 X 2450,00 X 12000,00", "S355J2+N", "2458630"),
                    ("Hot Rolled Heavy Plates 12,00 X 2450,00 X 12000,00", "S355J2+N", "2458653"),
                ],
                [timbro("2902")],
            ),
        ),
        (
            "cert2.pdf",
            1,
            certificato("9", [("HEA 200", "S275JR", "K100"), ("HEA 200", "S275JR", "K200")], [timbro("77")]),
        ),
    ]
    r = _senza_packing(fogli)
    v = _voce(r, "LAMIERA 12")
    assert v["stato"] != "DA CONFERMARE" and v["colonne"]["COLATA"]["v"] == "2458653"
    assert v["colonne"]["CERT 3.1 ACCIAIERIA"]["v"].startswith("16524497809")
    assert any("Placche dichiarate sul DDT: 24G6302(A)" in n for n in v["note"])
    v = _voce(r, "HEA 200")  # senza colata sul DDT resta l'ambiguità di prima
    assert v["stato"] == "DA CONFERMARE" and v["colate_possibili"] == ["K100", "K200"]


def test_ddt_con_piu_colate_per_lo_stesso_spessore_una_voce_per_colata():
    """Decisione 3: placca per placca sul DDT -> una voce per colata, placche in nota."""
    from fascicolo_inventato import certificato, ddt, timbro

    riga = (
        "SP.015X2450X6000 Placca: 24E6061124(A) Colata: 143343 Placca: 24E6061124(B) Colata: 143343 "
        "Placca: 24EQ001796(A) Colata: 339044"
    )
    cert = certificato(
        "16024488927",
        [("Hot Rolled Heavy Plates 15,00 X 2450,00 X 12000,00", "S355J2+N", c) for c in ("442571", "143343", "339044")],
        [timbro("2902")],
    )
    r = _senza_packing([("ddt.pdf", 1, ddt("2902", [riga])), ("cert.pdf", 1, cert)])
    voci = {v["voce"]: v for v in r["voci"]}
    assert set(voci) == {"LAMIERA 15 · colata 143343", "LAMIERA 15 · colata 339044"}
    assert voci["LAMIERA 15 · colata 143343"]["colonne"]["COLATA"]["v"] == "143343"
    assert any("24E6061124(A), 24E6061124(B)" in n for n in voci["LAMIERA 15 · colata 143343"]["note"])
    assert all(v["stato"] != "DA CONFERMARE" for v in voci.values())


def test_ponte_prima_del_profilo_anche_se_scritto_diversamente():
    """C6: il certificato timbrato per il DDT vale anche se il profilo è scritto in un altro modo."""
    from fascicolo_inventato import certificato, ddt, timbro

    fogli = [
        ("ddt.pdf", 1, ddt("6559", ["TUBO 219,1x12,5"])),
        ("ddt2.pdf", 1, ddt("88", ["LAMIERA SP.10"], emittente="FORNITORE 002 SRL")),
        (
            "c1.pdf",
            1,
            certificato("977915", [("TUBO ELETTROSALDATO 219,1x12,5x12000", "S275JR", "3151783B")], [timbro("6559")]),
        ),
        ("c2.pdf", 1, certificato("977916", [("TUBO ELETTROSALDATO 219,1x12,5x12000", "S275JR", "3151784B")])),
        (
            "c3.pdf",
            1,
            certificato("55", [("HOT ROLLED STEEL PLATES 10.00 2000 12000", "S275JR", "C2589")], [timbro("88")]),
        ),
        (
            "c4.pdf",
            1,
            certificato("56", [("HOT ROLLED STEEL PLATES 10.00 2000 12000", "S275JR", "C2590")], [timbro("89")]),
        ),
    ]
    r = _senza_packing(fogli)
    v = _voce(r, "TUBO 219.1x12.5")
    assert v["colonne"]["CERT 3.1 ACCIAIERIA"]["v"].startswith("977915") and v["colonne"]["COLATA"]["v"] == "3151783B"
    assert any("profilo scritto diversamente" in a for a in v["avvisi"]) and v["stato"] != "DA CONFERMARE"
    v = _voce(r, "LAMIERA 10")
    assert v["colonne"]["COLATA"]["v"] == "C2589" and v["stato"] != "DA CONFERMARE"


def test_lista_del_commerciante_lega_ddt_certificato_e_colata():
    """C13: la lista di rintracciabilità (lettera con placca, colata, certificato) è un ponte con le colate."""
    from fascicolo_inventato import V, certificato, ddt, scheda

    lista = scheda(
        "lettera_accompagnamento",
        {"emittente": V("FORNITORE 001 SRL"), "ddt_citato": V("3332"), "data_ddt": V("14/02/2025")},
        [
            {
                "articolo": V("LAM. CALDO 5x1500x6000"),
                "placca": V("24064054"),
                "colata": V("24305236"),
                "certificato": V("15.329"),
            },
            {
                "articolo": V("LAM. CALDO 8x1500x6000"),
                "placca": V("1H4F6789"),
                "colata": V("6965529"),
                "certificato": V("L26627"),
            },
        ],
    )
    cert5 = certificato(
        "15.329", [("Hot Rolled Mill Edge Coil 5,00x1500xC", "S355J2+N", c) for c in ("24305235", "24305236")]
    )
    cert8 = certificato("L26627", [("Hot Rolled Mill Edge Strip 1500.0X8.00XCOIL", "S355J2+AR", "6965529")])
    fogli = [
        ("f.pdf", 1, ddt("G01 / 3332", ["LAM. CALDO 5x1500x6000", "LAM. CALDO 8x1500x6000"])),
        ("f.pdf", 2, lista),
        ("f.pdf", 3, cert5),
        ("f.pdf", 4, cert8),
    ]
    r = _senza_packing(fogli)
    v5, v8 = _voce(r, "LAMIERA 5"), _voce(r, "LAMIERA 8")
    assert v5["colonne"]["COLATA"]["v"] == "24305236" and v5["stato"] != "DA CONFERMARE"
    assert v8["colonne"]["COLATA"]["v"] == "6965529" and v8["stato"] != "DA CONFERMARE"
    assert any("lettera del distributore" in m for m in v8["motivi"])


def test_segno_a_mano_su_una_sola_colata_la_sceglie():
    """Decisione 1 (C7): freccia su una delle due colate del profilo -> quella colata, stato come se fosse unica."""
    from fascicolo_inventato import certificato, ddt, timbro

    # reale (anonimo): HEA 160 con due colate e una freccia; inventato: IPE 200 con segni su entrambe le colate
    c1 = certificato(
        "6577",
        [("HEA 160", "S275J0+AR", "150890"), ("HEA 160", "S275J0+AR", "152590")],
        [timbro("8027")],
        segni=[{"tipo": "freccia", "riga": 0, "testo": "", "zona": []}],
    )
    c2 = certificato(
        "6578",
        [("IPE 200", "S275JR", "700100"), ("IPE 200", "S275JR", "700200")],
        [timbro("8027")],
        segni=[
            {"tipo": "spunta", "riga": 0, "testo": "", "zona": []},
            {"tipo": "spunta", "riga": 1, "testo": "", "zona": []},
        ],
    )
    fogli = [
        ("ddt.pdf", 1, ddt("8027", ["TRAVI HE/A 160", "TRAVI IPE 200"])),
        ("ddt2.pdf", 1, ddt("20", ["UPN 100"], emittente="FORNITORE 002 SRL")),
        ("c1.pdf", 1, c1),
        ("c2.pdf", 1, c2),
    ]
    r = _senza_packing(fogli)
    v = _voce(r, "HEA 160")
    assert v["stato"] == "PROVATO" and v["colonne"]["COLATA"]["v"] == "150890" and v["colate_possibili"] == []
    assert any("scelta dal segno a mano" in a and "controllare l'originale" in a for a in v["avvisi"])
    v = _voce(r, "IPE 200")
    assert v["stato"] == "DA CONFERMARE" and v["colate_possibili"] == ["700100", "700200"]
    assert any("segni a mano su più colate" in a for a in v["avvisi"])


def test_dop_di_prodotto_collegata_per_fabbricante_e_organismo():
    """C10 (P3): stesso produttore e stesso organismo notificato stampato su certificato e DoP."""
    from fascicolo_inventato import V, certificato, ddt, scheda, timbro

    cert = certificato(
        "202478791",
        [("IPE160 L.12.1M", "S275J0+AR", "CE256775")],
        [timbro("8027")],
        produttore="Compañía Española de Laminación S.L.",
    )
    cert["riferimenti"] = [{"tipo": "fpc", "v": "CE 0099 06 CELSA01BCN", "cit": "CE 0099 06 CELSA01BCN", "zona": []}]
    cert["trascrizione"] += "\nCE 0099 06 CELSA01BCN"
    dop_ok = scheda(
        "dop_ce_prodotto",
        {
            "fabbricante": V("CELSA - Compañía Española de Laminación S.L."),
            "numero_dop": V("CELSA01BCN"),
            "organismo": V("0099"),
            "norma": V("EN 10025-1"),
        },
    )
    dop_altro_organismo = scheda(
        "dop_ce_prodotto",
        {
            "fabbricante": V("Compañía Española de Laminación S.L."),
            "numero_dop": V("CELSA02BCN"),
            "organismo": V("0474"),
            "norma": V("EN 10025-1"),
        },
    )
    dop_altro_produttore = scheda(
        "dop_ce_prodotto", {"fabbricante": V("ACCIAIERIE VERDI SPA"), "numero_dop": V("V-1"), "organismo": V("0099")}
    )
    fogli = [
        ("ddt.pdf", 1, ddt("8027", ["TRAVI IPE 160"])),
        ("ddt2.pdf", 1, ddt("20", ["UPN 100"], emittente="FORNITORE 002 SRL")),
        ("c.pdf", 1, cert),
        ("d1.pdf", 1, dop_ok),
        ("d2.pdf", 1, dop_altro_organismo),
        ("d3.pdf", 1, dop_altro_produttore),
    ]
    v = _voce(_senza_packing(fogli), "IPE 160")
    ce = v["colonne"]["CE/DoP ACCIAIERIA"]["v"]
    assert "DoP CELSA01BCN" in ce and "(collegata per fabbricante e organismo)" in ce
    assert "CELSA02BCN" not in ce and "V-1" not in ce


def test_certificato_con_timbro_che_cita_un_ddt_assente_diventa_voce_da_confermare():
    """C12: il cliente vede che manca un DDT: voce DA CONFERMARE e richiesta 'DDT N di <commerciante>'."""
    from fascicolo_inventato import certificato, ddt, timbro

    t = timbro("6559")
    t["chi"] = "F.lli Molteni s.p.a."
    arvedi = certificato("977915", [("TUBO ELETTROSALDATO 219,1x12,5x12000", "S355J2H", "3151783B")], [t])
    fogli = [
        ("ddt.pdf", 1, ddt("8027", ["TRAVI HEA 160"])),
        ("ddt2.pdf", 1, ddt("20", ["UPN 100"], emittente="FORNITORE 002 SRL")),
        ("c.pdf", 1, arvedi),
        ("c2.pdf", 1, certificato("55", [("HEA 160", "S275JR", "H1001")], [timbro("8027")])),
    ]
    r = _senza_packing(fogli)
    v = _voce(r, "TUBO 219.1x12.5x12000")
    assert v["stato"] == "DA CONFERMARE" and v["origine"] == "dal_certificato"
    assert v["richieste"] == ["DDT 6559 di F.lli Molteni s.p.a."]
    assert v["colonne"]["COLATA"]["v"] == "3151783B" and v["colonne"]["DDT COMMERCIANTE"]["v"].startswith("DDT n. 6559")
    assert v["colonne"]["COMMERCIANTE / CENTRO TRASF."]["v"] == "F.lli Molteni s.p.a."
    assert v["colonne"]["PARTE D'OPERA"]["v"].endswith("(da un certificato)")
    assert len(r["voci"]) == 3  # il certificato usato (HEA 160) non genera un'altra voce


def test_segni_croce_escludono_e_non_scelgono():
    from fascicolo_inventato import certificato, ddt, timbro

    # reale (anonimo): partite barrate con una croce, una evidenziata; inventato: tutte barrate tranne una
    c1 = certificato(
        "16024488927",
        [("Hot Rolled Heavy Plates 15,00 X 2450,00 X 12000,00", "S275JR", c) for c in ("442571", "143343", "442770")],
        [timbro("2902")],
        segni=[
            {"tipo": "croce", "riga": 0, "testo": "", "zona": []},
            {"tipo": "evidenziatore", "riga": 1, "testo": "", "zona": []},
            {"tipo": "croce", "riga": 2, "testo": "", "zona": []},
        ],
    )
    c2 = certificato(
        "77",
        [("HEA 200", "S275JR", c) for c in ("700100", "700200", "700300")],
        [timbro("20")],
        segni=[
            {"tipo": "croce", "riga": 0, "testo": "", "zona": []},
            {"tipo": "croce", "riga": 2, "testo": "", "zona": []},
        ],
    )
    fogli = [
        ("ddt.pdf", 1, ddt("2902", ["LAMIERE SP.015X2450X6000"])),
        ("ddt2.pdf", 1, ddt("20", ["HEA 200"], emittente="FORNITORE 002 SRL")),
        ("c1.pdf", 1, c1),
        ("c2.pdf", 1, c2),
    ]
    r = _senza_packing(fogli)
    v = _voce(r, "LAMIERA 15")
    assert v["colonne"]["COLATA"]["v"] == "143343" and v["stato"] == "PROVATO"
    v = _voce(r, "HEA 200")
    assert v["colonne"]["COLATA"]["v"] == "700200" and any("barrate" in a for a in v["avvisi"])


def test_dop_collegata_per_ddt_del_produttore_anche_con_etichetta_nel_campo():
    from fascicolo_inventato import V, certificato, ddt, scheda, timbro

    cert = certificato("6577", [("HEA 160", "S275JR", "150890")], [timbro("8027")])
    cert["testata"]["ddt_produttore"] = V("DDT/DELIVNOTE BA/6577")
    cert["trascrizione"] += "\nDDT/DELIVNOTE BA/6577"
    dop = scheda(
        "dop_ce_prodotto",
        {"fabbricante": V("PRODUTTORE 001 SPA"), "numero_dop": V("03 N 2025"), "ddt_citato": V("BA/6577")},
    )
    fogli = [
        ("ddt.pdf", 1, ddt("8027", ["HEA 160"])),
        ("ddt2.pdf", 1, ddt("20", ["UPN 100"], emittente="FORNITORE 002 SRL")),
        ("c.pdf", 1, cert),
        ("d.pdf", 1, dop),
    ]
    v = _voce(_senza_packing(fogli), "HEA 160")
    assert "DoP 03 N 2025" in v["colonne"]["CE/DoP ACCIAIERIA"]["v"]
