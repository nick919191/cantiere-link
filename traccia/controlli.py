"""Controlli Python sulla scheda scritta da Claude, prima di congelarla in archivio.

Una scheda entra solo se: ha la forma giusta, ha tutti i campi della sua famiglia, ogni valore ha una citazione
che sta nella trascrizione (o nel testo nativo) e il valore sta nella citazione. Le zone, quando la pagina ha
testo nativo, si ricalcolano esatte dalla posizione delle parole.
"""

import re
import unicodedata

from .famiglie import FAMIGLIE, TIPI_RIFERIMENTO, TIPI_SEGNO, campi

CHIAVI = [
    "famiglia",
    "utile",
    "motivo",
    "orientamento",
    "bianca",
    "continua_pagina_prima",
    "trascrizione",
    "testata",
    "righe",
    "riferimenti",
    "timbri",
    "segni",
    "avvisi",
]
CAMPI_TIMBRO = ["chi", "testo", "ddt_citato", "data_ddt", "destinatario", "a_mano", "zona"]
CAMPI_ENUM = {"tipo_proposto", "tipo_materiale", "servizio", "componente"}  # valori scelti, non trascritti


def piatto(testo: str) -> str:
    """Forma di confronto: minuscole, senza accenti, solo lettere e cifre separate da uno spazio."""
    t = unicodedata.normalize("NFKD", testo or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", t))


def _compatto(testo: str) -> str:
    return piatto(testo).replace(" ", "")


def _zona_valida(z) -> bool:
    return z == [] or (
        isinstance(z, list)
        and len(z) == 4
        and all(isinstance(v, int) and 0 <= v <= 1000 for v in z)
        and z[0] < z[2]
        and z[1] < z[3]
    )


def _valore(campo: str, v, testo_pagina: str, errori: list[str]) -> None:
    if not isinstance(v, dict) or set(v) != {"v", "cit", "zona"}:
        errori.append(f"{campo}: serve un oggetto {{v, cit, zona}}")
        return
    if not isinstance(v["v"], str) or not isinstance(v["cit"], str):
        errori.append(f"{campo}: v e cit devono essere testo")
        return
    if not _zona_valida(v["zona"]):
        errori.append(f"{campo}: zona deve essere [] oppure [x0, y0, x1, y1] interi 0-1000 con x0<x1, y0<y1")
    if not v["v"]:
        return
    if campo.split(".")[-1] in CAMPI_ENUM:
        return
    if not v["cit"]:
        errori.append(f"{campo}: valore senza citazione")
    elif _compatto(v["cit"]) not in _compatto(testo_pagina):
        errori.append(f"{campo}: la citazione {v['cit'][:60]!r} non si trova nella trascrizione")
    elif _compatto(v["v"]) not in _compatto(v["cit"]):
        errori.append(f"{campo}: il valore {v['v'][:40]!r} non sta nella sua citazione")


def valida(scheda, testo_nativo: str = "") -> list[str]:
    """Errori in italiano, da restituire a Claude per la correzione. Lista vuota = scheda valida."""
    if not isinstance(scheda, dict):
        return ["la scheda deve essere un oggetto JSON"]
    errori = [f"manca la chiave {k!r}" for k in CHIAVI if k not in scheda]
    errori += [f"chiave non prevista {k!r}" for k in scheda if k not in CHIAVI]
    if errori:
        return errori
    famiglia = scheda["famiglia"]
    if famiglia not in FAMIGLIE:
        return [f"famiglia {famiglia!r} non valida: una tra {', '.join(FAMIGLIE)}"]
    if scheda["orientamento"] not in (0, 90, 180, 270):
        errori.append("orientamento: 0, 90, 180 o 270")
    for k in ("utile", "bianca", "continua_pagina_prima"):
        if not isinstance(scheda[k], bool):
            errori.append(f"{k}: true o false")
    for k in ("trascrizione", "motivo"):
        if not isinstance(scheda[k], str):
            errori.append(f"{k}: testo")
    if errori:
        return errori
    testo = scheda["trascrizione"] + "\n" + (testo_nativo or "")
    c_testata, c_righe = campi()[famiglia]
    testata = scheda["testata"]
    if not isinstance(testata, dict) or set(testata) != set(c_testata):
        errori.append(f"testata: servono esattamente i campi {', '.join(c_testata) or '(nessuno)'}")
    else:
        for k in c_testata:
            _valore(k, testata[k], testo, errori)
    if not isinstance(scheda["righe"], list) or (scheda["righe"] and not c_righe):
        errori.append("righe: lista" + ("" if c_righe else " vuota per questa famiglia"))
    else:
        for i, riga in enumerate(scheda["righe"]):
            if not isinstance(riga, dict) or set(riga) != set(c_righe):
                errori.append(f"righe[{i}]: servono esattamente i campi {', '.join(c_righe)}")
                continue
            for k in c_righe:
                _valore(f"righe[{i}].{k}", riga[k], testo, errori)
    for i, r in enumerate(scheda["riferimenti"] if isinstance(scheda["riferimenti"], list) else [None]):
        if not isinstance(r, dict) or set(r) != {"tipo", "v", "cit", "zona"} or r["tipo"] not in TIPI_RIFERIMENTO:
            errori.append(f"riferimenti[{i}]: {{tipo, v, cit, zona}} con tipo tra {', '.join(TIPI_RIFERIMENTO)}")
        else:
            _valore(f"riferimenti[{i}]", {k: r[k] for k in ("v", "cit", "zona")}, testo, errori)
    for i, t in enumerate(scheda["timbri"] if isinstance(scheda["timbri"], list) else [None]):
        if not isinstance(t, dict) or set(t) != set(CAMPI_TIMBRO) or not isinstance(t.get("a_mano"), bool):
            errori.append(f"timbri[{i}]: servono {', '.join(CAMPI_TIMBRO)} (a_mano true/false)")
        elif not _zona_valida(t["zona"]):
            errori.append(f"timbri[{i}]: zona non valida")
        else:
            for campo in ("chi", "testo", "ddt_citato", "data_ddt", "destinatario"):
                if not isinstance(t[campo], str):
                    errori.append(f"timbri[{i}].{campo}: testo richiesto")
                elif t[campo] and _compatto(t[campo]) not in _compatto(testo):
                    errori.append(f"timbri[{i}].{campo}: non si trova nella trascrizione")
            if not t["testo"]:
                errori.append(f"timbri[{i}]: testo del timbro mancante")
            elif isinstance(t["ddt_citato"], str) and isinstance(t["testo"], str):
                if _compatto(t["ddt_citato"]) not in _compatto(t["testo"]):
                    errori.append(f"timbri[{i}]: DDT non presente nel testo del timbro")
    for i, s in enumerate(scheda["segni"] if isinstance(scheda["segni"], list) else [None]):
        if (
            not isinstance(s, dict)
            or set(s) != {"tipo", "riga", "testo", "zona"}
            or s["tipo"] not in TIPI_SEGNO
            or not isinstance(s["riga"], int)
        ):
            errori.append(f"segni[{i}]: {{tipo, riga, testo, zona}} con tipo tra {', '.join(TIPI_SEGNO)}")
    if not isinstance(scheda["avvisi"], list) or not all(isinstance(a, str) for a in scheda["avvisi"]):
        errori.append("avvisi: lista di frasi")
    return errori


def zona_esatta(parole: list[list], valore: str, citazione: str) -> list[int] | None:
    """Riquadro delle parole del testo nativo che contengono il valore (dentro la citazione, se possibile)."""
    if not parole or not valore:
        return None
    gettoni = [_compatto(p[4]) for p in parole]
    obiettivo = _compatto(valore)
    if not obiettivo:
        return None
    contesto = _compatto(citazione)
    candidati = []
    for i in range(len(gettoni)):
        unito = ""
        for j in range(i, min(i + 12, len(gettoni))):
            unito += gettoni[j]
            if obiettivo in unito:
                finestra = "".join(gettoni[max(0, i - 8) : j + 9])
                candidati.append((contesto[:20] not in finestra, j - i, i, j))
                break
            if len(unito) > len(obiettivo) + 40:
                break
    if not candidati:
        return None
    _, _, i, j = min(candidati)
    scelte = parole[i : j + 1]
    return [min(p[0] for p in scelte), min(p[1] for p in scelte), max(p[2] for p in scelte), max(p[3] for p in scelte)]


def aggiungi_zone_esatte(scheda: dict, parole: list[list]) -> None:
    """Sulle pagine con testo nativo la zona di ogni valore diventa esatta; altrimenti resta quella di Claude."""

    def tratta(v: dict) -> None:
        z = zona_esatta(parole, v.get("v", ""), v.get("cit", ""))
        v["zona_esatta"] = z is not None
        if z:
            v["zona"] = z

    for v in scheda.get("testata", {}).values():
        tratta(v)
    for riga in scheda.get("righe", []):
        for v in riga.values():
            tratta(v)
    for r in scheda.get("riferimenti", []):
        tratta(r)
