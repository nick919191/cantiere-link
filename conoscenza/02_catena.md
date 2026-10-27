# 02 · Ruoli e catena a ritroso

## Ruoli (fino a quattro livelli)
| Livello | Ruolo | Emette |
|---|---|---|
| 1 | acciaieria / produttore (anche di bulloneria) | certificato 3.1, DoP e CE del prodotto, DDT verso il commerciante (fuori perimetro) |
| 2 | commerciante / centro di trasformazione (può tagliare, forare, firmare una DoP EN 1090 della sua lavorazione: **fornitore intermedio**, non costruttore) | DDT verso il costruttore, timbro o copia conforme sui certificati, lettere |
| 3 | costruttore metallico (carpenteria) | DoP EN 1090 dell'opera, packing o tabella, DDT verso il cliente |
| 4 | cliente / cantiere | nulla |

- **Il ruolo si decide dal fascicolo, non dalla pagina**: il costruttore è chi riceve i DDT dei commercianti
  (destinatario con più emittenti distinti, acciaierie escluse); chi gli emette DDT è un fornitore. Prova migliore:
  identificativo fiscale validato, se disponibile. Il motore attuale confronta la ragione sociale normalizzata
  completa e non effettua ancora la validazione della P.IVA. Non basta una prima parola comune.
- Margine stretto (pochi DDT, due destinatari quasi alla pari): ruolo DA CONFERMARE, mai scelto a caso.
- Su una pagina di certificato ci sono spesso 3-4 aziende (produttore, cliente, commerciante che timbra, costruttore
  a penna): campi separati.

## La catena
```
tabella / packing del costruttore  ->  DDT del commerciante  ->  certificato 3.1  ->  colata
          (dichiara)                    (prova la consegna)      (prova il materiale)   (solo il codice)
```
Chiavi: **numero DDT**, **numero certificato**, **colata**. Profilo e qualità servono a controllare, non a provare.

| Da | A | Chiave | Forza |
|---|---|---|---|
| packing | DDT | numero DDT (+ data + commerciante) | aggancio principale |
| tabella del costruttore | certificato | **numero del certificato dichiarato** | aggancio principale (vedi sotto) |
| DDT | certificato | ponte: timbro, lettera o campo DDT con il numero del DDT | prova |
| certificato | colata | riga con lo stesso profilo; unica colata, oppure scelta | prova se unica |
| certificato | DoP prodotto | numero DoP / FPC stampato sul 3.1 (P1) o riferimento in comune (P2) | prova del CE, non del lotto |
| profilo, qualità, dimensioni, stesso commerciante | qualsiasi | compatibilità | **mai** prova da sola |

- La packing è **l'indice del fascicolo**: ogni riga è una casella da riempire; casella vuota = MANCANTE con un
  nome preciso (quale certificato, quale DDT, di chi).
- **Livello di partenza**: quanti anelli il costruttore dichiara già (solo materiale + DDT; oppure la catena intera;
  oppure nulla). Decide da dove parte l'incrocio.
- Rapporto N:M: un materiale con più DDT, un DDT con più materiali. Mai assumere 1:1.
- Un documento non citato dal costruttore **non entra da solo** nella catena: va in "documenti non usati" con il
  motivo.

## La tabella del costruttore come fonte del certificato dichiarato
Colonne (sinonimi da riconoscere con un vocabolario, non con posizioni fisse):

| Campo | Intestazioni viste o sinonimi |
|---|---|
| profilo | profilo, materiale, descrizione; scritture di distinta `PL10*80` (piatto o lamiera sp. 10), `L60*6` (angolare) |
| qualità | qualità, GR, grado |
| n. certificato | n. certificato, colata o n. certificato |
| emesso da | emesso da, acciaieria -> **produttore dichiarato** |
| data | data -> è la data del **certificato**, non del DDT |
| fornito da | fornito da -> **commerciante** |
| rif. ordine | rif. ordine (da non confondere col DDT) |
| rif. DDT | rif. DDT, DDT consegna, D.D.T. n. -> **numero DDT**, spesso senza data |

Regole:
1. **Una voce = un certificato dichiarato + un DDT + un profilo/spessore.** Centinaia di righe della tabella (pezzi)
   diventano decine di voci.
2. Il certificato si cerca **per numero dichiarato**, poi si controlla il profilo. Il numero può comparire sul
   certificato con un prefisso o una forma diversa (es. inventato: dichiarato "4455", certificato "99-4455"): stesso
   numero se il dichiarato è la coda intera del letto; avviso, non errore.
3. Se il certificato dichiarato manca: **MANCANTE con il numero dichiarato e il fornitore**, da chiedere. Mai
   sostituirlo con un altro certificato dello stesso profilo.
4. Valori presi dalla tabella e non visti su un 3.1 si marcano "(dichiarato dal costruttore)".
5. La data della tabella è del certificato: la data del DDT resta vuota se non c'è il DDT.
6. Pezzi ricavati da un profilo più largo (es. inventato: pezzo da 75 da un piatto da 80): legame **dedotto**, da
   scrivere nella nota.
7. Parte d'opera: dal **titolo della tabella** o della sezione (es. "telai", "copertura"), non dal nome del file.

## Ponti certificato -> DDT
| Tipo | Come si presenta | Vale |
|---|---|---|
| A timbro del commerciante | "COPIA CONFORME ALL'ORIGINALE Rif. Ns. ddt n. N del data", "valido per cliente X, DDT N. N del data", sovrascritta digitale "<commerciante> - DDT nr N del data" | sulla **propria pagina** |
| B lettera del distributore | "Delivery note no. N from data" + posizioni | per il **documento** (blocco), con posizione in comune |
| C campo DDT del produttore | "DDT N", "documento di trasporto N del" stampato dal produttore | ponte solo se il DDT è del perimetro; di solito è acciaieria -> commerciante: **no** |
| D segni a mano | freccia, cerchio, evidenziatore su una colata | **scelgono la colata, non provano la consegna** |

- Il ponte vale solo se il numero citato è un DDT dell'opera (commerciante -> costruttore).
- "Lieferschein-Nr. LS-..." dentro il 3.1, albarán, "Documento di trasporto" stampato dal produttore: consegna del
  produttore al distributore, **non** ponte.
- Certificato timbrato per un **altro DDT** del fascicolo: non vale per questo DDT; si segnala.
- Timbro con numero o data non leggibili: nessun ponte, DA CONFERMARE, testo grezzo in nota.
- Peso sul timbro diverso dal DDT: avviso, stato invariato.
- Numero DDT scritto a penna: l'OCR lo perde o lo storpia spesso (3 casi su 6 visti); la visione lo legge, ma il
  valore resta un **segno a mano** con avviso (regola del motore).

## Copie
- Stesso certificato = stesso produttore + stesso numero (+ stesse colate). Le copie con timbri o segni diversi si
  **conservano tutte**: il timbro di una copia può essere il ponte. Mai deduplicare per numero o per testo.
- Stesso DDT in più file o scansioni: conservare le copie, fonte principale quella con la testata leggibile.
