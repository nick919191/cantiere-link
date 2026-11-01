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


def _colate_riga(r: dict) -> list[tuple[str, list[str]]]:
    """Colate dichiarate su una riga di DDT: dal campo `colata` (più colate separate da ';'), con la placca del
    campo `placca`, oppure lette nel testo della riga ('Placca: ... Colata: ...')."""
    campo = [c.strip() for c in re.split(r"[;|]", _v(r.get("colata"))) if c.strip()]
    if campo:
        placche = [p.strip() for p in re.split(r"[;|]", _v(r.get("placca"))) if p.strip()]
        esito: dict[str, list[str]] = {}
        for i, c in enumerate(campo):
            esito.setdefault(c, [])
            for p in placche if len(campo) == 1 else placche[i : i + 1]:
                if p not in esito[c]:
                    esito[c].append(p)
        return list(esito.items())
    return nz.colate_dichiarate(" ".join(_v(r.get(k)) for k in ("descrizione", "profilo")))


def _chiave_riga(profilo: str, descrizione: str) -> str:
    """Chiave del materiale: il campo profilo se porta una misura ('SP.012X2450X6000'); altrimenti la descrizione
    ('LAM. CALDO' + 'LAM. CALDO S355J2 ... 6000x1500x 8,00' -> LAMIERA 8); altrimenti ciò che c'è."""
    tentativi = [nz.profilo(t) if t.strip() else "" for t in (profilo, descrizione, f"{descrizione} {profilo}")]
    for chiave in tentativi:  # prima una forma riconosciuta con misura ('ANGOLARE A LATI UGUALI' + 'LT=50 SP=5')
        if nz.riconosciuta(chiave) and re.search(r"\d", chiave):
            return chiave
    for chiave in tentativi:
        if re.search(r"\d", chiave):
            return chiave
    return nz.profilo(profilo or descrizione)


def _pagina_di(testo: str) -> tuple[int, int] | None:
    m = re.search(r"(\d+)\s*(?:/|di|of|von)\s*(\d+)", testo or "", re.I)
    return (int(m.group(1)), int(m.group(2))) if m and 0 < int(m.group(1)) <= int(m.group(2)) <= 50 else None


def costruisci(pagine: list[dict], schede: dict[str, dict], mappe: dict[str, str | None] | None = None) -> dict:
    """pagine: elenco del lavoro (pid, file, pagina, ...); schede: pid -> scheda letta; mappe: pid -> famiglia data
    dal riconoscimento delle pagine (DeepSeek), usata per dire che cosa c'è nelle pagine non lette."""
    info = {p["pid"]: p for p in pagine}
    mappe = mappe or {}
    fonti = Fonti(info)
    packing, ddt, certificati, dop_costr, dop_prod, lettere, escluse = [], [], [], [], [], [], []
    scartate = []  # righe della packing senza materiale né certificato
    parziali = []  # pagine lette a metà (famiglia e testata, senza righe): il motore non le dà per complete
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
        if s.get("parziale"):
            parziali.append(pid)
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
                    "servizi": [],
                    "avvisi": [],
                    "fonti": {k: fonti.aggiungi(pid, k, t.get(k)) for k in ("numero", "data", "emittente")},
                }
                ddt.append(doc)
            for r in s.get("riferimenti", []):
                if r.get("v"):
                    doc["riferimenti"].append((r.get("tipo", ""), r["v"]))
            ultimo[(p["file"], fam)] = doc
            for i, r in enumerate(s.get("righe", [])):
                if _v(r.get("servizio")).lower() == "si" or nz.e_riferimento(_v(r.get("descrizione"))):
                    doc.setdefault("servizi", []).append(_v(r.get("descrizione")))
                    continue
                colate = _colate_riga(r)
                chiave = _chiave_riga(_v(r.get("profilo")), _v(r.get("descrizione")))
                if not chiave and colate and doc["righe"]:
                    # riga di sole colate/placche (continuazione della riga di materiale precedente, anche da
                    # un'altra pagina): le colate vanno alla riga prima
                    prima = doc["righe"][-1]
                    for c, placche in colate:
                        if c not in prima["colate"]:
                            prima["colate"].append(c)
                        prima["placche"].setdefault(c, [])
                        prima["placche"][c] += [p for p in placche if p not in prima["placche"][c]]
                        prima["fonti"].setdefault("colata", fonti.aggiungi(pid, f"r{i}.colata", r.get("colata")))
                    continue
                doc["righe"].append(
                    {
                        "pid": pid,
                        "descrizione": _v(r.get("descrizione")),
                        "chiave": chiave,
                        "qualita": _v(r.get("qualita")),
                        "quantita": f"{_v(r.get('quantita'))} {_v(r.get('unita'))}".strip(),
                        "colate": [c for c, _ in colate],
                        "placche": {c: p for c, p in colate},
                        "certificato": _v(r.get("certificato")),
                        "fonti": {
                            k: fonti.aggiungi(pid, f"r{i}.{k}", r.get(k))
                            for k in ("descrizione", "profilo", "qualita", "colata", "placca", "certificato")
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
                        and (
                            (
                                data == c["data_iso"]
                                and (not produttore or not c["produttore"] or stessa(produttore, c["produttore"]))
                            )
                            # stesso numero nello stesso file: stesso certificato anche se produttore o data sono
                            # letti con un refuso su una delle pagine ('AFV Accisierie' / 'AFV Acclaierie')
                            or info[c["pagine"][0]]["file"] == p["file"]
                        )
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
                    "riferimenti": [(r.get("tipo", ""), r["v"]) for r in s.get("riferimenti", []) if r.get("v")],
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
            righe = [
                {
                    "posizione": _v(r.get("posizione")),
                    "articolo": _v(r.get("articolo")),
                    "placca": _v(r.get("placca")),
                    "colata": _v(r.get("colata")),
                    "certificato": _v(r.get("certificato")),
                    "fonti": {k: fonti.aggiungi(pid, f"r{i}.{k}", r.get(k)) for k in ("colata", "certificato")},
                }
                for i, r in enumerate(s.get("righe", []))
            ]
            lettere.append(
                {
                    "pid": pid,
                    "emittente": _v(t.get("emittente")),
                    "ddt_citato": _v(t.get("ddt_citato")),
                    "posizioni": [r["posizione"] for r in righe],
                    "certificati": [r["certificato"] for r in righe],
                    "righe": righe,
                    "fid": fonti.aggiungi(pid, "ddt_citato", t.get("ddt_citato")),
                }
            )

    _timbri_a_penna_per_data(ddt, certificati, stessa)
    for c in certificati:
        totali = {n for _, n in c["pagine_di"]}
        viste = {i for i, _ in c["pagine_di"]}
        c["incompleto"] = bool(totali) and viste != set(range(1, max(totali) + 1))
        c["pagine_di_testo"] = ", ".join(f"{i}/{n}" for i, n in sorted(set(c["pagine_di"])))

    _liste_lette_come_ddt(ddt, lettere, stessa)
    costruttore = _costruttore(ddt, dop_costr, packing, stessa)
    _tipi(ddt, costruttore, stessa)
    _liste_lette_come_certificati(ddt, certificati, lettere, stessa)
    commercianti = [d["emittente"] for d in ddt if d["tipo"] == "commerciante_costruttore" and d["emittente"]]
    dop_intermedi = [
        d
        for d in dop_costr
        if d.get("fabbricante")
        and not (costruttore and stessa(d["fabbricante"], costruttore))
        and any(stessa(d["fabbricante"], c) for c in commercianti)
    ]
    dop_costr = [d for d in dop_costr if d not in dop_intermedi]
    non_lette = [p for p in pagine if p["pid"] not in schede or schede[p["pid"]].get("famiglia") == "illeggibile"]
    return {
        "formato": FORMATO,
        "non_lette": [p["pid"] for p in non_lette],
        "non_lette_dettagli": [
            {"pid": p["pid"], "file": p["file"], "pagina": p["pagina"], "famiglia": mappe.get(p["pid"])}
            for p in non_lette
        ],
        "parziali": parziali,
        "costruttore": costruttore,
        "aziende": aziende.gruppi,
        "packing": packing,
        "packing_scartate": scartate,
        "ddt": ddt,
        "certificati": certificati,
        "dop_costruttore": dop_costr,
        "dop_fornitore_intermedio": dop_intermedi,
        "dop_prodotto": dop_prod,
        "lettere": lettere,
        "escluse": escluse,
        "fonti": fonti.tutte,
    }


def _timbri_a_penna_per_data(ddt: list[dict], certificati: list[dict], stessa) -> None:
    """Numero del DDT scritto a penna sul timbro e letto male ('1002' per '1062'): se nessun DDT del fascicolo lo
    porta, ma uno solo ha la stessa data del timbro e un numero che differisce per una cifra (e, se serve a
    scegliere, lo stesso emittente del timbro), il timbro cita quello. Il numero letto resta in `ddt_letto`."""
    for c in certificati:
        for t in c["timbri"]:
            n = t.get("ddt_citato", "")
            if not n or not t.get("a_mano") or not t.get("data_ddt"):
                continue
            if any(nz.cita_ddt(n, d["numero"]) for d in ddt):
                continue
            data = nz.data_iso(t["data_ddt"])
            candidati = [d for d in ddt if d["data_iso"] and d["data_iso"] == data and nz.quasi_uguale(n, d["numero"])]
            if len(candidati) > 1 and t.get("chi"):
                candidati = [d for d in candidati if d["emittente"] and stessa(t["chi"], d["emittente"])]
            if len(candidati) != 1:
                continue
            scelto = candidati[0]
            t["ddt_letto"], t["ddt_citato"] = n, scelto["numero"]
            c["avvisi"].append(
                f"sul timbro il numero del DDT letto è {n}: preso il DDT {scelto['numero']} di {scelto['emittente']} "
                f"con la stessa data ({t['data_ddt']})"
            )


CONTO_LAVORAZIONE = re.compile(r"conto\s*lavor|c/\s*lavor|lavorazione\s+per\s+conto|in\s+conto\s+terzi", re.I)
RESO = re.compile(r"\breso\b|\bresi\b|\brestituzione\b|\britorno\b", re.I)


def _liste_lette_come_ddt(ddt: list[dict], lettere: list[dict], stessa) -> None:
    """Una lista di rintracciabilità letta come DDT (stesso emittente di un DDT, stesso progressivo del numero,
    righe senza materiale ma con colate) non è un DDT: diventa una lettera che cita quel DDT."""
    for d in list(ddt):
        if not d["righe"] or any(r["chiave"] for r in d["righe"]) or not any(r["colate"] for r in d["righe"]):
            continue
        prog = nz.progressivo(d["numero"])
        altro = next(
            (
                e
                for e in ddt
                if e is not d
                and any(r["chiave"] for r in e["righe"])
                and prog
                and nz.progressivo(e["numero"]) == prog
                and stessa(e["emittente"], d["emittente"])
            ),
            None,
        )
        if not altro:
            continue
        ddt.remove(d)
        righe = [
            {
                "posizione": "",
                "articolo": "",
                "placca": p,
                "colata": c,
                "certificato": r.get("certificato", ""),
                "fonti": {},
            }
            for r in d["righe"]
            for c in r["colate"]
            for p in (r["placche"].get(c) or [""])
        ]
        lettere.append(
            {
                "pid": d["pagine"][0],
                "emittente": d["emittente"],
                "ddt_citato": altro["numero"],
                "posizioni": [],
                "certificati": [r["certificato"] for r in righe if r["certificato"]],
                "righe": righe,
                "fid": d["fonti"].get("numero"),
                "da_ddt": d["numero"],
            }
        )
        altro["avvisi"].append(
            f"lista di rintracciabilità {d['numero']} (pagina {d['pagine']}) letta come DDT: usata come lista"
        )


def _liste_lette_come_certificati(ddt: list[dict], certificati: list[dict], lettere: list[dict], stessa) -> None:
    """Un "certificato" il cui produttore è il commerciante di un DDT del perimetro non è un 3.1 (li emettono le
    acciaierie): è la sua lista di rintracciabilità (placca -> colata -> certificato) e vale come lettera per il DDT
    che cita (campo DDT o timbro)."""
    commercianti = [d for d in ddt if d["tipo"] == "commerciante_costruttore" and d["emittente"]]
    for c in list(certificati):
        if not c["produttore"] or not any(stessa(c["produttore"], d["emittente"]) for d in commercianti):
            continue
        citati = [c.get("ddt_produttore", "")] + [t["ddt_citato"] for t in c["timbri"]]
        doc = next(
            (
                d
                for d in commercianti
                for n in citati
                if n and (nz.cita_ddt(n, d["numero"]) or nz.cita_ddt(d["numero"], n))
            ),
            None,
        )
        if not doc:
            continue
        certificati.remove(c)
        lettere.append(
            {
                "pid": c["pagine"][0],
                "emittente": c["produttore"],
                "ddt_citato": doc["numero"],
                "posizioni": [],
                "certificati": [v for v, _ in c["ce_dop"]],
                "righe": [
                    {
                        "posizione": "",
                        "articolo": r["descrizione"],
                        "placca": r.get("lotto", ""),
                        "colata": r["colata"],
                        "certificato": "",
                        "fonti": r["fonti"],
                    }
                    for r in c["righe"]
                    if r["colata"]
                ],
                "fid": c["fonti"].get("numero"),
                "da_certificato": c["numero"],
            }
        )
        doc["avvisi"].append(
            f"documento {c['numero']} di {c['produttore']} letto come certificato: è la lista del commerciante, "
            "usata come lista"
        )


def _tipi(ddt: list[dict], costruttore: str, stessa) -> None:
    """Tipo di ogni DDT dal fascicolo (conoscenza 02): emesso dal costruttore -> costruttore_cliente, oppure
    costruttore_terzista se la causale dice conto lavorazione o se un DDT del terzista lo cita come reso; ricevuto
    dal costruttore -> commerciante_costruttore, oppure terzista_cantiere se è un reso (causale, righe che citano
    il reso del DDT N, riferimento a un DDT emesso dal costruttore). Il resto è fuori perimetro."""
    emessi = [d for d in ddt if costruttore and stessa(d["emittente"], costruttore)]
    ricevuti = [d for d in ddt if d not in emessi and costruttore and stessa(d["destinatario"], costruttore)]
    for d in ddt:
        d["tipo"] = "fuori_perimetro"
        d["tramite"] = ""
        d["incoerente"] = bool(d["emittente"] and d["destinatario"] and stessa(d["emittente"], d["destinatario"]))
        if d["incoerente"]:
            d["avvisi"].append("emittente e destinatario letti come la stessa azienda: ruolo del DDT da controllare")
    emessi = [d for d in emessi if not (d["destinatario"] and stessa(d["emittente"], d["destinatario"]))]
    ricevuti = [d for d in ricevuti if not (d["emittente"] and stessa(d["emittente"], d["destinatario"]))]
    for d in emessi:
        d["tipo"] = "costruttore_terzista" if CONTO_LAVORAZIONE.search(_testo_ddt(d)) else "costruttore_cliente"
    for d in ricevuti:
        citati = [v for tipo, v in d.get("riferimenti", []) if tipo == "ddt"]
        resi = [e for e in emessi if any(nz.stesso_numero(v, e["numero"]) in ("uguale", "serie") for v in citati)]
        testo = _testo_ddt(d)
        if resi or (RESO.search(testo) and re.search(r"\bddt\b|\bd\.d\.t\b|documento di trasporto", testo, re.I)):
            d["tipo"] = "terzista_cantiere"
            for e in resi:
                e["tipo"] = "costruttore_terzista"
                e["tramite"] = _prima_riga(e["destinatario"] or d["emittente"])
        else:
            d["tipo"] = "commerciante_costruttore"
    for e in emessi:
        if e["tipo"] == "costruttore_terzista" and not e["tramite"]:
            e["tramite"] = _prima_riga(e["destinatario"])


def _prima_riga(testo: str) -> str:
    return (testo or "").strip().splitlines()[0].strip() if (testo or "").strip() else ""


def _testo_ddt(d: dict) -> str:
    return " ".join([d.get("causale", "")] + [r.get("descrizione", "") for r in d["righe"]] + d.get("servizi", []))


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
