# dop_ce_prodotto · DoP / CE dell'acciaieria o del prodotto

Riconosci: "Dichiarazione di prestazione / Declaration of performance / Leistungserklärung", 305/2011, punti
dell'allegato III, norma armonizzata EN 10025-1, EN 10219-1, EN 10210-1, EN 15048-1, EN 14399-1; organismo
notificato a 4 cifre; FPC "NNNN-CPR-...". Etichetta CE di prodotto. Non è questa famiglia: DoP EN 1090
(`dop_costruttore`); certificato con tabella di colate (`certificato_31`).

testata: fabbricante, numero_dop, data, norma, organismo, fpc, qualita, ddt_citato
righe: (nessuna)

- `qualita`: qualità coperte come scritte (es. "S275JR, S355J2").
- `ddt_citato`: numero DDT stampato in testa alla pagina, se c'è (spesso del produttore verso il commerciante).
- Pagine seguenti della stessa DoP: `continua_pagina_prima: true` solo se c'è lo stesso numero DoP, oppure contatore
  e testata uguali.
