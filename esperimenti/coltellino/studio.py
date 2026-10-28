"""Studio dei pattern: quali righe e colonne si ripetono (modulo) e quali portano i valori (sonde e codici).

Uso: .venv\\Scripts\\python esperimenti\\coltellino\\studio.py "<cartella SCL>" > studio.md
"""

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import corpus  # noqa: E402

CODICE = re.compile(r"\b[A-Z]{0,4}[-/ ]?\d{4,}[A-Z0-9/.-]*\b")


def forma(riga: str) -> str:
    """Forma della riga: minuscole, cifre -> #, senza spazi doppi. Righe con la stessa forma = stesso modulo."""
    t = re.sub(r"\d", "#", riga.lower())
    return re.sub(r"\s+", " ", re.sub(r"[|*_#]{2,}", "#", t)).strip()


def righe(testo: str) -> list[str]:
    out = []
    for r in testo.splitlines():
        r = r.strip()
        if not r or r.startswith("![") or re.fullmatch(r"\|?[\s|:-]*\|?", r):
            continue
        out.append(r)
    return out


def main():
    pagine = corpus.carica(Path(sys.argv[1]))
    per_fam = defaultdict(list)
    for p in pagine:
        per_fam[p["famiglia"]].append(p)

    print("# Studio dei pattern · 3 cantieri SCL\n")
    for fam, ps in sorted(per_fam.items(), key=lambda x: -len(x[1])):
        if len(ps) < 5:
            continue
        documenti = {p["documento"] for p in ps}
        emittenti = Counter(p["emittente"] for p in ps)
        car = sorted(len(p["testo"]) for p in ps)
        print(f"## {fam} · {len(ps)} pagine, {len(documenti)} documenti, {len(emittenti)} emittenti")
        print(f"caratteri: mediana {car[len(car) // 2]}, 90° {car[int(len(car) * 0.9)]}, max {car[-1]}\n")

        # righe di modulo: stessa forma in molti documenti di emittenti diversi
        docs_per_forma, emit_per_forma, sonde_per_forma, car_per_forma = (
            defaultdict(set),
            defaultdict(set),
            Counter(),
            Counter(),
        )
        for p in ps:
            oss = [corpus.compatto(v) for _, v in corpus.osservabili(p)]
            for r in righe(p["testo"]):
                f = forma(r)
                docs_per_forma[f].add(p["documento"])
                emit_per_forma[f].add(p["emittente"])
                car_per_forma[f] += len(r)
                c = corpus.compatto(r)
                sonde_per_forma[f] += sum(1 for v in oss if v and v in c)
        modulo = [f for f in docs_per_forma if len(docs_per_forma[f]) >= 3 and len(emit_per_forma[f]) >= 2]
        tot_car = sum(len(p["testo"]) for p in ps)
        car_modulo = sum(car_per_forma[f] for f in modulo)
        car_modulo_muto = sum(car_per_forma[f] for f in modulo if not sonde_per_forma[f])
        print(
            f"righe di modulo (>=3 documenti, >=2 emittenti): {len(modulo)} forme, "
            f"{car_modulo * 100 // max(tot_car, 1)}% dei caratteri; senza sonde: "
            f"{car_modulo_muto * 100 // max(tot_car, 1)}%\n"
        )
        print("| documenti | caratteri | sonde | forma |\n|---|---|---|---|")
        for f in sorted(modulo, key=lambda f: -car_per_forma[f])[:25]:
            print(f"| {len(docs_per_forma[f])} | {car_per_forma[f]} | {sonde_per_forma[f]} | `{f[:110]}` |")

        # parole che precedono i valori: le etichette utili
        etichette = Counter()
        for p in ps:
            for _, v in corpus.osservabili(p):
                for r in righe(p["testo"]):
                    i = r.lower().find(v.lower()[:12])
                    if i > 0:
                        prima = re.findall(r"[a-zà-ü.°]{2,}", r[:i].lower())[-3:]
                        etichette[" ".join(prima)] += 1
                        break
        print("\netichette prima dei valori:", ", ".join(f"«{e}» {n}" for e, n in etichette.most_common(20)))

        # quanto pesano tabelle, righe lunghe, intestazioni societarie
        tab = sum(len(r) for p in ps for r in righe(p["testo"]) if r.startswith("|"))
        lunghe = sum(len(r) for p in ps for r in righe(p["testo"]) if len(r) > 200 and not r.startswith("|"))
        print(
            f"\npeso: tabelle {tab * 100 // max(tot_car, 1)}%, righe di testo >200 car {lunghe * 100 // max(tot_car, 1)}%"
        )
        celle = Counter()
        for p in ps:
            for r in righe(p["testo"]):
                if r.startswith("|"):
                    for c in r.strip("|").split("|"):
                        c = c.strip()
                        if not c:
                            celle["vuota"] += 1
                        elif re.fullmatch(r"[<>≤≥]?\s*\d+[.,]\d+", c):
                            celle["decimale"] += 1
                        elif re.fullmatch(r"\d+", c):
                            celle["intero"] += 1
                        else:
                            celle["testo"] += 1
        print("celle di tabella:", dict(celle), "\n")


if __name__ == "__main__":
    main()
