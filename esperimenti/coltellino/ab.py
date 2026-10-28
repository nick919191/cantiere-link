"""Prova A/B sul modello: stesse pagine, stesse istruzioni, testo integrale contro testo del coltellino.

Campione stratificato dai 3 cantieri SCL (pagine con valori noti). Per ciascun ramo: token, tempo, schede.
Qualità: (1) valori noti ritrovati nella scheda (richiamo delle sonde); (2) accordo campo per campo tra i due rami.
Uso: .venv\\Scripts\\python esperimenti\\coltellino\\ab.py "<cartella SCL>" [pagine per famiglia]
"""

import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "ocr_mistral"))
import coltellino  # noqa: E402
import corpus  # noqa: E402
import prova as p1  # noqa: E402
import prova2  # noqa: E402

from traccia.agente import _options  # noqa: E402
from traccia.controlli import piatto  # noqa: E402

FAMIGLIE = {"certificato_31": 12, "dop_ce_prodotto": 10, "ddt": 10, "packing_costruttore": 4}


def valori_scheda(s: dict) -> list[str]:
    out = [v["v"] for v in s["testata"].values()]
    out += [v["v"] for r in s["righe"] for v in r.values()]
    out += [r["v"] for r in s["riferimenti"]] + [t[k] for t in s["timbri"] for k in ("ddt_citato", "data_ddt", "testo")]
    return [v for v in out if v]


def main():
    scl = Path(sys.argv[1])
    per_famiglia = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    pagine = corpus.carica(scl)
    random.seed(7)
    campione = []
    for fam, n in FAMIGLIE.items():
        candidate = [p for p in pagine if p["famiglia"] == fam and corpus.osservabili(p)]
        campione += random.sample(candidate, min(per_famiglia or n, len(candidate)))
    dizionari = {
        c: coltellino.impara([p for p in pagine if p["cantiere"] != c], lambda p: [v for _, v in p["sonde"]])
        for c in corpus.CANTIERI
    }
    testi = {
        "integrale": {p["chiave"]: p["testo"] for p in campione},
        "coltellino": {
            p["chiave"]: coltellino.taglia(p["testo"], p["famiglia"], dizionari[p["cantiere"]]) for p in campione
        },
    }
    modello, sforzo = _options()
    esiti = {}
    for ramo, testo_di in testi.items():
        conta = p1.Contatore()
        richieste = []
        for fam in FAMIGLIE:
            gruppo = [p for p in campione if p["famiglia"] == fam]
            richieste += [(fam, lotto) for lotto in p1.lotti(gruppo, p1.PAGINE_PER_LOTTO)]

        def leggi(richiesta, testo_di=testo_di, conta=conta, ramo=ramo):
            fam, lotto = richiesta
            contenuto = [
                {
                    "type": "input_text",
                    "text": json.dumps(
                        {
                            "pid": p["chiave"],
                            "file": p["documento"],
                            "pagina": p["pagina"],
                            "testo_ocr": testo_di[p["chiave"]],
                        },
                        ensure_ascii=False,
                    ),
                }
                for p in lotto
            ]
            return p1.chiama(ramo, prova2.istruzioni_per(fam), contenuto, modello, sforzo, conta)

        inizio = time.perf_counter()
        compatte = {}
        with ThreadPoolExecutor(p1.LOTTI_IN_PARALLELO) as pool:
            for parziale in pool.map(leggi, richieste):
                compatte.update(parziale)
        secondi = time.perf_counter() - inizio
        schede = {k: prova2.espandi(c) for k, c in compatte.items() if isinstance(c, dict)}
        trovate = totali = 0
        for p in campione:
            oss = corpus.osservabili(p)
            valori = [corpus.compatto(v) for v in valori_scheda(schede[p["chiave"]])] if p["chiave"] in schede else []
            totali += len(oss)
            trovate += sum(
                1
                for _, v in oss
                if any(corpus.compatto(v) in x or x in corpus.compatto(v) for x in valori if len(x) >= 3)
            )
        esiti[ramo] = {
            "secondi": round(secondi, 1),
            "token": conta.fasi[ramo],
            "schede": len(schede),
            "sonde_ritrovate": f"{trovate}/{totali}",
            "caratteri": sum(len(t) for t in testo_di.values()),
        }
        esiti[ramo]["_schede"] = schede
        print(ramo, json.dumps({k: v for k, v in esiti[ramo].items() if k != "_schede"}, ensure_ascii=False))

    # accordo campo per campo tra i due rami
    uguali = diversi = solo_integrale = solo_ridotto = 0
    diff = []
    a, b = esiti["integrale"]["_schede"], esiti["coltellino"]["_schede"]
    for k in a.keys() & b.keys():
        for campo, x, y in p1._valori(a[k], b[k]):
            if piatto(x) == piatto(y):
                uguali += bool(x)
            elif not y:
                solo_integrale += 1
                diff.append((k[-8:], campo, x, y))
            elif not x:
                solo_ridotto += 1
                diff.append((k[-8:], campo, x, y))
            else:
                diversi += 1
                diff.append((k[-8:], campo, x, y))
    print(
        "accordo:",
        {"uguali": uguali, "diversi": diversi, "solo_integrale": solo_integrale, "solo_ridotto": solo_ridotto},
    )
    for d in diff[:40]:
        print("  ", d)


if __name__ == "__main__":
    main()
