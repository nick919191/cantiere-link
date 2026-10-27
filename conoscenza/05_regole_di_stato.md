# 05 · Regole di stato

Gli stati li decide **solo il motore deterministico** (`traccia/motore.py`): stesse prove, stesso risultato.
L’agente legge le pagine ma non decide gli stati. Ogni cambio delle regole richiede un aumento di `VERSIONE` e test.

## Voci
- Con la tabella o packing del costruttore che dichiara il certificato: **una voce = certificato dichiarato + DDT +
  profilo/spessore**. Piatti dello stesso spessore si separano per piatto di origine (il più stretto, tra quelli del
  DDT o del certificato, da cui il pezzo si ricava).
- Senza certificato dichiarato: una voce = DDT + profilo.
- Senza packing nel fascicolo: voci prese dai DDT ricevuti dal costruttore, con avviso.

## Stati
| Stato | Condizione |
|---|---|
| **PROVATO** | certificato (dichiarato, cercato per **numero**) e DDT presenti; **timbro o lettera con il numero del DDT** sul certificato; **una sola colata** per il profilo |
| **DEDOTTO** | certificato e DDT presenti e coerenti, una sola colata, **nessun timbro** |
| **DA CONFERMARE** | più colate; legame incerto; pagine del certificato mancanti; certificato timbrato per un **altro** DDT; DDT non nel fascicolo; numero letto diverso tra copie |
| **MANCANTE** | il certificato dichiarato non è nel fascicolo: nella colonna il **numero dichiarato**, nelle note il fornitore a cui chiederlo. **Mai** un altro certificato con lo stesso profilo |

Tetti:
- segno a mano sulla colata (freccia, evidenziatore) -> al massimo DA CONFERMARE;
- numero del DDT scritto a penna sul timbro -> al massimo DA CONFERMARE (`PENNA_VALE_COME_PROVA` nel motore);
- voci prese dai DDT perché manca la packing -> al massimo DEDOTTO;
- pezzo ricavato da un profilo più largo -> al massimo DEDOTTO.

Senza certificato dichiarato: candidati con lo stesso profilo e classe compatibile; ponte con il numero del DDT ->
come sopra; certificati timbrati per un altro DDT scartati; certificato intestato al commerciante -> DEDOTTO; un solo
candidato senza indizi -> DA CONFERMARE per esclusione; nessun candidato -> MANCANTE.

## Principi fissi
- Mai valori inventati; anomalie (manoscritti, timbri illeggibili, documenti mancanti) = avviso esplicito.
- Lettura incompleta ≠ MANCANTE.
- PROVATO indica un legame scritto sui documenti; non sostituisce la verifica di un tecnico.
