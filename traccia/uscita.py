"""Composizione dell'uscita (solo Python): letture in archivio -> prove -> motore -> Excel, prove HTML, fascicolo.

Stesse letture, stessa uscita. Nessun orologio nei contenuti: l'ora sta solo negli eventi della piattaforma.
"""

import json
import shutil
import uuid
from pathlib import Path

from . import lavoro as lv
from . import percorsi
from .excel import scrivi
from .famiglie import NOMI
from .motore import COLONNE, elabora
from .prove import costruisci
from .provenienza import immagine_dritta, pagina_cella
from .riordino import crea

NOME_EXCEL = "tracciabilita.xlsx"


def _schede(cartella: Path) -> tuple[list[dict], dict[str, dict]]:
    pagine = lv.pagine(cartella)
    schede = {}
    for p in pagine:
        s = lv.scheda_pagina(p)
        if s:
            schede[p["pid"]] = s
    return pagine, schede


def componi(cartella: Path) -> dict:
    lv.evento(cartella, tipo="componi", testo="Collego a ritroso: tabella -> DDT -> certificato -> colata")
    pagine, schede = _schede(cartella)
    prove = costruisci(pagine, schede)
    indice = json.loads((cartella / "pagine.json").read_text(encoding="utf-8"))
    prove["file_non_letti"] = [p["file"] for p in indice if not p.get("pid")]
    risultato = elabora(prove)
    uscita = cartella / (".uscita-" + uuid.uuid4().hex)
    (uscita / "prove" / "img").mkdir(parents=True)
    (uscita / "prove" / "ritagli").mkdir(parents=True)
    info = {p["pid"]: p for p in pagine}

    # immagini dritte e ritagli usati
    ritagli: dict[str, list[str]] = {}
    for pid, s in schede.items():
        for r in s.get("ritagli", []):
            src = lv.cartella_ritagli() / r["file"]
            if src.exists():
                shutil.copyfile(src, uscita / "prove" / "ritagli" / r["file"])
                ritagli.setdefault(pid, []).append(f"ritagli/{r['file']}")

    link = {}
    for v in risultato["voci"]:
        for j, c in enumerate(COLONNE):
            fonti = []
            for fid in v["colonne"][c]["fonti"]:
                f = prove["fonti"][fid]
                gradi = schede[f["pid"]].get("orientamento", 0)
                immagine_dritta(
                    cartella / "pagine" / f"{f['pid']}.png", gradi, uscita / "prove" / "img" / f"{f['pid']}.png"
                )
                fonti.append({**f, "img": f"img/{f['pid']}.png", "gradi": gradi})
            if not fonti:
                continue
            nome = f"v{v['n']:03d}_c{j + 1:02d}.html"
            titolo = f"Voce {v['n']} · {v['voce']} · {v['stato']}"
            (uscita / "prove" / nome).write_text(
                pagina_cella(titolo, c, v["colonne"][c]["v"], fonti, ritagli), encoding="utf-8"
            )
            link[(v["n"], c)] = f"prove/{nome}"

    def pagine_voce(v: dict) -> str:
        per_file: dict[str, list[int]] = {}
        for pid in v["pagine"]:
            per_file.setdefault(info[pid]["file"], []).append(info[pid]["pagina"])
        return "; ".join(f"{f} p{', '.join(map(str, sorted(n)))}" for f, n in sorted(per_file.items()))

    stato = lv.stato(cartella)
    documenti = []
    per_file: dict[str, list[dict]] = {}
    for p in stato["pagine"]:
        per_file.setdefault(p["file"], []).append(p)
    for f, ps in sorted(per_file.items()):
        famiglie = sorted({NOMI.get(p.get("famiglia", ""), "") for p in ps if p.get("famiglia")})
        documenti.append(
            [
                f,
                len(ps),
                sum(1 for p in ps if p["stato"] == "letta"),
                sum(1 for p in ps if p["stato"] != "letta"),
                ", ".join(famiglie),
            ]
        )

    usati = set(risultato["documenti_usati"])
    non_usati = []
    for d in prove["ddt"]:
        if d["id"] not in usati:
            motivo = {
                "costruttore_cliente": "DDT del costruttore al cliente: non porta la catena dei materiali",
                "fuori_perimetro": "DDT non diretto al costruttore (es. acciaieria -> commerciante)",
            }.get(
                d["tipo"],
                "DDT non dichiarato dal costruttore per questo cantiere"
                + (f" (commessa {d['commessa']})" if d["commessa"] else ""),
            )
            non_usati.append([_dove(d["pagine"], info), f"DDT {d['numero']} di {d['emittente']}", motivo])
    for c in prove["certificati"]:
        if c["id"] not in usati:
            profili = ", ".join(sorted({r["chiave"] for r in c["righe"]}))[:120]
            non_usati.append(
                [
                    _dove(c["pagine"], info),
                    f"Certificato {c['numero']} di {c['produttore']} ({profili})",
                    "Non dichiarato dal costruttore né collegato a una voce",
                ]
            )
    for e in prove["escluse"]:
        non_usati.append([_dove([e["pid"]], info), NOMI.get(e["famiglia"], e["famiglia"]), e["motivo"]])

    avvisi = []
    if risultato["avviso_packing"]:
        avvisi.append(
            "Packing / tabella del costruttore MANCANTE: voci prese dai DDT ricevuti dal costruttore "
            "(stato massimo DEDOTTO)."
        )
    if stato["non_lette"]:
        avvisi.append(
            f"Pagine non lette dopo {lv.MAX_TENTATIVI} tentativi: "
            + ", ".join(_dove([pid], info) for pid in stato["non_lette"])
            + ". Lettura incompleta."
        )
    for pid, s in sorted(schede.items()):
        for a in s.get("avvisi", []):
            avvisi.append(f"{_dove([pid], info)}: {a}")

    metodo = [
        "Lettura: Claude con la visione, una volta per pagina, con le istruzioni della cartella (versione "
        f"{percorsi.versione_lettura()}); ogni valore ha pagina, citazione e zona.",
        "Controlli Python: citazione presente nella trascrizione, valore dentro la citazione, una colata per voce.",
        "A ritroso: tabella/packing del costruttore -> DDT del commerciante -> certificato 3.1 -> colata.",
        "Una voce = certificato dichiarato + DDT + profilo/spessore; senza dichiarazione: DDT + profilo.",
        "PROVATO: certificato e DDT presenti, timbro o lettera con il numero del DDT, una sola colata.",
        "DEDOTTO: certificato e DDT presenti e coerenti, una sola colata, nessun timbro.",
        "DA CONFERMARE: più colate, legame incerto, pagine del certificato mancanti, timbro per un altro DDT, DDT "
        "assente, numero del DDT scritto a penna, segni a mano.",
        "MANCANTE: certificato dichiarato non presente; nella colonna il numero dichiarato, da chiedere al fornitore.",
        "Ogni cella con una fonte ha un collegamento alla pagina del documento con il dato evidenziato.",
    ]
    excel = uscita / NOME_EXCEL
    scrivi(
        excel,
        risultato,
        prove,
        {
            "link": link,
            "pagine_voce": pagine_voce,
            "non_usati": non_usati,
            "documenti": documenti,
            "avvisi": avvisi,
            "metodo": metodo,
        },
    )
    crea(cartella, pagine, schede, uscita / "fascicolo_ordinato")
    (uscita / "prove.json").write_text(json.dumps(prove, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    (uscita / "risultato.json").write_text(json.dumps(risultato, ensure_ascii=False, indent=1), encoding="utf-8")
    riepilogo = {
        "impronta": lv.impronta_letture(cartella),
        "conteggio": risultato["conteggio"],
        "voci": len(risultato["voci"]),
        "excel": "uscita/" + NOME_EXCEL,
        "motore": risultato["motore"],
        "impronta_prove": risultato["impronta_prove"],
    }
    (uscita / "riepilogo.json").write_text(json.dumps(riepilogo, ensure_ascii=False, indent=1), encoding="utf-8")
    finale = cartella / "uscita"
    if finale.exists():
        versioni = cartella / "versioni"
        versioni.mkdir(exist_ok=True)
        finale.rename(versioni / uuid.uuid4().hex)
    uscita.rename(finale)
    lv.evento(cartella, tipo="pronto", testo="Excel pronto", conteggio=risultato["conteggio"])
    return riepilogo


def _dove(pids: list[str], info: dict) -> str:
    per_file: dict[str, list[int]] = {}
    for pid in pids:
        per_file.setdefault(info[pid]["file"], []).append(info[pid]["pagina"])
    return "; ".join(f"{f} p{', '.join(map(str, sorted(n)))}" for f, n in sorted(per_file.items()))
