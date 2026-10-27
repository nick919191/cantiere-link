# 03 · Come si legge una pagina

## Forma unica della scheda
Ogni pagina utile diventa una scheda della sua famiglia, sempre con la stessa forma. Un documento più grande ha solo
più righe.

```
testata     chi emette, a chi, tipo, numero, data (+ campi della famiglia)
righe       una per materiale / colata / pezzo (profilo, dimensioni, qualità, colata, lotto, quantità, segno)
riferimenti altri documenti citati: DDT, certificati, ordini, DoP/FPC
timbri      un elemento per timbro o scritta aggiunta: chi, testo, DDT citato, data, a mano sì/no
avvisi      solo ciò che una persona deve controllare
```
Ogni valore porta **pagina, citazione** (le parole che lo provano) e, se possibile, **zona** della pagina.

## Regole di lettura (valgono per tutte le famiglie)
1. Trascrivere come è scritto; solo ciò che è sulla pagina, nessuna conoscenza esterna; mai completare cifre mancanti.
2. Immagine chiara e OCR diverso (S/5, O/0, B/8, I/1): valore visto + avviso "OCR diverso: ..."; immagine non chiara:
   valore + "da confermare".
3. **Testata separata dalle righe**: se le righe falliscono, la testata (produttore, numero, data) resta, con avviso
   "righe da rileggere". Scartare tutto il certificato perché manca la colata è stato l'errore principale delle regole
   (metà delle pagine 3.1 perse).
4. Colata cercata in colonna **e** in riquadro con etichetta (Colata / Heat / Cast / Charge / Schmelze).
5. Segni a mano (freccia, croce, evidenziatore, spunta): si registrano come segno sulla riga; **chi legge non decide**
   quale riga vale.
6. Numeri CE/CPR e DoP mai nel numero del certificato.
7. Data del certificato da Date / Data / Z02 / riga della firma ("Luogo, gg.mm.aaaa"); mai l'anno di una norma, mai la
   data di un timbro, di un ordine o del DDT.
8. Campi vuoti: stringa vuota, mai un valore "probabile".

## Controlli Python dopo la lettura (deterministici)
- La **citazione deve stare nel testo della pagina** e il valore nella citazione; altrimenti il valore si scarta.
- Numero dichiarato: un valore di certificato vale per una voce solo se viene da una pagina che porta il numero
  dichiarato dal costruttore.
- Una colata sola per voce; con più colate la voce non prende colata e le alternative vanno in nota.
- Colata valida: almeno tre cifre; non uguale a qualità, lotto, ordine, codice fornitore; non intervallo di misura.
- Profilo e qualità normalizzati con le funzioni del motore (`normalizza.profilo`, `classe`).

## Casi difficili visti
| Caso | Che cosa fare |
|---|---|
| Pagina ruotata di 90° | raddrizzare o leggere ruotata; le regole semplici di raddrizzamento sbagliano 2-3 pagine su 7 |
| Pagina bianca (retro) | escludere dall'immagine (inchiostro quasi nullo), non mandarla alla lettura |
| Testo nativo con solo una sovrascritta (resto immagine) | serve la lettura dell'immagine |
| Tabelle che l'OCR non rende (riquadro numero/data vuoto) | numero DA CONFERMARE; la visione lo legge |
| Certificato su più pagine ("1/2", "2/2") | stesso numero = stesso certificato; la pagina 2/2 con solo CE appartiene alla 1/2 |
| Nel fascicolo solo una pagina di un certificato di più pagine (es. "3/4") | righe mancanti = lettura incompleta; chiedere le pagine mancanti |
| Copie dello stesso certificato lette diverse (0/8, 1/L) | conservare entrambe; più candidati = DA CONFERMARE |
| Numero sbiadito | avviso, mai indovinare |
| Date impossibili su timbri a penna | avviso "manoscritto" |

## Misure di riferimento
- Certificati 3.1 difficili (7 pagine, 86 campi): regole 33%, OCR con annotazione 73%, ricostruzione dagli archivi
  77%, modello con visione e istruzioni bozza 2: **90%**. Base per scegliere la lettura con
  visione.
- DDT: scheda dal testo OCR + regole 99% su 7 pagine, 100% su 4 di verifica.
- DoP di prodotto: 48% al primo passaggio su pagine nuove: la regola generale non
  è ancora solida.
