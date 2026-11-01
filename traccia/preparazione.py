"""Preparazione (deterministica): file caricati -> una immagine PNG e una scheda tecnica per ogni pagina.

Per ogni pagina: PNG a 150 dpi (quella che legge l'agente), testo nativo del PDF con la posizione di ogni parola
(serve a calcolare le zone esatte), impronta del PNG (chiave dell'archivio), pagina bianca sì/no.
Gli originali non si toccano: gli ZIP si aprono in ingresso/estratti/.
"""

import hashlib
import io
import json
import math
import threading
import zipfile
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageSequence

DPI = 150
DPI_RITAGLIO = 300
ESTENSIONI_PDF = {".pdf"}
ESTENSIONI_IMMAGINE = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
SOGLIA_INCHIOSTRO = 0.0005  # quota di pixel scuri sotto cui una pagina senza testo è bianca
MAX_FILE_ZIP = 2000
MAX_PIXEL_PAGINA = 50_000_000  # oltre, la scala si riduce: una pagina 14400x14400 pt a 150 dpi sarebbe 3,6 GB
MAX_PAGINE_FILE = 1000  # un file con più pagine viene dichiarato non leggibile
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
            base, n = nome, 1
            while str(nome).casefold() in nomi:  # A.pdf e a.pdf sono lo stesso file su Windows: si rinomina il secondo
                n += 1
                nome = base.with_name(f"{base.stem} ({n}){base.suffix}")
            nomi.add(str(nome).casefold())
            uscita = destinazione / zip_path.stem / nome
            if not uscita.resolve().is_relative_to(destinazione.resolve()):
                raise ValueError("percorso non valido nell’archivio")
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


def file_sorgente(ingresso: Path, falliti: dict[str, str] | None = None) -> list[Path]:
    """PDF e immagini da leggere, in ordine fisso (percorso relativo, senza maiuscole).

    Un archivio corrotto o oltre i limiti si estrae per quanto possibile, viene segnato in `falliti`
    (percorso relativo -> motivo) e non ferma gli altri file; non si ritenta a ogni preparazione.
    """
    estratti = ingresso / "estratti"
    budget = {"file": 0, "byte": 0}
    for z in sorted(ingresso.glob("*.zip")):
        cartella = estratti / z.stem
        complete, fallito = cartella / ".complete", cartella / ".fallito"
        if not complete.exists():
            try:
                _estrai_zip(z, estratti, budget)
            except (zipfile.BadZipFile, ValueError, OSError) as e:
                cartella.mkdir(parents=True, exist_ok=True)
                fallito.write_text(f"{type(e).__name__}: {e}"[:200], encoding="utf-8")
            cartella.mkdir(parents=True, exist_ok=True)
            complete.touch()
        if fallito.exists() and falliti is not None:
            falliti[z.relative_to(ingresso).as_posix()] = fallito.read_text(encoding="utf-8")
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


# pdfium non regge due thread insieme, e un errore lì dentro fa cadere tutta l'app: i file si possono aggiungere mentre
# l'analisi compone i documenti ordinati, quindi preparazione e riordino girano davvero insieme.
PDFIUM = threading.RLock()


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


def _scala(pagina: pdfium.PdfPage, dpi: int) -> float:
    """Scala di resa: quella dei dpi richiesti, ridotta se la pagina dichiara più pixel di MAX_PIXEL_PAGINA."""
    w, h = pagina.get_size()
    scala = dpi / 72
    pixel = w * h * scala * scala
    return scala * math.sqrt(MAX_PIXEL_PAGINA / pixel) if pixel > MAX_PIXEL_PAGINA else scala


def _pagine_di(sorgente: Path):
    """(numero pagina, png, testo nativo, parole, totale pagine)."""
    if sorgente.suffix.lower() in ESTENSIONI_PDF:
        with PDFIUM:
            doc = pdfium.PdfDocument(sorgente)
            totale = len(doc)
        try:
            if totale > MAX_PAGINE_FILE:
                raise ValueError(f"troppe pagine ({totale}, massimo {MAX_PAGINE_FILE})")
            for i in range(totale):
                with PDFIUM:  # si rilascia a ogni pagina: chi aspetta non resta fermo per tutto il file
                    pagina = doc[i]
                    buf = io.BytesIO()
                    pagina.render(scale=_scala(pagina, DPI)).to_pil().convert("RGB").save(buf, format="PNG")
                    testo, parole = _parole(pagina)
                    pagina.close()
                yield i + 1, buf.getvalue(), testo, parole, totale
        finally:
            with PDFIUM:
                doc.close()
    else:
        with Image.open(sorgente) as img:
            totale = getattr(img, "n_frames", 1)  # TIFF multipagina: una pagina per fotogramma
            for numero, fotogramma in enumerate(ImageSequence.Iterator(img), 1):
                pagina = fotogramma.convert("RGB")
                pagina.thumbnail((1754, 1754))
                buf = io.BytesIO()
                pagina.save(buf, format="PNG", optimize=False)
                yield numero, buf.getvalue(), "", [], totale


def prepara(cartella_lavoro: Path, avviso=lambda **_: None) -> list[dict]:
    """Prepara le pagine del lavoro; rifarla dà lo stesso risultato. Ritorna l'elenco delle pagine.

    I file già preparati (presenti in pagine.json) conservano i loro pid: i file aggiunti dopo ricevono i pid
    successivi. Così letture, chat e tentativi delle pagine esistenti restano validi.
    """
    ingresso = cartella_lavoro / "ingresso"
    pagine_dir = cartella_lavoro / "pagine"
    pagine_dir.mkdir(parents=True, exist_ok=True)
    indice = cartella_lavoro / "pagine.json"
    precedenti = json.loads(indice.read_text(encoding="utf-8")) if indice.exists() else []
    gia_fatti = {v["file"] for v in precedenti if v.get("pid")}
    elenco = [v for v in precedenti if v.get("pid")]
    prossimo = max((int(v["pid"][1:]) for v in elenco), default=0) + 1
    falliti: dict[str, str] = {}
    sorgenti = [s for s in file_sorgente(ingresso, falliti) if s.relative_to(ingresso).as_posix() not in gia_fatti]
    for indice_file, sorgente in enumerate(sorgenti):
        relativo = sorgente.relative_to(ingresso).as_posix()
        try:
            for numero, png, testo, parole, totale in _pagine_di(sorgente):
                pid = f"p{prossimo:04d}"
                prossimo += 1
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
            # Le pagine già preparate di questo file si tolgono: alla prossima preparazione si ritenta da capo e,
            # se fallisce ancora, il file resta "non letto" per il motore (fascicolo incompleto -> DA CONFERMARE).
            parziali = [v for v in elenco if v.get("pid") and v["file"] == relativo]
            for v in parziali:
                elenco.remove(v)
                for suffisso in (".png", ".json"):
                    (pagine_dir / f"{v['pid']}{suffisso}").unlink(missing_ok=True)
            elenco.append({"pid": None, "file": relativo, "errore": type(e).__name__, "pagine_parziali": len(parziali)})
            dopo = f", dopo {len(parziali)} pagine" if parziali else ""
            avviso(tipo="errore", testo=f"{relativo}: file non leggibile ({type(e).__name__}{dopo})")
        avviso(tipo="file", testo=relativo, n=indice_file + 1, totale=len(sorgenti))
    for relativo, motivo in sorted(falliti.items()):  # in coda, così l'ordine non cambia tra una preparazione e l'altra
        elenco.append({"pid": None, "file": relativo, "errore": motivo})
        avviso(tipo="errore", testo=f"{relativo}: archivio non leggibile ({motivo})")
    temporaneo = indice.with_suffix(".tmp")
    temporaneo.write_text(json.dumps(elenco, ensure_ascii=False, indent=1), encoding="utf-8")
    temporaneo.replace(indice)
    return elenco


def info_pagina(cartella_lavoro: Path, pid: str) -> dict:
    return json.loads((cartella_lavoro / "pagine" / f"{pid}.json").read_text(encoding="utf-8"))


def ritaglio(cartella_lavoro: Path, info: dict, zona: list[int]) -> bytes:
    """Ritaglio ad alta risoluzione della zona (0-1000 sull'immagine della pagina)."""
    sorgente = cartella_lavoro / "ingresso" / info["file"]
    x0, y0, x1, y1 = (max(0, min(1000, v)) / 1000 for v in zona)
    if sorgente.suffix.lower() in ESTENSIONI_PDF:
        with PDFIUM:
            doc = pdfium.PdfDocument(sorgente)
            try:
                pagina = doc[info["pagina"] - 1]
                img = pagina.render(scale=_scala(pagina, DPI_RITAGLIO)).to_pil().convert("RGB")
            finally:
                doc.close()
    else:
        with Image.open(sorgente) as originale:
            originale.seek(info["pagina"] - 1)
            img = originale.convert("RGB")
    w, h = img.size
    taglio = img.crop((int(x0 * w), int(y0 * h), max(int(x1 * w), int(x0 * w) + 1), max(int(y1 * h), int(y0 * h) + 1)))
    buf = io.BytesIO()
    taglio.save(buf, format="PNG")
    return buf.getvalue()
