# lettera_accompagnamento · lettera del distributore che accompagna i certificati

Riconosci: "Certificate 1/1", "Delivery note no. N from data", "Pos. item", "quantity certificate", "produced
automatically, requires no signature".

testata: emittente, ddt_citato, data_ddt, ordine
righe: posizione, articolo, quantita, certificato

- `ddt_citato` = numero dopo "Delivery note no."; una riga per posizione.
