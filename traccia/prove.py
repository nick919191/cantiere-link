"""Dalle schede delle pagine alle prove del fascicolo (deterministico).

Raggruppa le pagine in documenti (DDT, certificati, DoP, tabella del costruttore), decide i ruoli dal fascicolo
(costruttore = chi riceve i DDT da più emittenti) e registra per ogni valore la sua fonte: pagina, citazione, zona.
"""

import re

from . import normalizza as nz

FORMATO = "prove/2"


def _v(campo: dict | None) -> str:
    return (campo or {}).get("v", "").strip()


class Aziende:
    """Chi è chi nel fascicolo: ragioni sociali confrontate per nucleo (normalizza.stessa_azienda) e, quando un
    documento stampa la partita IVA, per partita IVA: stessa P.IVA = stessa azienda, qualunque sia il nome."""

    def __init__(self):
        self.per_piva: dict[str, list[str]] = {}

    def registra(self, nome: str, piva: str) -> None:
        p = nz.piva(piva)
        if nome and p:
            nomi = self.per_piva.setdefault(p, [])
            if nome not in nomi:
                nomi.append(nome)

    @property
    def gruppi(self) -> list[list[str]]:
        return [nomi for nomi in self.per_piva.values() if nomi]

    def stessa(self, a: str, b: str) -> bool:
        return bool(a and b) and nz.stessa_azienda(a, b, self.gruppi)


def _consecutive(info: dict, prima: list[str], pid: str) -> bool:
    """La pagina `pid` viene subito dopo l'ultima pagina di `prima` nello stesso file."""
    if not prima:
        return False
    a, b = info[prima[-1]], info[pid]
    return a["file"] == b["file"] and b["pagina"] == a["pagina"] + 1


def _stesso_ddt(d: dict, numero: str, data: str, emittente: str, destinatario: str, stessa) -> bool:
    """Stesso DDT: stesso numero, stessa data, stesso destinatario e stesso emittente (dove letti)."""
    return (
        nz.numero_normale(numero) == nz.numero_normale(d["numero"])
        and (not data or not d["data_iso"] or data == d["data_iso"])
        and (not destinatario or not d["destinatario"] or stessa(destinatario, d["destinatario"]))
        and (not emittente or not d["emittente"] or stessa(emittente, d["emittente"]))
    )


def _quasi_uguali(a: str, b: str) -> bool:
    """Due numeri letti che differiscono per un solo carattere ('2027' e '8027'): stessa lunghezza, una differenza."""
    a, b = nz.numero_normale(a), nz.numero_normale(b)
    return len(a) == len(b) >= 3 and sum(x != y for x, y in zip(a, b, strict=True)) == 1


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
    scartate = []  # righe della packing senza materiale né certificato
    ultimo: dict[tuple[str, str], dict] = {}  # (file, famiglia) -> ultimo documento, per le pagine di seguito
    aziende = Aziende()
    for s in schede.values():
        t = s.get("testata", {})
        if s.get("famiglia") == "ddt":
            aziende.registra(_v(t.get("emittente")), _v(t.get("piva_emittente")))
            aziende.registra(_v(t.get("destinatario")), _v(t.get("piva_destinatario")))
        elif s.get("famiglia") == "dop_costruttore":
            aziende.registra(_v(t.get("fabbricante")), _v(t.get("piva")))
    stessa = aziende.stessa

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
                else:  # non porta la catena: non si usa, ma si dice (avviso nell'Excel)
                    scartate.append({"pid": pid, "indice": i})

        elif fam == "ddt":
            numero, data = _v(t.get("numero")), nz.data_iso(_v(t.get("data")))
            emittente, destinatario = _v(t.get("emittente")), _v(t.get("destinatario"))
            doc = next(
                (d for d in ddt if numero and _stesso_ddt(d, numero, data, emittente, destinatario, stessa)), None
            )
            if doc:
                if pid not in doc["pagine"]:
                    doc["pagine"].append(pid)
                    doc["copie"] += 1
            elif not numero and seguito:
                doc = seguito
                doc["pagine"].append(pid)
            elif (
                seguito
                and _consecutive(info, seguito["pagine"], pid)
                and data == seguito["data_iso"]
                and stessa(destinatario, seguito["destinatario"])
                and stessa(emittente, seguito["emittente"])
                and ((_pagina_di(_v(t.get("pagina_di"))) or (1, 1))[0] > 1 or _quasi_uguali(numero, seguito["numero"]))
            ):
                # pagina seguente dello stesso DDT con il numero letto diverso (es. '2027' per '8027')
                doc = seguito
                doc["pagine"].append(pid)
                doc["avvisi"].append(
                    f"numero letto {numero} sulla pagina {info[pid]['pagina']}, {doc['numero']} sulle altre"
                )
            else:
                doc = {
                    "id": f"D{len(ddt) + 1}",
                    "numero": numero,
                    "data": _v(t.get("data")),
                    "data_iso": data,
                    "emittente": emittente,
                    "destinatario": destinatario,
                    "destinazione": _v(t.get("destinazione")),
                    "commessa": _v(t.get("commessa")),
                    "causale": _v(t.get("causale")),
                    "piva_emittente": nz.piva(_v(t.get("piva_emittente"))),
                    "piva_destinatario": nz.piva(_v(t.get("piva_destinatario"))),
                    "tipo_proposto": _v(t.get("tipo_proposto")),
                    "pagine": [pid],
                    "copie": 1,
                    "righe": [],
                    "riferimenti": [],
                    "avvisi": [],
                    "fonti": {k: fonti.aggiungi(pid, k, t.get(k)) for k in ("numero", "data", "emittente")},
                }
                ddt.append(doc)
            for r in s.get("riferimenti", []):
                if r.get("v"):
                    doc["riferimenti"].append((r.get("tipo", ""), r["v"]))
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
                produttore, data = _v(t.get("produttore")), nz.data_iso(_v(t.get("data")))
                doc = next(
                    (
                        c
                        for c in certificati
                        if numero
                        and nz.numero_normale(numero) == nz.numero_normale(c["numero"])
                        and data == c["data_iso"]
                        and (not produttore or not c["produttore"] or stessa(produttore, c["produttore"]))
                    ),
                    None,
                )
                if doc:
                    doc["pagine"].append(pid)
                    doc["copie"] += 1
                else:
                    doc = {
                        "id": f"C{len(certificati) + 1}",
                        "numero": numero,
                        "data_iso": data,
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

    costruttore = _costruttore(ddt, dop_costr, packing, stessa)
    for d in ddt:
        if costruttore and stessa(d["emittente"], costruttore):
            d["tipo"] = "costruttore_cliente"
        elif costruttore and stessa(d["destinatario"], costruttore):
            d["tipo"] = "commerciante_costruttore"
        else:
            d["tipo"] = "fuori_perimetro"
    return {
        "formato": FORMATO,
        "non_lette": [
            p["pid"] for p in pagine if p["pid"] not in schede or schede[p["pid"]].get("famiglia") == "illeggibile"
        ],
        "costruttore": costruttore,
        "aziende": aziende.gruppi,
        "packing": packing,
        "packing_scartate": scartate,
        "ddt": ddt,
        "certificati": certificati,
        "dop_costruttore": dop_costr,
        "dop_prodotto": dop_prod,
        "lettere": lettere,
        "escluse": escluse,
        "fonti": fonti.tutte,
    }


def _raggruppa(nomi: list[str], stessa) -> list[list[str]]:
    """Nomi letti in forme diverse ('S.A.C.I.F. SRL', 'SACIF S.r.l. VIA...') messi nello stesso gruppo."""
    gruppi: list[list[str]] = []
    for nome in nomi:
        g = next((g for g in gruppi if any(stessa(nome, x) for x in g)), None)
        if g is None:
            gruppi.append([nome])
        elif nome not in g:
            g.append(nome)
    return gruppi


def _costruttore(ddt: list[dict], dop_costr: list[dict], packing: list[dict], stessa) -> str:
    """Regola R3: il costruttore è il destinatario dei DDT con più emittenti distinti; la DoP EN 1090 conferma."""
    destinatari = _raggruppa([d["destinatario"] for d in ddt if d["destinatario"]], stessa)
    emittenti_di: dict[int, list[list[str]]] = {}
    for i, gruppo in enumerate(destinatari):
        emessi = [
            d["emittente"] for d in ddt if d["destinatario"] and any(stessa(d["destinatario"], x) for x in gruppo)
        ]
        emittenti_di[i] = _raggruppa([e for e in emessi if e], stessa)
    fabbricanti = [d.get("fabbricante", "") for d in dop_costr if d.get("fabbricante")]
    if destinatari:
        ordinati = sorted(range(len(destinatari)), key=lambda i: (-len(emittenti_di[i]), destinatari[i][0]))
        migliore = ordinati[0]
        for f in fabbricanti:
            if any(stessa(f, x) for x in destinatari[migliore]):
                return f
        if len(ordinati) == 1 or len(emittenti_di[migliore]) > len(emittenti_di[ordinati[1]]):
            return destinatari[migliore][0]
    if len(_raggruppa(fabbricanti, stessa)) == 1:
        return fabbricanti[0]
    return ""
