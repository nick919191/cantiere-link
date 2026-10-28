"""Misura del coltellino sui 3 cantieri SCL, alla cieca: il dizionario si impara sugli altri due cantieri.

Per ogni cantiere e famiglia: caratteri prima/dopo, sonde perse (valori usati dal motore), codici persi (numeri e
sigle di 4+ cifre: DDT, certificati, colate). Confronto con il taglio della prova 2 (cantiere-link).
Uso: .venv\\Scripts\\python esperimenti\\coltellino\\misura.py "<cartella SCL>" [--esempi]
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "ocr_mistral"))
import coltellino  # noqa: E402
import corpus  # noqa: E402
import prova2  # noqa: E402

CODICE = re.compile(r"(?<![\w])[A-Z]{0,4}[-/]?\d{4,}[A-Z0-9/-]*")


def codici(testo: str) -> set[str]:
    return {corpus.compatto(c) for c in CODICE.findall(testo.upper())}


def main():
    pagine = corpus.carica(Path(sys.argv[1]))
    risultati = defaultdict(lambda: defaultdict(int))
    perse_elenco = []
    for cantiere in corpus.CANTIERI:
        addestramento = [p for p in pagine if p["cantiere"] != cantiere]
        dizionario = coltellino.impara(addestramento, lambda p: [v for _, v in p["sonde"]])
        for p in (p for p in pagine if p["cantiere"] == cantiere):
            fam = p["famiglia"]
            traccia = []
            tagli = {
                "coltellino": coltellino.taglia(p["testo"], fam, dizionario, traccia),
                "colonne": coltellino.taglia(p["testo"], fam, dizionario, modo="colonne"),
                "prova2": prova2.taglia(p["testo"], fam if fam in prova2.PAROLE or fam == "da_escludere" else None),
            }
            for chiave in ("TOTALE", f"{cantiere}", f"famiglia:{fam}"):
                r = risultati[chiave]
                r["pagine"] += 1
                r["caratteri"] += len(p["testo"])
                oss = corpus.osservabili(p)
                r["sonde"] += len(oss)
                cod = codici(p["testo"])
                r["codici"] += len(cod)
                for nome, t in tagli.items():
                    r[f"{nome}.caratteri"] += len(t)
                    perse = corpus.perse(p, t)
                    r[f"{nome}.sonde_perse"] += len(perse)
                    r[f"{nome}.codici_persi"] += len(cod - codici(t))
                    if nome == "coltellino" and chiave == "TOTALE":
                        for s in perse:
                            v = corpus.compatto(s[1])
                            regole = [(g, rr[:120]) for g, rr in traccia if v in corpus.compatto(rr)]
                            perse_elenco.append({"famiglia": fam, "sonda": s, "regole": regole[:2]})
    print(
        f"{'gruppo':34} {'pag':>4} {'car':>8} | {'celle':>18} {'sonde':>9} {'codici':>9} | "
        f"{'colonne':>18} {'sonde':>9} {'codici':>9} | {'prova2':>18} {'sonde':>9} {'codici':>9}"
    )
    for chiave, r in sorted(risultati.items(), key=lambda x: (x[0] != "TOTALE", x[0])):

        def col(nome, r=r):
            car = r[f"{nome}.caratteri"]
            return (
                f"{car:>8} ({100 - car * 100 // max(r['caratteri'], 1):>3}% via) "
                f"{r[f'{nome}.sonde_perse']:>4}/{r['sonde']:<4} {r[f'{nome}.codici_persi']:>4}/{r['codici']:<4}"
            )

        print(
            f"{chiave:34} {r['pagine']:>4} {r['caratteri']:>8} | {col('coltellino')} | {col('colonne')} | "
            f"{col('prova2')}"
        )
    if "--codici" in sys.argv:  # quali codici spariscono: servono o sono telefoni e partite IVA?
        pagine_c = [p for p in pagine if p["cantiere"] == "Gstaad"]
        diz = coltellino.impara([p for p in pagine if p["cantiere"] != "Gstaad"], lambda p: [v for _, v in p["sonde"]])
        visti = 0
        for p in pagine_c:
            t = coltellino.taglia(p["testo"], p["famiglia"], diz)
            for c in sorted(codici(p["testo"]) - codici(t))[:3]:
                riga = next((r for r in p["testo"].splitlines() if c in corpus.compatto(r)), "")
                print(p["famiglia"], c, "|", riga.strip()[:110])
                visti += 1
            if visti > 45:
                break
    if "--esempi" in sys.argv:
        print(json.dumps(perse_elenco[:60], ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()
