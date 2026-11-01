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


def test_lista_del_commerciante_divide_la_voce_per_colata_e_il_preciso_vince_sul_generico():
    from fascicolo_inventato import V, certificato, ddt, scheda, timbro

    lista = scheda(
        "lettera_accompagnamento",
        {"emittente": V("FORNITORE 001 SRL"), "ddt_citato": V("51159"), "data_ddt": V("16/09/2025")},
        [
            {"placca": V("PP64808201"), "colata": V("SU36217")},
            {"placca": V("PP64808202"), "colata": V("SU36217")},
            {"placca": V("PP64113902"), "colata": V("SU35302")},
        ],
    )
    generica = scheda(
        "lettera_accompagnamento",
        {"emittente": V("FORNITORE 001 SRL"), "ddt_citato": V("3332"), "data_ddt": V("14/02/2025")},
        [{"colata": V("24064054"), "certificato": V("24064054")}],  # coil, senza articolo: generica
    )
    precisa = scheda(
        "lettera_accompagnamento",
        {"emittente": V("FORNITORE 001 SRL"), "ddt_citato": V("3332"), "data_ddt": V("14/02/2025")},
        [{"articolo": V("LAM. CALDO 5,00 x1500,00 x 6000,00"), "colata": V("24305236")}],
    )
    c1 = certificato("P1", [("HOT ROLLED PLATE 15x2500x6000", "S275JR", "SU36217")], [timbro("51159")])
    c2 = certificato("P2", [("HOT ROLLED PLATE 15x2500x6000", "S275JR", "SU35302")], [timbro("51159")])
    c3 = certificato("15.329", [("Hot Rolled Mill Edge Coil 5,00x1500xC", "S275JR", "24305236")], [timbro("3332")])
    fogli = [
        ("f.pdf", 1, ddt("G02 / 51159", ["L.DA TRENO S355J2 Pz 8 6000x2500x15,00"])),
        ("f.pdf", 2, lista),
        ("f.pdf", 3, c1),
        ("f.pdf", 4, c2),
        ("g.pdf", 1, ddt("G01 / 3332", ["LAM. CALDO 6000x1500x5,00"], emittente="FORNITORE 002 SRL")),
        ("g.pdf", 2, generica),
        ("g.pdf", 3, precisa),
        ("g.pdf", 4, c3),
    ]
    r = _senza_packing(fogli)
    voci = {v["voce"]: v for v in r["voci"]}
    assert {"LAMIERA 15 · colata SU36217", "LAMIERA 15 · colata SU35302", "LAMIERA 5 · colata 24305236"} <= set(voci)
    assert voci["LAMIERA 15 · colata SU36217"]["colonne"]["COLATA"]["v"] == "SU36217"
    assert any("PP64808201, PP64808202" in n for n in voci["LAMIERA 15 · colata SU36217"]["note"])
    assert voci["LAMIERA 15 · colata SU35302"]["colonne"]["CERT 3.1 ACCIAIERIA"]["v"].startswith("P2")
    assert "24064054" not in voci  # la riga generica (coil) non fa voce: c'è la riga precisa
    assert voci["LAMIERA 5 · colata 24305236"]["stato"] == "PROVATO"


def test_ddt_letto_male_non_toglie_la_richiesta_del_ddt_citato_dal_timbro():
    """Un DDT con emittente = destinatario è una lettura sbagliata: il certificato che cita quel numero resta una
    voce da confermare con la richiesta del DDT al commerciante del timbro."""
    from fascicolo_inventato import V, certificato, ddt, timbro

    t = timbro("6559")
    t["chi"] = "F.lli Molteni s.p.a."
    sbagliato = ddt("6559", ["T NERO SALDATO 219,1 X 12,5"], emittente="COSTRUTTORE 001 SRL", destinatario="ALTRO SRL")
    sbagliato["testata"]["piva_destinatario"] = V("01234567890")
    buono = ddt("30", ["UPN 100"], emittente="COSTRUTTORE 001 SRL", destinatario="CLIENTE SRL")
    buono["testata"]["piva_emittente"] = V("01234567890")
    fogli = [
        ("ddt.pdf", 1, ddt("8027", ["TRAVI HEA 160"])),
        ("ddt2.pdf", 1, ddt("20", ["UPN 100"], emittente="FORNITORE 002 SRL")),
        ("x.pdf", 1, sbagliato),
        ("y.pdf", 1, buono),
        ("c.pdf", 1, certificato("977915", [("TUBO ELETTROSALDATO 219,1x12,5x12000", "S355J2H", "3151783B")], [t])),
    ]
    r = _senza_packing(fogli)
    v = _voce(r, "TUBO 219.1x12.5x12000")
    assert v["stato"] == "DA CONFERMARE" and v["richieste"] == ["DDT 6559 di F.lli Molteni s.p.a."]


def _con_packing(fogli):
    pagine = [{"pid": f"p{i:04d}", "file": f, "pagina": n} for i, (f, n, _) in enumerate(fogli, 1)]
    return elabora(costruisci(pagine, {p["pid"]: s for p, (_, _, s) in zip(pagine, fogli, strict=True)}))


def test_piatto_scritto_senza_parola_sul_certificato_vale_per_il_piatto_dichiarato():
    """0.7.1 (Viollier): il certificato CELSA scrive '70X10 L.6.00m' (letto come tubo) per il piatto 70x10; il timbro
    stampato scrive il DDT '3209 - 1' per il DDT 3209/1 che il costruttore chiama 3209."""
    from fascicolo_inventato import V, certificato, ddt, riga_tabella, scheda, timbro

    tab = scheda("packing_costruttore", {"titolo": V("Copertura")}, [riga_tabella("PL10*70", "201952727", "3209")])
    t = timbro("3209 - 1")
    cert = certificato("201952727", [("70X10 L.6.00m", "S275JR +AR", "CE613171")], [t])
    r = _con_packing([("t.pdf", 1, tab), ("d.pdf", 1, ddt("3209/1", ["FERRO PIATTO 70X10"])), ("c.pdf", 1, cert)])
    v = _voce(r, "PL10*70")
    assert v["stato"] == "PROVATO" and v["colonne"]["COLATA"]["v"] == "CE613171"
    assert any("scritto diversamente" in a for a in v["avvisi"])


def test_certificato_dichiarato_assente_sostituito_da_quello_timbrato_per_lo_stesso_ddt():
    """0.7.1 (Viollier): il ciclo dichiara GI2300/2021, il certificato stampa G1200/2021 ma il timbro a penna cita il
    DDT 1062 e il profilo c'è: vale, al massimo DEDOTTO, senza richiesta del certificato dichiarato."""
    from fascicolo_inventato import V, certificato, ddt, riga_tabella, scheda, timbro

    tab = scheda("packing_costruttore", {"titolo": V("Copertura")}, [riga_tabella("L50*5", "GI2300/2021", "1062")])
    cert = certificato(
        "G1200/2021",
        [("ANG.50X50X5", "S275JR+AR", "151166"), ("ANG.50X50X5", "S275JR+AR", "22005213")],
        [timbro("1062", a_mano=True)],
        segni=[{"tipo": "croce", "riga": 0}],
    )
    d = ddt("01062", ["ANGOLARE A LATI UGUALI LT=50.0 LT=50.0 SP=5.0 LU=L.C."])
    r = _con_packing([("t.pdf", 1, tab), ("d.pdf", 1, d), ("c.pdf", 1, cert)])
    v = _voce(r, "L50*5")
    assert v["stato"] == "DEDOTTO" and v["colonne"]["COLATA"]["v"] == "22005213"
    assert "G1200/2021" in v["colonne"]["CERT 3.1 ACCIAIERIA"]["v"]
    assert any("diverso da quello dichiarato" in a for a in v["avvisi"])
    assert not any("certificato" in x for x in v["richieste"])


def test_ddt_a_penna_letto_male_ripreso_per_data_ed_emittente():
    """0.7.1 (Viollier): sul timbro '1062' è letto '1002'; nessun DDT 1002, ma il DDT 1062 dello stesso giorno c'è:
    il timbro vale per quello, il certificato non diventa una voce fantasma che chiede il DDT 1002."""
    from fascicolo_inventato import V, certificato, ddt, riga_tabella, scheda, timbro

    t = timbro("1002", a_mano=True)
    t["chi"], t["data_ddt"] = "Magazzino CELESTRI di Gallarate", "18/5/22"
    beltrame = certificato("283664", [("UN. ANG. 120X80X10", "S275JR+AR", "BE 198928")], [t])
    d = ddt("01062", ["ANGOLARE A LATI UGUALI LT=120 LA=80 SP=10"], emittente="CELESTRI S.R.L.")
    d["testata"]["data"] = V("18/05/2022")
    riga = riga_tabella("L120*80*10", "283664", "1062", fornito="CELESTRI")
    tab = scheda("packing_costruttore", {"titolo": V("Copertura")}, [riga])
    r = _con_packing([("t.pdf", 1, tab), ("d.pdf", 1, d), ("c.pdf", 1, beltrame)])
    assert [v["stato"] for v in r["voci"]] == ["DEDOTTO"], [(v["motivi"], v["avvisi"]) for v in r["voci"]]
    v = r["voci"][0]
    assert any("letto 1002" in a for a in v["avvisi"])
    # se il costruttore non dichiara quel materiale, il certificato resta fuori: nessuna voce "dal certificato"
    # che chieda il DDT 1002 (prima della 0.7.1 ne nasceva una)
    altra = scheda("packing_costruttore", {"titolo": V("Copertura")}, [riga_tabella("HEB 180", "777", "200")])
    r2 = _con_packing([("t.pdf", 1, altra), ("d.pdf", 1, d), ("c.pdf", 1, beltrame)])
    assert [v["origine"] for v in r2["voci"]] == ["costruttore"]


def test_titolo_diverso_da_pagina_a_pagina_non_divide_la_voce():
    """0.7.1 (Viollier): il ciclo TELAI di tre pagine è letto con titolo 'RINTRACCIABITA' MATERIALI' a pagina 1 e 'VIA
    VIOLLIER MILANO' a pagina 3: stesso certificato, DDT e profilo nello stesso file -> una voce, titoli uniti."""
    from fascicolo_inventato import V, certificato, ddt, riga_tabella, scheda, timbro

    p1 = scheda(
        "packing_costruttore", {"titolo": V("RINTRACCIABITA' MATERIALI")}, [riga_tabella("HEB 180", "777", "200")]
    )
    p3 = scheda("packing_costruttore", {"titolo": V("VIA VIOLLIER MILANO")}, [riga_tabella("HEB 180", "777", "200")])
    altro = scheda("packing_costruttore", {"titolo": V("Portali")}, [riga_tabella("HEB 180", "777", "200")])
    cert = certificato("99-777", [("HEB 180", "S275J0+AR", "H1001")], [timbro("200")])
    r = _con_packing(
        [
            ("ciclo.pdf", 1, p1),
            ("ciclo.pdf", 3, p3),
            ("ciclo2.pdf", 1, altro),
            ("d.pdf", 1, ddt("200", ["TRAVE HEB 180"])),
            ("c.pdf", 1, cert),
        ]
    )
    parti = sorted(v["parte_opera"] for v in r["voci"])
    assert parti == ["Portali", "RINTRACCIABITA' MATERIALI / VIA VIOLLIER MILANO"]  # un altro file resta un'altra voce
    assert all(v["stato"] == "PROVATO" for v in r["voci"])


def test_nome_del_file_del_certificato_che_cita_il_ddt_fa_da_ponte_dedotto():
    """0.7.2 (Valentino): due certificati con lo stesso piatto, timbri a penna illeggibili; il file del primo si
    chiama 'certificato ddt 300.pdf': è lui, DEDOTTO con avviso. Senza il nome resterebbe 'più certificati'."""
    from fascicolo_inventato import certificato, ddt

    fogli = [
        ("ddt300.pdf", 1, ddt("300", ["FERRO U 200", "RIF. COMM NC 2501", "PIATTO 60x10"])),
        (
            "certificato ddt 300.pdf",
            1,
            certificato("A1", [("FLAT 60X10", "S275JR", "K1001"), ("UPN 200", "S275JR", "K2002")]),
        ),
        ("altri/certificato ddt 999.pdf", 1, certificato("B2", [("FLAT 60X10", "S275JR", "K3003")])),
    ]
    r = _senza_packing(fogli)
    per_voce = {v["voce"]: v for v in r["voci"]}
    assert set(per_voce) == {"UPN 200", "PIATTO 60x10"}  # la riga 'RIF. COMM' non è una voce
    piatto = per_voce["PIATTO 60x10"]
    assert piatto["stato"] == "DEDOTTO" and piatto["colonne"]["COLATA"]["v"] == "K1001"
    assert any("nome del file" in m for m in per_voce["PIATTO 60x10"]["motivi"])
    assert any("nome del file" in a for a in per_voce["PIATTO 60x10"]["avvisi"])
    assert per_voce["UPN 200"]["stato"] == "DEDOTTO" and per_voce["UPN 200"]["colonne"]["COLATA"]["v"] == "K2002"


def test_tra_piu_certificati_con_il_ponte_dal_nome_vince_il_timbro_poi_il_profilo_esatto():
    """0.7.2 (Valentino): un PDF 'certificati piatti DDT 300.pdf' con tre certificati: tutti hanno il ponte dal
    nome; per il piatto 110x8 vince il certificato con il timbro, per il 150x10 quello con il profilo esatto."""
    from fascicolo_inventato import certificato, ddt, timbro

    f = "LAMINATI PIATTI/certificati piatti DDT 300.pdf"
    fogli = [
        ("ddt300.pdf", 1, ddt("300", ["PIATTO 110x8", "PIATTO 150x10"])),
        (f, 1, certificato("A1", [("FLAT 110X8", "S275JR", "K1001")], [timbro("300", a_mano=True)])),
        (f, 2, certificato("B2", [("FLAT 200X8", "S275JR", "K2002"), ("FLAT 150X10", "S275JR", "K2003")])),
        (f, 3, certificato("C3", [("LAMIERA 10x2000x6000", "S275JR", "K3003")])),
    ]
    r = _senza_packing(fogli)
    per_voce = {v["voce"]: v for v in r["voci"]}
    assert (
        per_voce["PIATTO 110x8"]["stato"] == "DEDOTTO" and per_voce["PIATTO 110x8"]["colonne"]["COLATA"]["v"] == "K1001"
    )
    assert (
        per_voce["PIATTO 150x10"]["stato"] == "DEDOTTO"
        and per_voce["PIATTO 150x10"]["colonne"]["COLATA"]["v"] == "K2003"
    )


def test_lettera_del_distributore_riconosciuta_dal_protocollo_nel_nome_del_file():
    """0.7.3 (Gstaad): la lettera Reyher cita il DDT e il protocollo 'RN2000689815', che è nel nome del file del
    certificato (il cui numero è un altro): è un ponte. La bulloneria si normalizza anche in inglese."""
    from fascicolo_inventato import V, certificato, ddt, scheda

    f = "845_RN2000689815_0082391771_000080.pdf"
    lettera = scheda(
        "lettera_accompagnamento",
        {"emittente": V("F. REYHER Nchfg. GmbH & Co. KG"), "ddt_citato": V("82391771")},
        [{"posizione": V("60"), "articolo": V("4017.08204.0120.050"), "certificato": V("RN2000689815")}],
    )
    # qualità vuota sul certificato: il DDT inventato dice S275JR su ogni riga e la classe 8.8 lo scarterebbe
    cert = certificato("YF25RY498-46019", [("HEX BOLT-ISO4017 ISO FIT-M12X50-8.8U", "", "B1-2503163")])
    fogli = [
        (
            "ddt.pdf",
            1,
            ddt("82391771", ["I 4017 8.8U CE nut M 12 x 50 --- HDG SB"], emittente="F. REYHER Nchfg. GmbH & Co. KG"),
        ),
        ("845_RN2000692061_0082391771_000070.pdf", 1, lettera),  # la lettera sta nel file del protocollo dopo
        (f, 2, cert),
    ]
    r = _senza_packing(fogli)
    v = _voce(r, "VITE M12x50")
    assert v["stato"] == "PROVATO" and v["colonne"]["COLATA"]["v"] == "B1-2503163"


def test_certificato_ancorato_a_un_ddt_del_fascicolo_non_genera_voci_fantasma():
    """0.7.3 (Gstaad): certificato con due timbri, uno per il DDT 2323 (nel fascicolo), uno di una vendita
    precedente (DDT 3330, assente): niente voce 'dal certificato' che chieda il DDT 3330."""
    from fascicolo_inventato import certificato, ddt, timbro

    cert = certificato(
        "219179", [("LAMIERA 5x1500x3000", "S275JR", "A52/1")], [timbro("3330", a_mano=True), timbro("2323")]
    )
    r = _senza_packing([("ddt.pdf", 1, ddt("2323", ["LAMIERA SP.5 1500X3000"])), ("c.pdf", 1, cert)])
    assert [v["origine"] for v in r["voci"]] == ["dai_ddt"] and r["voci"][0]["stato"] == "PROVATO"
    # tubi: stesse misure in comune o niente
    from traccia.motore import _affine

    assert _affine("TUBO 150x100", "TUBO 150x100x6") and not _affine("TUBO 100x100x3", "TUBO 100x100x5")


def test_certificato_intestato_a_un_altro_commerciante_non_vale_per_esclusione():
    """0.7.3 (Gstaad): i dadi M12 di Viteria non hanno certificato; quello dei dadi Reyher (intestato a Reyher, altro
    commerciante del fascicolo) non si prende 'per esclusione'."""
    from fascicolo_inventato import certificato, ddt

    c = certificato("YF25", [("HEX NUT-ISO4032-M12-8", "", "J431110101")])
    c["testata"]["cliente"]["v"] = "F. REYHER Nchfg. GmbH & Co. KG"
    fogli = [
        ("v.pdf", 1, ddt("2026/10188", ["DADI ES. CLASSE 8 M 12 tZn"], emittente="VITERIA EUGANEA SpA")),
        ("r.pdf", 1, ddt("82391771", ["I 4017 8.8U CE nut M 12 x 50"], emittente="F. REYHER Nchfg. GmbH & Co. KG")),
        ("c.pdf", 1, c),
    ]
    r = _senza_packing(fogli)
    dadi = _voce(r, "DADO M12")
    assert dadi["stato"] == "MANCANTE" and any("intestato a" in s for s in dadi["scartati"])


def test_tra_due_certificati_timbrati_per_lo_stesso_ddt_vale_quello_con_il_segno_a_mano():
    """0.7.3 (Gstaad): due certificati CELSA con l'UPN 160, entrambi timbrati per il DDT 4563: vale quello con la
    spunta sulla riga."""
    from fascicolo_inventato import certificato, ddt, timbro

    a = certificato(
        "04461778", [("UPN 160", "S275JR", "CE259891"), ("UPN 100", "S275JR", "CE637667")], [timbro("4563")]
    )
    a["segni"] = [{"tipo": "spunta", "riga": 0}]
    b = certificato("202572745", [("UPN 160", "S275JR", "CE260286")], [timbro("4563")])
    r = _senza_packing([("d.pdf", 1, ddt("4563", ["UNP 160"])), ("a.pdf", 1, a), ("b.pdf", 1, b)])
    v = _voce(r, "UPN 160")
    assert v["stato"] == "PROVATO" and v["colonne"]["COLATA"]["v"] == "CE259891"


def test_ddt_dichiarato_come_coda_e_colata_con_la_sigla_del_commerciante():
    """0.7.4 (progresso): la tabella del costruttore scrive il DDT '12000/' e il DDT Vanoli porta '1/12000' con
    'IPE MM. 400 CERT.COL. DU123329BJ0'; il certificato Duferco ha due IPE 400, colate 123329B e 999999B. La colata
    dichiarata (con la sigla DU davanti) sceglie la riga; senza timbro resta DEDOTTO."""
    from fascicolo_inventato import V, certificato, riga_tabella, scheda

    tab = scheda(
        "packing_costruttore",
        {"costruttore": V("COSTRUTTORE 001 SRL"), "titolo": V("Struttura scala")},
        [
            riga_tabella(
                "PROFILO S275J0 IPE 400 - A MIS/DISEGNO (66,3Kg/m)", "", "12000/", fornito="VANOLI FERRO S.P.A."
            ),
            riga_tabella("FINITURA GREZZO", "", "", fornito="COSTRUTTORE 001 SRL"),
            riga_tabella("BARRA FILETTATA Zn 8.8 M12x1000", "", "8603/", fornito="VITERIE OROBICHE SPA"),
        ],
    )
    d1 = scheda(
        "ddt",
        {
            "emittente": V("vanoli ferro S.p.A."),
            "destinatario": V("COSTRUTTORE 001 SRL"),
            "numero": V("1/12000"),
            "data": V("08/06/2021"),
        },
        [
            {
                "descrizione": V("TRAVI IPE MM. 400 (3°) S275 CERT.COL. DU123329BJ0"),
                "profilo": V("IPE MM. 400"),
                "qualita": V("S275"),
                "quantita": V("142"),
                "servizio": V("no"),
            }
        ],
    )
    d2 = scheda(
        "ddt",
        {
            "emittente": V("VITERIE OROBICHE s.p.a."),
            "destinatario": V("COSTRUTTORE 001 SRL"),
            "numero": V("2021-S_DVE-0008603"),
            "data": V("09/06/2021"),
        },
        [
            {
                "descrizione": V("BARRA FILETTATA 8.8 D.12X1MT"),
                "profilo": V(""),
                "qualita": V("8.8"),
                "quantita": V("7"),
                "servizio": V("no"),
            }
        ],
    )
    c1 = certificato(
        "354 2021", [("IPE 400", "S275J0 +AR", "123329B"), ("IPE 400", "S275J0 +AR", "999999B")], produttore="DUFERCO"
    )
    c1["testata"]["cliente"] = V("VANOLI FERRO SPA")
    c2 = certificato(
        "C3085-042-19",
        [("THREADED RODS M12X1.000 CLASS 8.8 PL", "8.8", "G191227813")],
        produttore="VITERIE OROBICHE S.p.A.",
    )
    c2["testata"]["cliente"] = V("VITERIE OROBICHE SPA")
    r = _senza_packing(
        [
            ("registro.pdf", 1, tab),
            ("plico.pdf", 3, d1),
            ("plico.pdf", 59, d2),
            ("plico.pdf", 7, c1),
            ("plico.pdf", 62, c2),
        ]
    )
    per_voce = {v["voce"]: v for v in r["voci"]}
    assert not any(v.startswith("FINITURA") for v in per_voce)  # riga di finitura: non è una voce
    ipe = next(v for k, v in per_voce.items() if "IPE 400" in k)
    assert ipe["stato"] == "DEDOTTO" and ipe["colonne"]["COLATA"]["v"] == "123329B"
    assert ipe["colonne"]["DDT COMMERCIANTE"]["v"].startswith("DDT n. 1/12000")
    assert any("DU123329BJ0" in m for m in ipe["motivi"])
    barra = per_voce["BARRA FILETTATA Zn 8.8 M12x1000"]
    assert barra["stato"] == "DEDOTTO" and barra["colonne"]["COLATA"]["v"] == "G191227813"
    assert barra["colonne"]["DDT COMMERCIANTE"]["v"].startswith("DDT n. 2021-S_DVE-0008603")
