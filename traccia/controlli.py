"""Controlli Python sulla scheda scritta dall'agente, prima di congelarla in archivio.

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
# Valori ammessi per i campi scelti (istruzioni/famiglie/*.md); vuoto = non determinato.
VALORI_ENUM = {
    "tipo_proposto": {
        "",
        "commerciante_costruttore",
        "acciaieria_commerciante",
        "costruttore_cliente",
        "non_determinabile",
    },
    "tipo_materiale": {"", "profilati_lamiere_tubi", "bulloneria", "materia_prima"},
    "servizio": {"", "si", "no"},
}
MAX_TRASCRIZIONE = 100_000  # caratteri: un testo ostile non deve gonfiare archivio, prove e contesto della chat
MAX_MOTIVO = 1000
MAX_AVVISI, MAX_AVVISO = 20, 300
MAX_ENUM = 40


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


VUOTO = {"v": "", "cit": "", "zona": []}


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
    nome = campo.split(".")[-1]
    if nome in CAMPI_ENUM:
        ammessi = VALORI_ENUM.get(nome)
        if ammessi is not None and v["v"] not in ammessi:
            errori.append(
                f"{campo}: valore {v['v'][:40]!r} non ammesso (uno tra {', '.join(sorted(a for a in ammessi if a))})"
            )
        elif len(v["v"]) > MAX_ENUM:
            errori.append(f"{campo}: valore troppo lungo")
        return
    if not v["cit"]:
        errori.append(f"{campo}: valore senza citazione")
    elif _compatto(v["cit"]) not in _compatto(testo_pagina):
        errori.append(f"{campo}: la citazione {v['cit'][:60]!r} non si trova nella trascrizione")
    elif _compatto(v["v"]) not in _compatto(v["cit"]):
        errori.append(f"{campo}: il valore {v['v'][:40]!r} non sta nella sua citazione")


class _Esito:
    """Raccoglie gli errori. Con `correggi` gli errori di campo non bloccano: il valore si scarta e resta un avviso
    sulla scheda (conoscenza 03, regola 3: la testata resta anche se una riga o un riferimento è sbagliato)."""

    def __init__(self, scheda: dict, correggi: bool):
        self.scheda, self.correggi = scheda, correggi
        self.bloccanti: list[str] = []
        self.avvisi: list[str] = []

    def campo(self, messaggi: list[str], azzera=None) -> bool:
        """Errori di campo: bloccanti senza `correggi`; altrimenti `azzera()` ripulisce e resta l'avviso."""
        if not messaggi:
            return False
        if self.correggi:
            self.avvisi += [f"valore scartato dal controllo: {m}"[:MAX_AVVISO] for m in messaggi]
            if azzera:
                azzera()
        else:
            self.bloccanti += messaggi
        return True

    def errori(self) -> list[str]:
        if self.avvisi and not self.bloccanti:
            avvisi = self.scheda.get("avvisi")
            self.scheda["avvisi"] = [a for a in avvisi if isinstance(a, str)] if isinstance(avvisi, list) else []
            for a in self.avvisi:
                if a not in self.scheda["avvisi"] and len(self.scheda["avvisi"]) < MAX_AVVISI:
                    self.scheda["avvisi"].append(a)
        return self.bloccanti


def _campi_valore(prefisso: str, oggetto: dict, nomi: list[str], testo: str, esito: _Esito) -> None:
    for k in nomi:
        messaggi: list[str] = []
        _valore(f"{prefisso}{k}", oggetto[k], testo, messaggi)
        esito.campo(messaggi, lambda k=k: oggetto.__setitem__(k, dict(VUOTO)))


def valida(scheda, testo_nativo: str = "", correggi: bool = False) -> list[str]:
    """Errori in italiano, da restituire all'agente per la correzione. Lista vuota = scheda valida.

    Con `correggi=True` tornano solo gli errori bloccanti (forma della scheda, famiglia, testata, righe): un
    riferimento, timbro o segno malformato viene tolto, un valore con citazione non trovata viene svuotato, un
    riferimento di tipo sconosciuto diventa `altro`; ogni correzione lascia un avviso sulla scheda.
    """
    if not isinstance(scheda, dict):
        return ["la scheda deve essere un oggetto JSON"]
    errori = [f"manca la chiave {k!r}" for k in CHIAVI if k not in scheda]
    estranee = [k for k in scheda if k not in CHIAVI]
    if correggi:
        for k in estranee:
            scheda.pop(k)
    else:
        errori += [f"chiave non prevista {k!r}" for k in estranee]
    if errori:
        return errori
    famiglia = scheda["famiglia"]
    if famiglia not in FAMIGLIE:
        return [f"famiglia {famiglia!r} non valida: una tra {', '.join(FAMIGLIE)}"]
    esito = _Esito(scheda, correggi)
    if scheda["orientamento"] not in (0, 90, 180, 270):
        esito.campo(["orientamento: 0, 90, 180 o 270"], lambda: scheda.__setitem__("orientamento", 0))
    for k in ("utile", "bianca", "continua_pagina_prima"):
        if not isinstance(scheda[k], bool):
            esito.campo([f"{k}: true o false"], lambda k=k: scheda.__setitem__(k, bool(scheda[k])))
    for k in ("trascrizione", "motivo"):
        if not isinstance(scheda[k], str):
            esito.bloccanti.append(f"{k}: testo")
    if esito.bloccanti:
        return esito.bloccanti
    if len(scheda["trascrizione"]) > MAX_TRASCRIZIONE:
        esito.bloccanti.append(f"trascrizione: oltre {MAX_TRASCRIZIONE} caratteri")
    if len(scheda["motivo"]) > MAX_MOTIVO:
        esito.campo(
            [f"motivo: oltre {MAX_MOTIVO} caratteri"],
            lambda: scheda.__setitem__("motivo", scheda["motivo"][:MAX_MOTIVO]),
        )
    testo = scheda["trascrizione"] + "\n" + (testo_nativo or "")
    c_testata, c_righe = campi()[famiglia]
    testata = scheda["testata"]
    if not isinstance(testata, dict) or set(testata) != set(c_testata):
        esito.bloccanti.append(f"testata: servono esattamente i campi {', '.join(c_testata) or '(nessuno)'}")
    else:
        _campi_valore("", testata, c_testata, testo, esito)
    if not isinstance(scheda["righe"], list) or (scheda["righe"] and not c_righe):
        esito.bloccanti.append("righe: lista" + ("" if c_righe else " vuota per questa famiglia"))
    else:
        for i, riga in enumerate(scheda["righe"]):
            if not isinstance(riga, dict) or set(riga) != set(c_righe):
                esito.bloccanti.append(f"righe[{i}]: servono esattamente i campi {', '.join(c_righe)}")
                continue
            _campi_valore(f"righe[{i}].", riga, c_righe, testo, esito)
    _riferimenti(scheda, testo, esito)
    _timbri(scheda, testo, esito)
    _segni(scheda, esito)
    avvisi = scheda["avvisi"]
    if not isinstance(avvisi, list) or not all(isinstance(a, str) for a in avvisi):
        esito.campo(
            ["avvisi: lista di frasi"],
            lambda: scheda.__setitem__(
                "avvisi", [a for a in avvisi if isinstance(a, str)] if isinstance(avvisi, list) else []
            ),
        )
    elif len(avvisi) > MAX_AVVISI or any(len(a) > MAX_AVVISO for a in avvisi):
        esito.campo(
            [f"avvisi: al massimo {MAX_AVVISI} frasi di {MAX_AVVISO} caratteri"],
            lambda: scheda.__setitem__("avvisi", [a[:MAX_AVVISO] for a in avvisi[:MAX_AVVISI]]),
        )
    return esito.errori()


def _riferimenti(scheda: dict, testo: str, esito: _Esito) -> None:
    elenco = scheda["riferimenti"]
    if not isinstance(elenco, list):
        esito.campo(["riferimenti: lista"], lambda: scheda.__setitem__("riferimenti", []))
        return
    tenuti = []
    for i, r in enumerate(elenco):
        if not isinstance(r, dict) or set(r) != {"tipo", "v", "cit", "zona"}:
            esito.campo([f"riferimenti[{i}]: {{tipo, v, cit, zona}} con tipo tra {', '.join(TIPI_RIFERIMENTO)}"])
            continue
        if r["tipo"] not in TIPI_RIFERIMENTO:
            # tipo non in elenco (es. "cup", "cig"): non è un errore, il riferimento resta come `altro`
            esito.avvisi.append(f"riferimento di tipo «{str(r['tipo'])[:20]}» registrato come «altro»")
            r["tipo"] = "altro"
        messaggi: list[str] = []
        _valore(f"riferimenti[{i}]", {k: r[k] for k in ("v", "cit", "zona")}, testo, messaggi)
        if esito.campo(messaggi):
            continue
        tenuti.append(r)
    if esito.correggi:
        scheda["riferimenti"] = tenuti


def _timbri(scheda: dict, testo: str, esito: _Esito) -> None:
    elenco = scheda["timbri"]
    if not isinstance(elenco, list):
        esito.campo(["timbri: lista"], lambda: scheda.__setitem__("timbri", []))
        return
    tenuti = []
    for i, t in enumerate(elenco):
        if not isinstance(t, dict) or set(t) != set(CAMPI_TIMBRO) or not isinstance(t.get("a_mano"), bool):
            esito.campo([f"timbri[{i}]: servono {', '.join(CAMPI_TIMBRO)} (a_mano true/false)"])
            continue
        if not _zona_valida(t["zona"]):
            if esito.campo([f"timbri[{i}]: zona non valida"]):
                t["zona"] = []
        messaggi = []
        for campo in ("chi", "testo", "ddt_citato", "data_ddt", "destinatario"):
            if not isinstance(t[campo], str):
                messaggi.append(f"timbri[{i}].{campo}: testo richiesto")
            elif t[campo] and _compatto(t[campo]) not in _compatto(testo):
                messaggi.append(f"timbri[{i}].{campo}: non si trova nella trascrizione")
        if not isinstance(t["testo"], str) or not t["testo"]:
            messaggi.append(f"timbri[{i}]: testo del timbro mancante")
        elif isinstance(t["ddt_citato"], str) and _compatto(t["ddt_citato"]) not in _compatto(t["testo"]):
            messaggi.append(f"timbri[{i}]: DDT non presente nel testo del timbro")
        if esito.campo(messaggi):
            continue
        tenuti.append(t)
    if esito.correggi:
        scheda["timbri"] = tenuti


def _segni(scheda: dict, esito: _Esito) -> None:
    elenco = scheda["segni"]
    if not isinstance(elenco, list):
        esito.campo(["segni: lista"], lambda: scheda.__setitem__("segni", []))
        return
    tenuti = []
    for i, sg in enumerate(elenco):
        if (
            not isinstance(sg, dict)
            or set(sg) != {"tipo", "riga", "testo", "zona"}
            or sg["tipo"] not in TIPI_SEGNO
            or not isinstance(sg["riga"], int)
            or not _zona_valida(sg["zona"])
        ):
            esito.campo([f"segni[{i}]: {{tipo, riga, testo, zona}} con tipo tra {', '.join(TIPI_SEGNO)} e zona valida"])
            continue
        tenuti.append(sg)
    if esito.correggi:
        scheda["segni"] = tenuti


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
    """Sulle pagine con testo nativo la zona di ogni valore diventa esatta; altrimenti resta quella dell'agente."""

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
