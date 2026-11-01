# lettera_accompagnamento · lettera del distributore che accompagna i certificati

Riconosci: "Certificate 1/1", "Delivery note no. N from data", "Pos. item", "quantity certificate", "produced
automatically, requires no signature"; oppure la lista di rintracciabilità del commerciante ("lista
rintracciabilità", "certificati relativi al DDT n."): tabella placca -> colata -> n. certificato per un DDT.

testata: emittente, ddt_citato, data_ddt, ordine
righe: posizione, articolo, quantita, placca, colata, certificato

- `ddt_citato` = numero dopo "Delivery note no." o il n. DDT a cui la lista si riferisce; una riga per posizione o
  per placca. `articolo` = profilo o descrizione del materiale della riga, se scritto; `placca` e `colata` come
  stampate sulla riga (vuote se la lettera non le riporta).
