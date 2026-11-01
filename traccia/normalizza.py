"""Normalizzazione deterministica dei testi letti sui documenti.

Ogni funzione e' pura: stesso testo in ingresso, stessa chiave in uscita.
Qui non si decide nulla, si rendono confrontabili DDT e certificati.
Coperti: profili, piatti e lamiere (anche scritture di distinta come PL10*80, L60*6 e misure "LT= SP="),
bulloneria, numeri di documento con prefissi, anni e suffissi di serie.
"""

import re
import unicodedata

_TRAVI = re.compile(r"\b(HEA|HEB|HEM|IPE|UPN|UNP)\s*(\d+)")
_U = re.compile(r"\bU\s+(\d+)\s*X\s*\d+")
_TRE_DIM = re.compile(r"(\d+(?:\.\d+)?)\s*X\s*(\d+(?:\.\d+)?)\s*X\s*(\d+(?:\.\d+)?)")
_DUE_DIM = re.compile(r"(\d+(?:\.\d+)?)\s*X\s*(\d+(?:\.\d+)?)")
_TRE_DIM_SPAZI = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s+(\d{3,}(?:\.\d+)?)\s+(\d{3,}(?:\.\d+)?)(?![\d.])")
_DECIMI = re.compile(r"(\d+)/10\b")
_DECIMALE = re.compile(r"\d+\.\d+")
# Parole che dicono "lamiera" (anche 'SP.012X2450X6000', 'L.DA TRENO', 'PLATES') e parole che dicono "tubo".
_PAROLA_LAMIERA = re.compile(r"\bLAM|COIL|\bSTRIPS?\b|\bPLATES?\b|\bL\.?\s*DA\s+TRENO|\bSP\.\s*\d|\bSPESS")
_PAROLA_TUBO = re.compile(r"\bTUB[OI]|\bCRP\b|\bCHS\b|\bRHS\b|\bSHS\b|Ø|\bDIAM|\bD\.?\s*EST\b")
_PAROLA_PIATTO = re.compile(r"\bRC-|\bPIATT[OI]\b|\bFLAT\b|\bLARGH?[IO]\b")
# Una lamiera ha una sola misura piccola (spessore) e due grandi (larghezza, lunghezza).
SPESSORE_MAX, LATO_MIN = 60, 500


def _forma_lamiera(dims):
    """True se, tra le misure, una sola è uno spessore (<= 60) e le altre sono lati (>= 500)."""
    piccole = [d for d in dims if d <= SPESSORE_MAX]
    return len(piccole) == 1 and all(d >= LATO_MIN for d in dims if d > SPESSORE_MAX) and len(dims) >= 2


# Suffissi legali: tolti anche se incollati alla parola prima ('SETALS.P.A.' -> 'setalspa' -> 'setal').
_FORME_GIURIDICHE = {
    *"spa srl srls sas snc sapa scarl scrl coop gmbh ag kg ltd plc llc inc corp sl sa sau bv nv oy ab as sro".split(),
    "unipersonale",
}
_SUFFISSO_INCOLLATO = re.compile(r"(?<=[a-z]{3})(?:spa|srl|srls|sas|snc|sapa|gmbh)$")
# Parole che non identificano l'azienda (forma giuridica, congiunzioni).
_PAROLE_VUOTE = _FORME_GIURIDICHE | {
    "societa",
    "society",
    "soc",
    "company",
    "co",
    "nchfg",
    "e",
    "and",
    "di",
    "del",
    "della",
    "dei",
    "degli",
    "in",
    "the",
    "it",
}
# Da qui in poi è indirizzo o reparto, non ragione sociale: 'via', 'viale', un CAP a 5 cifre, 'divisione'...
_INIZIO_INDIRIZZO = re.compile(
    r"^(?:via|viale|vialle|piazza|pzza|piazzale|corso|largo|strada|str|loc|localita|zona|zi|km|sede|tel|fax|cap|"
    r"divisione|div|stabilimento|deposito|filiale|unit|plant|\d{5})$"
)


def numero(testo):
    """'5.0' -> '5', '33.70' -> '33.7'."""
    v = float(testo)
    return str(int(v)) if v == int(v) else f"{v:g}"


def profilo(descrizione):
    """Chiave del materiale: stessa chiave per la riga del DDT e per la riga del certificato.

    Esempi: 'TRAVI HE/A 200 L=500' -> 'HEA 200'; 'UPN220 L.6.1M' -> 'UPN 220';
    'LAM NERE 2000x1000x80/10' -> 'LAMIERA 8'; 'Coil 1250x5,00' -> 'LAMIERA 5'.
    """
    s = (descrizione or "").upper().replace(",", ".")
    s = re.sub(r"(?<=\d)\s*\*\s*(?=\d)", "X", s)  # '200,00*10,00' come '200X10'
    s = re.sub(r"POS\.\s*\d+\s*-\s*", "", s)
    s = re.sub(r"HE\s*/\s*([ABM])", r"HE\1", s)

    # Scritture di distinta del costruttore: PL<spessore>*<larghezza>, L<lato>*<spessore>.
    m = re.match(r"\s*PL\s*(\d+(?:\.\d+)?)\s*[*X]\s*(\d+(?:\.\d+)?)\s*$", s)
    if m:
        return f"PIATTO {numero(m.group(2))}x{numero(m.group(1))}"
    m = re.match(r"\s*L\s*(\d+)\s*[*X]\s*(\d+)(?:\s*[*X]\s*(\d+))?\s*$", s)
    if m:
        a, b, c = m.groups()
        return f"ANGOLARE {a} {a} {b}" if c is None else f"ANGOLARE {a} {b} {c}"

    # Bulloneria: la vite prima del dado ("viti ... + dado" e' una vite; "bulloni M12x50" pure).
    m = re.search(r"\b(?:VIT[EI]|BULLON[EI])\b.*?\bM(\d+)\s*X\s*(\d+)", s)
    if m:
        return f"VITE M{m.group(1)}x{m.group(2)}"
    m = re.search(r"\bDAD[OI]\b.*?\bM(\d+)\b", s)
    if m:
        return f"DADO M{m.group(1)}"
    m = re.search(r"\bRONDELL[AE]\b.*?\b(\d{4})\s*-?\s*(\d+)", s)
    if m:
        return f"RONDELLA {m.group(1)}-{m.group(2)}"
    m = re.search(r"\bRONDELL[AE]\b.*?\bM(\d+)\b", s)
    if m:
        return f"RONDELLA M{m.group(1)}"

    # Lamiere e coils: conta solo lo spessore. 'LAMIERA 60-10' è un piatto 60x10 (scrittura di distinta).
    if _PAROLA_LAMIERA.search(s) and not _PAROLA_TUBO.search(s) and not _PAROLA_PIATTO.search(s):
        m = re.search(r"\b(?:LAMIER[AE]|LAM\.?|PL)\s*(\d+)\s*-\s*(\d+)\b", s)
        if m:
            return f"PIATTO {numero(m.group(1))}x{numero(m.group(2))}"
        m = re.search(r"\bSPESSORE\s+(\d+(?:\.\d+)?)\s*MM\b", s) or re.search(
            r"\bSP(?:ESS(?:ORE)?)?\s*[=.:]?\s*(\d+(?:\.\d+)?)", s
        )
        if m:
            return f"LAMIERA {numero(m.group(1))}"
        m = _DECIMI.search(s)
        if m:
            return f"LAMIERA {numero(int(m.group(1)) / 10)}"
        m = _TRE_DIM.search(s) or _TRE_DIM_SPAZI.search(s)
        if m:
            return f"LAMIERA {numero(str(min(float(g) for g in m.groups())))}"
        m = _DUE_DIM.search(s)
        if m and _forma_lamiera([float(g) for g in m.groups()]):
            return f"LAMIERA {numero(str(min(float(g) for g in m.groups())))}"
        m = _DECIMALE.search(s)
        if m:
            return f"LAMIERA {numero(m.group(0))}"

    # Misure scritte per campo: LT=larghezza, LA=larghezza, AL=altezza, SP=spessore ('PIATTO LT=100,0 SP=10,0').
    misure = dict(re.findall(r"\b(LT|LA|AL|SP)\s*=\s*(\d+(?:\.\d+)?)", s))
    if _PAROLA_PIATTO.search(s):
        larghezza = misure.get("LT") or misure.get("LA")
        if larghezza and misure.get("SP"):
            return f"PIATTO {numero(larghezza)}x{numero(misure['SP'])}"
        m = _DUE_DIM.search(s)
        if m:
            return f"PIATTO {numero(m.group(1))}x{numero(m.group(2))}"
    if re.search(r"\bTUB[OI]\b", s) and misure.get("LT") and misure.get("AL") and misure.get("SP"):
        return f"TUBO {numero(misure['LT'])}x{numero(misure['AL'])}x{numero(misure['SP'])}"
    if re.search(r"\bANG(?:OLAR[EI]|OL[OI]|LE|\.)?\b|\bELLE\b", s):
        lati = re.findall(r"\b(?:LT|LA|AL)\s*=\s*(\d+(?:\.\d+)?)", s)
        if lati and misure.get("SP"):  # misure per campo sul DDT: 'LT=50.0 LT=50.0 SP=5.0'
            a, b = lati[0], lati[1] if len(lati) > 1 else lati[0]
            return f"ANGOLARE {numero(a)} {numero(b)} {numero(misure['SP'])}"
        m = _TRE_DIM.search(s)
        if m:
            return "ANGOLARE " + " ".join(numero(g) for g in m.groups())
        m = _DUE_DIM.search(s)
        if m:
            return f"ANGOLARE {numero(m.group(1))} {numero(m.group(1))} {numero(m.group(2))}"
    if re.search(r"\bROUND\b|\bTONDO\b", s):
        return "TONDO " + " ".join(re.findall(r"\d+", s)[:1])

    m = _TRAVI.search(s)
    if m:
        famiglia = "UPN" if m.group(1) == "UNP" else m.group(1)
        return f"{famiglia} {m.group(2)}"
    m = _U.search(s)
    if m:
        return f"UPN {m.group(1)}"
    m = re.search(r"(?<![A-Z0-9])U\s*(\d{2,3})(?![\dX.])", s)  # 'FERRO U 200', 'U200': il profilo a U è l'UPN
    if m:
        return f"UPN {m.group(1)}"

    # Tre misure senza parola: una sola piccola e due grandi è una lamiera ('6000x2500x15'); due piccole e una
    # lunghezza è un tubo ('30x10x1.5'). Con la parola tubo (TUBO, CRP, CHS, Ø) è sempre un tubo.
    tubo = bool(_PAROLA_TUBO.search(s))
    m = _TRE_DIM.search(s)
    if m:
        dims = [float(g) for g in m.groups()]
        if not tubo and _forma_lamiera(dims):
            return f"LAMIERA {numero(str(min(dims)))}"
        return "TUBO " + "x".join(numero(g) for g in m.groups())
    m = _TRE_DIM_SPAZI.search(s)
    if m and not tubo and _forma_lamiera([float(g) for g in m.groups()]):
        return f"LAMIERA {numero(str(min(float(g) for g in m.groups())))}"  # misure di un certificato con spazi
    if tubo or re.match(r"\s*\d+(?:\.\d+)?\s*X\s*\d", s):
        m = _DUE_DIM.search(s)
        if m:
            dims = [float(g) for g in m.groups()]
            if not tubo and _forma_lamiera(dims):
                return f"LAMIERA {numero(str(min(dims)))}"
            return "TUBO " + "x".join(numero(g) for g in m.groups())

    return re.sub(r"\s+", " ", s).strip()


_FAMIGLIE_CHIAVE = re.compile(r"^(?:HEA|HEB|HEM|IPE|UPN|PIATTO|LAMIERA|TUBO|ANGOLARE|TONDO|VITE|DADO|RONDELLA) ")


_RIFERIMENTO = re.compile(
    r"^\s*(?:RIF\.?|RIFERIMENTO|NS\.?\s*RIF|VS\.?\s*(?:ORD|RIF)|ORDINE|COMMESSA|CERTIFICAT[IO]\b|CERT\.)", re.I
)


def e_riferimento(descrizione):
    """Riga di un DDT che non è materiale: riferimento a commessa o ordine ('RIF. COMM NC 2501'), riga di addebito
    dei certificati ('CERTIFICATI: U 200')."""
    return bool(_RIFERIMENTO.match(descrizione or ""))


def riconosciuta(chiave):
    """True se la chiave è una forma normalizzata ('PIATTO 70x10'), non il testo com'era ('LT=50.0 SP=5.0')."""
    return bool(_FAMIGLIE_CHIAVE.match(chiave or ""))


def chiave_larga(chiave):
    """Chiave per documenti che descrivono il materiale a grandi linee (packing list):
    'RONDELLA 7089-10' e 'RONDELLA M10' -> 'RONDELLA 10'."""
    m = re.match(r"RONDELLA (?:\d{4}-|M)(\d+)$", chiave)
    return f"RONDELLA {m.group(1)}" if m else chiave


def stesso_ddt(a, b):
    """'45678' e '2026/45678' sono lo stesso DDT se il numero progressivo coincide."""
    if not a or not b:
        return False
    if a == b:
        return True
    return a.split("/")[-1] == b.split("/")[-1] and ("/" in a) != ("/" in b)


def identita_certificato(cert):
    """Due copie dello stesso certificato: stesso produttore e stesso numero."""
    return (min(aziende(cert.get("produttore")) or {""}), re.sub(r"\W", "", cert.get("numero") or "").lower())


def classe(qualita):
    """Classe di resistenza: 'S275J0+AR' -> 'S275', 'Classe 8.8' -> '8.8', 'VGS - 300 HV' -> '300HV'.

    Serve a escludere i certificati incompatibili (S275 contro S355), non a
    confrontare il grado completo: 'S355 JR' sul DDT e 'S355J2H' sul certificato
    sono la stessa classe, con un avviso.
    """
    s = (qualita or "").upper()
    m = re.search(r"\bS\s?(\d{3})", s)
    if m:
        return "S" + m.group(1)
    m = re.search(r"\b(\d+\.\d)\b", s)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d+)\s*HV\b", s)
    if m:
        return m.group(1) + "HV"
    return None


def grado(qualita):
    """Grado compatto per l'avviso: 'S355 JR' -> 'S355JR', 'S355J2H (EN ...)' -> 'S355J2H'."""
    m = re.search(r"\bS\s?\d{3}\s?[A-Z0-9]*", (qualita or "").upper())
    return m.group(0).replace(" ", "") if m else None


def gradi(qualita):
    """Gradi ammessi da una qualità con alternative: 'S275JR/J0' -> {'S275JR', 'S275J0'}."""
    base = grado(qualita)
    if not base:
        return set()
    m = re.match(r"S\d{3}", base)
    risultato = {base}
    for alt in re.findall(r"/\s*([A-Z0-9]{2})\b", (qualita or "").upper()):
        risultato.add(m.group(0) + alt)
    return risultato


def _parole(testo):
    t = unicodedata.normalize("NFKD", testo or "").encode("ascii", "ignore").decode().lower().replace(".", "")
    return [p for p in re.split(r"[^a-z0-9]+", t) if p]


def nuclei(nome):
    """Nuclei della ragione sociale, uno per ogni parte separata da '/': i token prima dell'indirizzo (via, CAP...)
    e prima del reparto (divisione...), senza forma giuridica, anche se incollata ('SETALS.P.A.' -> ['setal']).

    'S.A.C.I.F. SRL VIA NULLO N.5 20129 MILANO' -> [['sacif']]; 'Società Ambrosiana Costruzioni In Ferro Srl' ->
    [['ambrosiana', 'costruzioni', 'ferro']]. Ogni nucleo porta anche le sigle fatte con le iniziali delle parole
    ('sacif', 'fvs'), usate dal confronto.
    """
    risultato = []
    for parte in (nome or "").split("/"):
        parole = _parole(parte)
        prima = next((i for i, p in enumerate(parole) if i and _INIZIO_INDIRIZZO.match(p)), len(parole))
        parole = [_SUFFISSO_INCOLLATO.sub("", p) for p in parole[:prima]]
        parole = [p for p in parole if p]
        tokens = [p for p in parole if p not in _PAROLE_VUOTE]
        sigle = {"".join(p[0] for p in parole if p not in _FORME_GIURIDICHE), "".join(p[0] for p in tokens)}
        if tokens:
            risultato.append((tokens, {s for s in sigle if len(s) >= 3 and len(tokens) >= 2}))
    return risultato


def aziende(nome):
    """Nuclei della ragione sociale come testo ('sacif', 'ambrosiana costruzioni ferro'): per chiavi e confronti
    di uguaglianza. Per sapere se due nomi sono la stessa azienda usa `stessa_azienda`."""
    return {" ".join(tokens) for tokens, _ in nuclei(nome)}


def _stesso_token(a, b):
    if a == b:
        return True
    corto, lungo = sorted((a, b), key=len)
    return len(corto) >= 3 and corto.isalpha() and lungo.startswith(corto)


def _contenuto(piccolo, grande):
    return all(any(_stesso_token(p, g) for g in grande) for p in piccolo)


def stessa_azienda(a, b, gruppi=()):
    """True se i nuclei si contengono ('SACIF SRL' in 'S.A.C.I.F. SRL SOCIETA' AMBROSIANA COSTRUZIONI IN FERRO'),
    se uno è la sigla dell'altro ('FVS' = Ferramenta Villafranca Siderurgica), oppure se i due nomi stanno nello
    stesso gruppo di `gruppi` (alias del fascicolo: stessa partita IVA). Mai per la sola prima parola."""
    na, nb = nuclei(a), nuclei(b)
    for ta, sa in na:
        for tb, sb in nb:
            if _contenuto(ta, tb) or _contenuto(tb, ta) or "".join(ta) == "".join(tb):
                return True
            if sa & set(tb) or sb & set(ta):
                return True
    for gruppo in gruppi:
        if any(stessa_azienda(a, g) for g in gruppo) and any(stessa_azienda(b, g) for g in gruppo):
            return True
    return False


def piva(testo):
    """Partita IVA come sole cifre ('IT 00716810155' -> '00716810155'); vuoto se non ha 11 cifre."""
    cifre = re.sub(r"\D", "", testo or "")
    return cifre if len(cifre) == 11 else ""


_PREFISSO_COLATA = re.compile(r"^[a-z]{1,2}(?=\d{3})")
_SUFFISSO_COLATA = re.compile(r"(?<=\d{4})[a-z]{1,2}\d?$")
_ETICHETTA_COLATA = re.compile(
    r"\b(?:COLAT[AE]|HEAT|CAST|CHARGE|SCHMELZE|COL\.)\s*(?:N[.°º]?|NO\.?|NR\.?)?\s*[:.]?\s*([A-Z0-9][A-Z0-9/-]{2,})"
)
_ETICHETTA_PLACCA = re.compile(
    r"\b(?:PLACC[AH]E?|PLATE\s*(?:ID|N[.°º]?)|PIASTRA|LOTTO)\s*[:.]?\s*([A-Z0-9][A-Z0-9()/.-]*)"
)


def colata_normale(testo):
    """Forma di confronto di una colata: minuscole, solo lettere e cifre, senza il prefisso di 1-2 lettere incollato
    ('DU123329' -> '123329', 'CE256775' -> '256775') e senza il suffisso corto dopo le cifre ('123329BJ0' ->
    '123329', '3151783B' -> '3151783'). Solo per confrontare: il valore mostrato resta quello letto."""
    s = re.sub(r"[^a-z0-9]", "", (testo or "").lower())
    s = _PREFISSO_COLATA.sub("", s)
    return _SUFFISSO_COLATA.sub("", s)


def stessa_colata(a, b):
    """True se le due colate coincidono nella forma di confronto (almeno tre cifre)."""
    na, nb = colata_normale(a), colata_normale(b)
    return bool(na) and na == nb and len(re.sub(r"\D", "", na)) >= 3


def colate_dichiarate(testo):
    """Colate (e placche) scritte su una riga di DDT: 'Placca: 24G6302(A) Colata: 2458653 Placca: 24G6302(B)
    Colata: 2458653' -> [('2458653', ['24G6302(A)', '24G6302(B)'])]; 'CERT.COL. DU123329BJ0' -> [('DU123329BJ0', [])].
    Una riga con la parola colata/heat/cast/charge e un codice con almeno tre cifre dichiara una colata."""
    s = (testo or "").upper()
    eventi = [(m.start(), "colata", m.group(1)) for m in _ETICHETTA_COLATA.finditer(s)]
    eventi += [(m.start(), "placca", m.group(1)) for m in _ETICHETTA_PLACCA.finditer(s)]
    risultato: dict[str, list[str]] = {}
    placca = ""
    for _, tipo, valore in sorted(eventi):
        valore = valore.strip(".,;:")
        if tipo == "placca":
            placca = valore
        elif len(re.sub(r"\D", "", valore)) >= 3:
            risultato.setdefault(valore, [])
            if placca and placca not in risultato[valore]:
                risultato[valore].append(placca)
            placca = ""
    return list(risultato.items())


def cita_numero(testo, numero_ddt):
    """True se il testo contiene il numero come numero intero ('DDT4321' si', '43210' no)."""
    return re.search(rf"(?<!\d){re.escape(numero_ddt)}(?!\d)", testo or "") is not None


def posizioni(testo):
    """Posizioni d'ordine citate: 'pos. 60' -> {'60'}."""
    return set(re.findall(r"\bpos\.\s*(\d+)", testo or "", re.IGNORECASE))


def chili(testo):
    """Pesi in kg: '2 fogli - 2.000 kg' -> {2000}; 'PER QUANTITA' 706 kg' -> {706}."""
    return {int(m.replace(".", "")) for m in re.findall(r"(\d[\d.]*)\s*kg", testo or "", re.IGNORECASE)}


def numero_normale(testo):
    """Forma di confronto dei numeri di documento: '00731' = '731', '2026/45678' = '45678',
    '7.300/00' = '7300', 'CRT-512 908' = 'crt512908'. Il suffisso di serie ('4321/1') resta."""
    s = (testo or "").strip().lower()
    m = re.fullmatch(r"(?:19|20)\d\d\s*/\s*(\d+)", s) or re.fullmatch(r"(\d{3,})\s+(?:19|20)\d\d", s)
    if m:
        s = m.group(1)
    s = re.sub(r"/0+$", "", s)
    s = re.sub(r"(?<=\d)\s*-\s*(?=\d{1,2}$)", "/", s)  # '3209 - 1' sul timbro è il DDT '3209/1'
    s = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", s)
    s = re.sub(r"[^a-z0-9/]", "", s)
    s = re.sub(r"o(?=\d)|(?<=\d)o", "0", s)  # 'CO19604' e 'C019604' sono lo stesso numero (O letta come zero)
    return s.lstrip("0") or s


def quasi_uguale(a, b):
    """Numeri con le sole cifre della stessa lunghezza che differiscono per una cifra sola ('1002' e '01062'):
    serve per un numero scritto a penna e letto male, mai da solo."""
    ca, cb = re.sub(r"\D", "", a or "").lstrip("0"), re.sub(r"\D", "", b or "").lstrip("0")
    return len(ca) >= 3 and len(ca) == len(cb) and sum(x != y for x, y in zip(ca, cb, strict=True)) == 1


def stesso_numero(dichiarato, letto):
    """None se diversi; 'uguale' se uguali; 'serie' se uno solo dei due ha un suffisso di serie corto ('5678/1');
    'prefisso' se il letto ha un prefisso in più (o il contrario)."""
    a, b = numero_normale(dichiarato), numero_normale(letto)
    if not a or not b:
        return None
    if a == b:
        return "uguale"
    a2, b2 = a.replace("/", ""), b.replace("/", "")
    if a2 == b2:
        return "uguale"
    for x, y in ((a, b), (b, a)):
        m = re.fullmatch(r"(.+)/\d{1,2}", x)
        if m and "/" not in y and m.group(1) == y and len(y) >= 3:
            return "serie"
    if (len(a2) >= 5 and b2.endswith(a2)) or (len(b2) >= 5 and a2.endswith(b2)):
        return "prefisso"
    # numeri corti: il prefisso deve essere staccato ('99-777' contiene '777', '1777' no)
    if len(a2) >= 3 and re.search(rf"[^a-z0-9]{re.escape(a2)}$", (letto or "").lower().strip()):
        return "prefisso"
    return None


_DDT_NEL_NOME = re.compile(r"(?i)(?<![a-z])d\.?d\.?t\.?\s*(?:n\.?|nr\.?|num\.?)?\s*[:._-]?\s*(\d[\d./-]*\d|\d)")


def ddt_nel_nome(percorso):
    """Numeri di DDT citati nel nome del file o delle cartelle ('certificato ddt 5681 280325.pdf' -> ['5681'],
    'CERTIFICATI COPERTURA/DDT1062/[Untitled].pdf' -> ['1062']). Solo numeri preceduti da 'DDT'."""
    return [m.group(1) for m in _DDT_NEL_NOME.finditer(percorso or "")]


def cita_ddt(citato, numero_ddt):
    """True se il numero citato (timbro, lettera, tabella) è il DDT: uguale, con suffisso di serie, oppure la coda
    del numero del DDT dopo un separatore ('51159' per 'G02 / 51159'; non '1159')."""
    esito = stesso_numero(citato, numero_ddt)
    if esito in ("uguale", "serie"):
        return True
    coda = numero_normale(citato).replace("/", "")
    return (
        esito == "prefisso"
        and len(coda) >= 3
        and re.search(rf"[^a-z0-9]{re.escape(coda)}$", (numero_ddt or "").lower().strip()) is not None
    )


def contiene_numero(testo, numero):
    """True se il numero di documento (almeno 4 caratteri) compare nel testo come parola o come sequenza di parole
    consecutive, confrontando solo lettere e cifre: 'DDT/DELIVNOTE BA/6577' contiene 'BA/6577', 'note 2026/45678'
    contiene '45678'; '1066009422' non contiene '6577'."""
    a = re.sub(r"[^a-z0-9]", "", (numero or "").lower())
    if len(a) < 4:
        return False
    parole = re.findall(r"[a-z0-9]+", (testo or "").lower())
    for i in range(len(parole)):
        unito = ""
        for j in range(i, len(parole)):
            unito += parole[j]
            if unito == a:
                return True
            if len(unito) >= len(a):
                break
    return False


def progressivo(numero):
    """Parte finale del numero di documento dopo l'ultimo separatore: 'G02 / 51159' -> '51159', '38747/ 51159' ->
    '51159', '2026/45678' -> '45678'; vuoto se il numero non ha un separatore."""
    parti = [p for p in re.split(r"[^a-z0-9]+", (numero or "").lower().strip()) if p]
    return parti[-1].lstrip("0") if len(parti) >= 2 else ""


def dimensioni_piatto(chiave):
    """'PIATTO 80x10' -> (80.0, 10.0); 'LAMIERA 10' -> (None, 10.0); altro -> None."""
    m = re.fullmatch(r"PIATTO (\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)", chiave or "")
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.fullmatch(r"LAMIERA (\d+(?:\.\d+)?)", chiave or "")
    if m:
        return None, float(m.group(1))
    return None


def gruppo(chiave):
    """Raggruppamento delle voci della tabella: piatti e lamiere per spessore ('PL 10'), il resto per chiave."""
    d = dimensioni_piatto(chiave)
    return f"PL {numero(str(d[1]))}" if d else chiave


def data_iso(data):
    """'05/06/2026' -> '2026-06-05', anche dentro 'DDT n. 123 del 05/06/2026'; altrimenti il testo com'e'."""
    m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", data or "")
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\b", data or "")  # a penna: '18/5/22'
    if m:
        anno = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
        return f"{anno}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return data or ""
