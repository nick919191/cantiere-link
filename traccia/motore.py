"""Motore di regole 0.5.0: dalle prove del fascicolo alle voci con stato. Nessuna AI, nessun caso, nessun orologio.

Regole (conoscenza/05_regole_di_stato.md):
- voce = certificato dichiarato dal costruttore + DDT + profilo/spessore; senza dichiarazione DDT + profilo;
- il certificato dichiarato si cerca per NUMERO; se manca: MANCANTE con il numero dichiarato e il fornitore, mai un
  altro certificato con lo stesso profilo;
- PROVATO: certificato e DDT presenti, timbro (o lettera) con il numero del DDT, una sola colata;
- DEDOTTO: certificato e DDT presenti e coerenti, una sola colata, nessun timbro;
- DA CONFERMARE: più colate, legame incerto, pagine del certificato mancanti, certificato timbrato per un altro DDT,
  DDT non nel fascicolo;
- tetti: segno a mano sulla colata -> al massimo DA CONFERMARE; timbro scritto a penna -> al massimo DA CONFERMARE
  (impostazione PENNA_VALE_COME_PROVA); perimetro dai DDT (packing assente) -> al massimo DEDOTTO; pezzo ricavato
  da un profilo più largo -> al massimo DEDOTTO.
"""

import hashlib
import json

from . import normalizza as nz

VERSIONE = "0.5.0"
PENNA_VALE_COME_PROVA = False

STESSO = ("uguale", "serie")  # '5678' e '5678/1' sono lo stesso DDT (suffisso di serie), con avviso
PROVATO, DEDOTTO, DA_CONFERMARE, MANCANTE = "PROVATO", "DEDOTTO", "DA CONFERMARE", "MANCANTE"
ORDINE = {PROVATO: 0, DEDOTTO: 1, DA_CONFERMARE: 2, MANCANTE: 3}
NON_PRESENTE = "Non presente nel fascicolo"
COLONNE = [
    "PRODUTTORE",
    "COLATA",
    "TIPO DI ACCIAIO",
    "CE/DoP ACCIAIERIA",
    "CERT 3.1 ACCIAIERIA",
    "COMMERCIANTE / CENTRO TRASF.",
    "CE/DoP CENTRO",
    "DDT COMMERCIANTE",
    "COSTRUTTORE",
    "CE/DoP COSTRUTTORE",
    "DDT COSTRUTTORE",
    "PARTE D'OPERA",
]


def _tetto(stato: str, massimo: str) -> str:
    return stato if ORDINE[stato] >= ORDINE[massimo] else massimo


def _c(v: str, *fonti) -> dict:
    return {"v": v, "fonti": [f for f in fonti if f]}


def _stessa(a: str, b: str) -> bool:
    return bool(nz.aziende(a) & nz.aziende(b))


# ---------- voci ----------
def _etichetta(righe: list[dict]) -> str:
    dims = [nz.dimensioni_piatto(r["chiave"]) for r in righe]
    if dims and all(d and d[0] for d in dims):
        larghezze = sorted({nz.numero(str(d[0])) for d in dims}, key=float)
        base = f"PL{nz.numero(str(dims[0][1]))}*{'/'.join(larghezze)}"
    else:
        base = " / ".join(sorted({r.get("materiale") or r["chiave"] for r in righe}))
    return f"{base}, {len(righe)} righe" if len(righe) > 1 else base


def voci_dal_fascicolo(prove: dict) -> list[dict]:
    voci = []
    if prove["packing"]:
        gruppi: dict[tuple, list] = {}
        for r in prove["packing"]:
            chiave = (
                nz.numero_normale(r.get("certificato", "")),
                nz.numero_normale(r.get("ddt", "")),
                nz.gruppo(r["chiave"]),
                r.get("titolo", ""),
            )
            gruppi.setdefault(chiave, []).append(r)
        for righe in gruppi.values():
            primo = next((r for r in righe if r.get("certificato")), righe[0])
            voci.append(
                {
                    "origine": "costruttore",
                    "righe": righe,
                    "etichetta": _etichetta(righe),
                    "chiavi": sorted({r["chiave"] for r in righe}),
                    "parte_opera": primo.get("titolo", ""),
                    **{
                        k: next((r.get(k, "") for r in righe if r.get(k)), "")
                        for k in (
                            "certificato",
                            "emesso_da",
                            "data_certificato",
                            "fornito_da",
                            "ddt",
                            "data_ddt",
                            "qualita",
                        )
                    },
                    "fonti": primo["fonti"],
                }
            )
    else:
        for d in prove["ddt"]:
            if d["tipo"] != "commerciante_costruttore":
                continue
            per_chiave: dict[str, list] = {}
            for r in d["righe"]:
                per_chiave.setdefault(r["chiave"], []).append(r)
            for chiave, righe in per_chiave.items():
                voci.append(
                    {
                        "origine": "dai_ddt",
                        "righe": [],
                        "etichetta": chiave,
                        "chiavi": [chiave],
                        "parte_opera": "",
                        "certificato": "",
                        "emesso_da": "",
                        "data_certificato": "",
                        "fornito_da": d["emittente"],
                        "ddt": d["numero"],
                        "data_ddt": d["data"],
                        "qualita": righe[0]["qualita"],
                        "fonti": {},
                    }
                )
    return voci


# ---------- confronto dei profili ----------
def _riga_ddt(voce: dict, doc: dict | None) -> dict | None:
    if not doc:
        return None
    dims = [nz.dimensioni_piatto(c) for c in voce["chiavi"]]
    if dims and all(dims):
        spessore = dims[0][1]
        larghezza = max((d[0] or 0) for d in dims)
        adatte = []
        for r in doc["righe"]:
            d = nz.dimensioni_piatto(r["chiave"])
            if d and d[1] == spessore and (d[0] is None or d[0] >= larghezza):
                adatte.append((d[0] if d[0] is not None else 1e9, r["pid"], r))
        return min(adatte, key=lambda x: (x[0], x[1]))[2] if adatte else None
    larghe = {nz.chiave_larga(c) for c in voce["chiavi"]}
    return next((r for r in doc["righe"] if nz.chiave_larga(r["chiave"]) in larghe), None)


def _righe_cert(cert: dict, voce: dict, riga_ddt: dict | None) -> tuple[list[dict], bool]:
    """Righe del certificato per la voce e se il pezzo è ricavato da un profilo più largo."""
    if riga_ddt:
        obiettivo = [riga_ddt["chiave"]]
    else:
        obiettivo = voce["chiavi"]
    dims = [nz.dimensioni_piatto(c) for c in obiettivo]
    if dims and all(dims):
        spessore = dims[0][1]
        larghezza = max((d[0] or 0) for d in dims)
        per_larghezza = {}
        for r in cert["righe"]:
            d = nz.dimensioni_piatto(r["chiave"])
            if d and d[1] == spessore and (d[0] is None or d[0] >= larghezza):
                if riga_ddt and d[0] is not None and nz.dimensioni_piatto(riga_ddt["chiave"])[0] not in (None, d[0]):
                    continue
                per_larghezza.setdefault(d[0] if d[0] is not None else 1e9, []).append(r)
        if not per_larghezza:
            return [], False
        w = min(per_larghezza)
        voce_w = {nz.dimensioni_piatto(c)[0] for c in voce["chiavi"]}
        ricavato = w < 1e9 and voce_w != {w}
        return per_larghezza[w], ricavato
    larghe = {nz.chiave_larga(c) for c in obiettivo}
    return [r for r in cert["righe"] if nz.chiave_larga(r["chiave"]) in larghe], False


def _per_colata(righe: list[dict]) -> list[dict]:
    scelte = {}
    for r in righe:
        if r["colata"] and r["colata"] not in scelte:
            scelte[r["colata"]] = r
    return list(scelte.values())


# ---------- una voce ----------
class Motore:
    def __init__(self, prove: dict):
        self.p = prove
        self.ddt_noti = [d for d in prove["ddt"] if d["tipo"] not in ("costruttore_cliente", "fuori_perimetro")]
        self.pid_file = {f["pid"]: f["file"] for f in prove["fonti"].values()}

    def ddt_di(self, voce: dict) -> dict | None:
        trovati = [d for d in self.ddt_noti if nz.stesso_numero(voce["ddt"], d["numero"]) in STESSO]
        if voce["fornito_da"]:
            stessi = [d for d in trovati if _stessa(d["emittente"], voce["fornito_da"])]
            trovati = stessi
        return trovati[0] if len(trovati) == 1 else None

    def ponti(self, cert: dict, numero_ddt: str) -> list[dict]:
        timbri = [t for t in cert["timbri"] if nz.stesso_numero(t["ddt_citato"], numero_ddt) in STESSO]
        file_cert = {self.pid_file.get(pid) for pid in cert["pagine"]}
        lettere = [
            {
                "chi": "lettera del distributore",
                "ddt_citato": lt["ddt_citato"],
                "testo": f"Delivery note no. {lt['ddt_citato']}",
                "a_mano": False,
                "pid": lt["pid"],
                "fid": lt.get("fid"),
            }
            for lt in self.p["lettere"]
            if nz.stesso_numero(lt["ddt_citato"], numero_ddt) in STESSO
            and self.pid_file.get(lt["pid"]) in file_cert
            and any(nz.stesso_numero(n, cert["numero"]) in STESSO for n in lt.get("certificati", []))
        ]
        return timbri + lettere

    def timbrato_altrove(self, cert: dict, numero_ddt: str) -> list[str]:
        altri = set()
        for t in cert["timbri"]:
            if t["ddt_citato"] and not nz.stesso_numero(t["ddt_citato"], numero_ddt):
                if any(nz.stesso_numero(t["ddt_citato"], d["numero"]) in STESSO for d in self.ddt_noti):
                    altri.add(t["ddt_citato"])
        return sorted(altri)

    def dividi(self, voce: dict) -> list[dict]:
        """Piatti dello stesso spessore dichiarati insieme: si separano per profilo di origine (il piatto più stretto
        tra quelli del DDT, o del certificato dichiarato, da cui il pezzo si ricava). Senza documenti, insieme."""
        dims = [nz.dimensioni_piatto(r["chiave"]) for r in voce["righe"]]
        if not voce["righe"] or not all(d and d[0] for d in dims):
            return [voce]
        doc = self.ddt_di(voce) if voce["ddt"] else None
        sorgenti = [r["chiave"] for r in (doc or {}).get("righe", [])]
        if not sorgenti and voce["certificato"]:
            for c in self.p["certificati"]:
                if nz.stesso_numero(voce["certificato"], c["numero"]):
                    sorgenti += [r["chiave"] for r in c["righe"]]
        spessore = dims[0][1]
        larghezze = sorted({d[0] for s in sorgenti if (d := nz.dimensioni_piatto(s)) and d[1] == spessore and d[0]})
        if not larghezze:
            return [voce]
        gruppi: dict[float, list] = {}
        for r, d in zip(voce["righe"], dims, strict=True):
            origine = next((w for w in larghezze if w >= d[0]), 0.0)
            gruppi.setdefault(origine, []).append(r)
        if len(gruppi) == 1:
            return [voce]
        return [
            {**voce, "righe": righe, "etichetta": _etichetta(righe), "chiavi": sorted({r["chiave"] for r in righe})}
            for _, righe in sorted(gruppi.items())
        ]

    def decidi(self, voce: dict) -> dict:
        doc_ddt = self.ddt_di(voce) if voce["ddt"] else None
        riga_ddt = _riga_ddt(voce, doc_ddt)
        motivi, avvisi, scartati, richieste = [], [], [], []
        if doc_ddt and nz.stesso_numero(voce["ddt"], doc_ddt["numero"]) == "serie":
            avvisi.append(f"il costruttore scrive DDT {voce['ddt']}, il DDT porta {doc_ddt['numero']}")
        fornitore = voce["fornito_da"] or (doc_ddt or {}).get("emittente", "")
        classe_ddt = nz.classe((riga_ddt or {}).get("qualita") or voce.get("qualita"))

        cert, righe, ricavato, ponti = None, [], False, []
        if voce["certificato"]:
            trovati = [c for c in self.p["certificati"] if nz.stesso_numero(voce["certificato"], c["numero"])]
            if not trovati:
                motivi.append(f"il costruttore dichiara il certificato {voce['certificato']}: non è nel fascicolo")
                richieste.append(f"certificato {voce['certificato']}")
            elif len(trovati) > 1:
                motivi.append("più certificati con lo stesso numero: identificazione non univoca")
            else:
                cert = trovati[0]
                if nz.stesso_numero(voce["certificato"], cert["numero"]) == "prefisso":
                    avvisi.append(f"il costruttore scrive {voce['certificato']}, il certificato porta {cert['numero']}")
                righe, ricavato = _righe_cert(cert, voce, riga_ddt)
        else:
            cert, righe, ricavato = self._cerca_per_profilo(voce, doc_ddt, riga_ddt, classe_ddt, scartati, motivi)

        if voce["ddt"] and not doc_ddt:
            richieste.append(f"DDT {voce['ddt']}")
        stato = self._stato(voce, cert, righe, doc_ddt, riga_ddt, ricavato, motivi, avvisi)
        if self.p.get("non_lette") or self.p.get("file_non_letti"):
            stato = DA_CONFERMARE
            avvisi.append("fascicolo non letto completamente: esito provvisorio, assenze non accertate")
        if not self.p.get("costruttore"):
            stato = DA_CONFERMARE
            avvisi.append("ruolo del costruttore non individuato in modo univoco")
        if cert:
            ponti = self.ponti(cert, voce["ddt"]) if voce["ddt"] else []
            if cert.get("incompleto") and not righe:
                richieste.append(f"pagine mancanti del certificato {cert['numero']} ({cert['pagine_di_testo']})")
        colate = _per_colata(righe)
        return {
            "stato": stato,
            "cert": cert,
            "righe_cert": righe,
            "colata": colate[0] if len(colate) == 1 else None,
            "colate_possibili": [r["colata"] for r in colate] if len(colate) > 1 else [],
            "ddt": doc_ddt,
            "riga_ddt": riga_ddt,
            "ponte": ponti[0] if ponti else None,
            "ricavato": ricavato,
            "motivi": motivi,
            "avvisi": avvisi,
            "scartati": scartati,
            "fornitore": fornitore,
            "richieste": richieste,
        }

    def _cerca_per_profilo(self, voce, doc_ddt, riga_ddt, classe_ddt, scartati, motivi):
        candidati = []
        for c in self.p["certificati"]:
            righe, ricavato = _righe_cert(c, voce, riga_ddt)
            compatibili = [r for r in righe if not (classe_ddt and nz.classe(r["qualita"]) not in (None, classe_ddt))]
            if righe and not compatibili:
                scartati.append(f"certificato {c['numero']}: classe diversa dal DDT")
            if compatibili:
                candidati.append((c, compatibili, ricavato))
        if voce["ddt"]:
            con_ponte = [x for x in candidati if self.ponti(x[0], voce["ddt"])]
            if len(con_ponte) == 1:
                return con_ponte[0]
            if len(con_ponte) > 1:
                motivi.append(
                    "più certificati timbrati per questo DDT: " + ", ".join(sorted(x[0]["numero"] for x in con_ponte))
                )
                return None, [], False
            restanti = []
            for x in candidati:
                altrove = self.timbrato_altrove(x[0], voce["ddt"])
                if altrove:
                    scartati.append(f"certificato {x[0]['numero']}: timbrato per il DDT {', '.join(altrove)}")
                else:
                    restanti.append(x)
            candidati = restanti
        if not candidati:
            motivi.append("nessun certificato nel fascicolo per questo materiale")
            return None, [], False
        intestati = [x for x in candidati if doc_ddt and _stessa(x[0]["cliente"], doc_ddt["emittente"])]
        scelti = intestati or candidati
        if len(scelti) > 1:
            motivi.append("più certificati possibili: " + ", ".join(sorted(x[0]["numero"] for x in scelti)))
            return None, [], False
        if not intestati:
            motivi.append(
                "abbinato per esclusione: unico certificato con questo profilo, senza intestazione al commerciante"
            )
        return scelti[0]

    def _stato(self, voce, cert, righe, doc_ddt, riga_ddt, ricavato, motivi, avvisi) -> str:
        if not cert:
            return MANCANTE if not any(m.startswith("più ") for m in motivi) else DA_CONFERMARE
        colate = _per_colata(righe)
        ponti = self.ponti(cert, voce["ddt"]) if voce["ddt"] else []
        altrove = self.timbrato_altrove(cert, voce["ddt"]) if voce["ddt"] else []
        if not righe:
            if cert.get("incompleto"):
                motivi.append(
                    f"nel fascicolo solo le pagine {cert['pagine_di_testo']} del certificato: la riga del "
                    f"profilo non c'è"
                )
            else:
                motivi.append("il profilo della voce non compare sul certificato")
            stato = DA_CONFERMARE
        elif len(colate) > 1:
            segnate = [s for s in cert["segni"] if s["colata"] in {r["colata"] for r in colate}]
            motivi.append(f"più colate per il profilo sul certificato ({', '.join(r['colata'] for r in colate)})")
            if segnate:
                avvisi.append(f"segno a mano ({segnate[0]['tipo']}) sulla colata {segnate[0]['colata']}: da confermare")
            stato = DA_CONFERMARE
        elif not colate:
            motivi.append("colata non leggibile sul certificato")
            stato = DA_CONFERMARE
        elif voce["ddt"] and not doc_ddt:
            motivi.append(f"DDT {voce['ddt']} non nel fascicolo")
            if altrove:
                motivi.append(f"il certificato è timbrato per il DDT {', '.join(altrove)}")
            stato = DA_CONFERMARE
        elif ponti:
            p = ponti[0]
            motivi.append(
                f"timbro di {p['chi'] or 'commerciante'} sul certificato con il DDT {p.get('ddt_citato') or ''}"
            )
            if p["a_mano"] and not PENNA_VALE_COME_PROVA:
                avvisi.append("numero del DDT scritto a penna sul timbro: da confermare")
                stato = DA_CONFERMARE
            else:
                stato = PROVATO
        elif altrove:
            motivi.append(f"il certificato è timbrato per un altro DDT ({', '.join(altrove)})")
            stato = DA_CONFERMARE
        elif not voce["ddt"]:
            motivi.append("nessun DDT dichiarato per la voce")
            stato = DA_CONFERMARE
        elif voce["certificato"] or (doc_ddt and _stessa(cert["cliente"], doc_ddt["emittente"])):
            motivi.append("certificato e DDT presenti e coerenti, senza timbro con il numero del DDT")
            stato = DEDOTTO
        else:
            stato = DA_CONFERMARE
        if ricavato:
            avvisi.append("pezzi ricavati da un profilo più largo (dedotto)")
            stato = _tetto(stato, DEDOTTO)
        if voce["origine"] == "dai_ddt":
            stato = _tetto(stato, DEDOTTO)
        if riga_ddt and righe and colate:
            g_ddt, g_cert = nz.gradi(riga_ddt["qualita"]), nz.grado(righe[0]["qualita"])
            if g_ddt and g_cert and g_cert not in g_ddt:
                avvisi.append(f"il DDT dice {riga_ddt['qualita']}, il certificato {g_cert}")
        return stato


# ---------- colonne e note ----------
def _cantiere(prove: dict) -> dict:
    costr = prove["costruttore"]
    dop = next((d for d in prove["dop_costruttore"] if costr and _stessa(d.get("fabbricante", ""), costr)), None)
    if dop:
        pezzi = [f"DoP n. {dop.get('numero_dop', '')}" + (f" del {dop['data']}" if dop.get("data") else "")]
        pezzi += [f"CE {dop['cpr']}"] if dop.get("cpr") else []
        pezzi += [x for x in (dop.get("norma"), dop.get("classe_esecuzione")) if x]
        ce = _c("; ".join(pezzi), dop["fonti"].get("numero_dop"), dop["fonti"].get("cpr"))
    else:
        ce = _c(NON_PRESENTE)
    ddt_costr = [d for d in prove["ddt"] if d["tipo"] == "costruttore_cliente"]
    ddt_c = (
        _c(
            "; ".join(f"DDT n. {d['numero']} del {d['data']}" for d in ddt_costr),
            *[d["fonti"].get("numero") for d in ddt_costr],
        )
        if ddt_costr
        else _c(NON_PRESENTE)
    )
    fonti_costr = [fid for fid, f in prove["fonti"].items() if costr and _stessa(f["valore"], costr)]
    return {"costruttore": _c(costr or "Non individuato", *fonti_costr), "ce": ce, "ddt": ddt_c}


def _dop_del_certificato(prove: dict, cert: dict) -> list[dict]:
    """DoP di prodotto collegate al certificato solo con prova (scheda 07 §5): P1 numero DoP o FPC stampato sul 3.1,
    P2 DDT dell'acciaieria stampato su entrambi. Mai per sola compatibilità di fabbricante o qualità."""
    trovate = []
    for d in prove["dop_prodotto"]:
        p1 = any(
            nz.stesso_numero(v, d.get(k, "")) == "uguale" for v, _ in cert["ce_dop"] for k in ("numero_dop", "fpc")
        )
        p2 = (
            bool(cert.get("ddt_produttore"))
            and nz.stesso_numero(cert["ddt_produttore"], d.get("ddt_citato", "")) in STESSO
        )
        if (p1 or p2) and d not in trovate:
            trovate.append(d)
    return trovate


def _colonne(prove: dict, voce: dict, dec: dict, cantiere: dict) -> dict:
    cert, rc, doc = dec["cert"], dec["colata"], dec["ddt"]
    vf = voce["fonti"]
    if cert:
        produttore = _c(cert["produttore"], cert["fonti"].get("produttore"))
        numero = _c(
            f"{cert['numero']} del {cert['data']}" if cert["data"] else cert["numero"],
            cert["fonti"].get("numero"),
            cert["fonti"].get("data"),
        )
        pezzi = [(v, f) for v, f in cert["ce_dop"]]
        for d in _dop_del_certificato(prove, cert):
            testo = "DoP" + (f" {d['numero_dop']}" if d.get("numero_dop") else f" (DDT acciaieria {d['ddt_citato']})")
            testo += f", {d['norma']}" if d.get("norma") else ""
            pezzi.append((testo, d["fonti"].get("numero_dop") or d["fonti"].get("ddt_citato")))
        ce = _c("; ".join(v for v, _ in pezzi) or NON_PRESENTE, *[f for _, f in pezzi])
    elif voce["certificato"]:
        produttore = _c(
            f"{voce['emesso_da']} (dichiarato dal costruttore)" if voce["emesso_da"] else "", vf.get("emesso_da")
        )
        data = f" del {voce['data_certificato']}" if voce["data_certificato"] else ""
        numero = _c(f"{voce['certificato']}{data} - non nel fascicolo", vf.get("certificato"))
        ce = _c(NON_PRESENTE)
    else:
        produttore, numero, ce = _c(NON_PRESENTE), _c(NON_PRESENTE), _c(NON_PRESENTE)
    if rc:
        tipo = _c(rc["qualita"], rc["fonti"].get("qualita"))
    elif dec["righe_cert"]:
        tipo = _c(dec["righe_cert"][0]["qualita"], dec["righe_cert"][0]["fonti"].get("qualita"))
    elif voce.get("qualita"):
        tipo = _c(f"{voce['qualita']} (dichiarato)", vf.get("qualita"))
    else:
        tipo = _c((dec["riga_ddt"] or {}).get("qualita", ""), (dec["riga_ddt"] or {}).get("fonti", {}).get("qualita"))
    commerciante = (
        _c(doc["emittente"], doc["fonti"].get("emittente")) if doc else _c(voce["fornito_da"], vf.get("fornito_da"))
    )
    if doc:
        ddt = _c(
            f"DDT n. {doc['numero']}" + (f" del {doc['data']}" if doc["data"] else ""),
            doc["fonti"].get("numero"),
            doc["fonti"].get("data"),
        )
    elif voce["ddt"]:
        ddt = _c(f"DDT n. {voce['ddt']} - non nel fascicolo", vf.get("ddt"))
    else:
        ddt = _c(NON_PRESENTE)
    centro = next(
        (
            d
            for d in prove["dop_prodotto"]
            if commerciante["v"] and _stessa(d.get("fabbricante", ""), commerciante["v"])
        ),
        None,
    )
    titolo = voce["parte_opera"]
    return {
        "PRODUTTORE": produttore,
        "COLATA": _c(rc["colata"], rc["fonti"].get("colata")) if rc else _c(""),
        "TIPO DI ACCIAIO": tipo,
        "CE/DoP ACCIAIERIA": ce,
        "CERT 3.1 ACCIAIERIA": numero,
        "COMMERCIANTE / CENTRO TRASF.": commerciante,
        "CE/DoP CENTRO": _c(f"DoP {centro.get('numero_dop', '')}", centro["fonti"].get("numero_dop"))
        if centro
        else _c(NON_PRESENTE),
        "DDT COMMERCIANTE": ddt,
        "COSTRUTTORE": cantiere["costruttore"],
        "CE/DoP COSTRUTTORE": cantiere["ce"],
        "DDT COSTRUTTORE": cantiere["ddt"],
        "PARTE D'OPERA": _c(f"{titolo} - {voce['etichetta']}" if titolo else voce["etichetta"], vf.get("materiale")),
    }


def _note(stato: str, dec: dict) -> list[str]:
    note = []
    if stato == MANCANTE and dec["richieste"]:
        note.append(f"Chiedere a {dec['fornitore'] or 'fornitore'}: " + "; ".join(dec["richieste"]) + ".")
    elif dec["richieste"]:
        note.append("Da chiedere: " + "; ".join(dec["richieste"]) + ".")
    if dec["colate_possibili"]:
        note.append("Colate possibili: " + ", ".join(dec["colate_possibili"]) + ".")
    if stato != MANCANTE:
        note += [m[0].upper() + m[1:] + "." for m in dec["motivi"][:2]]
    note += [a[0].upper() + a[1:] + "." for a in dec["avvisi"]]
    return note


def elabora(prove: dict) -> dict:
    """Prove (formato prove/2) -> risultato/2. Stesse prove, stesso risultato."""
    m = Motore(prove)
    cantiere = _cantiere(prove)
    voci = []
    for voce in (v for gruppo in voci_dal_fascicolo(prove) for v in m.dividi(gruppo)):
        dec = m.decidi(voce)
        pagine = sorted(
            {r["pid"] for r in voce["righe"]}
            | set((dec["ddt"] or {}).get("pagine", []))
            | set((dec["cert"] or {}).get("pagine", []))
        )
        voci.append(
            {
                "voce": voce["etichetta"],
                "parte_opera": voce["parte_opera"],
                "origine": voce["origine"],
                "ddt": voce["ddt"],
                "certificato_dichiarato": voce["certificato"],
                "stato": dec["stato"],
                "colonne": _colonne(prove, voce, dec, cantiere),
                "note": _note(dec["stato"], dec),
                "motivi": dec["motivi"],
                "avvisi": dec["avvisi"],
                "scartati": dec["scartati"],
                "pagine": pagine,
                "fornitore": dec["fornitore"],
                "richieste": dec["richieste"],
                "documenti": [x["id"] for x in (dec["ddt"], dec["cert"]) if x],
                "colate_possibili": dec["colate_possibili"],
            }
        )
    voci.sort(key=lambda v: (v["parte_opera"], nz.data_iso(v["colonne"]["DDT COMMERCIANTE"]["v"]), v["ddt"], v["voce"]))
    for i, v in enumerate(voci, 1):
        v["n"] = i
    conteggio = {s: sum(1 for v in voci if v["stato"] == s) for s in ORDINE}
    usati = {d for v in voci for d in v["documenti"]}
    return {
        "formato": "risultato/2",
        "motore": VERSIONE,
        "impronta_prove": impronta(prove),
        "conteggio": conteggio,
        "voci": voci,
        "documenti_usati": sorted(usati),
        "avviso_packing": not prove["packing"],
    }


def impronta(dati) -> str:
    return hashlib.sha256(json.dumps(dati, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]
