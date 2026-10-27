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
_DECIMI = re.compile(r"(\d+)/10\b")
_DECIMALE = re.compile(r"\d+\.\d+")

_PAROLE_VUOTE = {"spa", "srl", "gmbh", "kg", "co", "nchfg", "sau", "sl", "ltd"}


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

    # Lamiere e coils: conta solo lo spessore.
    if re.search(r"\bLAM|\bCOIL", s):
        m = re.search(r"\bSPESSORE\s+(\d+(?:\.\d+)?)\s*MM\b", s) or re.search(r"\bSP\s*[=.:]?\s*(\d+(?:\.\d+)?)", s)
        if m:
            return f"LAMIERA {numero(m.group(1))}"
        m = _TRE_DIM.search(s)
        if m:
            return f"LAMIERA {numero(str(min(float(g) for g in m.groups())))}"
        m = _DECIMI.search(s)
        if m:
            return f"LAMIERA {numero(int(m.group(1)) / 10)}"
        m = _DECIMALE.search(s)
        if m:
            return f"LAMIERA {numero(m.group(0))}"

    # Misure scritte per campo: LT=larghezza, LA=larghezza, AL=altezza, SP=spessore ('PIATTO LT=100,0 SP=10,0').
    misure = dict(re.findall(r"\b(LT|LA|AL|SP)\s*=\s*(\d+(?:\.\d+)?)", s))
    if re.search(r"\bRC-|\bPIATT[OI]\b|\bFLAT\b|\bLARGHI\b", s):
        larghezza = misure.get("LT") or misure.get("LA")
        if larghezza and misure.get("SP"):
            return f"PIATTO {numero(larghezza)}x{numero(misure['SP'])}"
        m = _DUE_DIM.search(s)
        if m:
            return f"PIATTO {numero(m.group(1))}x{numero(m.group(2))}"
    if re.search(r"\bTUB[OI]\b", s) and misure.get("LT") and misure.get("AL") and misure.get("SP"):
        return f"TUBO {numero(misure['LT'])}x{numero(misure['AL'])}x{numero(misure['SP'])}"
    if re.search(r"\bANG(?:OLAR[EI]|OL[OI]|LE|\.)?\b|\bELLE\b", s):
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

    m = _TRE_DIM.search(s)
    if m:
        return "TUBO " + "x".join(numero(g) for g in m.groups())
    if "TUBO" in s or re.match(r"\s*\d+(?:\.\d+)?\s*X\s*\d", s):
        m = _DUE_DIM.search(s)
        if m:
            return "TUBO " + "x".join(numero(g) for g in m.groups())

    return re.sub(r"\s+", " ", s).strip()


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


def aziende(nome):
    """Ragioni sociali complete senza suffisso legale, mai soltanto la prima parola."""
    risultato = set()
    for parte in (nome or "").split("/"):
        parte = unicodedata.normalize("NFKD", parte).encode("ascii", "ignore").decode().lower().replace(".", "")
        parole = [p for p in re.split(r"[^a-z0-9]+", parte) if p and p not in _PAROLE_VUOTE]
        if parole:
            risultato.add(" ".join(parole))
    return risultato


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
    s = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", s)
    s = re.sub(r"[^a-z0-9/]", "", s)
    return s.lstrip("0") or s


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
    """'05/06/2026' -> '2026-06-05'; altrimenti il testo com'e'."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", data or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else (data or "")
