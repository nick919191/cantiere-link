"""Dalle schede delle pagine alle prove del fascicolo (deterministico).

Raggruppa le pagine in documenti (DDT, certificati, DoP, tabella del costruttore), decide i ruoli dal fascicolo
(costruttore = chi riceve i DDT da più emittenti) e registra per ogni valore la sua fonte: pagina, citazione, zona.
"""

import re
from collections import defaultdict

from . import normalizza as nz

FORMATO = "prove/2"


def _v(campo: dict | None) -> str:
    return (campo or {}).get("v", "").strip()


def _nucleo(nome: str) -> frozenset:
    return frozenset(nz.aziende(nome))


def _stessa_azienda(a: str, b: str) -> bool:
    return bool(_nucleo(a) & _nucleo(b))


class Fonti:
    def __init__(self, pagine: dict[str, dict]):
        self.pagine = pagine
        self.tutte: dict[str, dict] = {}

    def aggiungi(self, pid: str, campo: str, valore: dict | None) -> str | None:
        if not valore or not _v(valore):
            return None
        fid = f"{pid}.{campo}"
        p = self.pagine[pid]
        self.tutte[fid] = {
            "pid": pid,
            "file": p["file"],
            "pagina": p["pagina"],
            "valore": _v(valore),
            "cit": valore.get("cit", ""),
            "zona": valore.get("zona", []),
            "esatta": bool(valore.get("zona_esatta")),
        }
        return fid

    def zona(self, pid: str, campo: str, testo: str, zona: list) -> str:
        fid = f"{pid}.{campo}"
        p = self.pagine[pid]
        self.tutte[fid] = {
            "pid": pid,
            "file": p["file"],
            "pagina": p["pagina"],
            "valore": testo,
            "cit": testo,
            "zona": zona,
            "esatta": False,
        }
        return fid


def _pagina_di(testo: str) -> tuple[int, int] | None:
    m = re.search(r"(\d+)\s*(?:/|di|of|von)\s*(\d+)", testo or "", re.I)
    return (int(m.group(1)), int(m.group(2))) if m and 0 < int(m.group(1)) <= int(m.group(2)) <= 50 else None


def costruisci(pagine: list[dict], schede: dict[str, dict]) -> dict:
    """pagine: elenco del lavoro (pid, file, pagina, ...); schede: pid -> scheda letta."""
    info = {p["pid"]: p for p in pagine}
    fonti = Fonti(info)
    packing, ddt, certificati, dop_costr, dop_prod, lettere, escluse = [], [], [], [], [], [], []
    ultimo: dict[tuple[str, str], dict] = {}  # (file, famiglia) -> ultimo documento, per le pagine di seguito

    for p in pagine:
        pid = p["pid"]
        s = schede.get(pid)
        if not s:
            continue
        fam, t = s["famiglia"], s.get("testata", {})
        seguito = ultimo.get((p["file"], fam))
        if fam in ("da_escludere", "illeggibile"):
            escluse.append(
                {"pid": pid, "famiglia": fam, "motivo": s.get("motivo", ""), "bianca": s.get("bianca", False)}
            )
            continue

        if fam == "packing_costruttore":
            titolo = _v(t.get("titolo")) or (seguito or {}).get("titolo", "")
            doc = {"tipo": "packing", "pagine": [pid], "titolo": titolo, "costruttore": _v(t.get("costruttore"))}
            ultimo[(p["file"], fam)] = doc
            for i, r in enumerate(s.get("righe", [])):
                riga = {k: _v(r.get(k)) for k in r}
                riga.update(
                    pid=pid,
                    indice=i,
                    titolo=titolo,
                    chiave=nz.profilo(riga.get("materiale", "")),
                    fonti={k: fonti.aggiungi(pid, f"r{i}.{k}", r[k]) for k in r},
                )
                if riga.get("materiale") or riga.get("certificato"):
                    packing.append(riga)

        elif fam == "ddt":
            numero = _v(t.get("numero"))
            if not numero and seguito:
                doc = seguito
                doc["pagine"].append(pid)
            else:
                chiave = (frozenset(_nucleo(_v(t.get("emittente")))), nz.numero_normale(numero) or pid)
                doc = next((d for d in ddt if d["chiave"] == chiave), None)
                if doc:
                    doc["pagine"].append(pid)
                else:
                    doc = {
                        "id": f"D{len(ddt) + 1}",
                        "chiave": chiave,
                        "numero": numero,
                        "data": _v(t.get("data")),
                        "emittente": _v(t.get("emittente")),
                        "destinatario": _v(t.get("destinatario")),
                        "destinazione": _v(t.get("destinazione")),
                        "commessa": _v(t.get("commessa")),
                        "tipo_proposto": _v(t.get("tipo_proposto")),
                        "pagine": [pid],
                        "righe": [],
                        "fonti": {k: fonti.aggiungi(pid, k, t.get(k)) for k in ("numero", "data", "emittente")},
                    }
                    ddt.append(doc)
            ultimo[(p["file"], fam)] = doc
            for i, r in enumerate(s.get("righe", [])):
                if _v(r.get("servizio")).lower() == "si":
                    continue
                descr = _v(r.get("profilo")) or _v(r.get("descrizione"))
                doc["righe"].append(
                    {
                        "pid": pid,
                        "descrizione": _v(r.get("descrizione")),
                        "chiave": nz.profilo(descr),
                        "qualita": _v(r.get("qualita")),
                        "quantita": f"{_v(r.get('quantita'))} {_v(r.get('unita'))}".strip(),
                        "fonti": {
                            k: fonti.aggiungi(pid, f"r{i}.{k}", r.get(k)) for k in ("descrizione", "profilo", "qualita")
                        },
                    }
                )

        elif fam == "certificato_31":
            numero = _v(t.get("numero"))
            if (
                (not numero or s.get("continua_pagina_prima"))
                and seguito
                and (not numero or nz.stesso_numero(numero, seguito["numero"]))
            ):
                doc = seguito
                doc["pagine"].append(pid)
            else:
                chiave = (
                    frozenset(_nucleo(_v(t.get("produttore")))),
                    nz.numero_normale(numero) or pid,
                    nz.data_iso(_v(t.get("data"))),
                )
                doc = next((c for c in certificati if c["chiave"] == chiave), None)
                if doc:
                    doc["pagine"].append(pid)
                    doc["copie"] += 1
                else:
                    doc = {
                        "id": f"C{len(certificati) + 1}",
                        "chiave": chiave,
                        "numero": numero,
                        "data": _v(t.get("data")),
                        "produttore": _v(t.get("produttore")),
                        "cliente": _v(t.get("cliente")),
                        "tipo_materiale": _v(t.get("tipo_materiale")),
                        "pagine": [pid],
                        "copie": 1,
                        "righe": [],
                        "timbri": [],
                        "segni": [],
                        "ce_dop": [],
                        "pagine_di": [],
                        "avvisi": [],
                        "ddt_produttore": _v(t.get("ddt_produttore")),
                        "fonti": {k: fonti.aggiungi(pid, k, t.get(k)) for k in ("numero", "data", "produttore")},
                    }
                    certificati.append(doc)
            ultimo[(p["file"], fam)] = doc
            pd = _pagina_di(_v(t.get("pagina_di")))
            if pd:
                doc["pagine_di"].append(pd)
            for i, r in enumerate(s.get("righe", [])):
                colata = re.sub(r"^(?:no|n)\.?\s*", "", _v(r.get("colata")), flags=re.I)
                descr = " ".join(x for x in (_v(r.get("profilo")), _v(r.get("dimensioni"))) if x)
                doc["righe"].append(
                    {
                        "pid": pid,
                        "indice": i,
                        "descrizione": descr,
                        "chiave": nz.profilo(descr),
                        "qualita": _v(r.get("qualita")),
                        "colata": colata if len(re.sub(r"\D", "", colata)) >= 3 else "",
                        "lotto": _v(r.get("lotto")),
                        "componente": _v(r.get("componente")),
                        "fonti": {
                            k: fonti.aggiungi(pid, f"r{i}.{k}", r.get(k)) for k in ("profilo", "qualita", "colata")
                        },
                    }
                )
            for i, tb in enumerate(s.get("timbri", [])):
                doc["timbri"].append(
                    {
                        **{k: tb[k] for k in ("chi", "testo", "ddt_citato", "data_ddt", "a_mano")},
                        "pid": pid,
                        "fid": fonti.zona(pid, f"timbro{i}", tb["testo"], tb["zona"]),
                    }
                )
            for sg in s.get("segni", []):
                riga = s["righe"][sg["riga"]] if 0 <= sg["riga"] < len(s.get("righe", [])) else None
                doc["segni"].append({"tipo": sg["tipo"], "pid": pid, "colata": _v((riga or {}).get("colata"))})
            for i, r in enumerate(s.get("riferimenti", [])):
                if r["tipo"] in ("dop", "fpc") and r["v"]:
                    doc["ce_dop"].append((r["v"], fonti.aggiungi(pid, f"rif{i}", r)))
            doc["avvisi"] += s.get("avvisi", [])

        elif fam == "dop_costruttore":
            dop_costr.append(
                {
                    "pid": pid,
                    **{k: _v(v) for k, v in t.items()},
                    "fonti": {k: fonti.aggiungi(pid, k, v) for k, v in t.items()},
                }
            )
        elif fam == "dop_ce_prodotto":
            dop_prod.append(
                {
                    "pid": pid,
                    **{k: _v(v) for k, v in t.items()},
                    "fonti": {k: fonti.aggiungi(pid, k, v) for k, v in t.items()},
                }
            )
        elif fam == "lettera_accompagnamento":
            lettere.append(
                {
                    "pid": pid,
                    "ddt_citato": _v(t.get("ddt_citato")),
                    "posizioni": [_v(r.get("posizione")) for r in s.get("righe", [])],
                    "certificati": [_v(r.get("certificato")) for r in s.get("righe", [])],
                    "fid": fonti.aggiungi(pid, "ddt_citato", t.get("ddt_citato")),
                }
            )

    for c in certificati:
        totali = {n for _, n in c["pagine_di"]}
        viste = {i for i, _ in c["pagine_di"]}
        c["incompleto"] = bool(totali) and viste != set(range(1, max(totali) + 1))
        c["pagine_di_testo"] = ", ".join(f"{i}/{n}" for i, n in sorted(set(c["pagine_di"])))

    costruttore = _costruttore(ddt, dop_costr, packing)
    for d in ddt:
        if costruttore and _stessa_azienda(d["emittente"], costruttore):
            d["tipo"] = "costruttore_cliente"
        elif costruttore and _stessa_azienda(d["destinatario"], costruttore):
            d["tipo"] = "commerciante_costruttore"
        else:
            d["tipo"] = "fuori_perimetro"
        d.pop("chiave")
    for c in certificati:
        c.pop("chiave")
    return {
        "formato": FORMATO,
        "non_lette": [
            p["pid"] for p in pagine if p["pid"] not in schede or schede[p["pid"]].get("famiglia") == "illeggibile"
        ],
        "costruttore": costruttore,
        "packing": packing,
        "ddt": ddt,
        "certificati": certificati,
        "dop_costruttore": dop_costr,
        "dop_prodotto": dop_prod,
        "lettere": lettere,
        "escluse": escluse,
        "fonti": fonti.tutte,
    }


def _costruttore(ddt: list[dict], dop_costr: list[dict], packing: list[dict]) -> str:
    """Regola R3: il costruttore è il destinatario dei DDT con più emittenti distinti; la DoP EN 1090 conferma."""
    emittenti = defaultdict(set)
    nomi = {}
    for d in ddt:
        if d["destinatario"]:
            n = _nucleo(d["destinatario"])
            emittenti[n].add(_nucleo(d["emittente"]))
            nomi.setdefault(n, d["destinatario"])
    fabbricanti = [d.get("fabbricante", "") for d in dop_costr if d.get("fabbricante")]
    if emittenti:
        ordinati = sorted(emittenti, key=lambda n: (-len(emittenti[n]), sorted(n)))
        migliore = ordinati[0]
        for f in fabbricanti:
            if _nucleo(f) & migliore:
                return f
        if len(ordinati) == 1 or len(emittenti[migliore]) > len(emittenti[ordinati[1]]):
            return nomi[migliore]
    if len({_nucleo(f) for f in fabbricanti}) == 1:
        return fabbricanti[0]
    return ""
