"""Coltellino: riduce il testo OCR di una pagina tenendo i valori e togliendo il modulo, prima di inviarlo al modello.

Regole deterministiche, misurate su 439 pagine di 3 cantieri: −47% di testo, nessun valore usato dal motore perso.
  pulizia   - segnaposto, righe separatrici, celle vuote, righe ripetute, numerazioni «1. 2. 3. ... 99.»,
              annotazioni JSON ripetute dall'OCR in loop (si tiene ogni testo una volta);
  contatti  - pezzi brevi di soli contatti: telefono, fax, e-mail, sito, partita IVA, REA, IBAN;
  prosa     - testo lungo quasi senza cifre: condizioni di vendita, formule legali (mai se porta un valore);
  misure    - nei certificati, celle decimali di analisi chimica e prove meccaniche;
  modulo    - frasi che compaiono in molti documenti di emittenti diversi e non hanno mai portato un valore: le
              impara l'app dai cantieri già analizzati su questo computer (nessun dizionario di altri clienti).
"""

import json
import re
import threading

from . import percorsi

CONTATTI = re.compile(
    r"partita iva|p\.? ?iva|codice fiscale|cod\. ?fisc|capitale sociale|cap\. ?soc|r\.?e\.?a\.|"
    r"registro (delle )?imprese|reg\. ?imp|\btel[.:]|\btelefono|\bphone|\bph\b|\bfax\b|e-?mail|www\.|\.com\b|"
    r"\.it\b|\bpec\b|iban|\bbic\b|swift|banca d'appoggio|\bbanco\b|n\.? ?iscr",
    re.I,
)
# misure di analisi e prove: 0,08 · 0,010 · 1,31 — non pesi (1.855), lunghezze (18,10), colate con suffisso (247916.2)
DECIMALE = re.compile(r"[<>≤≥]?\s*-?(?:0[.,]\d+|[1-9][.,]\d{1,2})")
SOCIETA = re.compile(r"\b(s\.?p\.?a|s\.?r\.?l|s\.?l|s\.?a|gmbh|ltd|ag|co\.?)\b\.?", re.I)
VALORE = re.compile(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\bddt\b|d\.d\.t|n[°o.]\s*\d|numero|num\.|doc\.", re.I)
PROTETTO = re.compile(  # pezzi che portano un valore: mai tolti come prosa o modulo
    r"\ben ?\d{3,5}|\b(hea|heb|hem|ipe|ipn|upn|upe|unp|piatt|lamier|tubo|angolar|l ?\d+x)\b|\d+ ?[x×] ?\d+|"
    r"\bs ?\d{3}|\bddt\b|d\.d\.t|n[°o.] ?\d|colata|heat|cast|charge|lotto|\bcpr\b|dop\b",
    re.I,
)
ANNOTAZIONE = re.compile(r'\[?\{"box_2d"')
DIDASCALIA = re.compile(r'"caption"\s*:\s*"((?:[^"\\]|\\.)*)"')
NUMERAZIONE = re.compile(r"^(\d{1,3}\.\s*){8,}$")
FAMIGLIE_INTATTE = {"packing_costruttore"}  # tabelle di tracciabilità: ogni cella è un dato
# Formule fisse del modello di DoP (Reg. UE 305/2011): testo di legge, uguale per ogni fabbricante.
FORMULE_DOP = re.compile(
    r"uso previsto|intended use|conforme alla prestazione|in conformity with the declared|sole responsibility|"
    r"responsabilità esclusiva|sistema di valutazione|system of evaluation|prestazione dichiarata|"
    r"declared performance|impieghi strutturali|structural steel products",
    re.I,
)
_LOCK = threading.Lock()


def forma(riga: str) -> str:
    t = re.sub(r"\d", "#", riga.lower())
    return re.sub(r"\s+", " ", re.sub(r"[|*_#]{2,}", "#", t)).strip()


def _compatto(testo: str) -> str:
    return re.sub(r"[^a-z0-9]", "", testo.lower())


def _candidata(f: str) -> bool:
    """Solo frasi: niente numeri dentro, niente ragioni sociali, almeno 4 parole (marchi e città restano)."""
    return (
        len(f) >= 6
        and "#" not in re.sub(r"^[#.\s]+", "", f)
        and not SOCIETA.search(f)
        and len(re.findall(r"[a-zà-ü]{2,}", f)) >= 4
    )


def _pezzi(testo: str) -> list[str]:
    out = []
    for r in testo.splitlines():
        r = r.strip()
        if r:
            out.append(r)
        if r.startswith("|"):  # anche le celle: nelle DoP e nei DDT il modulo sta dentro le tabelle
            out += [c.strip() for c in r.strip("|").split("|") if len(c.strip()) >= 15]
    return out


# ---------- dizionario imparato sul computer dell'utente ----------
def _file():
    return percorsi.RADICE / "coltellino.json"


def _statistiche() -> dict:
    f = _file()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def dizionario() -> frozenset[str]:
    """Forme di modulo: >=3 documenti, >=2 emittenti, mai un valore."""
    return frozenset(f for f, s in _statistiche().items() if len(s["d"]) >= 3 and len(s["e"]) >= 2 and not s.get("v"))


def impara(pagine: list[dict]) -> None:
    """`pagine`: {testo, documento, emittente, valori}. Aggiorna le statistiche delle frasi ripetute."""
    with _LOCK:
        stat = _statistiche()
        for p in pagine:
            valori = [c for c in (_compatto(v) for v in p["valori"]) if len(c) >= 3]
            for r in _pezzi(p["testo"]):
                f = forma(r)
                if not _candidata(f):
                    continue
                s = stat.setdefault(f, {"d": [], "e": [], "v": False})
                if p["documento"] not in s["d"] and len(s["d"]) < 20:
                    s["d"].append(p["documento"])
                if p["emittente"] and p["emittente"] not in s["e"] and len(s["e"]) < 20:
                    s["e"].append(p["emittente"])
                c = _compatto(r)
                if any(v in c for v in valori):
                    s["v"] = True
        f = _file()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(stat, ensure_ascii=False), encoding="utf-8")
        tmp.replace(f)


# ---------- taglio ----------
def _annotazioni(riga: str) -> str:
    """Annotazioni JSON ripetute -> ogni didascalia una sola volta (il contenuto resta, le ripetizioni no)."""
    i = ANNOTAZIONE.search(riga).start()
    viste, testi = set(), []
    for m in DIDASCALIA.finditer(riga[i:]):
        t = m.group(1).replace("\\n", "\n").replace('\\"', '"')
        k = _compatto(t)
        if k and k not in viste:
            viste.add(k)
            testi.append(t)
    return riga[:i] + "\n" + "\n".join(testi)


def _contatto(testo: str) -> bool:
    """Solo pezzi brevi di soli contatti: una cella lunga mescola contatti e dati (intestazione con numero e data)."""
    return len(testo) <= 90 and bool(CONTATTI.search(testo)) and not VALORE.search(testo)


def _prosa(testo: str, soglia: int) -> bool:
    return len(testo) > soglia and sum(ch.isdigit() for ch in testo) < 0.03 * len(testo) and not PROTETTO.search(testo)


def _formula(testo: str, famiglia: str | None) -> bool:
    return (
        famiglia in ("dop_ce_prodotto", "dop_costruttore")
        and bool(FORMULE_DOP.search(testo))
        and not (PROTETTO.search(testo))
    )


def _cella_utile(cella: str, famiglia: str | None, diz) -> bool:
    if not cella or _contatto(cella) or _prosa(cella, 120) or _formula(cella, famiglia):
        return False
    if famiglia == "certificato_31" and DECIMALE.fullmatch(cella):
        return False
    return not (len(cella) >= 15 and forma(cella) in diz)


def taglia(testo: str, famiglia: str | None, diz: frozenset[str] = frozenset()) -> str:
    intatta = famiglia in FAMIGLIE_INTATTE
    righe = []
    for riga in testo.splitlines():
        righe += _annotazioni(riga).splitlines() if ANNOTAZIONE.search(riga) else [riga]
    uscita, viste = [], set()
    for riga in righe:
        r = riga.strip()
        if not r or r.startswith("![") or re.fullmatch(r"\[tbl-\d+\.\w+\]\(tbl-\d+\.\w+\)", r):
            continue
        tabella = r.startswith("|")
        if tabella:
            celle = [c.strip() for c in r.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in celle):
                continue
            if not intatta:
                celle = [c for c in celle if _cella_utile(c, famiglia, diz)]
                if not celle:
                    continue
                r = "| " + " | ".join(celle) + " |"
        elif not intatta and (
            NUMERAZIONE.match(r) or _prosa(r, 200) or _contatto(r) or _formula(r, famiglia) or forma(r) in diz
        ):
            continue
        if not intatta:
            chiave = _compatto(r)
            if chiave in viste and not tabella:  # righe di tabella uguali sono prodotti distinti
                continue
            viste.add(chiave)
        uscita.append(r)
    return "\n".join(uscita)
