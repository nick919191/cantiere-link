"""Corpus di studio: le pagine dei cantieri SCL (Gstaad, Viollier, Valentino) con famiglia, testo e sonde.

Sola lettura sulla cartella SCL. Per ogni pagina:
- famiglia: dalla classificazione dell'elaborazione (verificata a mano per le pagine "verde"/"verde_revisione");
- testo: OCR Mistral già pagato (dati/letture) oppure testo nativo del PDF originale;
- sonde: i valori che il motore ha usato da quella pagina (prove.json): numeri, colate, profili, date, DoP...
  Una sonda è "osservabile" se si trova nel testo intero; un taglio la "perde" se non si trova più nel testo tagliato.
"""

import json
import re
import unicodedata
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

import pypdfium2 as pdfium

CANTIERI = {"Gstaad": "3f655474", "Viollier": "7674671e", "Valentino": "27f3cf70"}


def compatto(testo: str) -> str:
    t = unicodedata.normalize("NFKD", testo or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


class _Tabella(HTMLParser):
    """Tabella HTML di Mistral -> righe markdown «| a | b |» (le celle unite restano una cella)."""

    def __init__(self):
        super().__init__()
        self.righe, self.riga, self.cella, self.dentro = [], [], [], False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.riga = []
        elif tag in ("td", "th"):
            self.cella, self.dentro = [], True
            self.unite = int(dict(attrs).get("colspan") or 1)
        elif tag == "br" and self.dentro:
            self.cella.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.riga.append(re.sub(r"\s+", " ", "".join(self.cella)).strip())
            self.riga += [""] * (self.unite - 1)  # celle unite: colonne allineate alle intestazioni
            self.dentro = False
        elif tag == "tr":
            self.righe.append("| " + " | ".join(self.riga) + " |")

    def handle_data(self, data):
        if self.dentro:
            self.cella.append(data)


def _con_tabelle(markdown: str, tabelle: list) -> str:
    def sostituisci(m):
        i = int(m.group(1))
        if i >= len(tabelle):
            return m.group(0)
        t = tabelle[i]
        html = t.get("content", "") if isinstance(t, dict) else str(t)
        parser = _Tabella()
        parser.feed(html)
        return "\n".join(parser.righe)

    return re.sub(r"\[tbl-(\d+)\.\w+\]\(tbl-\d+\.\w+\)", sostituisci, markdown)


def _testo_nativo(scl: Path, chiave: str) -> str:
    sha, pagina = chiave.rsplit("_", 1)
    sorgente = next((scl / "dati" / "originali").glob(sha + ".*"), None)
    if not sorgente or sorgente.suffix.lower() != ".pdf":
        return ""
    doc = pdfium.PdfDocument(sorgente)
    try:
        pag = doc[int(pagina) - 1]
        tp = pag.get_textpage()
        testo = tp.get_text_range()
        tp.close()
        pag.close()
        return testo.replace("\r\n", "\n")
    finally:
        doc.close()


def _sonde(prove: dict) -> dict[tuple[str, int], list[tuple[str, str]]]:
    """(id documento, pagina) -> [(tipo, valore)]."""
    per_pagina = defaultdict(list)

    def metti(doc, pagina, tipo, valore):
        valore = str(valore or "").strip()
        if doc and pagina and len(compatto(valore)) >= 3 and "non individuato" not in valore.lower():
            per_pagina[(doc, int(pagina))].append((tipo, valore))

    for c in prove.get("certificati", []):
        for k in ("numero", "produttore", "data"):
            metti(c.get("doc"), c.get("pagina"), f"certificato.{k}", c.get(k))
    for r in prove.get("righe_certificato", []):
        doc, _, pagina = str(r.get("cert", "")).partition("@")
        for k in ("colata", "profilo", "qualita"):
            metti(doc, pagina or 0, f"riga_cert.{k}", r.get(k))
    for r in prove.get("righe_ddt", []):
        for k in ("ddt", "data", "qualita"):
            metti(r.get("doc"), r.get("pagina"), f"riga_ddt.{k}", r.get(k))
    for d in prove.get("dop", []):
        for k in ("numero_dop", "fpc", "organismo", "norma"):
            metti(d.get("doc"), d.get("pagina"), f"dop.{k}", d.get(k))
    for p in prove.get("packing", []):
        for k in ("ddt", "data", "materiale"):
            metti(p.get("doc"), p.get("pagina"), f"packing.{k}", p.get(k))
    for s in prove.get("segni", []):
        metti(s.get("doc"), s.get("pagina"), "segno.ddt_citato", s.get("ddt_citato"))
    return per_pagina


def carica(scl: Path) -> list[dict]:
    pagine = []
    for cantiere, prefisso in CANTIERI.items():
        cartella = next((scl / "dati" / "elaborazioni").glob(prefisso + "*"))
        classi = json.loads((cartella / "classificazione.json").read_text(encoding="utf-8"))
        prove = json.loads((cartella / "prove.json").read_text(encoding="utf-8"))
        id_per_file = {d["file"]: d["id"] for d in prove.get("documenti", [])}
        sonde = _sonde(prove)
        for c in classi:
            chiave = c["chiave"]
            lettura = scl / "dati" / "letture" / f"{chiave}.json"
            if lettura.exists():
                dati = json.loads(lettura.read_text(encoding="utf-8"))
                testo, fonte = _con_tabelle(dati.get("markdown", ""), dati.get("tabelle") or []), "ocr"
            else:
                testo, fonte = _testo_nativo(scl, chiave), "nativo"
            doc = id_per_file.get(c.get("documento"))
            pagine.append(
                {
                    "cantiere": cantiere,
                    "chiave": chiave,
                    "documento": c.get("documento", ""),
                    "pagina": c.get("pagina"),
                    "famiglia": c.get("famiglia") or "non_classificata",
                    "emittente": c.get("emittente") or "",
                    "stato": c.get("stato"),
                    "fonte": fonte,
                    "testo": testo or "",
                    "sonde": sonde.get((doc, int(c.get("pagina") or 0)), []),
                }
            )
    return pagine


def osservabili(pagina: dict) -> list[tuple[str, str]]:
    intero = compatto(pagina["testo"])
    return [s for s in pagina["sonde"] if compatto(s[1]) in intero]


def perse(pagina: dict, tagliato: str) -> list[tuple[str, str]]:
    resto = compatto(tagliato)
    return [s for s in osservabili(pagina) if compatto(s[1]) not in resto]
