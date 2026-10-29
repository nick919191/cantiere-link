"""Proposta B: lettura parola per parola su certificati 3.1 veri. Testo di Mistral, posizioni ricavate in locale.

Per ogni pagina:
  raddrizza   - giro di 90° dedotto dalla forma dei blocchi Mistral (righe alte e strette = pagina girata), verso
                scelto con la fiducia di Tesseract, poi inclinazione fine (±3°) con la varianza della proiezione;
  righe       - proiezione dei pixel scuri dopo aver tolto le linee della griglia: bande di testo e celle;
  parole      - il testo resta quello di Mistral; ogni parola prende la posizione della parola Tesseract che le
                corrisponde (posizione esatta) o, se Tesseract non l'ha letta, quella della sua cella o della sua
                frazione di riga (posizione stimata);
  dati        - confronto tollerante (O/0, I/1, S/5…) ma ancorato: i valori della tabella solo nella riga della loro
                colata, quelli di testata solo fuori dalle righe di indirizzo.
Le pagine restano in risultati/ (fuori da git): sono documenti di un cliente.

Uso: .venv\\Scripts\\python esperimenti\\demo_attesa\\genera_parole.py [<cartella del lavoro>]
Senza cartella del lavoro le immagini si prendono da risultati/simulazione_31.html (pagine p0008 e p0011).
"""

import base64
import difflib
import io
import json
import math
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

QUI = Path(__file__).parent
CODICE = QUI.parents[1]
sys.path.insert(0, str(CODICE))
from traccia.coltellino import CONTATTI  # noqa: E402

LAVORO = "20261028-002735-fa0ec032"
PID = ["p0008", "p0011"]
RIS = CODICE / "esperimenti" / "ocr_mistral" / "risultati"
TESSERACT = shutil.which("tesseract") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
CATENA = ["packing_costruttore", "ddt", "certificato_31", "dop_ce_prodotto", "dop_costruttore",
          "lettera_accompagnamento", "da_escludere", "illeggibile"]
NOMI = {"packing_costruttore": "Tabella costruttore", "ddt": "DDT", "certificato_31": "Certificato 3.1",
        "dop_ce_prodotto": "DoP/CE prodotto", "dop_costruttore": "DoP costruttore",
        "lettera_accompagnamento": "Lettera", "da_escludere": "Non pertinente", "illeggibile": "Illeggibile"}
INDIRIZZO = re.compile(r"\bvia\b|\bviale\b|\bpiazza\b|\b\d{5}\b|\(\w{2}\)|stabilimento|sede", re.I)
CONFUSI = str.maketrans("OQDILZSGB|!", "00011256811")
CAMPI = {"profilo": "profilo", "qualita": "qualità", "colata": "colata", "pezzi": "pezzi", "peso": "peso kg",
         "numero": "certificato", "data": "data", "cliente": "cliente", "ordine": "ordine", "ddt_produttore": "DDT",
         "norma_prodotto": "norma", "produttore": "produttore", "marchio": "marchio"}


# ---------- confronto ----------
def norma(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).upper()
    s = re.sub(r"[\s.\-/,;:'’]", "", s)
    return s.translate(CONFUSI)


def simile(a: str, b: str) -> float:
    a, b = norma(a), norma(b)
    if not a or not b:
        return 0.0
    return 1.0 if a == b else difflib.SequenceMatcher(None, a, b).ratio()


def uguale(valore: str, testo: str) -> bool:
    """Uguali dopo la mappa di confusione; una lettera di scarto solo per valori lunghi (≥ 6)."""
    a, b = norma(valore), norma(testo)
    if not a or not b:
        return False
    if a == b:
        return True
    return len(a) >= 6 and abs(len(a) - len(b)) <= 1 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.9


# ---------- immagini ----------
def immagini(cartella: Path | None) -> dict[str, Image.Image]:
    if cartella and (cartella / "pagine").exists():
        return {p: Image.open(cartella / "pagine" / f"{p}.png").convert("RGB") for p in PID}
    h = (QUI / "risultati" / "simulazione_31.html").read_text(encoding="utf-8")
    vecchie = json.loads(re.search(r"const PAGINE = (\[.*?\]);\n", h, re.S).group(1))
    return {p: Image.open(io.BytesIO(base64.b64decode(v["img"].split(",")[1]))).convert("RGB")
            for p, v in zip(PID, vecchie, strict=False)}


def scuro(im: Image.Image) -> Image.Image:
    """Inchiostro = 255, carta = 0 (scala di grigi)."""
    g = ImageOps.autocontrast(im.convert("L"))
    return g.point(lambda v: 255 if v < 150 else 0)


def profilo(ink: Image.Image, asse: str) -> list[float]:
    """Frazione di inchiostro per riga ('y') o per colonna ('x')."""
    if asse == "y":
        return [v / 255 for v in ink.resize((1, ink.height), Image.BOX).get_flattened_data()]
    return [v / 255 for v in ink.resize((ink.width, 1), Image.BOX).get_flattened_data()]


def tratti(valori: list[float], soglia: float, unisci: int = 1, minimo: int = 2) -> list[list[int]]:
    out = []
    for i, v in enumerate(valori):
        if v > soglia:
            if out and i - out[-1][1] <= unisci + 1:
                out[-1][1] = i
            else:
                out.append([i, i])
    return [t for t in out if t[1] - t[0] + 1 >= minimo]


def inclinazione(ink: Image.Image) -> float:
    piccola = ink.resize((ink.width // 2, ink.height // 2))
    meglio, voto = 0.0, -1.0
    for d10 in range(-30, 31, 2):
        r = piccola.rotate(d10 / 10, expand=False, fillcolor=0)
        p = profilo(r, "y")
        v = statistics.pvariance(p)
        if v > voto:
            meglio, voto = d10 / 10, v
    return meglio


def tesseract(im: Image.Image, scala: int = 3) -> tuple[list[list], float]:
    """Parole Tesseract in coordinate 0-1000 dell'immagine data, e fiducia media."""
    grande = ImageOps.autocontrast(im.convert("L")).resize((im.width * scala, im.height * scala), Image.LANCZOS)
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "p.png"
        grande.save(f)
        out = subprocess.run([TESSERACT, str(f), "-", "--psm", "11", "-l", "eng", "tsv"],
                             capture_output=True).stdout.decode("utf-8", "replace")
    parole, fid = [], []
    for riga in out.splitlines()[1:]:
        c = riga.split("\t")
        if len(c) == 12 and c[11].strip() and float(c[10]) > 0:
            x, y, w, h = (int(v) for v in c[6:10])
            parole.append([x / grande.width * 1000, y / grande.height * 1000, (x + w) / grande.width * 1000,
                           (y + h) / grande.height * 1000, c[11].strip(), float(c[10])])
            fid.append(float(c[10]))
    return parole, (statistics.mean(fid) if fid else 0.0)


# ---------- raddrizzamento ----------
def giro_da_blocchi(blocchi: list[dict]) -> bool:
    """Le righe di testo corte sono larghe e basse; se sono alte e strette la pagina è girata di 90°."""
    forme = []
    for b in blocchi:
        if b.get("type") in ("text", "title", "header") and "\n" not in b.get("content", "").strip():
            w = b["bottom_right_x"] - b["top_left_x"]
            h = b["bottom_right_y"] - b["top_left_y"]
            if w > 0 and h > 0:
                forme.append(h / w)
    return bool(forme) and statistics.median(forme) > 1.5


def verso(blocchi: list[dict]) -> int:
    """Mistral elenca i blocchi in ordine di lettura: se i primi stanno a sinistra, l'alto della pagina è a sinistra
    e si gira in senso orario; se stanno a destra, in senso antiorario."""
    terzo = max(1, len(blocchi) // 3)
    primi = statistics.mean(b["top_left_x"] for b in blocchi[:terzo])
    ultimi = statistics.mean(b["top_left_x"] for b in blocchi[-terzo:])
    return -90 if primi < ultimi else 90


def trasforma(gradi: int, W: int, H: int):
    """Punto (x, y) dell'originale -> punto dell'immagine girata con PIL rotate(gradi, expand=True)."""
    if gradi == -90:  # orario
        return lambda x, y: (H - y, x), (H, W)
    if gradi == 90:  # antiorario
        return lambda x, y: (y, W - x), (H, W)
    return lambda x, y: (x, y), (W, H)


# ---------- pagina ----------
def righe_blocco(b: dict) -> list[list[str]]:
    """Righe del blocco Mistral; per le tabelle, le celle (vuote comprese)."""
    out = []
    for r in b.get("content", "").splitlines():
        r = r.strip()
        if not r or set(r) <= set("|-: "):
            continue
        if b.get("type") == "table":
            out.append([c.strip() for c in r.strip("|").split("|")])
        else:
            out.append([r.lstrip("# ").strip()])
    return out


def parole_da(testo: str, x0: float, x1: float, y0: float, y1: float, tess: list[list]) -> list[list]:
    """Parole di un pezzo di testo Mistral dentro un rettangolo: posizione esatta se Tesseract l'ha letta lì."""
    tokens = testo.split()
    if not tokens:
        return []
    dentro = [t for t in tess if t[0] >= x0 - 6 and t[2] <= x1 + 6 and (t[1] + t[3]) / 2 >= y0 - 4
              and (t[1] + t[3]) / 2 <= y1 + 4]
    totale = sum(len(t) for t in tokens) + len(tokens) - 1
    out, pos = [], 0
    for tok in tokens:
        a = x0 + (x1 - x0) * pos / totale
        b = x0 + (x1 - x0) * (pos + len(tok)) / totale
        pos += len(tok) + 1
        meglio = max(dentro, key=lambda t: simile(tok, t[4]) - abs((t[0] + t[2]) / 2 - (a + b) / 2) / 2000,
                     default=None)
        if meglio and len(norma(tok)) >= 2 and simile(tok, meglio[4]) >= 0.75:
            out.append([meglio[0], meglio[1], meglio[2], meglio[3], tok, 1])
            dentro.remove(meglio)
        else:
            out.append([a, y0, b, y1, tok, 0])
    return out


def scegli_bande(bande: list[list[int]], dati: list[list[str]], reg: tuple, Wd: int, Hd: int,
                 tess: list[list]) -> list[list[int]]:
    """Le righe dati sono N bande consecutive: si prova ogni partenza e vince quella in cui Tesseract legge, banda
    per banda, più parole della riga Mistral corrispondente (i residui delle righe vuote non tornano mai)."""
    n = len(dati)
    if len(bande) <= n:
        return bande

    def voto(s):
        tot = 0
        for celle, (b0, b1) in zip(dati, bande[s:s + n], strict=False):
            y0, y1 = (reg[1] + b0 - 2) * 1000 / Hd, (reg[1] + b1 + 2) * 1000 / Hd
            lette = [t[4] for t in tess if y0 <= (t[1] + t[3]) / 2 <= y1]
            tot += sum(1 for tok in " ".join(celle).split() if any(simile(tok, w) >= 0.8 for w in lette))
        return tot

    s = max(range(len(bande) - n + 1), key=voto)
    return bande[s:s + n]


def pagina(pid: str, im: Image.Image, ocr: dict, scheda: dict, vecchio_box: list[int]) -> dict:
    t0 = time.perf_counter()
    blocchi = [b for b in ocr["blocchi"] if b.get("content", "").strip() and not b["content"].startswith("![")]
    tab0 = next(b for b in blocchi if b.get("type") == "table")
    # dimensioni dell'originale su cui Mistral ha dato le coordinate (la miniatura ha le stesse proporzioni)
    W = round(tab0["bottom_right_x"] / (vecchio_box[2] / 1000))
    H = round(tab0["bottom_right_y"] / (vecchio_box[3] / 1000))
    sx, sy = im.width / W, im.height / H

    # 1. raddrizza: 90° dai blocchi, verso con Tesseract, poi inclinazione fine
    gradi = verso(blocchi) if giro_da_blocchi(blocchi) else 0
    dritta = im.rotate(gradi, expand=True, fillcolor="white")
    incl = inclinazione(scuro(dritta))
    if incl:
        dritta = dritta.rotate(incl, expand=False, fillcolor="white", resample=Image.BICUBIC)
    t_raddrizza = time.perf_counter() - t0
    giro, (Wd, Hd) = trasforma(gradi, im.width, im.height)
    cx, cy = Wd / 2, Hd / 2
    ca, sa = math.cos(math.radians(-incl)), math.sin(math.radians(-incl))

    def punto(x, y):  # coordinate Mistral originali -> pixel della pagina raddrizzata
        X, Y = giro(x * sx, y * sy)
        dx, dy = X - cx, Y - cy
        return cx + dx * ca - dy * sa, cy + dx * sa + dy * ca

    def scatola(b):
        xs, ys = zip(*(punto(x, y) for x in (b["top_left_x"], b["bottom_right_x"])
                       for y in (b["top_left_y"], b["bottom_right_y"])), strict=True)
        return [max(0, min(xs)), max(0, min(ys)), min(Wd, max(xs)), min(Hd, max(ys))]

    # 2. posizioni: Tesseract sulla pagina dritta + proiezione dei pixel
    t1 = time.perf_counter()
    tess, fid = tesseract(dritta)
    t_tess = time.perf_counter() - t1
    t2 = time.perf_counter()
    ink = scuro(dritta)
    k = lambda v, n: v * 1000 / n  # noqa: E731
    parole, righe_tab = [], []

    for bi, b in enumerate(blocchi):
        x0, y0, x1, y1 = scatola(b)
        reg = (int(x0), int(y0), int(x1) + 1, int(y1) + 1)
        zona = ink.crop(reg)
        # via le linee della griglia: colonne e righe quasi piene
        vert = [i for i, v in enumerate(profilo(zona, "x")) if v > 0.55]
        oriz = [i for i, v in enumerate(profilo(zona, "y")) if v > 0.45]
        z = zona.copy()
        d = ImageDraw.Draw(z)
        for i in vert:
            d.line([(i, 0), (i, z.height)], fill=0, width=3)
        for i in oriz:
            d.line([(0, i), (z.width, i)], fill=0, width=3)
        bande = tratti(profilo(z, "y"), 0.012, unisci=1, minimo=3)
        righe = righe_blocco(b)
        if b.get("type") == "table":
            # righe dati: prima cella piena, almeno una cifra, nessuna etichetta «italiano / english»
            dati = [r for r in righe if r[0] and any(re.search(r"\d", c) for c in r) and not any(" / " in c for c in r)
                    and not re.search(r"(CT|OBC|DB|CAT|SIT)\d", " ".join(r))]
            alte = statistics.median(b1 - b0 + 1 for b0, b1 in bande) if bande else 0
            divise = []
            for b0, b1 in bande:
                if b1 - b0 + 1 < 0.5 * alte:  # residui di linee e timbri, non righe di testo
                    continue  # due righe di testo troppo vicine finiscono in una banda: si dividono
                n = round((b1 - b0 + 1) / alte) if alte and (b1 - b0 + 1) > 1.8 * alte else 1
                divise += [[b0 + (b1 - b0 + 1) * i // n, b0 + (b1 - b0 + 1) * (i + 1) // n - 1] for i in range(n)]
            usate = scegli_bande(divise, dati, reg, Wd, Hd, tess)
            tagli = sorted(set(vert))

            def segmenti(banda, z=z, tagli=tagli):
                """Pezzi di inchiostro della banda, spezzati sulle linee verticali (separatori di cella)."""
                pezzo = z.crop((0, banda[0] - 1, z.width, banda[1] + 2))
                out = []
                for s0, s1 in tratti(profilo(pezzo, "x"), 0.02, unisci=12, minimo=2):
                    inizio = s0
                    for t in tagli:
                        if s0 < t < s1:
                            if t - 2 > inizio:
                                out.append([inizio, t - 2])
                            inizio = t + 2
                    if s1 > inizio:
                        out.append([inizio, s1])
                return out

            # 1° giro: dove Tesseract ha letto una cella, quella è la posizione della sua colonna (stesso indice in
            # ogni riga Mistral)
            colonne: dict[int, list[list[float]]] = {}
            for celle, banda in zip(dati, usate, strict=False):
                y0, y1 = (reg[1] + banda[0] - 2) * 1000 / Hd, (reg[1] + banda[1] + 2) * 1000 / Hd
                lette = [t for t in tess if y0 <= (t[1] + t[3]) / 2 <= y1]
                for c, testo in enumerate(celle):
                    if not testo:
                        continue
                    prese = [t for t in lette for tok in testo.split() if len(norma(tok)) >= 2
                             and simile(tok, t[4]) >= 0.8]
                    if prese:
                        colonne.setdefault(c, []).append([min(t[0] for t in prese), max(t[2] for t in prese)])
            centro = {c: statistics.median((a + b) / 2 for a, b in v) for c, v in colonne.items()}
            # 2° giro: ogni cella va sul segmento d'inchiostro più vicino al centro della sua colonna
            for r_i, (celle, banda) in enumerate(zip(dati, usate, strict=False)):
                seg = [[k(reg[0] + s0, Wd), k(reg[0] + s1 + 1, Wd)] for s0, s1 in segmenti(banda)]
                Y0, Y1 = k(reg[1] + banda[0] - 1, Hd), k(reg[1] + banda[1] + 1, Hd)
                piene = [(c, t) for c, t in enumerate(celle) if t]
                liberi = list(seg)
                for c, testo in piene:
                    if c in centro and liberi:
                        s = min(liberi, key=lambda s: abs((s[0] + s[1]) / 2 - centro[c]))
                    elif liberi:  # colonna mai letta: il segmento libero in ordine
                        s = liberi[0]
                    else:
                        s = [centro.get(c, 500) - 20, centro.get(c, 500) + 20]
                    if s in liberi:
                        liberi.remove(s)
                    for p in parole_da(testo, s[0], s[1], Y0, Y1, tess):
                        parole.append(p + ["", len(righe_tab) + r_i, f"t{len(righe_tab) + r_i}"])
            righe_tab_base = len(righe_tab)
            for r_i, celle in enumerate(dati):
                righe_tab.append({"celle": [c for c in celle if c], "y": k(reg[1] + usate[r_i][0], Hd)
                                  if r_i < len(usate) else 1000, "i": righe_tab_base + r_i})
            # intestazioni della tabella: solo le parole Tesseract che corrispondono al testo Mistral
            testa = " ".join(c for r in righe if r not in dati for c in r if c)
            vocab = {norma(t): t for t in testa.split() if len(norma(t)) >= 3}
            primo = k(reg[1] + usate[0][0], Hd) if usate else 1000
            for t in tess:
                if k(reg[1], Hd) - 4 <= t[1] < primo - 2 and k(reg[0], Wd) - 4 <= t[0] <= k(reg[2], Wd):
                    m = difflib.get_close_matches(norma(t[4]), list(vocab), n=1, cutoff=0.8)
                    if m:
                        parole.append([t[0], t[1], t[2], t[3], vocab[m[0]], 1, "", -1, f"h{bi}"])
        else:
            linee = [r[0] for r in righe]
            if not bande:
                bande = [[0, z.height - 1]]
            if len(bande) != len(linee):  # una banda per riga Mistral, divisa in parti uguali
                bande = [[round(z.height * i / len(linee)), round(z.height * (i + 1) / len(linee)) - 1]
                         for i in range(len(linee))]
            for li, (testo, (b0, b1)) in enumerate(zip(linee, bande, strict=False)):
                pezzo = z.crop((0, b0, z.width, b1 + 1))
                seg = tratti(profilo(pezzo, "x"), 0.02, unisci=12, minimo=1)
                a, c = (seg[0][0], seg[-1][1] + 1) if seg else (0, z.width)
                for p in parole_da(testo, k(reg[0] + a, Wd), k(reg[0] + c, Wd), k(reg[1] + b0 - 1, Hd),
                                   k(reg[1] + b1 + 1, Hd), tess):
                    parole.append(p + ["", -1, f"b{bi}r{li}"])
    t_proiezione = time.perf_counter() - t2

    # 3. dati: tabella ancorata alla colata, testata fuori dagli indirizzi
    trovati = []
    for r in scheda.get("righe", []):
        col = r["colata"]["v"]
        if not col:
            continue
        i = next((j for j, rt in enumerate(righe_tab) if any(uguale(col, re.sub(r"^No\.?\s*", "", c, flags=re.I))
                                                             for c in rt["celle"])), None)
        if i is None:
            continue
        gruppo = set(range(max(0, i - 2), i + 1))
        voce = {"riga": len(trovati), "righe": sorted(gruppo)}
        for campo in ("profilo", "qualita", "colata", "pezzi", "peso"):
            v = r[campo]["v"]
            if not v:
                continue
            for p in parole:
                if p[7] in gruppo and not p[6]:
                    stesso = uguale(v, re.sub(r"^No\.?\s*", "", p[4], flags=re.I)) if campo == "colata" else False
                    # il valore può stare su più parole (HEA 120, S275J0 +AR): si confrontano parole consecutive
                    if not stesso:
                        vicine = [q for q in parole if q[8] == p[8] and q[0] >= p[0]]
                        vicine.sort(key=lambda q: q[0])
                        n = len(v.split())
                        stesso = uguale(v, " ".join(q[4] for q in vicine[:n])) and len(vicine) >= n
                        if stesso:
                            for q in vicine[1:n]:
                                q[6] = "·"
                    if stesso:
                        p[6] = CAMPI[campo]
                        voce[campo] = v
                        break
        voce["y"] = righe_tab[i - 2]["y"] if i >= 2 else righe_tab[i]["y"]
        trovati.append(voce)
    testata = scheda.get("testata", {})
    for campo, nome in CAMPI.items():
        v = testata.get(campo, {}).get("v", "") if campo in testata else ""
        if not v or campo in ("profilo", "qualita", "colata", "pezzi", "peso"):
            continue
        n = len(v.split())
        per_riga = {}
        for p in parole:
            per_riga.setdefault(p[8], []).append(p)
        fatto = False
        for _, gruppo in sorted(per_riga.items(), key=lambda kv: (min(q[1] for q in kv[1]), kv[1][0][0])):
            frase = " ".join(q[4] for q in sorted(gruppo, key=lambda q: q[0]))
            if CONTATTI.search(frase) or (INDIRIZZO.search(frase) and campo not in ("produttore",)):
                continue
            ordinate = sorted(gruppo, key=lambda q: q[0])
            for s in range(len(ordinate) - n + 1):
                pezzo = ordinate[s:s + n]
                if any(q[6] for q in pezzo):
                    continue
                if uguale(v, " ".join(q[4] for q in pezzo)) and (len(norma(v)) >= 4 or n > 1):
                    pezzo[0][6] = nome
                    for q in pezzo[1:]:
                        q[6] = "·"
                    fatto = True
                    break
            if fatto and len(norma(v)) < 6:
                break
            if fatto and campo not in ("norma_prodotto",):
                break

    img = dritta.copy()
    img.thumbnail((1100, 1100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    esatte = sum(1 for p in parole if p[5])
    prova = dritta.copy()
    dp = ImageDraw.Draw(prova)
    for p in parole:
        box = [p[0] * Wd / 1000, p[1] * Hd / 1000, p[2] * Wd / 1000, p[3] * Hd / 1000]
        dp.rectangle(box, outline=(230, 90, 0) if p[6] else ((40, 110, 220) if p[5] else (150, 150, 150)))
    prova.save(QUI / "risultati" / f"controllo_{pid}.png")
    print(f"{pid}: giro {gradi}°, inclinazione {incl}°, {len(parole)} parole "
          f"({esatte} esatte), {len(righe_tab)} righe tabella, {len(trovati)} voci, dati "
          f"{sum(1 for p in parole if p[6] and p[6] != '·')}; tempi raddrizza {t_raddrizza:.2f}s "
          f"tesseract {t_tess:.2f}s proiezione {t_proiezione:.2f}s")
    return {
        "pid": pid,
        "tipo": "Certificato 3.1",
        "img": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(),
        "w": img.width, "h": img.height,
        "giro": -gradi, "incl": incl,
        "parole": [[round(p[0], 1), round(p[1], 1), round(p[2], 1), round(p[3], 1), p[4], p[6], p[5], p[7], p[8]]
                   for p in parole],
        "voci": trovati,
        "tempi": [round(t_raddrizza, 2), round(t_tess, 2), round(t_proiezione, 2)],
    }


def ordine_catena(pagine: dict) -> list[dict]:
    """Ordine dello ZIP e della vista: famiglia in ordine di catena, poi ordine di arrivo."""
    voci = [{"pid": p, "fam": v.get("famiglia_attuale") or v.get("famiglia_modello") or "illeggibile"}
            for p, v in pagine.items()]
    for i, v in enumerate(voci):
        v["arrivo"] = i
    return sorted(voci, key=lambda v: (CATENA.index(v["fam"]) if v["fam"] in CATENA else 99, v["arrivo"]))


def main():
    cartella = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    ims = immagini(cartella)
    h = (QUI / "risultati" / "simulazione_31.html").read_text(encoding="utf-8")
    vecchie = json.loads(re.search(r"const PAGINE = (\[.*?\]);\n", h, re.S).group(1))
    schede = json.loads((RIS / f"{LAVORO}_v3" / "schede.json").read_text(encoding="utf-8"))
    elenco = json.loads((RIS / f"{LAVORO}_v2" / "pagine.json").read_text(encoding="utf-8"))
    pagine = []
    for pid, vecchia in zip(PID, vecchie, strict=False):
        ocr = json.loads((RIS / f"{LAVORO}_v2" / "ocr" / f"{pid}.json").read_text(encoding="utf-8"))
        tab = next(b["box"] for b in vecchia["blocchi"] if b["tipo"] == "table")
        pagine.append(pagina(pid, ims[pid], ocr, schede[pid], tab))
    ordine = ordine_catena(elenco)
    dati = {"pagine": pagine, "ordine": ordine, "nomi": NOMI, "catena": CATENA}
    modello = (QUI / "modello_parole.html").read_text(encoding="utf-8")
    uscita = QUI / "risultati" / "parole_31.html"
    uscita.write_text(modello.replace("/*DATI*/{}", json.dumps(dati, ensure_ascii=False)), encoding="utf-8")
    print(uscita)


if __name__ == "__main__":
    main()
