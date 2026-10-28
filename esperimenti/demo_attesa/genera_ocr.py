"""Simulazione su certificati 3.1 veri: immagine della scansione, blocchi OCR Mistral con la loro posizione, testo letto,
parti tolte dal coltellino e dati estratti (dalle schede della prova 3). Resta in risultati/ (documenti di clienti).

Uso: .venv\\Scripts\\python esperimenti\\demo_attesa\\genera_ocr.py <cartella del lavoro> <pid> [<pid> ...]
"""

import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

QUI = Path(__file__).parent
sys.path.insert(0, str(QUI.parent / "coltellino"))
import coltellino  # noqa: E402


def compatto(t: str) -> str:
    return "".join(c for c in t.lower() if c.isalnum())


def valori(scheda: dict) -> list[tuple[str, str]]:
    out = [(k, v["v"]) for k, v in scheda["testata"].items() if v["v"]]
    for r in scheda["righe"]:
        out += [(k, v["v"]) for k, v in r.items() if v["v"] and k in ("profilo", "qualita", "colata", "peso", "pezzi")]
    out += [(f"timbro: {t['chi'] or 'ddt'}", t["ddt_citato"]) for t in scheda["timbri"] if t["ddt_citato"]]
    return out


def main():
    lavoro = Path(sys.argv[1])
    pids = sys.argv[2:]
    risultati = QUI.parent / "ocr_mistral" / "risultati"
    ocr_dir = risultati / f"{lavoro.name}_v2" / "ocr"
    schede = json.loads((risultati / f"{lavoro.name}_v3" / "schede.json").read_text(encoding="utf-8"))
    dizionario = coltellino.carica(coltellino.DIZIONARIO)
    pagine = []
    for pid in pids:
        ocr = json.loads((ocr_dir / f"{pid}.json").read_text(encoding="utf-8"))
        png = Image.open(lavoro / "pagine" / f"{pid}.png").convert("RGB")
        w, h = png.size
        img = png.copy()
        img.thumbnail((700, 1000))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        dati = valori(schede[pid]) if schede.get(pid) else []
        blocchi = []
        for b in ocr["blocchi"]:
            testo = b.get("content", "").strip()
            if not testo or testo.startswith("!["):
                continue
            tenuto = coltellino.taglia(testo, "certificato_31", dizionario)
            righe = []
            tenute = {compatto(r) for r in tenuto.splitlines()}
            for r in testo.splitlines():
                r = r.strip()
                if r and not set(r) <= set("|-: "):
                    righe.append([r[:160], compatto(r) in tenute or any(compatto(r) in t for t in tenute if t)])
            c = compatto(testo)
            blocchi.append({
                "box": [
                    round(float(b["top_left_x"]) / w * 1000), round(float(b["top_left_y"]) / h * 1000),
                    round(float(b["bottom_right_x"]) / w * 1000), round(float(b["bottom_right_y"]) / h * 1000),
                ],
                "tipo": b.get("type", ""),
                "righe": righe,
                "dati": [[k, v] for k, v in dati if compatto(v) and compatto(v) in c],
            })
        blocchi.sort(key=lambda b: (b["box"][1], b["box"][0]))
        pagine.append({
            "tipo": "Certificato 3.1",
            "img": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(),
            "blocchi": blocchi,
            "caratteri": [len(ocr["testo"]), len(coltellino.taglia(ocr["testo"], "certificato_31", dizionario))],
        })
    modello = (QUI / "modello_ocr.html").read_text(encoding="utf-8")
    uscita = QUI / "risultati" / "simulazione_31.html"
    uscita.parent.mkdir(exist_ok=True)
    uscita.write_text(modello.replace("/*PAGINE*/[]", json.dumps(pagine, ensure_ascii=False)), encoding="utf-8")
    print(uscita, [len(p["blocchi"]) for p in pagine], "blocchi", [p["caratteri"] for p in pagine])


if __name__ == "__main__":
    main()
