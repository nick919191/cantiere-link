# 06 · Che cosa deve contenere l'Excel


## Foglio "Tracciabilità" (per il cliente)
Una riga per **voce** (certificato dichiarato + DDT + profilo; senza dichiarazione: DDT + profilo).
Colonne, in quest'ordine:

| Colonna | Che cosa | Regole |
|---|---|---|
| PRODUTTORE | acciaieria / fabbricante del componente | "(dichiarato dal costruttore)" se non visto su un 3.1 |
| COLATA | **solo il codice** | vuota se più colate; alternative in NOTE |
| TIPO DI ACCIAIO | grado (profilati) o classe (bulloneria) | dal 3.1; dal DDT solo con nota |
| CE/DoP ACCIAIERIA | "DoP n; CE NNNN-CPR-..." | solo con prova P1/P2 |
| CERT 3.1 ACCIAIERIA | "n del data" | MANCANTE: numero dichiarato + "non nel fascicolo" |
| COMMERCIANTE / CENTRO TRASF. | emittente del DDT | |
| CE/DoP CENTRO | DoP firmata dal commerciante | oggi costante (punto aperto) |
| DDT COMMERCIANTE | "DDT n. N del data" | senza data: "DDT n. N - non nel fascicolo" o solo numero, mai "del " vuoto |
| COSTRUTTORE | fabbricante della DoP EN 1090 | uno per cantiere |
| CE/DoP COSTRUTTORE | "DoP n del data; CE ...; EN 1090-1, EXCn" | |
| DDT COSTRUTTORE | DDT costruttore -> cliente | "Non presente nel fascicolo" se manca |
| PARTE D'OPERA | **dal titolo della tabella** + voce come scritta | es. inventato: "Telai - PL10*80, 7 righe" |
| STATO | PROVATO / DEDOTTO / DA CONFERMARE / MANCANTE | dal motore |
| NOTE | **frasi pulite per il cliente** | niente codici, niente motivi tecnici lunghi |

## Fogli separati
| Foglio | Contenuto |
|---|---|
| **Prove** | per voce: stato e pagine usate (file + pagina) |
| **Provenienza** | per **ogni cella**: valore, documento, pagina, citazione, zona; **link** a una pagina con l'immagine del documento e il riquadro evidenziato dove sta il dato |
| **Motivi** | regole del motore applicate, certificati scartati e perché |
| **Richieste ai fornitori** | per fornitore: certificati e DDT da chiedere (numero dichiarato, profilo, voce), pagine mancanti di un certificato |
| **Documenti non usati** | documento, contenuto, perché non entra (altra commessa, non dichiarato, escluso, tipo nuovo) |
| **Documenti** | file, pagine, lette, non lette, famiglia |
| **Avvisi** | manoscritti, timbri illeggibili, conflitti di numero, lettura incompleta, avvisi fissi |
| **Metodo** | regole usate, versione del motore e delle istruzioni di lettura, che cosa non è verificato |

## Regole di scrittura
- Tutto come testo: nessun valore letto può diventare formula.
- Stesso fascicolo -> stesso Excel (ordine fisso delle voci, nessuna data di generazione dentro le celle dati).
- Le note per il cliente dicono **che cosa fare** ("chiedere a <fornitore> il certificato N"), i motivi stanno in
  Motivi e Prove.
