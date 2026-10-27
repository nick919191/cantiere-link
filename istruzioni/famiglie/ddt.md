# ddt · documento di trasporto

Riconosci: "documento di trasporto", D.P.R. 472/96, causale del trasporto, vettore, firme, colli, peso;
"delivery note No.", "Lieferschein-Nr.". Non è DDT: fattura; lettera "Certificate 1/1" che cita un "Delivery note
no." (`lettera_accompagnamento`); certificato con un campo DDT (`certificato_31`).

testata: emittente, destinatario, destinazione, numero, data, ordine, commessa, pagina_di, tipo_proposto
righe: descrizione, profilo, qualita, quantita, unita, posizione, servizio

- `numero` = il riquadro NUMERO / N documento / delivery note No., come stampato. Non ordine, non codice cliente.
- `tipo_proposto`: `commerciante_costruttore` (venditore -> carpenteria), `acciaieria_commerciante` (intestazione di
  un'acciaieria, destinatario un commerciante), `costruttore_cliente` (pezzi "NR. n", "fornitura e posa", consegna in
  cantiere), `non_determinabile`. È una proposta: il ruolo lo decide il fascicolo.
- Una riga per riga della tabella. `descrizione` come scritta; `profilo` = profilo e misura come scritti nella
  descrizione (es. "HEB 180", "PIATTO 80x10", "LAM. SP=8"); `qualita` solo se scritta sulla riga.
- `servizio`: "si" per righe che non sono materiale (contributo certificazione, certificato materiale, trasporto,
  forature), altrimenti "no". "PROVINO" = materiale con avviso "provino".
- `pagina_di`: "1/2", "PAG. 002"... se stampato.
