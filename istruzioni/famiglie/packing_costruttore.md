# packing_costruttore · packing o tabella di tracciabilità del costruttore

Riconosci: "packing list", "tabella riassuntiva", "elenco materiali", "ciclo di lavorazione", "rintracciabilità";
SHIPPER = costruttore; righe di materiale con il DDT di consegna; oppure tabella con colonne n. certificato,
emesso da, fornito da, rif. ordine, rif. DDT, ripetute riga per riga ("EN 10204 3.1" su ogni riga).
Non è questa famiglia: "PACKING LIST page N" di un fornitore con colli e pesi (è `ddt`); distinta da software di
disegno senza DDT né certificati (`da_escludere`).

testata: costruttore, cliente, titolo, commessa, data
righe: materiale, qualita, quantita, posizione, certificato, emesso_da, data_certificato, fornito_da, rif_ordine, ddt, data_ddt, destino

- `titolo`: titolo della tabella o della sezione (es. "Telai", "Copertura"): diventa la parte d'opera.
- Una riga per riga della tabella, nell'ordine della pagina. `materiale` come scritto (es. "PL10*80", "HEA 140").
- Intestazioni solo sulla prima pagina: sulle pagine seguenti usa le colonne nello stesso ordine e scrivi
  `continua_pagina_prima: true`.
- `ddt`: solo il numero del DDT (colonna rif. DDT / DDT consegna); `rif_ordine` è un'altra cosa.
- `data_certificato`: la data della colonna data accanto al certificato (non è la data del DDT).
- Packing a due colonne: `fornito_da` = commerciante prima di "DDT", `ddt` e `data_ddt` dopo.
