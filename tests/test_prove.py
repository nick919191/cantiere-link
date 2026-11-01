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
