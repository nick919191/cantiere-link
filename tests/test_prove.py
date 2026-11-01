"""Dalle schede alle prove: ragioni sociali, copie dei DDT, partita IVA (C1, C8)."""

from fascicolo_inventato import V, ddt, scheda

from traccia.prove import costruisci


def _prove(fogli):
    pagine = [{"pid": f"p{i:04d}", "file": f, "pagina": n} for i, (f, n, _) in enumerate(fogli, 1)]
    return costruisci(pagine, {p["pid"]: s for p, (_, _, s) in zip(pagine, fogli, strict=True)})


def test_destinatario_con_indirizzo_e_sigla_per_esteso_e_il_costruttore():
    fogli = [
        ("a.pdf", 1, ddt("10", ["HEB 180"], emittente="FORNITORE 001 SRL", destinatario="C.O.S.T.R. SRL")),
        (
            "b.pdf",
            1,
            ddt(
                "20",
                ["IPE 200"],
                emittente="FORNITORE 002 SPA",
                destinatario="C.O.S.T.R. SRL COSTRUZIONI OFFICINE STRUTTURE TRAVI RHO VIA VERDI 3 20017 RHO",
            ),
        ),
        (
            "c.pdf",
            1,
            ddt("30", ["UPN 100"], emittente="FORNITORE 003 SRL", destinatario="COSTR S.r.l.\nVIA VERDI, 3\n20017 RHO"),
        ),
        (
            "d.pdf",
            1,
            ddt(
                "40", ["NR. 3 TRAVI"], emittente="Costruzioni Officine Strutture Travi Rho Srl", destinatario="CLIENTE"
            ),
        ),
    ]
    prove = _prove(fogli)
    assert prove["costruttore"] == "C.O.S.T.R. SRL"
    assert [d["tipo"] for d in prove["ddt"]] == ["commerciante_costruttore"] * 3 + ["costruttore_cliente"]


def test_stessa_partita_iva_stessa_azienda_anche_con_nome_diverso():
    d1 = ddt("10", ["HEB 180"], emittente="FORNITORE 001 SRL", destinatario="OFFICINE ALFA SRL")
    d1["testata"]["piva_destinatario"] = V("Partita IVA 01234567890", "Partita IVA 01234567890")
    d2 = ddt("20", ["IPE 200"], emittente="FORNITORE 002 SRL", destinatario="GRUPPO BETA SPA")
    d2["testata"]["piva_destinatario"] = V("P.IVA 01234567890", "P.IVA 01234567890")
    d3 = ddt("30", ["NR. 2 TRAVI"], emittente="BETA S.P.A.", destinatario="CANTIERE")
    d3["testata"]["piva_emittente"] = V("01234567890")
    dop = scheda(
        "dop_costruttore", {"fabbricante": V("ALFA S.R.L."), "piva": V("IT01234567890"), "norma": V("EN 1090-1")}
    )
    prove = _prove([("a.pdf", 1, d1), ("b.pdf", 1, d2), ("c.pdf", 1, d3), ("d.pdf", 1, dop)])
    assert prove["aziende"] == [["OFFICINE ALFA SRL", "GRUPPO BETA SPA", "BETA S.P.A.", "ALFA S.R.L."]]
    assert prove["costruttore"] == "ALFA S.R.L."
    assert [d["tipo"] for d in prove["ddt"]] == ["commerciante_costruttore"] * 2 + ["costruttore_cliente"]


def test_copie_dello_stesso_ddt_unite_anche_con_suffisso_incollato():
    # reale: 'SETAL S.P.A.' e 'SETALS.P.A.' sulla copia; inventato: 'OFFICINE ALFA S.R.L.' e 'OFFICINE ALFASRL'
    fogli = [
        ("f.pdf", 1, ddt("2902", ["LAMIERA 8"], emittente="SETAL S.P.A.", destinatario="S.A.C.I.F. SRL")),
        ("f.pdf", 9, ddt("2902", ["LAMIERA 8"], emittente="SETALS.P.A.", destinatario="S.A.C.I.F. SRL")),
        ("g.pdf", 1, ddt("77", ["HEA 100"], emittente="OFFICINE ALFA S.R.L.", destinatario="S.A.C.I.F. SRL")),
        (
            "g.pdf",
            2,
            ddt("77", ["HEA 100"], emittente="OFFICINE ALFASRL", destinatario="SACIF SRL VIA NULLO 5 20129 MILANO"),
        ),
        ("g.pdf", 3, ddt("77", ["HEA 100"], emittente="OFFICINE GAMMA SRL", destinatario="SACIF SRL")),
    ]
    prove = _prove(fogli)
    assert [(d["numero"], d["pagine"], d["copie"]) for d in prove["ddt"]] == [
        ("2902", ["p0001", "p0002"], 2),
        ("77", ["p0003", "p0004"], 2),
        ("77", ["p0005"], 1),  # stesso numero ma altro emittente: altro DDT
    ]


def test_seconda_pagina_con_numero_letto_diverso_resta_nello_stesso_ddt():
    # reale: pagina 2 del DDT 8027 letta '2027'; inventato: pagina 2 del DDT 5100 letta '5700'
    p1 = ddt("8027", ["HEA 160"], emittente="FVS SPA", destinatario="S.A.C.I.F. S.R.L.")
    p1["testata"]["pagina_di"] = V("001")
    p2 = ddt("2027", ["UPN 160"], emittente="FVS SPA", destinatario="S.A.C.I.F. S.R.L.\nVIA NULLO, 5\n20129 MILANO")
    p2["testata"]["pagina_di"] = V("002")
    q1 = ddt("5100", ["IPE 120"], emittente="ALFA SRL", destinatario="BETA SRL")
    q2 = ddt(
        "5700", ["IPE 140"], emittente="ALFA SRL", destinatario="BETA SRL"
    )  # senza pagina_di: differisce di una cifra
    q3 = ddt("9999", ["IPE 160"], emittente="ALFA SRL", destinatario="BETA SRL")  # numero tutto diverso: altro DDT
    prove = _prove([("a.pdf", 2, p1), ("a.pdf", 3, p2), ("b.pdf", 1, q1), ("b.pdf", 2, q2), ("b.pdf", 3, q3)])
    assert [(d["numero"], d["pagine"]) for d in prove["ddt"]] == [
        ("8027", ["p0001", "p0002"]),
        ("5100", ["p0003", "p0004"]),
        ("9999", ["p0005"]),
    ]
    assert prove["ddt"][0]["avvisi"] == ["numero letto 2027 sulla pagina 3, 8027 sulle altre"]
    assert {r["chiave"] for r in prove["ddt"][0]["righe"]} == {"HEA 160", "UPN 160"}


def test_righe_del_ddt_con_colate_e_placche():
    # reale: colate scritte nella descrizione; inventato: campi colata e placca compilati dal lettore
    d = ddt("2902", ["SP.015X2450X6000 Placca: 24E6061124(A) Colata: 143343 Placca: 24E6061126(A) Colata: 442770"])
    d2 = ddt("77", ["LAMIERA 8x1500x3000"])
    d2["righe"][0]["colata"] = V("K100; K200")
    d2["righe"][0]["placca"] = V("P1; P2")
    d2["righe"][0]["certificato"] = V("5503")
    prove = _prove([("a.pdf", 1, d), ("b.pdf", 1, d2)])
    r = prove["ddt"][0]["righe"][0]
    assert r["chiave"] == "LAMIERA 15" and r["colate"] == ["143343", "442770"]
    assert r["placche"] == {"143343": ["24E6061124(A)"], "442770": ["24E6061126(A)"]}
    r = prove["ddt"][1]["righe"][0]
    assert r["colate"] == ["K100", "K200"] and r["placche"] == {"K100": ["P1"], "K200": ["P2"]}
    assert r["certificato"] == "5503" and r["fonti"]["colata"]


def test_lettera_con_righe_placca_colata_certificato():
    lettera = scheda(
        "lettera_accompagnamento",
        {"emittente": V("FORNITORE 001 SRL"), "ddt_citato": V("300"), "data_ddt": V("01/02/2026")},
        [
            {
                "articolo": V("LAM. CALDO 8x1500x6000"),
                "placca": V("P1"),
                "colata": V("H3003"),
                "certificato": V("5503"),
            },
            {
                "articolo": V("LAM. CALDO 8x1500x6000"),
                "placca": V("P2"),
                "colata": V("H3004"),
                "certificato": V("5503"),
            },
        ],
    )
    prove = _prove([("l.pdf", 1, lettera)])
    lt = prove["lettere"][0]
    assert lt["ddt_citato"] == "300" and lt["certificati"] == ["5503", "5503"]
    assert [(r["placca"], r["colata"]) for r in lt["righe"]] == [("P1", "H3003"), ("P2", "H3004")]


def test_terzista_conto_lavorazione_e_reso_non_sono_fornitori():
    """C9: costruttore -> zincatore (conto lavorazione) e reso del zincatore al cantiere alimentano DDT COSTRUTTORE,
    mai le voci. Reale (anonimo): reso che cita 'Reso Vs. ddt n.'; inventato: causale conto lavorazione."""
    from traccia.motore import elabora

    fogli = [
        ("a.pdf", 1, ddt("10", ["HEA 160"], emittente="FORNITORE 001 SRL", destinatario="COSTRUTTORE 001 SRL")),
        ("b.pdf", 1, ddt("20", ["IPE 200"], emittente="FORNITORE 002 SRL", destinatario="COSTRUTTORE 001 SRL")),
    ]
    uscita = ddt(
        "587",
        ["N. 14 Travi HEA 160", "N. 57 TUBO 76,1X5 L. 1320 mm"],
        emittente="Costruttore 001 S.r.l.",
        destinatario="ZINCATURA NORD SPA",
    )
    uscita["testata"]["causale"] = V("CONTO LAVORAZIONE")
    reso = ddt(
        "5.877",
        ["Ns. IC n. 6058/Z Reso Vs. ddt. n. 0000587 del 30/09/2025 TUBO 76,1x5"],
        emittente="zincatura nord spa",
        destinatario="COSTRUTTORE 001 SRL",
    )
    reso["riferimenti"] = [{"tipo": "ddt", "v": "0000587", "cit": "Reso Vs. ddt. n. 0000587", "zona": []}]
    reso["trascrizione"] += "\nReso Vs. ddt. n. 0000587"
    altro = ddt("99", ["UPN 100"], emittente="COSTRUTTORE 001 SRL", destinatario="CLIENTE FINALE SRL")
    prove = _prove(fogli + [("c.pdf", 1, uscita), ("d.pdf", 1, reso), ("e.pdf", 1, altro)])
    tipi = {d["numero"]: d["tipo"] for d in prove["ddt"]}
    assert tipi == {
        "10": "commerciante_costruttore",
        "20": "commerciante_costruttore",
        "587": "costruttore_terzista",
        "5.877": "terzista_cantiere",
        "99": "costruttore_cliente",
    }
    assert next(d for d in prove["ddt"] if d["numero"] == "587")["tramite"] == "ZINCATURA NORD SPA"
    r = elabora(prove)
    assert {v["voce"] for v in r["voci"]} == {"HEA 160", "IPE 200"}  # niente voci dal terzista
    colonna = r["voci"][0]["colonne"]["DDT COSTRUTTORE"]["v"]
    assert "DDT n. 587" in colonna and "tramite ZINCATURA NORD SPA" in colonna and "DDT n. 99" in colonna
    assert "5.877" in colonna and "reso al cantiere" in colonna


def test_reso_senza_causale_riconosciuto_dal_riferimento_al_ddt_del_costruttore():
    fogli = [
        ("a.pdf", 1, ddt("10", ["HEA 160"], emittente="FORNITORE 001 SRL", destinatario="COSTRUTTORE 001 SRL")),
        ("b.pdf", 1, ddt("20", ["IPE 200"], emittente="FORNITORE 002 SRL", destinatario="COSTRUTTORE 001 SRL")),
        (
            "c.pdf",
            1,
            ddt("300", ["N. 3 TRAVI HEA 160"], emittente="COSTRUTTORE 001 SRL", destinatario="VERNICIATURA SUD SRL"),
        ),
    ]
    reso = ddt("77", ["TRAVI HEA 160 verniciate"], emittente="VERNICIATURA SUD SRL", destinatario="COSTRUTTORE 001 SRL")
    reso["riferimenti"] = [{"tipo": "ddt", "v": "300", "cit": "300", "zona": []}]
    reso["trascrizione"] += "\n300"
    prove = _prove(fogli + [("d.pdf", 1, reso)])
    tipi = {d["numero"]: d["tipo"] for d in prove["ddt"]}
    assert tipi["300"] == "costruttore_terzista" and tipi["77"] == "terzista_cantiere"


def test_dop_en_1090_del_fornitore_intermedio_non_e_del_costruttore():
    """C11: la DoP EN 1090 del commerciante che taglia va in CE/DoP CENTRO della voce, non in CE/DoP COSTRUTTORE."""
    from traccia.motore import elabora

    fogli = [
        (
            "a.pdf",
            1,
            ddt(
                "8027",
                ["HEA 160"],
                emittente="FERRAMENTA VILLAFRANCA SIDERURGICA S.p.A.",
                destinatario="S.A.C.I.F. SRL",
            ),
        ),
        ("b.pdf", 1, ddt("20", ["IPE 200"], emittente="FORNITORE 002 SRL", destinatario="SACIF SRL")),
        (
            "c.pdf",
            1,
            scheda(
                "dop_costruttore",
                {
                    "fabbricante": V("FVS S.p.A."),
                    "numero_dop": V("9588.25"),
                    "norma": V("EN 1090-1:2009"),
                    "ddt_citato": V("8027"),
                },
            ),
        ),
        (
            "d.pdf",
            1,
            scheda(
                "dop_costruttore",
                {"fabbricante": V("FVS S.p.A."), "numero_dop": V("9000.25"), "norma": V("EN 1090-1:2009")},
            ),
        ),
        (
            "e.pdf",
            1,
            scheda(
                "dop_costruttore",
                {
                    "fabbricante": V("SACIF SRL"),
                    "numero_dop": V("D-7"),
                    "norma": V("EN 1090-1"),
                    "classe_esecuzione": V("EXC3"),
                },
            ),
        ),
    ]
    prove = _prove(fogli)
    assert prove["costruttore"] == "SACIF SRL"
    assert [d["numero_dop"] for d in prove["dop_costruttore"]] == ["D-7"]
    assert [d["numero_dop"] for d in prove["dop_fornitore_intermedio"]] == ["9588.25", "9000.25"]
    r = elabora(prove)
    v = next(v for v in r["voci"] if v["voce"] == "HEA 160")
    assert v["colonne"]["CE/DoP COSTRUTTORE"]["v"].startswith("DoP n. D-7")
    assert v["colonne"]["CE/DoP CENTRO"]["v"].startswith("DoP EN 1090 9588.25")  # quella che cita il DDT 8027
    assert "cita il DDT" in v["colonne"]["CE/DoP CENTRO"]["perche"]
    v = next(v for v in r["voci"] if v["voce"] == "IPE 200")
    assert v["colonne"]["CE/DoP CENTRO"]["v"] == "Non presente nel fascicolo"


def test_righe_del_ddt_con_elenco_di_colate_e_profilo_senza_misura():
    """Letture reali: colate nel campo come '143343; 442770; 339044' con le placche, profilo 'LAM. CALDO' senza
    misura (la misura sta nella descrizione), righe di sole colate che continuano la riga di materiale."""
    d = ddt("2902", ["SP.015X2450X6000", "LAM. CALDO S355J2 EN 10025-2 SPIAN. Pz 7 6000x1500x 8,00"])
    d["righe"][0]["colata"] = V("143343; 143343; 442770; 339044")
    d["righe"][0]["placca"] = V("24E6061124(A); 24E6061124(B); 24E6061126(A); 24EQ001796(A)")
    d["righe"][1]["profilo"] = V("LAM. CALDO")
    seguito = ddt("", ["", "SP.010X2000X6000"])
    seguito["righe"][0]["colata"] = V("C5051; C5081")
    seguito["righe"][0]["placca"] = V("C5051B (10-02B); C5081A (06-01A)")
    seguito["righe"][0]["descrizione"] = V("")
    seguito["righe"][0]["profilo"] = V("")
    prove = _prove([("a.pdf", 1, d), ("a.pdf", 2, seguito)])
    righe = prove["ddt"][0]["righe"]
    assert [r["chiave"] for r in righe] == ["LAMIERA 15", "LAMIERA 8", "LAMIERA 10"]
    assert righe[0]["colate"] == ["143343", "442770", "339044"]
    assert righe[0]["placche"]["143343"] == ["24E6061124(A)", "24E6061124(B)"]
    assert righe[1]["colate"] == ["C5051", "C5081"]  # riga di sole colate: alla riga di materiale prima
    assert righe[1]["placche"] == {"C5051": ["C5051B (10-02B)"], "C5081": ["C5081A (06-01A)"]}


def test_lista_di_rintracciabilita_letta_come_ddt_o_come_certificato_diventa_lettera():
    from fascicolo_inventato import certificato

    fogli = [
        ("a.pdf", 1, ddt("G02 / 51159", ["L.DA TRENO S355J2 Pz 8 6000x2500x15,00"], emittente="ROSSINI SPA")),
        ("b.pdf", 1, ddt("20", ["IPE 200"], emittente="FORNITORE 002 SRL")),
    ]
    lista = ddt("38747/ 51159", ["", ""], emittente="Rossini S.p.A. - Società Unipersonale")
    for r, (c, p) in zip(lista["righe"], (("SU36217", "X2590744"), ("SU35302", "X2590753")), strict=True):
        r["descrizione"] = V("")
        r["profilo"] = V("")
        r["colata"] = V(c)
        r["placca"] = V(p)
    # "certificato" emesso dal commerciante: è la sua lista placca -> colata
    finto = certificato(
        "6738/3332", [("LAM. CALDO 5,00 x1500,00 x 6000,00", "S355J2+N", "24305236")], produttore="ROSSINI SPA"
    )
    finto["testata"]["ddt_produttore"] = V("3332")
    finto["trascrizione"] += "\n3332"
    fogli += [
        ("c.pdf", 1, lista),
        ("d.pdf", 1, ddt("G01 / 3332", ["LAM. CALDO 6000x1500x5,00"], emittente="ROSSINI SPA")),
        ("e.pdf", 1, finto),
    ]
    prove = _prove(fogli)
    assert [d["numero"] for d in prove["ddt"]] == ["G02 / 51159", "20", "G01 / 3332"]
    assert prove["certificati"] == []
    liste = {lt["ddt_citato"]: lt for lt in prove["lettere"]}
    assert [(r["colata"], r["placca"]) for r in liste["G02 / 51159"]["righe"]] == [
        ("SU36217", "X2590744"),
        ("SU35302", "X2590753"),
    ]
    assert liste["G01 / 3332"]["righe"][0]["colata"] == "24305236" and liste["G01 / 3332"]["righe"][0][
        "articolo"
    ].startswith("LAM. CALDO")
    assert any("letta come DDT" in a for a in prove["ddt"][0]["avvisi"])


def test_emittente_uguale_al_destinatario_non_decide_il_ruolo():
    fogli = [
        ("a.pdf", 1, ddt("10", ["HEA 160"], emittente="FORNITORE 001 SRL", destinatario="COSTRUTTORE 001 SRL")),
        ("b.pdf", 1, ddt("20", ["IPE 200"], emittente="FORNITORE 002 SRL", destinatario="COSTRUTTORE 001 SRL")),
    ]
    sbagliato = ddt("6559", ["TUBO 219,1x12,5"], emittente="COSTRUTTORE 001 SRL", destinatario="ALTRO SRL")
    sbagliato["testata"]["piva_destinatario"] = V("01234567890")
    buono = ddt("30", ["UPN 100"], emittente="COSTRUTTORE 001 SRL", destinatario="CLIENTE SRL")
    buono["testata"]["piva_emittente"] = V("01234567890")
    prove = _prove(fogli + [("c.pdf", 1, sbagliato), ("d.pdf", 1, buono)])
    tipi = {d["numero"]: d["tipo"] for d in prove["ddt"]}
    assert tipi["6559"] == "fuori_perimetro" and tipi["30"] == "costruttore_cliente"
    assert any("stessa azienda" in a for a in next(d for d in prove["ddt"] if d["numero"] == "6559")["avvisi"])


def test_chiave_riga_preferisce_la_forma_riconosciuta():
    """DDT con descrizione e misure in campi separati: 'ANGOLARE A LATI UGUALI' + 'LT=50.0 LT=50.0 SP=5.0'."""
    from traccia.prove import _chiave_riga

    assert _chiave_riga("LT=50.0 LT=50.0 SP=5.0 LU=L.C.", "ANGOLARE A LATI UGUALI") == "ANGOLARE 50 50 5"
    assert _chiave_riga("SP=3.00 LA=1000 LU=2000", "LAMIERE A CALDO") == "LAMIERA 3"
    assert _chiave_riga("SP.012X2450X6000", "LAMIERA") == "LAMIERA 12"  # il campo profilo con la misura vince ancora


def test_certificato_spezzato_su_due_pagine_con_refuso_nel_produttore_resta_uno():
    """0.7.2 (Valentino): pagine 1 e 3 dello stesso certificato nello stesso PDF, produttore letto 'AFV Accisierie'
    e 'AFV Acclaierie': un certificato solo, non due con lo stesso numero."""
    from fascicolo_inventato import V, certificato

    c1 = certificato("47189", [("FLAT 100X10", "S275JR", "BE 1001")], produttore="AFV Accisierie Beltrame")
    c2 = certificato("47189", [("FLAT 20X10", "S275JR", "BE 1002")], produttore="AFV Acclaierie Beltrame")
    c2["testata"]["data"] = V("11/01/2026")  # anche la data letta diversa
    pagine = [
        {"pid": "p1", "file": "certificati.pdf", "pagina": 1},
        {"pid": "p2", "file": "certificati.pdf", "pagina": 3},
    ]
    prove = costruisci(pagine, {"p1": c1, "p2": c2})
    assert len(prove["certificati"]) == 1 and prove["certificati"][0]["pagine"] == ["p1", "p2"]
    # in due file diversi restano due certificati
    pagine2 = [{"pid": "p1", "file": "a.pdf", "pagina": 1}, {"pid": "p2", "file": "b.pdf", "pagina": 1}]
    assert len(costruisci(pagine2, {"p1": c1, "p2": c2})["certificati"]) == 2


def test_copia_del_certificato_senza_numero_si_unisce_a_quello_con_il_numero():
    """0.7.3 (Gstaad): seconda copia del certificato Duferco con il numero non letto ma stessa colata e stesso
    produttore: un certificato solo, con i timbri e i segni di entrambe le copie."""
    from fascicolo_inventato import V, certificato, timbro

    c1 = certificato("4323 2026", [("HEA 140", "S275J0+AR", "158548")], produttore="TRAVI E PROFILATI SPA")
    c2 = certificato("", [("HEA 140", "S275J0+AR", "158548"), ("HEB 500", "S355J2", "158670")], [timbro("5004")])
    c2["testata"]["produttore"] = V("Travi e Profilati di Pallanzeno")
    pagine = [{"pid": "p1", "file": "a.pdf", "pagina": 1}, {"pid": "p2", "file": "b.pdf", "pagina": 1}]
    prove = costruisci(pagine, {"p1": c1, "p2": c2})
    assert len(prove["certificati"]) == 1
    c = prove["certificati"][0]
    assert c["numero"] == "4323 2026" and c["pagine"] == ["p1", "p2"] and len(c["timbri"]) == 1
    assert {r["chiave"] for r in c["righe"]} == {"HEA 140", "HEB 500"}


def test_timbro_a_penna_letto_male_ripreso_per_data_e_emittente():
    """0.7.3 (Gstaad): '480' per '4870' sul timbro FVS del 29/05/26; il DDT FVS di quel giorno è uno solo."""
    from fascicolo_inventato import V, certificato, ddt, timbro

    t = timbro("480", a_mano=True)
    t["chi"], t["data_ddt"] = "FVS S.p.a.", "29/05/26"
    cert = certificato("202572745", [("UPN 160", "S275JR", "CE259891")], [t])
    d = ddt("4870", ["UNP 160"], emittente="FERRAMENTA VILLAFRANCA SIDERURGICA SPA")
    d["testata"]["data"] = V("29/05/2026")
    altro = ddt("4563", ["IPE 140"], emittente="FERRAMENTA VILLAFRANCA SIDERURGICA SPA")
    pagine = [{"pid": f"p{i}", "file": f"{i}.pdf", "pagina": 1} for i in range(3)]
    prove = costruisci(pagine, {"p0": cert, "p1": d, "p2": altro})
    tb = prove["certificati"][0]["timbri"][0]
    assert tb["ddt_citato"] == "4870" and tb["ddt_letto"] == "480"


def test_due_copie_dello_stesso_certificato_in_file_diversi_con_produttore_letto_diverso():
    """0.7.3 (Gstaad): 219179 letto 'METINVEST FERRIERA VALSIDER' in un file e 'FERRERA VALSIDER' in un altro, data
    uguale ma produttore no: stessa colata nelle righe, un certificato solo."""
    from fascicolo_inventato import certificato

    c1 = certificato(
        "219179", [("LAMIERA 5x1500x3000", "S355J2", "A02/25300264")], produttore="METINVEST FERRIERA VALSIDER"
    )
    c2 = certificato(
        "219179",
        [("LAMIERA 4x1500x3000", "S355J2", "A02/25300260"), ("LAMIERA 5x1500x3000", "S355J2", "A02/25300264")],
        produttore="FERRERA VALSIDER SPA",
    )
    pagine = [{"pid": "p1", "file": "a.pdf", "pagina": 1}, {"pid": "p2", "file": "b.pdf", "pagina": 1}]
    prove = costruisci(pagine, {"p1": c1, "p2": c2})
    assert len(prove["certificati"]) == 1 and {r["chiave"] for r in prove["certificati"][0]["righe"]} == {
        "LAMIERA 4",
        "LAMIERA 5",
    }
