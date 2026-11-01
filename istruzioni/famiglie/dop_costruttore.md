# dop_costruttore · DoP / etichetta CE del costruttore (EN 1090)

Riconosci: "Dichiarazione di prestazione" con norma armonizzata **EN 1090-1/-2**, classe EXCn, VVCP 2+, metodo 3a;
oppure etichetta CE con "EN 1090" e "N° certificato FPC". Conta la norma del campo "norma armonizzata", non le norme
citate per le qualità. Se EN 1090 non è scritta sulla pagina non è questa famiglia.

testata: fabbricante, numero_dop, data, cpr, organismo, norma, classe_esecuzione, commessa, opera, piva, ddt_citato
righe: (nessuna)

- `fabbricante` = punto "identificazione del fabbricante" (non il progettista, non l'organismo notificato).
- `cpr` = numero del certificato FPC "NNNN/CPR/NNNN" o "NNNN-CPR-NNNN".
- Etichetta CE senza titolo DoP: compila ciò che c'è, avviso "etichetta CE, numero e data DoP non presenti".
- `piva` = partita IVA del fabbricante, se stampata sulla pagina.
- `ddt_citato` = numero del DDT di consegna citato dalla DoP ("DDT di consegna n."), se c'è. Una DoP EN 1090 di
  un commerciante o centro di trasformazione (taglio, foratura) è di un fornitore intermedio, non del
  costruttore: va letta lo stesso in questa famiglia, con il DDT citato.
