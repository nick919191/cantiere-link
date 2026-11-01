"""Preparazione: ZIP corrotti o con nomi ambigui, TIFF multipagina, file preparati a metà (A4, A5, M10)."""

import io
import zipfile

from pdf_minimo import pdf_con_testo
from PIL import Image

from traccia import preparazione
from traccia.preparazione import prepara


def _lavoro(radice, nome="prep"):
    cartella = radice / "lavori" / nome
    (cartella / "ingresso").mkdir(parents=True)
    return cartella


def test_zip_corrotto_non_blocca_gli_altri_file(radice):
    cartella = _lavoro(radice)
    (cartella / "ingresso" / "rotto.zip").write_bytes(b"PK\x03\x04 non sono un archivio")
    (cartella / "ingresso" / "buono.pdf").write_bytes(pdf_con_testo(["DDT 1"]))
    elenco = prepara(cartella)
    assert [v["file"] for v in elenco if v["pid"]] == ["buono.pdf"]
    fallito = next(v for v in elenco if not v["pid"])
    assert fallito["file"] == "rotto.zip" and "BadZipFile" in fallito["errore"]
    assert (cartella / "ingresso" / "estratti" / "rotto" / ".complete").exists()
    # la seconda preparazione non ritenta l'estrazione e dà lo stesso esito
    assert prepara(cartella) == elenco


def test_zip_con_nomi_diversi_solo_per_maiuscole(radice):
    cartella = _lavoro(radice)
    with zipfile.ZipFile(cartella / "ingresso" / "doc.zip", "w") as z:
        z.writestr("A.pdf", pdf_con_testo(["uno"]))
        z.writestr("a.pdf", pdf_con_testo(["due"]))
        z.writestr("a.PDF", pdf_con_testo(["tre"]))
    elenco = prepara(cartella)
    nomi = sorted(v["file"] for v in elenco)
    assert len(nomi) == 3 and all(v["pid"] for v in elenco)
    assert nomi == ["estratti/doc/A (2).pdf", "estratti/doc/A (3).PDF", "estratti/doc/A.pdf"] or len(set(nomi)) == 3


def test_tiff_multipagina_una_pagina_per_fotogramma(radice):
    cartella = _lavoro(radice)
    fotogrammi = [Image.new("RGB", (200, 300), colore) for colore in ("white", "black", "gray")]
    fotogrammi[0].save(cartella / "ingresso" / "scansione.tif", save_all=True, append_images=fotogrammi[1:])
    elenco = prepara(cartella)
    assert [(v["pagina"], v["pagine_file"]) for v in elenco] == [(1, 3), (2, 3), (3, 3)]
    assert len({v["impronta"] for v in elenco}) == 3
    info = preparazione.info_pagina(cartella, "p0002")
    with Image.open(io.BytesIO(preparazione.ritaglio(cartella, info, [0, 0, 1000, 1000]))) as img:
        assert img.getpixel((5, 5)) == (0, 0, 0)  # secondo fotogramma, nero


def test_file_preparato_a_meta_si_ritenta(radice, monkeypatch):
    cartella = _lavoro(radice)
    (cartella / "ingresso" / "sano.pdf").write_bytes(pdf_con_testo(["sano"]))
    (cartella / "ingresso" / "zoppo.pdf").write_bytes(pdf_con_testo(["zoppo"]))
    vero = preparazione._pagine_di

    def zoppo(sorgente):
        for pagina in vero(sorgente):
            yield pagina
            if sorgente.name == "zoppo.pdf":
                raise RuntimeError("pagina 2 illeggibile")

    monkeypatch.setattr(preparazione, "_pagine_di", zoppo)
    elenco = prepara(cartella)
    assert [v["file"] for v in elenco if v["pid"]] == ["sano.pdf"]
    fallito = next(v for v in elenco if not v["pid"])
    assert fallito["file"] == "zoppo.pdf" and fallito["pagine_parziali"] == 1
    assert not any(p.name.startswith("p0002") for p in (cartella / "pagine").iterdir())
    monkeypatch.setattr(preparazione, "_pagine_di", vero)
    elenco = prepara(cartella)  # ri-preparazione: il file a metà si ritenta da capo
    assert sorted(v["file"] for v in elenco if v["pid"]) == ["sano.pdf", "zoppo.pdf"]
    assert all(v["pid"] for v in elenco)


def test_pdfium_si_usa_un_thread_alla_volta(radice, monkeypatch):
    """Preparazione, ritagli e riordino possono girare insieme: pdfium senza blocco fa cadere l'app (0xc0000374)."""
    import pypdfium2 as pdfium
    from test_flusso import _crea_lavoro, _leggi_tutto

    from traccia import cli
    from traccia.preparazione import PDFIUM, info_pagina, ritaglio

    aperture = []
    originale = pdfium.PdfDocument.__init__

    def controlla(self, *args, **kwargs):
        aperture.append(PDFIUM._is_owned())
        originale(self, *args, **kwargs)

    monkeypatch.setattr(pdfium.PdfDocument, "__init__", controlla)
    cartella, schede = _crea_lavoro(radice)
    pagine = _leggi_tutto(cartella, schede)
    cli.componi("prova")
    pdf = next(p for p in pagine if p["file"].endswith(".pdf"))
    assert ritaglio(cartella, info_pagina(cartella, pdf["pid"]), [0, 0, 500, 500])
    assert len(aperture) > 1 and all(aperture)
