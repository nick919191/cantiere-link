# certificato_31 · certificato di controllo EN 10204 3.1 (profilati, lamiere, tubi, bulloneria)

Riconosci: "3.1", "EN 10204", "inspection certificate", "certificato di collaudo/controllo", "Abnahmeprüfzeugnis",
tabella con colata (heat, cast, charge, colata, Schmelze). Codici EN 10168: A01 produttore, A03 numero, A06 cliente,
B01 prodotto, B02 grado, B07/B08 colata o lotto, Z02 data.
Non è questa famiglia: "certificato di controllo della produzione in fabbrica" (FPC di una DoP); patentini; DoP.
Una pagina "marcatura CE" con lo stesso numero di documento e "Pag. n/N" consecutivo è il seguito del certificato:
`certificato_31`, `continua_pagina_prima: true`, righe vuote, CE in `riferimenti`.

testata: produttore, marchio, stabilimento, numero, data, cliente, ordine, ddt_produttore, norma_prodotto, tipo_materiale, pagina_di
righe: profilo, dimensioni, qualita, colata, lotto, pezzi, peso, componente

- `produttore` = chi fabbrica e certifica (logo, A01, firma), ragione sociale; marchio di gruppo in `marchio`.
  Mai il cliente, mai il commerciante che ha timbrato la copia.
- `numero` = A03 / certificate n. / inspection document n. Mai CE, CPR, DoP, ordine, DDT.
- `tipo_materiale`: "profilati_lamiere_tubi", "bulloneria" o "materia_prima" (vergella/barra di un componente).
- `colata` = solo il codice, con prefissi e barre come scritti. Lotto, batch, matricola, plate id, ordine: mai in
  colata (`lotto` o niente). Limiti di norma, intervalli, dimensioni incollate: mai colate.
- Tabella con più righe per prodotto (profilo / grado / "No. 123456"): è UN prodotto, "No. 123456" è la colata.
- Modulo a caselle (COLATA - HEAT, PROFILO - PROFILE): una riga.
- Bulloneria: `profilo` come scritto (es. "ISO 4017 M12x50"), `qualita` = classe (8.8, 10.9, 8, 300 HV),
  `componente` = vite / dado / rondella; assieme vite+dado = due righe.
- `ddt_produttore`: DDT del produttore verso il commerciante (campo DDT stampato, Lieferschein, albarán).
- Timbri del commerciante con il numero del DDT: in `timbri` con `ddt_citato` (anche se stampati o sovrascritti).
- `pagina_di`: "1/2", "Pag. 3/4" se stampato; se manca qualche pagina del certificato, avviso.
