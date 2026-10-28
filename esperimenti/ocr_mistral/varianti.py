"""Varianti per il tempo d'attesa, una dopo l'altra sulle stesse pagine; tabella finale di tempi, token e campi.

Uso: .venv\\Scripts\\python esperimenti\\ocr_mistral\\varianti.py <cartella del lavoro>
"""

import json
import subprocess
import sys
import time
from pathlib import Path

VARIANTI = {
    "base": [],
    "pipeline": ["--pipeline"],
    "lotti2": ["--pipeline", "--lotto", "2", "--parallelo", "12"],
    "lotti1": ["--pipeline", "--lotto", "1", "--parallelo", "21"],
    "luna": ["--modello", "gpt-6-luna"],
    "luna_lotti2": ["--modello", "gpt-6-luna", "--pipeline", "--lotto", "2", "--parallelo", "12"],
}


def main():
    cartella = Path(sys.argv[1])
    qui = Path(__file__).parent
    righe = []
    for nome, opzioni in VARIANTI.items():
        inizio = time.perf_counter()
        subprocess.run(
            [sys.executable, str(qui / "prova2.py"), str(cartella), "--coltellino", "--nome", f"_{nome}", *opzioni],
            check=True,
            capture_output=True,
        )
        parete = time.perf_counter() - inizio
        r = json.loads((qui / "risultati" / f"{cartella.name}_v3_{nome}" / "rapporto.json").read_text(encoding="utf-8"))
        tok = r["token"]
        ingresso = sum(f.get("ingresso", 0) for f in tok.values())
        uscita = sum(f.get("uscita", 0) for f in tok.values())
        c = r["confronto_campi"]
        righe.append(
            (
                nome,
                r["secondi"],
                round(parete, 1),
                ingresso,
                uscita,
                c["uguali"] + c["solo_forma"],
                sum(c.values()),
                r["accettate"],
                r["verificate"],
            )
        )
        print(righe[-1], flush=True)
    print("\n| variante | secondi modello | ingresso | uscita | campi ok | accettate | verificate |")
    print("|---|---|---|---|---|---|---|")
    for nome, sec, _, i, u, ok, tot, acc, ver in righe:
        modello = sum(v for k, v in sec.items() if k != "A_ocr")
        print(f"| {nome} | {modello:.1f} | {i} | {u} | {ok}/{tot} | {acc} | {ver} |")


if __name__ == "__main__":
    main()
