---
description: Avvia la piattaforma nel browser ed esegue il flusso di lettura dei documenti caricati
---
Esegui questo flusso, sempre uguale, senza saltare passi. Rispondi all'utente in italiano, con frasi brevi.

1. Avvia la piattaforma: `python -m traccia avvia`. Apre il browser su localhost. Di' all'utente:
   "La piattaforma è aperta nel browser: carica i documenti del cantiere."
2. Aspetta il lavoro: `python -m traccia attendi` (timeout 600000 ms). Il comando torna con un JSON:
   - `{"niente": true}`: rilancia `python -m traccia attendi`.
   - `{"lavoro": ID, "domanda": QID, ...}`: una domanda nella chat. Vai al passo 5.
   - `{"lavoro": ID, "lotti": [[...], ...]}`: ci sono pagine da leggere. Vai al passo 3.
   - `{"lavoro": ID, "componi": true}`: tutte le pagine sono lette. Vai al passo 4.
3. Per ogni lotto avvia il sottoagente `lettore` con questo testo, sostituendo i valori:
   "Lavoro ID. Pagine: p0001 p0002 ... Segui .claude/agents/lettore.md."
   Avvia fino a 3 lettori alla volta; aspetta che finiscano, poi torna al passo 2 (le pagine non riuscite tornano
   nei lotti successivi; dopo 4 tentativi il comando le dichiara non lette e non le ripropone).
4. Componi l'uscita: `python -m traccia componi ID`. Python costruisce prove, stati, Excel, pagine di prova e
   fascicolo ordinato. Di' all'utente: "L'Excel è pronto nella piattaforma." Poi torna al passo 2.
5. Avvia il sottoagente `assistente` con: "Lavoro ID. Domanda QID. Segui .claude/agents/assistente.md."
   Quando finisce, torna al passo 2.

Regole:
- Non leggere tu le pagine e non rispondere tu alle domande: lo fanno solo `lettore` e `assistente`.
- Non cambiare l'ordine dei passi, non saltare `componi`, non scrivere file a mano.
- Se un comando dà errore, rilancialo una volta; se l'errore resta,
  `python -m traccia nota ID - "<che cosa è successo>"` e continua con il passo 2.
- Se l'utente chiude e riapre, `/avvia` riprende da dove era: le pagine già lette non si rileggono.
