"""Proposta A: «la catena viva». Un solo stato per cantiere, risultati in cima e onesti, famiglie in ordine di catena,
voci raggruppate nel punto in cui la catena si rompe, con la richiesta da fare a ciascun fornitore.

Due cantieri: uno vero preso dall'app aperta (API locale, sola lettura) e uno inventato, più vario, per vedere tutti i
grappoli. Resta in risultati/ (fuori da git).

Uso: .venv\\Scripts\\python esperimenti\\demo_attesa\\genera_catena.py [<id lavoro>] [<porta>]
"""

import json
import random
import re
import sys
import urllib.request
from pathlib import Path

QUI = Path(__file__).parent
ANELLI = ["tabella", "ddt", "cert", "colata", "prove", "ok"]
NOMI_ANELLI = {"tabella": "Tabella costruttore", "ddt": "DDT", "cert": "Certificato 3.1", "colata": "Colata",
               "prove": "Timbro e DoP", "ok": "Catena completa"}
PROFILO = re.compile(r"^(HEA|HEB|HEM|IPE|IPN|UPN|UPE|U|L|ANGOLARE|PIATTO|TUBO|LAMIERA)\b", re.I)


def anello(v: dict) -> str:
    """Dove si ferma la voce: dal motivo scritto dal motore, non da una regex sul testo delle caselle."""
    if v["stato"] == "PROVATO":
        return "ok"
    m = " ".join(v.get("motivi", []) + v.get("richieste", [])).lower()
    if re.search(r"ddt.*(non|manca)|senza ddt", m):
        return "ddt"
    if re.search(r"timbr|\bdop\b|\bce\b|marcatura", m):  # prima dei certificati: «certificato senza timbro»
        return "prove"
    if re.search(r"colat", m):
        return "colata"
    if re.search(r"certificat", m):
        return "cert"
    return "ok" if v["stato"] == "DEDOTTO" else "prove"


def motivo(v: dict) -> str:
    return (v.get("motivi") or v.get("richieste") or ["da verificare"])[0]


def voce(v: dict) -> dict:
    nome = v["voce"].strip()
    return {
        "n": v.get("n"), "voce": nome, "stato": v["stato"], "anello": anello(v), "motivo": motivo(v),
        "ddt": v.get("ddt", ""), "fornitore": v.get("fornitore", ""), "richieste": v.get("richieste", []),
        "colata": v["colonne"].get("COLATA", {}).get("v", ""),
        "intestazione": not PROFILO.match(nome) and (nome.startswith(".") or "INTERVENTO" in nome.upper()),
    }


def dal_app(lavoro: str, porta: int) -> dict:
    base = f"http://127.0.0.1:{porta}/api/lavori/{lavoro}"
    leggi = lambda p: json.loads(urllib.request.urlopen(base + p, timeout=5).read())  # noqa: E731
    stato, ris = leggi("/stato"), leggi("/risultato")
    return {
        "nome": stato["nome"], "vero": True, "fase": stato["fase"], "pagine": stato["pagine_totali"],
        "famiglie": stato["per_famiglia"], "avviso_packing": ris.get("avviso_packing", False),
        "voci": [voce(v) for v in ris["voci"]],
    }


def inventato() -> dict:
    """Cantiere inventato con tutti i casi: nomi e numeri di fantasia."""
    random.seed(7)
    profili = ["HEA 200", "HEB 220", "IPE 240", "UPN 160", "L 80x8", "HEA 160", "IPE 300", "PIATTO 200x10"]
    casi = ([("PROVATO", [], [])] * 22 +
            [("DEDOTTO", ["colata dedotta dal peso e dal profilo"], [])] * 6 +
            [("DA CONFERMARE", ["più colate possibili sul certificato"], [])] * 5 +
            [("DA CONFERMARE", ["certificato senza timbro del commerciante"], ["timbro sul certificato 3.1"])] * 4 +
            [("MANCANTE", ["nessun certificato nel fascicolo per questo materiale"], ["certificato 3.1"])] * 7 +
            [("MANCANTE", ["DDT del commerciante non nel fascicolo"], ["DDT di consegna"])] * 3)
    fornitori = ["Commercio Acciai Demo srl", "Centro Taglio Esempio spa"]
    voci = []
    for i, (st, mot, ric) in enumerate(casi):
        voci.append(voce({
            "n": i + 1, "voce": random.choice(profili), "stato": st, "motivi": mot, "richieste": ric,
            "ddt": str(100 + i // 6), "fornitore": fornitori[i % 2],
            "colonne": {"COLATA": {"v": "" if st == "MANCANTE" else f"D{4100 + i}"}},
        }))
    return {"nome": "Cantiere di esempio (dati inventati)", "vero": False, "fase": "pronto", "pagine": 64,
            "famiglie": {"packing_costruttore": 2, "ddt": 9, "certificato_31": 21, "dop_ce_prodotto": 18,
                         "dop_costruttore": 3, "lettera_accompagnamento": 2, "da_escludere": 7, "illeggibile": 2},
            "avviso_packing": False, "voci": voci}


def main():
    lavoro = sys.argv[1] if len(sys.argv) > 1 else "20261028-125509-22e1b8ef"
    porta = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    cantieri = []
    try:
        cantieri.append(dal_app(lavoro, porta))
    except OSError as e:
        print("app non raggiungibile, solo il cantiere inventato:", e)
    cantieri.append(inventato())
    dati = {"cantieri": cantieri, "anelli": ANELLI, "nomi_anelli": NOMI_ANELLI}
    modello = (QUI / "modello_catena.html").read_text(encoding="utf-8")
    uscita = QUI / "risultati" / "catena.html"
    uscita.write_text(modello.replace("/*DATI*/{}", json.dumps(dati, ensure_ascii=False)), encoding="utf-8")
    for c in cantieri:
        conta = {}
        for v in c["voci"]:
            conta[v["anello"]] = conta.get(v["anello"], 0) + 1
        print(c["nome"], len(c["voci"]), "voci", conta)
    print(uscita)


if __name__ == "__main__":
    main()
