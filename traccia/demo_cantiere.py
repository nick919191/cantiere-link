"""Cantiere di prova: 30 documenti inventati, una pagina ciascuno, in formato A5 con poco testo.

Serve come demo da rifar girare: aziende, numeri, colate e date non esistono. Le pagine sono piccole e corte
perché l'analisi con ChatGPT consumi pochi token (ogni pagina è un'immagine più il testo nativo).
"""

import json
import time
import uuid
from pathlib import Path

from . import percorsi
from .pdf_semplice import A5, pdf_con_testo

NOME = "Cantiere di prova (demo)"
COSTRUTTORE = "DEMO COSTRUZIONI SRL"
COMMERCIANTE = "DEMO ACCIAI SRL"
PRODUTTORE = "DEMO STEEL SPA"

# (profilo in tabella, qualità, certificato 3.1, DDT, descrizione sul DDT, profilo sul certificato, colata)
VOCI = [
    ("HEB 200", "S275JR", "1001", "101", "TRAVE HEB 200", "HEB 200", "H26001"),
    ("HEA 160", "S275JR", "1002", "102", "TRAVE HEA 160", "HEA 160", "H26002"),
    ("IPE 240", "S355J2", "1003", "103", "TRAVE IPE 240", "IPE 240", "H26003"),
    ("PL10*200", "S275JR", "1004", "104", "PIATTO 200x10", "FLAT 200X10", "H26004"),
    ("PL15*300", "S355J2", "1005", "105", "LARGO PIATTO 300x15", "FLAT 300X15", "H26005"),
    ("UPN 120", "S275JR", "1006", "106", "PROFILO UPN 120", "UPN 120", "H26006"),
    ("TUBO 100x100x5", "S355J2H", "1007", "107", "TUBOLARE 100x100x5", "SHS 100X100X5", "H26007"),
    ("L 80x80x8", "S275JR", "1008", "108", "ANGOLARE 80x80x8", "L 80X80X8", "H26008"),
]

# Certificati in più, non richiamati dalla tabella: finiscono tra i documenti non usati.
CERTIFICATI_EXTRA = [
    ("1009", "IPE 200", "S275JR", "H26009"),
    ("1010", "HEB 160", "S275JR", "H26010"),
    ("1011", "FLAT 150X12", "S355J2", "H26011"),
    ("1012", "UPN 100", "S275JR", "H26012"),
    ("1013", "HEA 200", "S355J2", "H26013"),
    ("1014", "FLAT 250X20", "S355J2", "H26014"),
    ("1015", "SHS 80X80X4", "S355J2H", "H26015"),
    ("1016", "L 60X60X6", "S275JR", "H26016"),
]


def _tabella() -> list[str]:
    righe = [
        f"{COSTRUTTORE} - TABELLA DI TRACCIABILITA' MATERIALI",
        "Commessa: DEMO-2026 - Telaio di prova",
        "N. | MATERIALE | QUALITA' | CERT. 3.1 | FORNITORE | DDT",
    ]
    for n, (profilo, qualita, cert, ddt, *_rest) in enumerate(VOCI, 1):
        righe.append(f"{n} | {profilo} | {qualita} | {cert} | {COMMERCIANTE} | {ddt}")
    righe.append(f"Certificati emessi da {PRODUTTORE}.")
    return righe


def _dop_costruttore() -> list[str]:
    return [
        "DICHIARAZIONE DI PRESTAZIONE n. DoP-DEMO-01",
        f"Fabbricante: {COSTRUTTORE}",
        "Prodotto: componenti strutturali in acciaio - Telaio di prova",
        "Norma: EN 1090-1:2009+A1:2011 - Classe di esecuzione EXC2",
        "Data: 05/03/2026",
    ]


def _ddt(voce) -> list[str]:
    profilo, qualita, cert, ddt, descrizione, *_rest = voce
    return [
        f"DOCUMENTO DI TRASPORTO n. {ddt} del 03/02/2026",
        f"Mittente: {COMMERCIANTE}",
        f"Destinatario: {COSTRUTTORE}",
        "Causale: vendita - Commessa DEMO-2026",
        f"Riga 1: {descrizione} - {qualita} - q.ta 2 - cert. 3.1 n. {cert}",
    ]


def _certificato(numero, profilo, qualita, colata, ddt=None) -> list[str]:
    righe = [
        "CERTIFICATO DI COLLAUDO 3.1 - EN 10204",
        f"Produttore: {PRODUTTORE}",
        f"Certificato n. {numero} del 10/01/2026",
        f"Cliente: {COMMERCIANTE}",
        f"Prodotto: {profilo} - {qualita} - Colata {colata}",
        "Analisi chimica e prove meccaniche conformi alla norma di prodotto.",
    ]
    if ddt:
        righe.append(f"Timbro: COPIA CONFORME - Rif. ns. DDT n. {ddt}")
    return righe


def _ce_prodotto(numero, prodotto) -> list[str]:
    return [
        f"DICHIARAZIONE DI PRESTAZIONE n. {numero}",
        f"Fabbricante: {PRODUTTORE}",
        f"Prodotto: {prodotto}",
        "Norma: EN 10025-1:2004 - Marcatura CE",
        "Data: 15/12/2025",
    ]


def documenti() -> list[tuple[str, list[str]]]:
    """(nome file, righe di testo) dei 30 documenti, in ordine di lettura."""
    docs = [("01_tabella_costruttore.pdf", _tabella()), ("02_dop_costruttore.pdf", _dop_costruttore())]
    for voce in VOCI:
        docs.append((f"ddt_{voce[3]}.pdf", _ddt(voce)))
    for _profilo, qualita, cert, ddt, _descrizione, profilo_cert, colata in VOCI:
        docs.append((f"cert_{cert}.pdf", _certificato(cert, profilo_cert, qualita, colata, ddt)))
    for numero, profilo, qualita, colata in CERTIFICATI_EXTRA:
        docs.append((f"cert_{numero}.pdf", _certificato(numero, profilo, qualita, colata)))
    docs.append(("ce_travi.pdf", _ce_prodotto("CE-DEMO-01", "Travi laminate a caldo S275JR / S355J2")))
    docs.append(("ce_piatti.pdf", _ce_prodotto("CE-DEMO-02", "Piatti e larghi piatti S275JR / S355J2")))
    docs.append(
        (
            "lettera_accompagnamento.pdf",
            [
                f"{COMMERCIANTE} - Lettera di accompagnamento",
                f"Spett.le {COSTRUTTORE}",
                "In allegato i certificati 3.1 relativi ai DDT da 101 a 108 della commessa DEMO-2026.",
                "Cordiali saluti.",
            ],
        )
    )
    docs.append(("nota_interna.pdf", ["Promemoria interno", "Verificare le consegne della settimana. Non pertinente."]))
    assert len(docs) == 30
    return docs


def crea() -> tuple[str, Path]:
    """Crea la cartella del cantiere di prova in lavori/ e ritorna (id, cartella). La preparazione è a parte."""
    id_lavoro = time.strftime("%Y%m%d-%H%M%S") + "-demo" + uuid.uuid4().hex[:4]
    cartella = percorsi.lavoro(id_lavoro)
    ingresso = cartella / "ingresso"
    ingresso.mkdir(parents=True)
    nomi = []
    for nome, righe in documenti():
        (ingresso / nome).write_bytes(pdf_con_testo(righe, A5, corpo=9))
        nomi.append(nome)
    (cartella / "info.json").write_text(
        json.dumps(
            {"nome": NOME, "creato": time.strftime("%d/%m/%Y %H:%M"), "file": nomi, "scartati": [], "demo": True},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return id_lavoro, cartella
