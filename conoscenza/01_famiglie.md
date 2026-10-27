# 01 · Famiglie di documento

Ogni **pagina** va in una famiglia (non ogni file: un PDF può contenere certificato, DoP e DDT insieme).
Famiglie usate dal progetto:

| Famiglia | Che cos'è | Alimenta |
|---|---|---|
| `packing_costruttore` | packing list o tabella di tracciabilità del costruttore | perimetro, parte d'opera, certificato dichiarato |
| `dop_costruttore` | DoP / etichetta CE EN 1090 del costruttore | COSTRUTTORE, CE/DoP COSTRUTTORE |
| `ddt` | documento di trasporto (commerciante -> costruttore, ma anche altri tipi) | COMMERCIANTE, DDT COMMERCIANTE |
| `certificato_31` | certificato di controllo EN 10204 3.1 (profilati, lamiere, tubi, bulloneria) | PRODUTTORE, COLATA, TIPO, CERT 3.1 |
| `dop_ce_prodotto` | DoP / CE dell'acciaieria o del prodotto | CE/DoP ACCIAIERIA, CE/DoP CENTRO |
| `lettera_accompagnamento` | lettera del distributore che lega DDT e certificato | ponte (stato) |
| `da_escludere` | pagine fuori perimetro (patentini, dichiarazioni, condizioni di vendita, bianche) | nulla |
| `illeggibile` | pagina che non si riesce a leggere | avviso "lettura incompleta" |

Peso sui fascicoli reali: certificati 3.1, DoP/CE di prodotto, DDT e packing = circa 85% delle pagine e quasi tutta
l'informazione per riga.

## Packing / tabella del costruttore
- **Forma A, packing**: titolo "PACKING LIST" / "tabella riassuntiva" / "elenco materiali", SHIPPER = costruttore,
  CONSIGNEE = cliente; due colonne MATERIALE | DDT DI CONSEGNA (commerciante + "DDT n DEL data").
- **Forma B, tabella di tracciabilità** ("ciclo di lavorazione", "rintracciabilità materiali"), multipagina: per pezzo
  posizione, profilo, qualità, **n. certificato**, EN 10204 3.1, **emesso da** (acciaieria), data, **fornito da**
  (commerciante), rif. ordine, **rif. DDT**, destino. Intestazioni solo sulla prima pagina; il numero DDT sta in
  colonna senza la parola DDT. È la catena intera dichiarata dal costruttore.
- Si riconosce la forma B dai blocchi ripetuti qualità -> "EN 10204 3.1" -> data; un certificato invece cita la norma
  una o due volte e porta analisi chimica e MPa.
- **Non è packing**: "PACKING LIST page N" di un fornitore con colli e pesi (fa parte del suo DDT); lista materiali da
  software di disegno (quantità, lunghezze, aree, pesi, senza DDT né colate: da escludere).
- **Può mancare** (visto in un fascicolo su tre): esito "packing del costruttore MANCANTE", perimetro preso dai DDT
  ricevuti dal costruttore, con avviso.

## DoP del costruttore (EN 1090)
- Titolo "Dichiarazione di prestazione", Reg. 305/2011, **EN 1090-1/-2**, classe EXCn, VVCP 2+, metodo 3a,
  certificato FPC `NNNN/CPR/NNNN`.
- Conta la norma del campo "norma armonizzata" (o sotto il marchio CE, o riga "metodo 3a / ZA.3"), non le norme
  citate per le qualità: una DoP EN 1090 che scrive "S275 secondo EN 10025-2" resta EN 1090.
- Etichetta CE su pagina separata: CPR, anno a due cifre, "N° Certificato FPC"; non porta numero e data della DoP.
- **DoP EN 1090 di un fornitore intermedio** (commerciante che taglia o fora): non è la DoP del costruttore; va nelle
  note della voce.
- Attenzione con la visione: in 13 descrizioni su 109 il modello ha "visto" EN 1090 leggendo il numero di un organismo
  notificato. Senza EN 1090 né EXC nel testo leggibile non è DoP del costruttore.

## DDT
Più segni insieme: "documento di trasporto", D.P.R. 472/96 (anche "472" con la data in mezzo), causale del trasporto,
vettore, firma conducente/destinatario, colli, peso; esteri "delivery note No.", "Lieferschein-Nr.".

Tre tipi, decisi **a livello di fascicolo**, non di pagina:

| Tipo | Come si riconosce | Nel perimetro |
|---|---|---|
| commerciante -> costruttore | destinatario = costruttore; destinazione "idem"; righe di certificato ("contributo certificazione", "(3.1)"); "peso teorico ante lavorazioni" | sì, è il DDT della voce |
| acciaieria -> commerciante | intestazione di un produttore, destinatario = commerciante | no, non fa ponte |
| costruttore -> cliente | emittente = costruttore; destinazione = cantiere; pezzi "NR. n", "fornitura e posa"; nessun certificato né colata | no per la catena; alimenta DDT COSTRUTTORE |

- Un DDT occupa più pagine: testata e righe possono stare su pagine diverse; l'ultima può avere solo peso, vettore,
  firme.
- Righe di **servizio** ("contributo certificazione", "concorso spese", "forature") non sono materiale; si conservano
  come servizio.
- "PROVINO" = pezzo di prova, non fornitura aggiuntiva.

## Certificato 3.1
- Segno forte ("3.1", "EN 10204", "inspection certificate", "certificato di collaudo/controllo") + tabella con colata
  (heat / cast / charge / colata).
- Codici EN 10168 come àncora: A01 produttore, A03 numero, A06 cliente, B01 prodotto, B02 grado, B07/B08 colata o
  lotto, Z02 data. Utili, non universali.
- Indizi senza falsi positivi su 330 pagine di altre famiglie: "inspection document n.", numero + "pag. n/N" sulla
  stessa pagina, "we hereby certify / si certifica che", firma dell'ispettore, "mechanical properties".
- **Falsi amici**: "certificato di controllo **della produzione in fabbrica**" è il FPC di una DoP; "heat treatment"
  non è colonna di colata; "EN 10204 3.1" compare anche nella tabella del costruttore; patentini di saldatura con
  "3.1" nel testo.
- **Allegato CE** del certificato: pagina "marcatura di conformità CE" con lo stesso numero del documento e contatore
  "Pag. n/N" consecutivo, senza titolo DoP. Appartiene al certificato (famiglia: decisione aperta).
- Disposizioni viste: tabella con più righe per prodotto (profilo / grado / "No. colata"), tabella semplice una riga
  per colata, modulo a caselle (un prodotto), bulloneria con coppie etichetta-valore.

### Bulloneria (viti, dadi, rondelle)
- Gruppo A (3.1, anche "Abnahmeprüfzeugnis", "in Anlehnung an EN 10204" = ispirato a, da annotare) + gruppo B (ISO 4014/
  4017 viti, 4032/4033/4034 dadi, 7089/7090/7091 e DIN 125 rondelle, EN 15048, EN 14399, ISO 898; "M12x50").
- Allegati che **non** generano voci: certificato della materia prima (vergella, coil) = prova di supporto della colata;
  dichiarazioni d'origine; lettera del distributore (ponte).

## DoP / CE del prodotto
- Titolo DoP / Declaration of performance / Leistungserklärung, 305/2011, struttura a punti dell'allegato III, norma
  armonizzata EN 10025-1, EN 10219-1, EN 10210-1, EN 15048-1, EN 14399-1; ON a 4 cifre; FPC `NNNN-CPR-...`.
- DoP su più pagine: le seguenti si legano alla prima solo con una prova (stesso numero DoP, oppure contatore
  consecutivo **e** stessa testata). Il contatore da solo non basta.
- Rinvio "DoP disponibile sul sito" = DoP citata, non presente.

## Lettera di accompagnamento
"Certificate 1/1", "Delivery note no. N from data", "Pos. item", "quantity certificate", "produced automatically,
requires no signature": lega le posizioni di un DDT ai certificati del blocco.

## Da escludere o segnalare
- Patentini saldatori (ISO 9606, WPS): esclusi dai test e senza dati personali nei report.
- Certificazioni aziendali come sola intestazione (ISO 9001...). Le sigle ISO in testata di un 3.1 **non** bastano.
- Dichiarazioni d'origine e sulle **sanzioni UE** (Reg. 833/2014, 269/2014): si scartano, anche se citano l'ordine;
  colate o valori di prova sulla stessa pagina la tengono dentro.
- Informativa imballaggi (anche con timbro "RICEVUTO": il timbro non fa il DDT), condizioni di vendita.
- **Pagine bianche** (retri di scansioni fronte/retro): l'OCR inventa formule, tabelle cinesi o "metatesto". Esito
  giusto: da escludere (pagina bianca), riconoscibile dall'immagine; non "illeggibile".
- Segno che nega l'esclusione: se c'è un n. DDT, una colata o un n. 3.1, la pagina non si esclude.
- Pagina ruotata di 90°: va raddrizzata o letta ruotata, non esclusa.
