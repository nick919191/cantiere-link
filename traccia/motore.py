"""Motore di regole 0.7.5: dalle prove del fascicolo alle voci con stato. Nessuna AI, nessun caso, nessun orologio.

Regole (conoscenza/05_regole_di_stato.md):
- voce = certificato dichiarato dal costruttore + DDT + profilo/spessore; senza dichiarazione DDT + profilo, e una
  voce per colata quando il DDT dichiara le colate placca per placca (VOCE_PER_COLATA);
- il certificato dichiarato si cerca per NUMERO; se manca: MANCANTE con il numero dichiarato e il fornitore, mai un
  altro certificato con lo stesso profilo; senza dichiarazione: prima la colata dichiarata sul DDT o dalla lista del
  commerciante, poi i certificati con il ponte (timbro o lettera con il numero del DDT), poi il profilo;
- PROVATO: certificato e DDT presenti, timbro (o lettera) con il numero del DDT, una sola colata (anche scelta dal
  segno a mano su una sola colata, con avviso);
- DEDOTTO: certificato e DDT presenti e coerenti, una sola colata, nessun timbro;
- DA CONFERMARE: più colate, legame incerto, pagine del certificato mancanti, certificato timbrato per un altro DDT,
  DDT non nel fascicolo, documento letto a metà, pagine della catena non lette nello stesso file;
- tetti: timbro con il numero del DDT scritto a penna -> al massimo DEDOTTO, mai sotto il certificato senza timbro
  (impostazione PENNA_VALE_COME_PROVA, 0.6.0); pezzo ricavato da un profilo più largo -> al massimo DEDOTTO. Dalla
  0.7.0 la packing assente non abbassa più lo stato (resta l'avviso e la dicitura "(dai DDT)").
  0.7.1 (da Viollier) O e 0 nei numeri; piatto scritto '70X10' sul certificato; DDT a penna letto male ripreso per
        data; certificato dichiarato assente sostituito da quello timbrato per lo stesso DDT (max DEDOTTO); una
        voce per file di packing anche se il titolo cambia da pagina a pagina.
  0.7.2 (da Valentino) 'FERRO U 200' è l'UPN 200; le righe di riferimento del DDT ('RIF. COMM', 'CERTIFICATI:') non
        sono voci; il nome del file o della cartella del certificato che cita il DDT è un ponte (DEDOTTO).
  0.7.3 (da Gstaad) bulloneria con parole inglesi/tedesche e codici ISO; 'PIATTI IN LAMIERA SPESSORE 10 MM'; date con
        punti; timbro a penna ripreso per data e emittente; copia del certificato senza numero unita; lettera del
        distributore riconosciuta dal protocollo nel nome del file; tubi affini solo con le stesse misure; nessuna
        voce fantasma da un certificato già ancorato a un DDT del fascicolo.
  0.7.4 (da progresso) il DDT dichiarato dal costruttore vale anche come coda del numero stampato ('12000/' per
        '1/12000', '8603/' per '2021-S_DVE-0008603'); colata dichiarata con la sigla del produttore davanti
        ('SICL2103435A' per 'CL21/03435A'); 'IPE MM. 400', 'LAMINATO ELLE 60x40x6', 'DADO MA16', barre filettate
        e tubi scritti per colonne; righe di finitura e servizio non sono voci; motivo esplicito quando la
        tabella del costruttore non dà la misura del profilo.
  0.7.5 (da Codogno, dopo la Verifica finale) sui DDT dei tubi la Ø letta '0' ('T NERO SALDATO S355J2 0 219,1 X 12,5'
        è il TUBO 219.1x12.5; 'T TONDO 0 60 X 5' un tubo tondo 60x5, non un tondo pieno).
"""

import hashlib
import json
import re

from . import normalizza as nz

VERSIONE = "0.7.5"
PENNA_VALE_COME_PROVA = False
VOCE_PER_COLATA = True  # DDT con più colate per lo stesso profilo (placca per placca): una voce per colata

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


def _c(v: str, *fonti, perche: str = "") -> dict:
    """Cella: valore, fonti (id in prove["fonti"]) e perché il motore ha messo lì quel dato (vista a tabella)."""
    return {"v": v, "fonti": [f for f in fonti if f], "perche": perche}


def _stessa(prove: dict, a: str, b: str) -> bool:
    """Stessa azienda: nuclei delle ragioni sociali e alias del fascicolo (stessa partita IVA)."""
    return nz.stessa_azienda(a, b, prove.get("aziende", []))


# ---------- voci ----------
def _etichetta(righe: list[dict]) -> str:
    dims = [nz.dimensioni_piatto(r["chiave"]) for r in righe]
    if dims and all(d and d[0] for d in dims):
        larghezze = sorted({nz.numero(str(d[0])) for d in dims}, key=float)
        base = f"PL{nz.numero(str(dims[0][1]))}*{'/'.join(larghezze)}"
    else:
        base = " / ".join(sorted({r.get("materiale") or r["chiave"] for r in righe}))
    return f"{base}, {len(righe)} righe" if len(righe) > 1 else base


def _colate_da_lettere(prove: dict, numero_ddt: str, chiavi: list[str]) -> dict[str, list[str]]:
    """Colate (con le placche) che le lettere o liste del commerciante dichiarano per un DDT e un materiale: le
    righe con un articolo compatibile valgono per quel materiale; quelle senza articolo valgono per tutti i
    materiali del DDT, ma solo se nessuna riga con articolo lo descrive (il preciso vince sul generico)."""
    if not numero_ddt:
        return {}
    precise: dict[str, list[str]] = {}
    generiche: dict[str, list[str]] = {}
    for lt in prove.get("lettere", []):
        if not nz.cita_ddt(lt.get("ddt_citato", ""), numero_ddt):
            continue
        for r in lt.get("righe", []):
            if not r.get("colata"):
                continue
            articolo = nz.profilo(r["articolo"]) if r.get("articolo") else ""
            if articolo and not any(articolo == k or _affine(articolo, k) for k in chiavi):
                continue
            dove = precise if articolo else generiche
            dove.setdefault(r["colata"], [])
            if r.get("placca") and r["placca"] not in dove[r["colata"]]:
                dove[r["colata"]].append(r["placca"])
    return precise or generiche


def voci_dal_fascicolo(prove: dict) -> list[dict]:
    voci = []
    if prove["packing"]:
        # Stesso certificato, stesso DDT, stesso gruppo di profilo, stesso file di packing: una voce. Il titolo
        # (parte d'opera) non separa: su un ciclo di più pagine il lettore lo prende diverso da pagina a pagina.
        pid_file = {f["pid"]: f["file"] for f in prove["fonti"].values()}
        gruppi: dict[tuple, list] = {}
        for r in prove["packing"]:
            chiave = (
                nz.numero_normale(r.get("certificato", "")),
                nz.numero_normale(r.get("ddt", "")),
                nz.gruppo(r["chiave"]),
                pid_file.get(r["pid"], ""),
            )
            gruppi.setdefault(chiave, []).append(r)
        for righe in gruppi.values():
            primo = next((r for r in righe if r.get("certificato")), righe[0])
            titoli = list(dict.fromkeys(r.get("titolo", "") for r in righe if r.get("titolo")))
            voci.append(
                {
                    "origine": "costruttore",
                    "righe": righe,
                    "etichetta": _etichetta(righe),
                    "chiavi": sorted({r["chiave"] for r in righe}),
                    "parte_opera": " / ".join(titoli),
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
                if r["chiave"]:  # una riga senza materiale riconoscibile non è una voce
                    per_chiave.setdefault(r["chiave"], []).append(r)
            for chiave, righe in per_chiave.items():
                base = {
                    "origine": "dai_ddt",
                    "righe": [],
                    "etichetta": chiave,
                    "chiavi": [chiave],
                    "parte_opera": "",
                    "certificato": next((r.get("certificato", "") for r in righe if r.get("certificato")), ""),
                    "emesso_da": "",
                    "data_certificato": "",
                    "fornito_da": d["emittente"],
                    "ddt": d["numero"],
                    "data_ddt": d["data"],
                    "qualita": next((r["qualita"] for r in righe if r["qualita"]), ""),
                    "fonti": {},
                    "colate_dichiarate": [],
                    "placche": [],
                }
                colate: dict[str, list[str]] = {}
                for r in righe:
                    for c in r.get("colate", []):
                        colate.setdefault(c, [])
                        colate[c] += [p for p in r.get("placche", {}).get(c, []) if p not in colate[c]]
                if not colate:  # il DDT non le stampa: forse le dichiara la lista del commerciante
                    colate = _colate_da_lettere(prove, d["numero"], [chiave])
                if colate and VOCE_PER_COLATA:
                    for c, placche in colate.items():
                        voci.append(
                            {
                                **base,
                                "etichetta": f"{chiave} · colata {c}",
                                "colate_dichiarate": [c],
                                "placche": placche,
                                "fonti": {
                                    "colata": next(
                                        (r["fonti"].get("colata") for r in righe if c in r.get("colate", [])), None
                                    )
                                },
                            }
                        )
                else:
                    voci.append(
                        {
                            **base,
                            "colate_dichiarate": list(colate),
                            "placche": [p for ps in colate.values() for p in ps],
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


def _affine(a: str, b: str) -> bool:
    """Profili scritti diversamente ma compatibili: stesso spessore per piatti e lamiere ('LAMIERA 10' e
    'PIATTO 200x10'); altrimenti stessa parola e stessa prima misura ('TUBO 219.1x12.5' e 'TUBO 219.1x12.5x12000')."""
    da, db = nz.dimensioni_piatto(a), nz.dimensioni_piatto(b)
    if da and db:
        return da[1] == db[1]
    if da or db:
        # 'PIATTO 70x10' e '70X10' scritto senza parola (preso per un tubo): stesse due misure, stesso piatto
        piatto, altro = (da, b) if da else (db, a)
        m = re.fullmatch(r"TUBO (\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)", altro)
        return bool(m and piatto[0] is not None and {float(m.group(1)), float(m.group(2))} == {piatto[0], piatto[1]})
    pa, pb = a.split(" ", 1), b.split(" ", 1)
    if pa[0] != pb[0]:
        return False
    if pa[0] == "TUBO":  # 'TUBO 150x100' e 'TUBO 150x100x6' sì; 'TUBO 100x100x3' e 'TUBO 100x100x5' no
        da_, db_ = (
            [float(x) for x in re.findall(r"\d+(?:\.\d+)?", pa[1] if len(pa) > 1 else "")],
            [float(x) for x in re.findall(r"\d+(?:\.\d+)?", pb[1] if len(pb) > 1 else "")],
        )
        n = min(len(da_), len(db_))
        return n >= 2 and da_[:n] == db_[:n]
    ma, mb = (
        re.search(r"\d+(?:\.\d+)?", pa[1] if len(pa) > 1 else ""),
        re.search(r"\d+(?:\.\d+)?", pb[1] if len(pb) > 1 else ""),
    )
    return bool(ma and mb) and float(ma.group()) == float(mb.group())


def _righe_affini(cert: dict, voce: dict, riga_ddt: dict | None) -> list[dict]:
    obiettivo = [riga_ddt["chiave"]] if riga_ddt else voce["chiavi"]
    return [r for r in cert["righe"] if any(_affine(o, r["chiave"]) for o in obiettivo)]


SEGNI_CHE_SCELGONO = {"freccia", "cerchio", "evidenziatore", "spunta"}  # la croce esclude, la scritta non decide


def _scegli_segnata(cert: dict, righe: list[dict]) -> tuple[list[dict], str | None]:
    """Decisione 1: con più colate per il profilo, un segno a mano (freccia, evidenziatore, cerchio) su UNA sola di
    loro la sceglie; la voce va avanti come se la colata fosse unica, con avviso. Segni su più colate: nessuna
    scelta."""
    colate = _per_colata(righe)
    if len(colate) < 2:
        return righe, None
    possibili = {r["colata"] for r in colate}
    segni = [s for s in cert.get("segni", []) if s.get("colata") in possibili]
    scelte = sorted({s["colata"] for s in segni if s["tipo"] in SEGNI_CHE_SCELGONO})
    barrate = sorted({s["colata"] for s in segni if s["tipo"] == "croce"})
    if len(scelte) == 1:
        tipo = next(s["tipo"] for s in segni if s["colata"] == scelte[0] and s["tipo"] in SEGNI_CHE_SCELGONO)
        return [r for r in righe if r["colata"] == scelte[0]], (
            f"colata {scelte[0]} scelta dal segno a mano ({tipo}): controllare l'originale"
        )
    if not scelte and barrate and len(possibili - set(barrate)) == 1:
        (rimasta,) = possibili - set(barrate)
        return [r for r in righe if r["colata"] == rimasta], (
            f"colata {rimasta} scelta perché le altre sono barrate a mano: controllare l'originale"
        )
    return righe, None


def _segno_su_una_colata(cert: dict, righe: list[dict]) -> bool:
    """True se un segno che sceglie (freccia, spunta...) sta su una sola delle colate di queste righe."""
    colate = {r["colata"] for r in righe if r["colata"]}
    scelte = {
        s["colata"] for s in cert.get("segni", []) if s["tipo"] in SEGNI_CHE_SCELGONO and s.get("colata") in colate
    }
    return len(scelte) == 1


def _per_colata(righe: list[dict]) -> list[dict]:
    scelte = {}
    for r in righe:
        if r["colata"] and r["colata"] not in scelte:
            scelte[r["colata"]] = r
    return list(scelte.values())


# ---------- una voce ----------
FAMIGLIE_DELLA_CATENA = {"ddt", "certificato_31", "packing_costruttore", "lettera_accompagnamento"}


class Motore:
    def __init__(self, prove: dict):
        self.p = prove
        self.ddt_noti = [d for d in prove["ddt"] if d["tipo"] == "commerciante_costruttore"]
        self.pid_file = {f["pid"]: f["file"] for f in prove["fonti"].values()}
        self.parziali = set(prove.get("parziali", []))

    def non_lette_vicine(self, documenti: list[dict | None], pid_righe: set[str]) -> list[str]:
        """Pagine non lette che possono riguardare la voce: senza riconoscimento (contenuto ignoto) oppure
        riconosciute come DDT, certificato, packing o lettera nello stesso file dei documenti della voce. Le non
        lette riconosciute come da escludere o DoP non contano (C4)."""
        dettagli = self.p.get("non_lette_dettagli")
        if dettagli is None:  # prove senza riconoscimento: ogni pagina non letta conta
            return list(self.p.get("non_lette", []))
        file = {self.pid_file.get(pid) for d in documenti if d for pid in d.get("pagine", [])}
        file |= {self.pid_file.get(pid) for pid in pid_righe}
        file.discard(None)
        vicine = []
        for n in dettagli:
            if n.get("famiglia") is None:
                vicine.append(n["pid"])
            elif n["famiglia"] in FAMIGLIE_DELLA_CATENA and (not file or n.get("file") in file):
                vicine.append(n["pid"])
        return vicine

    def ddt_di(self, voce: dict) -> dict | None:
        trovati = [
            d
            for d in self.ddt_noti
            if nz.stesso_numero(voce["ddt"], d["numero"]) in STESSO or nz.cita_ddt(voce["ddt"], d["numero"])
        ]
        if voce["fornito_da"]:
            stessi = [d for d in trovati if _stessa(self.p, d["emittente"], voce["fornito_da"])]
            trovati = stessi
        return trovati[0] if len(trovati) == 1 else None

    def ponti(self, cert: dict, numero_ddt: str) -> list[dict]:
        """Prove che legano il certificato al DDT, dalla più forte: timbro del commerciante con il numero del DDT,
        lettera del distributore, nome del file o della cartella che cita il DDT ('certificato ddt 5681.pdf')."""
        timbri = [t for t in cert["timbri"] if nz.cita_ddt(t["ddt_citato"], numero_ddt)]
        file_cert = {self.pid_file.get(pid) for pid in cert["pagine"]}
        dal_nome = []
        for pid in cert["pagine"]:
            file = self.pid_file.get(pid) or ""
            for n in nz.ddt_nel_nome(file):
                if nz.cita_ddt(n, numero_ddt) and not any(x["ddt_citato"] == n for x in dal_nome):
                    dal_nome.append(
                        {
                            "chi": "nome del file",
                            "ddt_citato": n,
                            "testo": file.replace("\\", "/").rsplit("/", 1)[-1],
                            "a_mano": False,
                            "dal_nome": True,
                            "pid": pid,
                            "fid": None,
                        }
                    )
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
            if nz.cita_ddt(lt["ddt_citato"], numero_ddt)
            and (
                (
                    self.pid_file.get(lt["pid"]) in file_cert
                    and (
                        any(nz.stesso_numero(n, cert["numero"]) in STESSO for n in lt.get("certificati", []))
                        or any(
                            nz.stessa_colata(r["colata"], c["colata"])
                            for r in lt.get("righe", [])
                            if r.get("colata")
                            for c in cert["righe"]
                        )
                    )
                )
                # il distributore cita il suo protocollo ('RN2000689815'), che è nel nome del file del certificato
                or any(
                    n and len(n) >= 6 and n.lower() in (f or "").lower()
                    for n in lt.get("certificati", [])
                    for f in file_cert
                )
            )
        ]
        return timbri + lettere + dal_nome

    def colate_dichiarate(self, voce: dict, riga_ddt: dict | None) -> list[str]:
        """Colate che il DDT (riga) o la lista del commerciante (lettera che cita il DDT) dichiarano per la voce."""
        if voce.get("colate_dichiarate"):
            return list(voce["colate_dichiarate"])
        if riga_ddt and riga_ddt.get("colate"):
            return list(riga_ddt["colate"])
        return list(_colate_da_lettere(self.p, voce["ddt"], voce["chiavi"]))

    def timbrato_altrove(self, cert: dict, numero_ddt: str) -> list[str]:
        altri = set()
        for t in cert["timbri"]:
            if t["ddt_citato"] and not nz.cita_ddt(t["ddt_citato"], numero_ddt):
                if any(nz.cita_ddt(t["ddt_citato"], d["numero"]) for d in self.ddt_noti):
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
        ambiguo = False  # più certificati candidati: non è un'assenza (MANCANTE) ma un dubbio (DA CONFERMARE)
        sostituito = False  # certificato dichiarato assente: ne vale uno timbrato per lo stesso DDT (max DEDOTTO)
        if voce["certificato"]:
            trovati = [c for c in self.p["certificati"] if nz.stesso_numero(voce["certificato"], c["numero"])]
            if not trovati:
                cert, righe, ricavato, ambiguo = self._cerca_per_ponte(
                    voce, doc_ddt, riga_ddt, classe_ddt, scartati, motivi, avvisi
                )
                if cert:
                    sostituito = True
                    motivi.append(
                        f"il costruttore dichiara il certificato {voce['certificato']}, che non è nel fascicolo; il "
                        f"certificato {cert['numero']} è timbrato per lo stesso DDT e ha il profilo"
                    )
                    avvisi.append("numero del certificato diverso da quello dichiarato: da verificare")
                else:
                    ambiguo = False
                    motivi.append(f"il costruttore dichiara il certificato {voce['certificato']}: non è nel fascicolo")
                    richieste.append(f"certificato {voce['certificato']}")
            elif len(trovati) > 1:
                ambiguo = True
                motivi.append("più certificati con lo stesso numero: identificazione non univoca")
            else:
                cert = trovati[0]
                if nz.stesso_numero(voce["certificato"], cert["numero"]) == "prefisso":
                    avvisi.append(f"il costruttore scrive {voce['certificato']}, il certificato porta {cert['numero']}")
                righe, ricavato = _righe_cert(cert, voce, riga_ddt)
                if not righe:  # profilo scritto diversamente ('70X10' senza parola per il piatto 70x10)
                    righe = _righe_affini(cert, voce, riga_ddt)
                    if righe:
                        obiettivo = [riga_ddt["chiave"]] if riga_ddt else voce["chiavi"]
                        avvisi.append(
                            f"profilo scritto diversamente: {' / '.join(obiettivo)} sul DDT, "
                            f"{', '.join(sorted({r['chiave'] for r in righe}))} sul certificato"
                        )
        else:
            dichiarate = self.colate_dichiarate(voce, riga_ddt)
            cert, righe, ricavato, ambiguo = self._cerca_per_colata(voce, dichiarate, riga_ddt, motivi, avvisi)
            if not cert and not ambiguo:
                cert, righe, ricavato, ambiguo = self._cerca_per_ponte(
                    voce, doc_ddt, riga_ddt, classe_ddt, scartati, motivi, avvisi
                )
            if not cert and not ambiguo:
                cert, righe, ricavato, ambiguo = self._cerca_per_profilo(
                    voce, doc_ddt, riga_ddt, classe_ddt, scartati, motivi
                )

        if cert:
            righe, scelta = _scegli_segnata(cert, righe)
            if scelta:
                avvisi.append(scelta)
        if voce["ddt"] and not doc_ddt:
            richieste.append(
                f"DDT {voce['ddt']} di {voce['fornito_da']}"
                if voce["origine"] == "dal_certificato" and voce["fornito_da"]
                else f"DDT {voce['ddt']}"
            )
        stato = self._stato(voce, cert, righe, doc_ddt, riga_ddt, ricavato, ambiguo, motivi, avvisi)
        if sostituito:
            stato = _tetto(stato, DEDOTTO)
        vicine = self.non_lette_vicine([doc_ddt, cert], {r["pid"] for r in voce["righe"]})
        if vicine or self.p.get("file_non_letti"):
            stato = DA_CONFERMARE
            avvisi.append(
                "fascicolo non letto completamente: esito provvisorio, assenze non accertate"
                + (f" (pagine non lette {', '.join(vicine[:6])})" if vicine else "")
            )
        a_meta = [d for d in (doc_ddt, cert) if d and self.parziali & set(d.get("pagine", []))]
        if a_meta:
            stato = DA_CONFERMARE
            motivi.append(
                "documento letto solo in parte (famiglia e testata, righe da rileggere): "
                + ", ".join(d.get("numero", "") for d in a_meta)
            )
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
            "placche": voce.get("placche", []),
        }

    def _cerca_per_colata(self, voce, dichiarate, riga_ddt, motivi, avvisi):
        """C5/C13: la colata dichiarata sul DDT (o dalla lista del commerciante) si cerca sui certificati prima del
        profilo: una colata per riga del DDT, nessuna ambiguità tra più colate dello stesso profilo."""
        if not dichiarate:
            return None, [], False, False
        trovati = []
        for c in self.p["certificati"]:
            righe = [r for r in c["righe"] if r["colata"] and any(nz.stessa_colata(r["colata"], d) for d in dichiarate)]
            if righe:
                trovati.append((c, righe))
        if not trovati:
            avvisi.append(
                f"colata {', '.join(dichiarate)} dichiarata sul DDT ma non trovata sui certificati del fascicolo"
            )
            return None, [], False, False
        if voce["ddt"]:
            con_ponte = [x for x in trovati if self.ponti(x[0], voce["ddt"])]
            trovati = con_ponte or trovati
        cert, righe = trovati[0]
        motivi.append(f"colata {', '.join(dichiarate)} dichiarata sul DDT e trovata sul certificato")
        if len(trovati) > 1:
            avvisi.append(
                "la stessa colata compare anche sui certificati " + ", ".join(x[0]["numero"] for x in trovati[1:])
            )
        obiettivo = [riga_ddt["chiave"]] if riga_ddt else voce["chiavi"]
        if not any(r["chiave"] in obiettivo or _affine(o, r["chiave"]) for r in righe for o in obiettivo):
            avvisi.append(
                f"profilo scritto diversamente: {' / '.join(obiettivo)} sul DDT, "
                f"{', '.join(sorted({r['chiave'] for r in righe}))} sul certificato"
            )
        return cert, righe, False, False

    def _cerca_per_ponte(self, voce, doc_ddt, riga_ddt, classe_ddt, scartati, motivi, avvisi):
        """C6: prima i certificati con il ponte (timbro o lettera con il numero del DDT); tra loro vale quello con
        righe dello stesso profilo o affini (stesso spessore o stessa famiglia e misura, scritte diversamente)."""
        if not voce["ddt"]:
            return None, [], False, False
        con_ponte = [c for c in self.p["certificati"] if self.ponti(c, voce["ddt"])]
        affini = []
        for c in con_ponte:
            righe, ricavato = _righe_cert(c, voce, riga_ddt)
            diverso = False
            if not righe:
                righe, ricavato, diverso = _righe_affini(c, voce, riga_ddt), False, True
            compatibili = [r for r in righe if not (classe_ddt and nz.classe(r["qualita"]) not in (None, classe_ddt))]
            if righe and not compatibili:
                scartati.append(f"certificato {c['numero']}: classe diversa dal DDT")
            if compatibili:
                affini.append((c, compatibili, ricavato, diverso))
        if not affini:
            return None, [], False, False
        if len(affini) > 1:
            # Più certificati legati allo stesso DDT: vince quello su cui il costruttore ha segnato a mano una sola
            # colata del profilo; poi chi ha un timbro o una lettera (il ponte "dal nome" lo danno tutti i certificati
            # di un file); a parità, chi ha il profilo esatto (non ricavato, non scritto diversamente).
            segnati = [x for x in affini if _segno_su_una_colata(x[0], x[1])]
            forti = [x for x in affini if any(not p.get("dal_nome") for p in self.ponti(x[0], voce["ddt"]))]
            if len(segnati) == 1:
                affini = segnati
            elif len(forti) == 1:
                affini = forti
            else:
                esatti = [x for x in (forti or affini) if not x[2] and not x[3]]
                if len(esatti) == 1:
                    affini = esatti
                elif len(esatti) > 1:  # piatto con la larghezza scritta batte la lamiera da cui si potrebbe tagliare
                    precisi = [
                        x
                        for x in esatti
                        if any((d := nz.dimensioni_piatto(r["chiave"])) and d[0] is not None for r in x[1])
                    ]
                    if len(precisi) == 1:
                        affini = precisi
        if len(affini) > 1:
            motivi.append(
                "più certificati timbrati per questo DDT: " + ", ".join(sorted(x[0]["numero"] for x in affini))
            )
            return None, [r for x in affini for r in x[1]], False, True
        cert, righe, ricavato, diverso = affini[0]
        if diverso:
            obiettivo = [riga_ddt["chiave"]] if riga_ddt else voce["chiavi"]
            avvisi.append(
                f"profilo scritto diversamente: {' / '.join(obiettivo)} sul DDT, "
                f"{', '.join(sorted({r['chiave'] for r in righe}))} sul certificato"
            )
        return cert, righe, ricavato, False

    def _cerca_per_profilo(self, voce, doc_ddt, riga_ddt, classe_ddt, scartati, motivi):
        """(certificato, righe, ricavato, ambiguo): ambiguo=True quando più certificati restano possibili."""
        candidati = []
        for c in self.p["certificati"]:
            righe, ricavato = _righe_cert(c, voce, riga_ddt)
            compatibili = [r for r in righe if not (classe_ddt and nz.classe(r["qualita"]) not in (None, classe_ddt))]
            if righe and not compatibili:
                scartati.append(f"certificato {c['numero']}: classe diversa dal DDT")
            if compatibili:
                candidati.append((c, compatibili, ricavato))
        if doc_ddt:
            # intestato a un altro commerciante del fascicolo (la bulloneria Reyher per i dadi di Viteria): fuori
            altri = [
                d["emittente"]
                for d in self.ddt_noti
                if d["emittente"] and not _stessa(self.p, d["emittente"], doc_ddt["emittente"])
            ]
            restanti = []
            for x in candidati:
                cliente = x[0]["cliente"]
                altro = (
                    cliente
                    and not _stessa(self.p, cliente, doc_ddt["emittente"])
                    and next((a for a in altri if _stessa(self.p, cliente, a)), None)
                )
                if altro:
                    scartati.append(f"certificato {x[0]['numero']}: intestato a {altro}, non a {doc_ddt['emittente']}")
                else:
                    restanti.append(x)
            candidati = restanti
        if voce["ddt"]:
            con_ponte = [x for x in candidati if self.ponti(x[0], voce["ddt"])]
            if len(con_ponte) == 1:
                return (*con_ponte[0], False)
            if len(con_ponte) > 1:
                motivi.append(
                    "più certificati timbrati per questo DDT: " + ", ".join(sorted(x[0]["numero"] for x in con_ponte))
                )
                return None, [], False, True
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
            return None, [], False, False
        intestati = [x for x in candidati if doc_ddt and _stessa(self.p, x[0]["cliente"], doc_ddt["emittente"])]
        scelti = intestati or candidati
        if len(scelti) > 1:
            motivi.append("più certificati possibili: " + ", ".join(sorted(x[0]["numero"] for x in scelti)))
            return None, [], False, True
        if not intestati:
            motivi.append(
                "abbinato per esclusione: unico certificato con questo profilo, senza intestazione al commerciante"
            )
        return (*scelti[0], False)

    def _stato(self, voce, cert, righe, doc_ddt, riga_ddt, ricavato, ambiguo, motivi, avvisi) -> str:
        if not cert:
            return DA_CONFERMARE if ambiguo else MANCANTE
        colate = _per_colata(righe)
        ponti = self.ponti(cert, voce["ddt"]) if voce["ddt"] else []
        altrove = self.timbrato_altrove(cert, voce["ddt"]) if voce["ddt"] else []
        if not righe:
            if not any(re.match(r"^[A-Z ]+ M?\d", k) for k in voce["chiavi"]):  # 'LAMIERA IN S275JR' senza spessore
                motivi.append(
                    "la tabella del costruttore non dà la misura del profilo: la riga del certificato non si individua"
                )
            elif cert.get("incompleto"):
                motivi.append(
                    f"nel fascicolo solo le pagine {cert['pagine_di_testo']} del certificato: la riga del "
                    f"profilo non c'è"
                )
            else:
                motivi.append("il profilo della voce non compare sul certificato")
            stato = DA_CONFERMARE
        elif len(colate) > 1:
            segnate = sorted({s["colata"] for s in cert["segni"] if s["colata"] in {r["colata"] for r in colate}})
            motivi.append(f"più colate per il profilo sul certificato ({', '.join(r['colata'] for r in colate)})")
            if len(segnate) > 1:
                avvisi.append(f"segni a mano su più colate ({', '.join(segnate)}): nessuna scelta possibile")
            stato = DA_CONFERMARE
        elif not colate:
            motivi.append("colata non leggibile sul certificato")
            stato = DA_CONFERMARE
        elif voce["ddt"] and not doc_ddt:
            motivi.append(f"DDT {voce['ddt']} non nel fascicolo")
            if altrove:
                motivi.append(f"il certificato è timbrato per il DDT {', '.join(altrove)}")
            stato = DA_CONFERMARE
        elif ponti and ponti[0].get("dal_nome"):
            p = ponti[0]
            motivi.append(f"il nome del file del certificato cita il DDT {p['ddt_citato']} ({p['testo']})")
            avvisi.append("collegamento dal nome del file, non da un timbro: da controllare sull'originale")
            stato = DEDOTTO
        elif ponti:
            p = ponti[0]
            motivi.append(
                f"timbro di {p['chi'] or 'commerciante'} sul certificato con il DDT {p.get('ddt_citato') or ''}"
            )
            if p.get("ddt_letto"):
                avvisi.append(
                    f"sul timbro il numero del DDT è letto {p['ddt_letto']}: preso il DDT {p['ddt_citato']} dello "
                    f"stesso giorno, da controllare sull'originale"
                )
            if p["a_mano"] and not PENNA_VALE_COME_PROVA:
                avvisi.append("numero del DDT scritto a penna sul timbro: da controllare sull'originale")
                stato = DEDOTTO
            else:
                stato = PROVATO
        elif altrove:
            motivi.append(f"il certificato è timbrato per un altro DDT ({', '.join(altrove)})")
            stato = DA_CONFERMARE
        elif not voce["ddt"]:
            motivi.append("nessun DDT dichiarato per la voce")
            stato = DA_CONFERMARE
        elif voce["certificato"] or (doc_ddt and _stessa(self.p, cert["cliente"], doc_ddt["emittente"])):
            motivi.append("certificato e DDT presenti e coerenti, senza timbro con il numero del DDT")
            stato = DEDOTTO
        else:
            stato = DA_CONFERMARE
        if ricavato:
            avvisi.append("pezzi ricavati da un profilo più largo (dedotto)")
            stato = _tetto(stato, DEDOTTO)
        # Decisione 2 (0.7.0): la packing assente rende incerto il perimetro, non la prova della singola catena:
        # nessun tetto sullo stato delle voci prese dai DDT; resta l'avviso globale e la dicitura "(dai DDT)".
        if riga_ddt and righe and colate:
            g_ddt, g_cert = nz.gradi(riga_ddt["qualita"]), nz.grado(righe[0]["qualita"])
            if g_ddt and g_cert and g_cert not in g_ddt:
                avvisi.append(f"il DDT dice {riga_ddt['qualita']}, il certificato {g_cert}")
        return stato


# ---------- colonne e note ----------
def _cantiere(prove: dict) -> dict:
    costr = prove["costruttore"]
    dop = next((d for d in prove["dop_costruttore"] if costr and _stessa(prove, d.get("fabbricante", ""), costr)), None)
    if dop:
        pezzi = [f"DoP n. {dop.get('numero_dop', '')}" + (f" del {dop['data']}" if dop.get("data") else "")]
        pezzi += [f"CE {dop['cpr']}"] if dop.get("cpr") else []
        pezzi += [x for x in (dop.get("norma"), dop.get("classe_esecuzione")) if x]
        ce = _c(
            "; ".join(pezzi),
            dop["fonti"].get("numero_dop"),
            dop["fonti"].get("cpr"),
            perche="DoP del costruttore trovata nel fascicolo, con lo stesso fabbricante.",
        )
    else:
        ce = _c(NON_PRESENTE, perche="Nel fascicolo non c'è una DoP del costruttore.")
    ddt_costr = [d for d in prove["ddt"] if d["tipo"] in ("costruttore_cliente", "costruttore_terzista")]
    ddt_resi = [d for d in prove["ddt"] if d["tipo"] == "terzista_cantiere"]
    pezzi = [
        f"DDT n. {d['numero']} del {d['data']}" + (f" (tramite {d['tramite']})" if d.get("tramite") else "")
        for d in ddt_costr
    ]
    pezzi += [f"DDT n. {d['numero']} del {d['data']} di {d['emittente']} (reso al cantiere)" for d in ddt_resi]
    ddt_c = (
        _c(
            "; ".join(pezzi),
            *[d["fonti"].get("numero") for d in ddt_costr + ddt_resi],
            perche="DDT con cui il costruttore ha consegnato il materiale al cliente, trovati nel fascicolo"
            + (" (anche tramite un terzista, es. zincatore)." if any(d.get("tramite") for d in ddt_costr) else "."),
        )
        if pezzi
        else _c(NON_PRESENTE, perche="Nel fascicolo non ci sono DDT del costruttore al cliente.")
    )
    fonti_costr = [fid for fid, f in prove["fonti"].items() if costr and _stessa(prove, f["valore"], costr)]
    costruttore = _c(
        costr or "Non individuato",
        *fonti_costr,
        perche="Chi ha preparato la tabella (packing) dei materiali o ha emesso i DDT al cliente."
        if costr
        else "Nessun documento indica con sicurezza il costruttore.",
    )
    return {"costruttore": costruttore, "ce": ce, "ddt": ddt_c}


def _dop_intermedia(prove: dict, commerciante: str, doc: dict | None) -> tuple[dict, bool] | None:
    """DoP EN 1090 del fornitore intermedio per la voce: stesso emittente del DDT della voce; se più d'una, quella
    che cita il numero del DDT (campo ddt_citato o riferimento di tipo ddt). (dop, cita_il_ddt)."""
    if not commerciante:
        return None
    candidate = [
        d for d in prove.get("dop_fornitore_intermedio", []) if _stessa(prove, d.get("fabbricante", ""), commerciante)
    ]
    if not candidate:
        return None
    numero = (doc or {}).get("numero", "")
    for d in candidate:
        citati = [d.get("ddt_citato", "")] + [v for tipo, v in d.get("riferimenti", []) if tipo == "ddt"]
        if numero and any(nz.cita_ddt(numero, c) or nz.cita_ddt(c, numero) for c in citati if c):
            return d, True
    return candidate[0], False


def _dop_del_certificato(prove: dict, cert: dict) -> list[tuple[dict, str]]:
    """DoP di prodotto collegate al certificato solo con prova (scheda 07 §5): P1 numero DoP o FPC stampato sul 3.1,
    P2 DDT dell'acciaieria stampato su entrambi, P3 stesso produttore e stesso organismo notificato (le 4 cifre
    accanto al marchio CE) stampato su certificato e DoP. Mai per sola compatibilità di fabbricante o qualità.
    (dop, regola)."""
    trovate = []
    for d in prove["dop_prodotto"]:
        p1 = any(
            nz.stesso_numero(v, d.get(k, "")) == "uguale" for v, _ in cert["ce_dop"] for k in ("numero_dop", "fpc")
        )
        p2 = bool(cert.get("ddt_produttore") and d.get("ddt_citato")) and (
            nz.stesso_numero(cert["ddt_produttore"], d["ddt_citato"]) in STESSO
            or nz.contiene_numero(cert["ddt_produttore"], d["ddt_citato"])
            or nz.contiene_numero(d["ddt_citato"], cert["ddt_produttore"])
        )
        organismo = re.search(r"\b\d{4}\b", d.get("organismo", "") or "")
        p3 = (
            bool(organismo)
            and _stessa(prove, d.get("fabbricante", ""), cert["produttore"])
            and any(nz.cita_numero(v, organismo.group()) for v, _ in cert["ce_dop"])
        )
        regola = "numero" if p1 else "ddt" if p2 else "fabbricante e organismo" if p3 else ""
        if regola and d not in [x for x, _ in trovate]:
            trovate.append((d, regola))
    return trovate


def _colonne(prove: dict, voce: dict, dec: dict, cantiere: dict) -> dict:
    cert, rc, doc = dec["cert"], dec["colata"], dec["ddt"]
    vf = voce["fonti"]
    if cert:
        produttore = _c(
            cert["produttore"],
            cert["fonti"].get("produttore"),
            perche="Acciaieria che ha emesso il certificato 3.1 collegato a questa voce.",
        )
        numero = _c(
            f"{cert['numero']} del {cert['data']}" if cert["data"] else cert["numero"],
            cert["fonti"].get("numero"),
            cert["fonti"].get("data"),
            perche="Certificato 3.1 collegato alla voce: è quello dichiarato dal costruttore (cercato per numero)"
            if voce["certificato"]
            else "Certificato 3.1 collegato alla voce: ha una riga con lo stesso profilo e la stessa qualità.",
        )
        pezzi = [(v, f) for v, f in cert["ce_dop"]]
        for d, regola in _dop_del_certificato(prove, cert):
            testo = "DoP" + (f" {d['numero_dop']}" if d.get("numero_dop") else f" (DDT acciaieria {d['ddt_citato']})")
            testo += f", {d['norma']}" if d.get("norma") else ""
            testo += " (collegata per fabbricante e organismo)" if regola == "fabbricante e organismo" else ""
            pezzi.append((testo, d["fonti"].get("numero_dop") or d["fonti"].get("ddt_citato")))
        ce = _c(
            "; ".join(v for v, _ in pezzi) or NON_PRESENTE,
            *[f for _, f in pezzi],
            perche="Marcatura CE e DoP stampate sul certificato, più le DoP collegate per numero, per DDT"
            " dell'acciaieria o per fabbricante e organismo notificato."
            if pezzi
            else "Né il certificato né il fascicolo riportano una DoP dell'acciaieria.",
        )
    elif voce["certificato"]:
        produttore = _c(
            f"{voce['emesso_da']} (dichiarato dal costruttore)" if voce["emesso_da"] else "",
            vf.get("emesso_da"),
            perche="Il certificato non è nel fascicolo: è il produttore scritto dal costruttore nella sua tabella.",
        )
        data = f" del {voce['data_certificato']}" if voce["data_certificato"] else ""
        numero = _c(
            f"{voce['certificato']}{data} - non nel fascicolo",
            vf.get("certificato"),
            perche="Il costruttore dichiara questo certificato, ma nel fascicolo non c'è: va chiesto al fornitore.",
        )
        ce = _c(NON_PRESENTE, perche="Senza certificato non si può collegare una DoP dell'acciaieria.")
    else:
        nessuno = "Nessun certificato dichiarato o trovato per questa voce."
        produttore, numero, ce = (
            _c(NON_PRESENTE, perche=nessuno),
            _c(NON_PRESENTE, perche=nessuno),
            _c(NON_PRESENTE, perche=nessuno),
        )
    if rc:
        tipo = _c(
            rc["qualita"],
            rc["fonti"].get("qualita"),
            perche="Qualità della riga del certificato da cui viene la colata.",
        )
    elif dec["righe_cert"]:
        tipo = _c(
            dec["righe_cert"][0]["qualita"],
            dec["righe_cert"][0]["fonti"].get("qualita"),
            perche="Qualità della prima riga del certificato con questo profilo.",
        )
    elif voce.get("qualita"):
        tipo = _c(
            f"{voce['qualita']} (dichiarato)",
            vf.get("qualita"),
            perche="Qualità scritta dal costruttore: nessun certificato la conferma.",
        )
    else:
        tipo = _c(
            (dec["riga_ddt"] or {}).get("qualita", ""),
            (dec["riga_ddt"] or {}).get("fonti", {}).get("qualita"),
            perche="Qualità scritta sulla riga del DDT." if dec["riga_ddt"] else "Qualità non trovata.",
        )
    commerciante = (
        _c(doc["emittente"], doc["fonti"].get("emittente"), perche="Chi ha emesso il DDT collegato a questa voce.")
        if doc
        else _c(
            voce["fornito_da"], vf.get("fornito_da"), perche="Fornitore indicato dal costruttore nella sua tabella."
        )
    )
    if doc:
        ddt = _c(
            f"DDT n. {doc['numero']}" + (f" del {doc['data']}" if doc["data"] else ""),
            doc["fonti"].get("numero"),
            doc["fonti"].get("data"),
            perche="DDT con cui il materiale è arrivato al costruttore: è il numero citato nella sua tabella"
            if voce["ddt"]
            else "DDT con cui il materiale è arrivato al costruttore: ha una riga con lo stesso profilo.",
        )
    elif voce["ddt"]:
        ddt = _c(
            f"DDT n. {voce['ddt']} - non nel fascicolo",
            vf.get("ddt"),
            perche="Il costruttore cita questo DDT, ma nel fascicolo non c'è.",
        )
    else:
        ddt = _c(NON_PRESENTE, perche="Nessun DDT trovato per questa voce.")
    centro = next(
        (
            d
            for d in prove["dop_prodotto"]
            if commerciante["v"] and _stessa(prove, d.get("fabbricante", ""), commerciante["v"])
        ),
        None,
    )
    intermedia = _dop_intermedia(prove, commerciante["v"], doc)
    if centro:
        dop_centro = _c(
            f"DoP {centro.get('numero_dop', '')}",
            centro["fonti"].get("numero_dop"),
            perche="DoP di prodotto emessa dallo stesso commerciante o centro di trasformazione.",
        )
    elif intermedia:
        d, cita = intermedia
        testo = "DoP EN 1090 " + (d.get("numero_dop") or "") + (f" del {d['data']}" if d.get("data") else "")
        testo += f", {d['norma']}" if d.get("norma") else ""
        dop_centro = _c(
            testo.strip(),
            d["fonti"].get("numero_dop"),
            d["fonti"].get("fabbricante"),
            perche="DoP EN 1090 del fornitore intermedio (commerciante che taglia o fora), "
            + ("che cita il DDT della voce." if cita else "emessa dal commerciante del DDT della voce."),
        )
    else:
        dop_centro = _c(NON_PRESENTE, perche="Nessuna DoP del commerciante nel fascicolo.")
    titolo = voce["parte_opera"]
    return {
        "PRODUTTORE": produttore,
        "COLATA": _c(
            rc["colata"],
            rc["fonti"].get("colata"),
            perche="Colata della riga del certificato con lo stesso profilo e la stessa qualità della voce.",
        )
        if rc
        else _c(
            "",
            perche="Il certificato ha più colate possibili per questo profilo: va scelta sull'originale."
            if dec["colate_possibili"]
            else "Senza una riga del certificato corrispondente la colata non si può ricavare.",
        ),
        "TIPO DI ACCIAIO": tipo,
        "CE/DoP ACCIAIERIA": ce,
        "CERT 3.1 ACCIAIERIA": numero,
        "COMMERCIANTE / CENTRO TRASF.": commerciante,
        "CE/DoP CENTRO": dop_centro,
        "DDT COMMERCIANTE": ddt,
        "COSTRUTTORE": cantiere["costruttore"],
        "CE/DoP COSTRUTTORE": cantiere["ce"],
        "DDT COSTRUTTORE": cantiere["ddt"],
        "PARTE D'OPERA": _c(
            (f"{titolo} - {voce['etichetta']}" if titolo else voce["etichetta"])
            + {"dai_ddt": " (dai DDT)", "dal_certificato": " (da un certificato)"}.get(voce["origine"], ""),
            vf.get("materiale"),
            perche={
                "dai_ddt": "Manca la tabella del costruttore: voce presa dai DDT che ha ricevuto.",
                "dal_certificato": "Certificato con un timbro che cita un DDT assente dal fascicolo: voce da "
                "confermare, da chiedere il DDT.",
            }.get(voce["origine"], "Voce presa dalla tabella del costruttore."),
        ),
    }


def _note(stato: str, dec: dict) -> list[str]:
    note = []
    if stato == MANCANTE and dec["richieste"]:
        note.append(f"Chiedere a {dec['fornitore'] or 'fornitore'}: " + "; ".join(dec["richieste"]) + ".")
    elif dec["richieste"]:
        note.append("Da chiedere: " + "; ".join(dec["richieste"]) + ".")
    if dec["colate_possibili"]:
        note.append("Colate possibili: " + ", ".join(dec["colate_possibili"]) + ".")
    if dec.get("placche"):
        note.append("Placche dichiarate sul DDT: " + ", ".join(dec["placche"]) + ".")
    if stato != MANCANTE:
        note += [m[0].upper() + m[1:] + "." for m in dec["motivi"][:2]]
    note += [a[0].upper() + a[1:] + "." for a in dec["avvisi"]]
    return note


def _voce_risultato(voce: dict, dec: dict, prove: dict, cantiere: dict) -> dict:
    pagine = sorted(
        {r["pid"] for r in voce["righe"]}
        | set((dec["ddt"] or {}).get("pagine", []))
        | set((dec["cert"] or {}).get("pagine", []))
    )
    return {
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


def _voci_dai_certificati(prove: dict, usati: set[str]) -> list[dict]:
    """C12: un certificato non usato il cui timbro cita un DDT che non è nel fascicolo diventa una voce DA
    CONFERMARE con la richiesta del DDT al commerciante del timbro: così si vede che manca un DDT."""
    numeri = [d["numero"] for d in prove["ddt"] if not d.get("incoerente")]  # un DDT letto male non "c'è"
    pid_file = {f["pid"]: f["file"] for f in prove["fonti"].values()}
    voci = []
    for c in prove["certificati"]:
        if c["id"] in usati or not c["righe"]:
            continue
        # Un certificato che un timbro o il nome del file legano a un DDT del fascicolo appartiene a quel DDT: gli
        # altri timbri (vendite precedenti del commerciante, copie riusate) non chiedono DDT che non c'entrano.
        nel_nome = [n for pid in c["pagine"] for n in nz.ddt_nel_nome(pid_file.get(pid) or "")]
        ancorato = any(nz.cita_ddt(n, x) for n in nel_nome for x in numeri) or any(
            t.get("ddt_citato") and any(nz.cita_ddt(t["ddt_citato"], x) for x in numeri) for t in c["timbri"]
        )
        if ancorato:
            continue
        citati: dict[str, dict] = {}
        for t in c["timbri"]:
            n = t.get("ddt_citato", "")
            if n and not any(nz.cita_ddt(n, x) or nz.cita_ddt(x, n) for x in numeri):
                citati.setdefault(nz.numero_normale(n), t)
        for t in citati.values():
            chiavi = sorted({r["chiave"] for r in c["righe"] if r["chiave"]})
            voci.append(
                {
                    "origine": "dal_certificato",
                    "righe": [],
                    "etichetta": " / ".join(chiavi) or c["numero"],
                    "chiavi": chiavi,
                    "parte_opera": "",
                    "certificato": c["numero"],
                    "emesso_da": c["produttore"],
                    "data_certificato": c["data"],
                    "fornito_da": t.get("chi", ""),
                    "ddt": t["ddt_citato"],
                    "data_ddt": t.get("data_ddt", ""),
                    "qualita": "",
                    "fonti": {"ddt": t.get("fid")},
                }
            )
    return voci


def elabora(prove: dict) -> dict:
    """Prove (formato prove/2) -> risultato/2. Stesse prove, stesso risultato."""
    m = Motore(prove)
    cantiere = _cantiere(prove)
    voci = []
    for voce in (v for gruppo in voci_dal_fascicolo(prove) for v in m.dividi(gruppo)):
        voci.append(_voce_risultato(voce, m.decidi(voce), prove, cantiere))
    usati = {d for v in voci for d in v["documenti"]}
    for voce in _voci_dai_certificati(prove, usati):
        dec = m.decidi(voce)
        voci.append(_voce_risultato(voce, dec, prove, cantiere))
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
