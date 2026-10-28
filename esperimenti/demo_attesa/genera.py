"""Demo dell'attesa: pagine vere del cantiere di prova (documenti inventati) e parole realmente estratte, con posizione.

Genera risultati/demo.html (fuori da git), una pagina sola con le immagini incorporate.
Uso: .venv\\Scripts\\python esperimenti\\demo_attesa\\genera.py
"""

import base64
import io
import json
import re
import sys
import tempfile
from pathlib import Path

from PIL import Image

CODICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODICE))

from traccia.demo_cantiere import documenti  # noqa: E402
from traccia.pdf_semplice import A5, pdf_con_testo  # noqa: E402
from traccia.preparazione import _pagine_di  # noqa: E402

SCELTI = ["01_tabella_costruttore.pdf", "ddt_", "cert_", "ce_travi.pdf", "02_dop_costruttore.pdf"]
TIPI = {
    "01_tabella": "Tabella del costruttore",
    "ddt_": "DDT del commerciante",
    "cert_": "Certificato 3.1",
    "ce_": "Etichetta CE",
    "02_dop": "DoP del costruttore",
}
CHIAVE = [  # parole che diventano dati: etichetta mostrata accanto
    ("colata", re.compile(r"^[A-Z]{0,3}\d{5,}[A-Z]?$")),
    ("profilo", re.compile(r"^(HEA|HEB|HEM|IPE|UPN|UPE|PIATTO|L)\d*$", re.I)),
    ("qualità", re.compile(r"^S\d{3}\w*$")),
    ("data", re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")),
    ("numero", re.compile(r"^(DDT|CE-|CERT|N\.)?[-\w/]*\d{2,}[-\w/]*$", re.I)),
]


def tipo(nome: str) -> str:
    return next(v for k, v in TIPI.items() if nome.startswith(k))


def main():
    docs = documenti()
    scelti = []
    for prefisso in SCELTI:
        scelti.append(next(d for d in docs if d[0].startswith(prefisso)))
    pagine = []
    with tempfile.TemporaryDirectory() as cartella:
        for nome, righe in scelti:
            pdf = Path(cartella) / nome
            pdf.write_bytes(pdf_con_testo(righe, A5, corpo=9))
            _, png, _, parole, _ = next(_pagine_di(pdf))
            img = Image.open(io.BytesIO(png)).convert("RGB")
            # le pagine del cantiere di prova hanno poco testo: si taglia il bianco sotto l'ultima riga
            fondo = min(1000, max(p[3] for p in parole) + 70) if parole else 1000
            img = img.crop((0, 0, img.width, int(img.height * fondo / 1000)))
            parole = [[x0, y0 * 1000 / fondo, x1, y1 * 1000 / fondo, t] for x0, y0, x1, y1, t in parole]
            img.thumbnail((620, 900))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=82)
            voci = []
            for x0, y0, x1, y1, parola in parole:
                etichetta = next((e for e, rx in CHIAVE if rx.match(parola.strip(".,;:"))), "")
                voci.append([x0, y0, x1, y1, parola, etichetta])
            pagine.append({
                "nome": nome,
                "tipo": tipo(nome),
                "img": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(),
                "w": img.width,
                "h": img.height,
                "parole": voci,
            })
    modello = (Path(__file__).parent / "modello.html").read_text(encoding="utf-8")
    uscita = Path(__file__).parent / "risultati" / "demo.html"
    uscita.parent.mkdir(exist_ok=True)
    uscita.write_text(modello.replace("/*PAGINE*/[]", json.dumps(pagine, ensure_ascii=False)), encoding="utf-8")
    print(uscita, sum(len(p["parole"]) for p in pagine), "parole")


if __name__ == "__main__":
    main()
