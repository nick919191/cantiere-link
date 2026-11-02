# 05 · Regole di stato

Gli stati li decide **solo il motore deterministico** (`traccia/motore.py`): stesse prove, stesso risultato.
L’agente legge le pagine ma non decide gli stati. Ogni cambio delle regole richiede un aumento di `VERSIONE` e test.

## Voci
- Con la tabella o packing del costruttore che dichiara il certificato: **una voce = certificato dichiarato + DDT +
  profilo/spessore**. Piatti dello stesso spessore si separano per piatto di origine (il più stretto, tra quelli del
  DDT o del certificato, da cui il pezzo si ricava).
- Senza certificato dichiarato: una voce = DDT + profilo. Se il DDT dichiara le colate placca per placca (es.
  "Placca: ... Colata: ..." sotto la riga), **una voce per colata**, con le placche in nota (decisione 3, 01/11/2026).
- Senza packing nel fascicolo: voci prese dai DDT ricevuti dal costruttore, con avviso e dicitura "(dai DDT)" in
  PARTE D'OPERA.

## Stati
| Stato | Condizione |
|---|---|
| **PROVATO** | certificato (dichiarato, cercato per **numero**) e DDT presenti; **timbro o lettera con il numero del DDT** sul certificato; **una sola colata** per il profilo (anche la colata dichiarata sul DDT o scelta dal segno a mano su una sola riga, con avviso) |
| **DEDOTTO** | certificato e DDT presenti e coerenti, una sola colata, **nessun timbro**, oppure timbro con il numero del DDT **scritto a penna** |
| **DA CONFERMARE** | più colate (senza colata dichiarata né segno su una sola); legame incerto; pagine del certificato mancanti; certificato timbrato per un **altro** DDT; DDT non nel fascicolo; numero letto diverso tra copie; documento letto a metà (testata senza righe); pagine non lette riconosciute come DDT, certificato, packing o lettera nello stesso file; certificato con timbro che cita un DDT assente dal fascicolo (voce "da un certificato", con la richiesta del DDT) |
| **MANCANTE** | il certificato dichiarato non è nel fascicolo: nella colonna il **numero dichiarato**, nelle note il fornitore a cui chiederlo. **Mai** un altro certificato con lo stesso profilo |

Tetti:
- numero del DDT scritto a penna sul timbro -> al massimo DEDOTTO, con avviso (`PENNA_VALE_COME_PROVA` nel motore).
  Dal motore 0.6.0 (31/10/2026, Nicola): prima era DA CONFERMARE, cioè sotto il certificato senza timbro. Confermato
  il 01/11/2026 (decisione 4);
- pezzo ricavato da un profilo più largo -> al massimo DEDOTTO.

Tetti tolti dalla 0.7.0 (01/11/2026, Nicola):
- segno a mano (freccia, evidenziatore, cerchio) su **una sola** delle colate del profilo: quella è la colata, stato
  come se fosse unica, avviso "colata scelta dal segno a mano: controllare l'originale" (decisione 1). Segni su più
  colate: nessuna scelta, DA CONFERMARE;
- packing o tabella del costruttore assente: la mancanza rende incerto il **perimetro** (quali materiali sono
  dell'opera), non la **prova** della singola catena: nessun tetto sullo stato, resta l'avviso globale e la dicitura
  "(dai DDT)" (decisione 2).

Senza certificato dichiarato, in quest'ordine:
1. **colata dichiarata** sulla riga del DDT ("Colata:", "Heat", "CERT.COL.") o dalla lista di rintracciabilità del
   commerciante (lettera con placca, colata, certificato per il DDT): il certificato che porta quella colata, una
   colata per riga del DDT, nessuna ambiguità; con il ponte -> PROVATO;
2. **ponte prima del profilo**: tra i certificati con timbro o lettera che citano il numero del DDT (anche come coda
   del numero, "51159" per "G02 / 51159") vale quello con righe dello stesso profilo o affini (stesso spessore per
   piatti e lamiere; stessa famiglia e misura per il resto), con avviso "profilo scritto diversamente"; più
   certificati con il ponte e righe compatibili -> DA CONFERMARE con le colate possibili;
3. **profilo**: candidati con lo stesso profilo e classe compatibile; certificati timbrati per un altro DDT scartati;
   certificato intestato al commerciante -> DEDOTTO; un solo candidato senza indizi -> DA CONFERMARE per esclusione;
   nessun candidato -> MANCANTE.

Il tetto "fascicolo non letto completamente" vale solo se tra le pagine non lette ce n'è una senza riconoscimento o
riconosciuta come DDT, certificato, packing o lettera **nello stesso file** dei documenti della voce; le non lette
riconosciute come da escludere o DoP non contano. Un documento letto a metà (scheda parziale: famiglia e testata,
righe da rileggere) rende DA CONFERMARE le voci che lo usano.

## Principi fissi
- Mai valori inventati; anomalie (manoscritti, timbri illeggibili, documenti mancanti) = avviso esplicito.
- Lettura incompleta ≠ MANCANTE.
- PROVATO indica un legame scritto sui documenti; non sostituisce la verifica di un tecnico.

Motore 0.6.1 (31/10/2026): stesse regole della 0.6.0; ogni cella ha in più il campo `perche` (perché il
motore ha messo lì quel dato, o perché manca), mostrato nella vista a tabella dell'app.

Motore 0.7.0 (01/11/2026, correzioni C1-C13 del report su Codogno): ragioni sociali confrontate per nucleo, sigla e
partita IVA; lamiere scritte come misure non sono tubi; colata dichiarata sul DDT e ponte prima del profilo; ruoli
terzista (conto lavorazione, reso) e DoP EN 1090 del fornitore intermedio in CE/DoP CENTRO; decisioni 1-5 sopra;
DoP di prodotto collegata anche per fabbricante e organismo notificato (P3); certificato con timbro che cita un DDT
assente -> voce DA CONFERMARE con richiesta del DDT.

Motore 0.7.4 (01/11/2026, verifica a tavolino del cantiere progresso): il numero di DDT scritto nella tabella del
costruttore vale anche come coda del numero stampato sul DDT ('12000/' per '1/12000', '8603/' per
'2021-S_DVE-0008603'); la colata dichiarata dal commerciante può portare davanti la sigla del produttore
('SICL2103435A' per 'CL21/03435A', 'OL142191' per '142191'): vale se la più corta ha almeno cinque cifre ed è la
coda dell'altra; 'IPE MM. 400', 'LAMINATO ELLE 60x40x6' (angolare), 'DADO MA16' / '16MA' / 'M- 12', barre filettate
('BARRA FILETTATA 8.8 D.12X1MT' = 'THREADED RODS M12X1.000' = M12x1000) e tubi scritti per colonne ('PROFILATI CAVI
... 5 100 100 12000' = TUBO 100x100x5) hanno una chiave; le righe di finitura e servizio della tabella del
costruttore ('FINITURA GREZZO', 'PRESTAZIONE SERVIZIO') non sono voci; quando la tabella non dà la misura del
profilo ('Lamiera in S275JR') il motivo lo dice, invece di "la riga del profilo non c'è". Restano da decidere:
materiale "da magazzino" del costruttore (fornitore = costruttore, DDT vuoto), prodotti con DoP/ETA senza 3.1
(ancoranti, tasselli), lista del fornitore intermedio come ponte tra il suo DDT e i certificati.

Motore 0.7.5 (02/11/2026, Codogno dopo la Verifica finale): sui DDT dei tubi la Ø è letta '0' o 'O' ('T NERO SALDATO
S355J2 0 219,1 X 12,5', 'T TONDO 0 60 X 5'): una cifra sola davanti a 'diametro X spessore', con una parola da tubo o la
'T' del commerciante, è la Ø; il tubo 219.1x12.5 si abbina al certificato 'TUBO 219,1x12,5x12000' (stesse prime misure)
e un tondo con lo spessore è un tubo tondo, non un tondo pieno.
