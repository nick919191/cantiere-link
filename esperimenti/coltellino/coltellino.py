"""Coltellino: taglia il testo OCR di una pagina tenendo i valori e togliendo il modulo.

Regole, tutte deterministiche:
  pulizia   - segnaposto di immagini, righe separatrici, celle vuote, righe ripetute nella pagina, righe di sole
              numerazioni («1. 2. 3. ... 99.»);
  contatti  - telefono, fax, e-mail, sito, partita IVA, capitale sociale, REA, IBAN;
  prosa     - righe di testo lunghe (>200 caratteri) quasi senza cifre: condizioni di vendita, formule legali;
  misure    - nei certificati, celle decimali delle tabelle (analisi chimica, prove meccaniche);
  modulo    - righe la cui «forma» compare in molti documenti di emittenti diversi e non ha mai portato un valore:
              si impara da cantieri già fatti (dizionario), si applica ai nuovi.
Il dizionario si impara con `impara(pagine)`; `taglia(testo, famiglia, dizionario)` restituisce il testo ridotto.
"""

import re
from collections import defaultdict

CONTATTI = re.compile(
    r"partita iva|p\.? ?iva|codice fiscale|cod\. ?fisc|capitale sociale|cap\. ?soc|r\.?e\.?a\.|"
    r"registro (delle )?imprese|reg\. ?imp|\btel[.:]|\btelefono|\bphone|\bph\b|\bfax\b|e-?mail|www\.|\.com\b|"
    r"\.it\b|\bpec\b|iban|\bbic\b|swift|banca d'appoggio|\bbanco\b|n\.? ?iscr",
    re.I,
)
# misure di analisi e prove: 0,08 · 0,010 · 1,31 · <0.5 — non pesi con le migliaia (1.855), lunghezze (18,10),
# colate con suffisso (247916.2)
DECIMALE = re.compile(r"[<>≤≥]?\s*-?(?:0[.,]\d+|[1-9][.,]\d{1,2})")
SOCIETA = re.compile(r"\b(s\.?p\.?a|s\.?r\.?l|s\.?l|s\.?a|gmbh|ltd|ag|co\.?)\b\.?", re.I)
VALORE = re.compile(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\bddt\b|d\.d\.t|n[°o.]\s*\d|numero|num\.|doc\.", re.I)


PROTETTO = re.compile(  # pezzi che portano un valore: mai tolti come prosa o modulo
    r"\ben ?\d{3,5}|\b(hea|heb|hem|ipe|ipn|upn|upe|unp|piatt|lamier|tubo|angolar|l ?\d+x)\b|\d+ ?[x×] ?\d+|"
    r"\bs ?\d{3}|\bddt\b|d\.d\.t|n[°o.] ?\d|colata|heat|cast|charge|lotto|\bcpr\b|dop\b",
    re.I,
)
ANNOTAZIONE = re.compile(r'\[?\{"box_2d"')  # OCR in loop: annotazioni JSON ripetute
DIDASCALIA = re.compile(r'"caption"\s*:\s*"((?:[^"\\]|\\.)*)"')


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


MISURA_INTESTAZIONE = re.compile(  # intestazioni di colonne di analisi chimica e prove meccaniche
    r"^(?:[A-Z]{0,2}\d{1,3}\s+)?(?:C|Mn|Si|P|S|Cr|Ni|Mo|Cu|Al|Alt|V|Nb|Ti|B|N|Sn|W|Ca|Ceq|CEV|CE)\s*%?$|"
    r"^(?:[A-Z]{0,2}\d{1,3}\s+)?(?:ReH|ReL|Rm|Rp0?[.,]?2|A\s*%?|A5|Z\s*%|KV\d?|KV/m|J|HB|HV|Rm/ReH)$|"
    r"yield|tensile|elong|impact|resilien|snervament|rottura|allungament|durezza|hardness|piega|bend|"
    r"temp\.?\s*°?c|°c|n/mm|mpa|\bkv\b",
    re.I,
)


def _colonne_misura(blocco: list[list[str]]) -> tuple[set[int], bool]:
    """Colonne da togliere in una tabella e se l'intestazione è stata riconosciuta (>=3 colonne di misura)."""
    colonne = set()
    for celle in blocco[:6]:  # le intestazioni stanno nelle prime righe
        trovate = {i for i, c in enumerate(celle) if c and MISURA_INTESTAZIONE.search(c) and not PROTETTO.search(c)}
        if len(trovate) >= 3:
            colonne |= trovate
    return colonne, len(colonne) >= 3


def _contatto(testo: str) -> bool:
    """Solo pezzi brevi di soli contatti: una cella lunga mescola contatti e dati (intestazione con numero e data)."""
    return len(testo) <= 90 and bool(CONTATTI.search(testo)) and not VALORE.search(testo)


NUMERAZIONE = re.compile(r"^(\d{1,3}\.\s*){8,}$")
FAMIGLIE_CERTIFICATO = {"certificato_31"}
FAMIGLIE_INTATTE = {"packing_costruttore"}  # tabelle di tracciabilità: ogni cella è un dato


def forma(riga: str) -> str:
    t = re.sub(r"\d", "#", riga.lower())
    return re.sub(r"\s+", " ", re.sub(r"[|*_#]{2,}", "#", t)).strip()


def _compatto(testo: str) -> str:
    return re.sub(r"[^a-z0-9]", "", testo.lower())


def impara(pagine: list[dict], valori_di) -> set[str]:
    """Forme di modulo: >=3 documenti, >=2 emittenti, mai un valore (`valori_di(pagina)` -> valori noti)."""
    documenti, emittenti, con_valore = defaultdict(set), defaultdict(set), set()
    for p in pagine:
        valori = [_compatto(v) for v in valori_di(p)]
        pezzi = []
        for r in p["testo"].splitlines():
            r = r.strip()
            pezzi.append(r)
            if r.startswith("|"):  # anche le celle: nelle DoP e nei DDT il modulo sta dentro le tabelle
                pezzi += [c.strip() for c in r.strip("|").split("|") if len(c.strip()) >= 15]
        for r in pezzi:
            if not r:
                continue
            f = forma(r)
            documenti[f].add(p["documento"])
            emittenti[f].add(p["emittente"])
            c = _compatto(r)
            if any(v and v in c for v in valori):
                con_valore.add(f)
    return {
        f
        for f in documenti
        if len(documenti[f]) >= 3
        and len(emittenti[f]) >= 2
        and f not in con_valore
        and len(f) >= 6
        and "#" not in re.sub(r"^[#.\s]+", "", f)  # niente numeri dentro la riga: una cifra può essere un valore
        and not SOCIETA.search(f)  # una ragione sociale ripetuta può essere il produttore
    }


def _prosa(testo: str, soglia: int) -> bool:
    """Testo lungo quasi senza cifre: condizioni, formule legali, descrizioni d'uso. Mai se porta un valore."""
    return len(testo) > soglia and sum(ch.isdigit() for ch in testo) < 0.03 * len(testo) and not PROTETTO.search(testo)


def _cella_utile(cella: str, certificato: bool, dizionario) -> bool:
    if not cella or _contatto(cella) or _prosa(cella, 120):
        return False
    if certificato and DECIMALE.fullmatch(cella):
        return False
    if len(cella) >= 15 and forma(cella) in dizionario:
        return False
    return True


def _blocchi_tabella(righe: list[str]) -> dict[int, tuple[set[int], bool]]:
    """Per ogni riga di tabella: colonne di misura del suo blocco e se l'intestazione è riconosciuta."""
    esito, blocco = {}, []

    def chiudi():
        if blocco:
            celle = [[c.strip() for c in righe[i].strip().strip("|").split("|")] for i in blocco]
            colonne = _colonne_misura(celle)
            esito.update({i: colonne for i in blocco})
            blocco.clear()

    for i, r in enumerate(righe):
        if r.strip().startswith("|"):
            blocco.append(i)
        else:
            chiudi()
    chiudi()
    return esito


def taglia(
    testo: str,
    famiglia: str | None,
    dizionario: set[str] | frozenset = frozenset(),
    traccia=None,
    modo: str = "celle",
) -> str:
    """`traccia`, se è una lista, riceve (regola, riga originale) per ogni riga tolta o ridotta.

    modo «celle»: nei certificati si tolgono le singole celle decimali.
    modo «colonne»: si tolgono le colonne di misura solo se le intestazioni sono riconosciute; le altre tabelle dei
    certificati restano intere, con un avviso.
    """
    intatta = famiglia in FAMIGLIE_INTATTE
    certificato = famiglia in FAMIGLIE_CERTIFICATO
    uscita, viste, avvisata = [], set(), False

    def via(regola, riga):
        if traccia is not None:
            traccia.append((regola, riga))

    righe = []
    for riga in testo.splitlines():
        if ANNOTAZIONE.search(riga):
            via("annotazioni", riga[:200])
            righe += _annotazioni(riga).splitlines()
        else:
            righe.append(riga)
    blocchi = _blocchi_tabella(righe) if modo == "colonne" and certificato else {}
    for n, riga in enumerate(righe):
        r = riga.strip()
        if not r or r.startswith("![") or re.fullmatch(r"\[tbl-\d+\.\w+\]\(tbl-\d+\.\w+\)", r):
            continue
        if r.startswith("|"):
            celle = [c.strip() for c in r.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in celle):
                continue
            if n in blocchi:
                colonne, riconosciuta = blocchi[n]
                if not riconosciuta:  # intestazioni non riconosciute: la tabella resta com'è
                    if not avvisata:
                        uscita.append("[tabella integrale: intestazioni di misura non riconosciute]")
                        avvisata = True
                    uscita.append(r)
                    continue
                if colonne:
                    via("colonne", r)
                    celle = [c for i, c in enumerate(celle) if i not in colonne]
            if not intatta:
                utili = [c for c in celle if _cella_utile(c, certificato and modo == "celle", dizionario)]
                if len(utili) < len([c for c in celle if c]):
                    via("misure", r)
                if not utili:
                    continue
                r = "| " + " | ".join(utili) + " |"
        elif not intatta:
            if NUMERAZIONE.match(r):
                via("pulizia", r)
                continue
            if _prosa(r, 200):
                via("prosa", r)
                continue
        if not intatta:
            if not r.startswith("|") and _contatto(r):
                via("contatti", r)
                continue
            if forma(r) in dizionario:
                via("modulo", r)
                continue
            chiave = _compatto(r)
            if chiave in viste and not r.startswith("|"):  # righe di tabella uguali sono righe di prodotto distinte
                continue
            viste.add(chiave)
        uscita.append(r)
    return "\n".join(uscita)
