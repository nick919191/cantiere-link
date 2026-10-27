"""Preparazione (deterministica): file caricati -> una immagine PNG e una scheda tecnica per ogni pagina.

Per ogni pagina: PNG a 150 dpi (quella che legge Claude), testo nativo del PDF con la posizione di ogni parola
(serve a calcolare le zone esatte), impronta del PNG (chiave dell'archivio), pagina bianca sì/no.
Gli originali non si toccano: gli ZIP si aprono in ingresso/estratti/.
"""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

DPI = 150
DPI_RITAGLIO = 300
ESTENSIONI_PDF = {".pdf"}
ESTENSIONI_IMMAGINE = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
SOGLIA_INCHIOSTRO = 0.0005  # quota di pixel scuri sotto cui una pagina senza testo è bianca
MAX_FILE_ZIP = 2000
MAX_BYTE_ZIP = 1_000_000_000
MAX_PROFONDITA_ZIP = 3


def _estrai_zip(zip_path: Path, destinazione: Path, budget=None, profondita=0) -> None:
    budget = budget if budget is not None else {"file": 0, "byte": 0}
    if profondita > MAX_PROFONDITA_ZIP:
        raise ValueError("troppi archivi annidati")
    with zipfile.ZipFile(zip_path) as z:
        membri = [m for m in z.infolist() if not m.is_dir()]
        budget["file"] += len(membri)
        budget["byte"] += sum(m.file_size for m in membri)
        if budget["file"] > MAX_FILE_ZIP or budget["byte"] > MAX_BYTE_ZIP:
            raise ValueError("archivio oltre i limiti di estrazione")
        nomi = set()
        for m in membri:
            nome = Path(m.filename.replace("\\", "/"))
            if nome.is_absolute() or ".." in nome.parts or nome.name.startswith(".") or ":" in str(nome):
                continue
            uscita = destinazione / zip_path.stem / nome
            if not uscita.resolve().is_relative_to(destinazione.resolve()):
                raise ValueError("percorso non valido nell’archivio")
            if str(nome).casefold() in nomi:
                raise ValueError("nomi duplicati nell’archivio")
            nomi.add(str(nome).casefold())
            uscita.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as src, uscita.open("wb") as dst:
                copiati = 0
                while blocco := src.read(1024 * 1024):
                    copiati += len(blocco)
                    if copiati > m.file_size or copiati > MAX_BYTE_ZIP:
                        raise ValueError("dimensione estratta non valida")
                    dst.write(blocco)
            if uscita.suffix.lower() == ".zip":
                _estrai_zip(uscita, uscita.parent, budget, profondita + 1)


def file_sorgente(ingresso: Path) -> list[Path]:
    """PDF e immagini da leggere, in ordine fisso (percorso relativo, senza maiuscole)."""
    estratti = ingresso / "estratti"
    budget = {"file": 0, "byte": 0}
    for z in sorted(ingresso.glob("*.zip")):
        complete = estratti / z.stem / ".complete"
        if not complete.exists():
            _estrai_zip(z, estratti, budget)
            complete.parent.mkdir(parents=True, exist_ok=True)
            complete.touch()
    validi = ESTENSIONI_PDF | ESTENSIONI_IMMAGINE
    tutti = [p for p in ingresso.rglob("*") if p.is_file() and p.suffix.lower() in validi]
    return sorted(tutti, key=lambda p: p.relative_to(ingresso).as_posix().casefold())


def _inchiostro(png: bytes) -> float:
    img = Image.open(io.BytesIO(png)).convert("L")
    img.thumbnail((400, 400))
    pixel = list(img.getdata())
    return sum(1 for v in pixel if v < 128) / max(len(pixel), 1)


def _ruota(u: float, v: float, gradi: int) -> tuple[float, float]:
    """Punto 0-1 della pagina non ruotata (origine in alto a sinistra) -> punto sull'immagine ruotata."""
    if gradi == 90:
        return 1 - v, u
    if gradi == 180:
        return 1 - u, 1 - v
    if gradi == 270:
        return v, 1 - u
    return u, v


def _parole(pagina: pdfium.PdfPage) -> tuple[str, list[list]]:
    """Testo nativo e parole con riquadro in coordinate 0-1000 dell'immagine (rotazione della pagina compresa)."""
    gradi = pagina.get_rotation() % 360
    w, h = pagina.get_size()
    if gradi in (90, 270):  # get_size dà la misura ruotata; i caratteri stanno nella pagina non ruotata
        w, h = h, w
    testo_pagina = pagina.get_textpage()
    n = testo_pagina.count_chars()
    testo = testo_pagina.get_text_range(0, n) if n else ""
    parole, corrente, riquadro = [], "", None

    def chiudi():
        if corrente and riquadro:
            x0, y0, x1, y1 = riquadro
            a = _ruota(x0 / w, 1 - y1 / h, gradi)
            b = _ruota(x1 / w, 1 - y0 / h, gradi)
            parole.append(
                [
                    round(min(a[0], b[0]) * 1000),
                    round(min(a[1], b[1]) * 1000),
                    round(max(a[0], b[0]) * 1000),
                    round(max(a[1], b[1]) * 1000),
                    corrente,
                ]
            )

    for i in range(n):
        c = testo_pagina.get_text_range(i, 1)
        if not c.strip():
            chiudi()
            corrente, riquadro = "", None
            continue
        sinistra, basso, destra, alto = testo_pagina.get_charbox(i)
        corrente += c
        riquadro = (
            (sinistra, basso, destra, alto)
            if riquadro is None
            else (min(riquadro[0], sinistra), min(riquadro[1], basso), max(riquadro[2], destra), max(riquadro[3], alto))
        )
    chiudi()
    testo_pagina.close()
    return testo.replace("\r\n", "\n").strip(), parole


def _pagine_di(sorgente: Path):
    """(numero pagina, png, testo nativo, parole, totale pagine)."""
    if sorgente.suffix.lower() in ESTENSIONI_PDF:
        doc = pdfium.PdfDocument(sorgente)
        try:
            for i in range(len(doc)):
                pagina = doc[i]
                buf = io.BytesIO()
                pagina.render(scale=DPI / 72).to_pil().convert("RGB").save(buf, format="PNG")
                testo, parole = _parole(pagina)
                pagina.close()
                yield i + 1, buf.getvalue(), testo, parole, len(doc)
        finally:
            doc.close()
    else:
        with Image.open(sorgente) as img:
            img = img.convert("RGB")
            img.thumbnail((1754, 1754))
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=False)
            yield 1, buf.getvalue(), "", [], 1


def prepara(cartella_lavoro: Path, avviso=lambda **_: None) -> list[dict]:
    """Prepara tutte le pagine del lavoro; rifarla dà lo stesso risultato. Ritorna l'elenco delle pagine."""
    ingresso = cartella_lavoro / "ingresso"
    pagine_dir = cartella_lavoro / "pagine"
    pagine_dir.mkdir(parents=True, exist_ok=True)
    elenco = []
    sorgenti = file_sorgente(ingresso)
    for indice_file, sorgente in enumerate(sorgenti):
        relativo = sorgente.relative_to(ingresso).as_posix()
        try:
            for numero, png, testo, parole, totale in _pagine_di(sorgente):
                pid = f"p{len(elenco) + 1:04d}"
                impronta = hashlib.sha256(png).hexdigest()[:24]
                bianca = not testo and _inchiostro(png) < SOGLIA_INCHIOSTRO
                (pagine_dir / f"{pid}.png").write_bytes(png)
                with Image.open(io.BytesIO(png)) as img:
                    larghezza, altezza = img.size
                info = {
                    "pid": pid,
                    "file": relativo,
                    "pagina": numero,
                    "pagine_file": totale,
                    "impronta": impronta,
                    "bianca": bianca,
                    "larghezza": larghezza,
                    "altezza": altezza,
                    "testo_nativo": testo,
                    "parole": parole,
                }
                (pagine_dir / f"{pid}.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
                elenco.append({k: info[k] for k in ("pid", "file", "pagina", "pagine_file", "impronta", "bianca")})
                avviso(tipo="pagina", pid=pid, testo=f"{relativo} · pagina {numero} di {totale}")
        except Exception as e:  # file rotto: si dichiara, non si ferma il lavoro
            elenco.append({"pid": None, "file": relativo, "errore": type(e).__name__})
            avviso(tipo="errore", testo=f"{relativo}: file non leggibile ({type(e).__name__})")
        avviso(tipo="file", testo=relativo, n=indice_file + 1, totale=len(sorgenti))
    (cartella_lavoro / "pagine.json").write_text(json.dumps(elenco, ensure_ascii=False, indent=1), encoding="utf-8")
    return elenco


def info_pagina(cartella_lavoro: Path, pid: str) -> dict:
    return json.loads((cartella_lavoro / "pagine" / f"{pid}.json").read_text(encoding="utf-8"))


def ritaglio(cartella_lavoro: Path, info: dict, zona: list[int]) -> bytes:
    """Ritaglio ad alta risoluzione della zona (0-1000 sull'immagine della pagina)."""
    sorgente = cartella_lavoro / "ingresso" / info["file"]
    x0, y0, x1, y1 = (max(0, min(1000, v)) / 1000 for v in zona)
    if sorgente.suffix.lower() in ESTENSIONI_PDF:
        doc = pdfium.PdfDocument(sorgente)
        try:
            img = doc[info["pagina"] - 1].render(scale=DPI_RITAGLIO / 72).to_pil().convert("RGB")
        finally:
            doc.close()
    else:
        img = Image.open(sorgente).convert("RGB")
    w, h = img.size
    taglio = img.crop((int(x0 * w), int(y0 * h), max(int(x1 * w), int(x0 * w) + 1), max(int(y1 * h), int(y0 * h) + 1)))
    buf = io.BytesIO()
    taglio.save(buf, format="PNG")
    return buf.getvalue()
