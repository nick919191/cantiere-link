# 04 · Errori tipici e regola che li evita

Esempi con valori inventati.

| # | Errore | Regola |
|---|---|---|
| 1 | **Norma letta come colata** ("EN 10025" -> colata 10025; "S355J2+N Min/Max" come riga) | la colata sta sotto un'intestazione o etichetta di colata; numeri di norma, limiti, intervalli (`54.1-58.2`) non sono colate |
| 2 | **Numero CPR/FPC al posto del 3.1** (`1234-CPR-0056` messo in CERT 3.1) | CE/CPR/DoP solo nel campo CE/DoP; il numero del 3.1 è A03 / "certificate n." |
| 3 | **O/0 e I/1, S/5, B/8** (`S275JO` = S275J0; `IPEL40` = IPE 140; `E275JR` = S275JR) | correggere solo dove la forma è nota e la serie esiste, con avviso; immagine chiara prevale sull'OCR |
| 4 | **Prefissi del numero** (dichiarato "4455", stampato "99-4455"; DDT "00731" = "731"; "2026/45678" = "45678"; "7.300/00" = "7300") | confronto su numero normalizzato; il suffisso di serie ("4321/1") resta; differenza = avviso |
| 5 | **Date dentro le norme** ("EN 10025-2:2019" letto come data; anno della norma come data del certificato) | data solo da etichetta di data, Z02 o riga firma, mai dalla norma |
| 6 | **Più colate per profilo** sul certificato | nessuna colata scelta; colonna vuota, alternative nelle note; DA CONFERMARE; segno a mano = avviso |
| 7 | **Pezzi ricavati da un profilo più largo** (pezzo 75 da piatto 80; 155 da 160) | legame dedotto, scritto in nota; non è lo stesso profilo per le regole di confronto |
| 8 | **Documenti di un'altra commessa** (DDT con commessa diversa da quella della DoP/tabella) | non entra nella catena; va in "Documenti non usati" con il motivo; la commessa è chiave debole, in nota |
| 9 | Lotto / batch / matricola presi come colata | lotto in campo lotto, mai in colata, anche se la colata manca |
| 10 | Produttore = cliente o commerciante che ha timbrato la copia | produttore da logo, A01, firma; marchio di gruppo ≠ ragione sociale |
| 11 | Numero DDT del commerciante preso dall'ordine, dal codice cliente, dal "Documento DT" dell'acciaieria | serve il riquadro NUMERO del DDT dell'opera |
| 12 | DDT acciaieria -> commerciante usato come ponte | fuori perimetro, non fa ponte |
| 13 | Rondella letta come tubo (`20 x 10,5 x 2`) | dimensioni d1 x d2 x h di rondella se c'è la norma di rondella |
| 14 | "PL 10" della distinta: piatto o lamiera? | lo decide il profilo del certificato dichiarato, se letto; altrimenti DA CONFERMARE |
| 15 | Certificato scartato tutto perché mancano le righe | testata tenuta, righe da rileggere |
| 16 | Data del timbro "copia conforme" presa come data del certificato | sono date diverse |
| 17 | Qualità del DDT ≠ qualità del certificato (J0/JR) | non uniformare: avviso, stessa classe |
| 18 | Numero DDT diverso tra nome del file, packing e pagina | tre fonti, nessuna corregge le altre; vale quello stampato sul DDT, conflitto in nota |
| 19 | Pagina bianca letta come contenuto (formule, tabelle cinesi inventate) | scarto dall'immagine prima della lettura |
| 20 | Visione che "vede" una norma non scritta (EN 1090 dal numero di un organismo) | la famiglia si conferma sul testo leggibile |
| 21 | Certificato di un altro cliente dello stesso produttore | intestatario diverso: non usarlo senza ponte; segnalare |
| 22 | Lettura incompleta scambiata per documento mancante | "non trovato tra le pagine lette" ≠ MANCANTE; pagine non lette sempre dichiarate |
