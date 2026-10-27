"""Fascicolo inventato per i test: aziende, numeri e colate non esistono. Simula le schede che scriverebbe Claude."""

from traccia.famiglie import campi


def V(v: str = "", cit: str | None = None, zona: list | None = None) -> dict:
    return {"v": v, "cit": (v if cit is None else cit) if v else "", "zona": zona or []}


def scheda(
    famiglia: str,
    testata: dict | None = None,
    righe: list[dict] | None = None,
    timbri=None,
    segni=None,
    riferimenti=None,
    continua=False,
    orientamento=0,
) -> dict:
    c_testata, c_righe = campi()[famiglia]
    t = {k: (testata or {}).get(k, V()) for k in c_testata}
    rr = [{k: r.get(k, V()) for k in c_righe} for r in (righe or [])]
    citazioni = [x["cit"] for x in t.values()] + [x["cit"] for r in rr for x in r.values()]
    citazioni += [x["cit"] for x in (riferimenti or [])]
    citazioni += [t[k] for t in (timbri or []) for k in ("chi", "testo", "ddt_citato", "data_ddt", "destinatario")]
    return {
        "famiglia": famiglia,
        "utile": famiglia not in ("da_escludere", "illeggibile"),
        "motivo": "test",
        "orientamento": orientamento,
        "bianca": False,
        "continua_pagina_prima": continua,
        "trascrizione": "\n".join(c for c in citazioni if c),
        "testata": t,
        "righe": rr,
        "riferimenti": riferimenti or [],
        "timbri": timbri or [],
        "segni": segni or [],
        "avvisi": [],
    }


def timbro(ddt: str, a_mano: bool = False) -> dict:
    return {
        "chi": "FORNITORE 001",
        "testo": f"COPIA CONFORME Rif. Ns. ddt n. {ddt}",
        "ddt_citato": ddt,
        "data_ddt": "",
        "destinatario": "",
        "a_mano": a_mano,
        "zona": [600, 50, 950, 120],
    }


def riga_tabella(materiale, certificato, ddt, emesso="PRODUTTORE 001", fornito="FORNITORE 001 SRL", qualita="S275JR"):
    return {
        "materiale": V(materiale),
        "qualita": V(qualita),
        "certificato": V(certificato),
        "emesso_da": V(emesso),
        "fornito_da": V(fornito),
        "ddt": V(ddt),
    }


def ddt(numero, righe, emittente="FORNITORE 001 SRL", destinatario="COSTRUTTORE 001 SRL"):
    return scheda(
        "ddt",
        {"emittente": V(emittente), "destinatario": V(destinatario), "numero": V(numero), "data": V("01/02/2026")},
        [
            {"descrizione": V(d), "profilo": V(d), "qualita": V("S275JR"), "quantita": V("1"), "servizio": V("no")}
            for d in righe
        ],
    )


def certificato(numero, righe, timbri=None, pagina_di="", produttore="PRODUTTORE 001 SPA", segni=None):
    return scheda(
        "certificato_31",
        {
            "produttore": V(produttore),
            "numero": V(numero),
            "data": V("10/01/2026"),
            "cliente": V("FORNITORE 001 SRL"),
            "pagina_di": V(pagina_di),
        },
        [{"profilo": V(p), "qualita": V(q), "colata": V(c)} for p, q, c in righe],
        timbri=timbri,
        segni=segni,
    )


def fascicolo() -> list[tuple[str, int, dict]]:
    """(file, pagina, scheda) in ordine."""
    tab = scheda(
        "packing_costruttore",
        {"costruttore": V("COSTRUTTORE 001 SRL"), "titolo": V("Telai")},
        [
            riga_tabella("HEB 180", "777", "200"),
            riga_tabella("PL10*60", "5502", "300"),
            riga_tabella("PL8*120", "5503", "300", qualita="S355J2"),
            riga_tabella("PL8*180", "5503", "300", qualita="S355J2"),
            riga_tabella("PL10*90", "5504", "400"),
            riga_tabella("PL10*155", "5505", "500"),
            riga_tabella("HEA 140", "5506", "600", fornito="FORNITORE 002 SRL"),
        ],
    )
    return [
        ("tabella.pdf", 1, tab),
        (
            "dop.pdf",
            1,
            scheda(
                "dop_costruttore",
                {
                    "fabbricante": V("COSTRUTTORE 001 SRL"),
                    "numero_dop": V("D-01"),
                    "data": V("05/03/2026"),
                    "norma": V("EN 1090-1"),
                },
            ),
        ),
        ("ddt200.pdf", 1, ddt("200", ["TRAVE HEB 180"])),
        ("ddt300.pdf", 1, ddt("300", ["PIATTO 60x10", "LAM. SP=8 LA=2000"])),
        ("ddt500.pdf", 1, ddt("500", ["LARGHI PIATTI 160x10"])),
        ("ddt600.pdf", 1, ddt("600", ["TRAVE HEA 140"], emittente="FORNITORE 002 SRL")),
        ("cert777.pdf", 1, certificato("99-777", [("HEB 180", "S275J0+AR", "H1001")], [timbro("200")])),
        ("cert5502.pdf", 1, certificato("5502", [("FLAT 60X10", "S275JR", "H2002")])),
        (
            "cert5503.pdf",
            1,
            certificato(
                "5503", [("LAMIERA 8x2000x6000", "S355J2+N", "H3003"), ("LAMIERA 8x2000x6000", "S355J2+N", "H3004")]
            ),
        ),
        ("cert5505.pdf", 1, certificato("5505", [("FLAT 160X10", "S275JR", "H5005")], [timbro("500")])),
        ("cert5506.pdf", 1, certificato("5506", [("HEA 140", "S275JR", "H6006")], [timbro("600", a_mano=True)])),
        ("varie.pdf", 1, scheda("da_escludere")),
    ]
