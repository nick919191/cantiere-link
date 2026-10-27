"""Pagine di prova: per ogni cella dell'Excel una pagina HTML statica con l'immagine del documento e il riquadro
evidenziato dove è stato preso il dato. Collegamenti relativi: funzionano anche a piattaforma spenta."""

import html
import io
from pathlib import Path

from PIL import Image

STILE = """
:root{--bg:#f5f5f7;--card:#fff;--ink:#1d1d1f;--muted:#6e6e73;--line:#e5e5ea;--accent:#0071e3;--accent-bg:#e8f1fc}
@media (prefers-color-scheme:dark){:root{--bg:#000;--card:#1c1c1e;--ink:#f5f5f7;--muted:#a1a1a6;--line:#38383a;
--accent:#2997ff;--accent-bg:#0a2540}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font-family:Inter,-apple-system,"Segoe UI",sans-serif}main{max-width:1100px;margin:0 auto;padding:28px 16px}
.k{font-size:12px;font-weight:600;color:var(--accent);letter-spacing:.04em;margin:0 0 6px}
h1{font-size:24px;margin:0 0 6px;letter-spacing:-.02em}.sub{color:var(--muted);margin:0 0 22px;font-size:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:18px}
.cit{font-size:14px;background:var(--accent-bg);border-radius:8px;padding:8px 12px;margin:8px 0 14px}
.pag{position:relative;display:inline-block;max-width:100%}.pag img{max-width:100%;display:block;border-radius:8px;
border:1px solid var(--line)}.box{position:absolute;border:3px solid #ff9f0a;background:rgba(255,159,10,.18);
border-radius:4px;box-shadow:0 0 0 4px rgba(255,159,10,.25)}.meta{font-size:13px;color:var(--muted)}
.rit{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.rit img{max-height:140px;border-radius:8px;
border:1px solid var(--line)}a{color:var(--accent)}
"""


def ruota_zona(zona: list[int], gradi: int) -> list[int]:
    """Zona 0-1000 dell'immagine originale -> zona sull'immagine ruotata in senso orario di `gradi`."""
    if not zona:
        return zona
    x0, y0, x1, y1 = zona
    if gradi == 90:
        return [1000 - y1, x0, 1000 - y0, x1]
    if gradi == 180:
        return [1000 - x1, 1000 - y1, 1000 - x0, 1000 - y0]
    if gradi == 270:
        return [y0, 1000 - x1, y1, 1000 - x0]
    return zona


def immagine_dritta(png: Path, gradi: int, destinazione: Path) -> None:
    if destinazione.exists():
        return
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(png) as img:
        dritta = img.rotate(-gradi, expand=True) if gradi else img.copy()
        dritta.thumbnail((1400, 1400))
        buf = io.BytesIO()
        dritta.save(buf, format="PNG", optimize=True)
    destinazione.write_bytes(buf.getvalue())


def pagina_cella(titolo: str, colonna: str, valore: str, fonti: list[dict], ritagli: dict[str, list]) -> str:
    """fonti: [{pid, file, pagina, cit, zona, esatta, img, gradi}]; ritagli: pid -> [percorsi relativi]."""
    blocchi = []
    for f in fonti:
        zona = ruota_zona(f["zona"], f["gradi"])
        box = ""
        if zona:
            x0, y0, x1, y1 = zona
            box = (
                f'<div class="box" style="left:{x0 / 10}%;top:{y0 / 10}%;width:{(x1 - x0) / 10}%;'
                f'height:{(y1 - y0) / 10}%"></div>'
            )
        precisione = (
            "zona esatta (testo del PDF)"
            if f["esatta"]
            else ("zona indicata da Claude" if zona else "zona non indicata")
        )
        rit = "".join(
            f'<a href="{html.escape(r)}"><img src="{html.escape(r)}" alt="ritaglio"></a>'
            for r in ritagli.get(f["pid"], [])
        )
        blocchi.append(
            f'<div class="card"><div class="meta">{html.escape(f["file"])} · pagina {f["pagina"]} · {precisione}</div>'
            f'<div class="cit">«{html.escape(f["cit"] or f["valore"])}»</div>'
            f'<div class="pag"><img src="{html.escape(f["img"])}" alt="pagina">{box}</div>'
            + (
                f'<div class="meta" style="margin-top:12px">Ritagli usati da Claude su questa pagina</div>'
                f'<div class="rit">{rit}</div>'
                if rit
                else ""
            )
            + "</div>"
        )
    if not blocchi:
        blocchi.append(
            '<div class="card">Nessuna fonte: il valore è un esito del motore (per esempio "non presente '
            'nel fascicolo").</div>'
        )
    return (
        f'<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width,initial-scale=1"><title>Prova del dato</title><style>{STILE}</style></head>'
        f'<body><main><p class="k">{html.escape(colonna)}</p><h1>{html.escape(valore or "(vuoto)")}</h1>'
        f'<p class="sub">{html.escape(titolo)}</p>{"".join(blocchi)}</main></body></html>'
    )
