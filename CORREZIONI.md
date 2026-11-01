# Correzioni della review 2026-10

> **Integrazione con la 0.5 (versione 0.5.1).** Le correzioni qui sotto sono nate sul branch `fix/review-2026-10`, su base
> 0.3.0, e sono state poi unite alla 0.5.0 nel branch `integrazione/0.5-correzioni`. La 0.5 aveva tolto chat e viste
> «catena»/«tracciabilità», quindi alcune righe valgono in forma diversa:
>
> - **Superate, perché la parte non esiste più**: U1, U4, U6, A1 sulla chat, B1 sul ruolo chat, B7, il test su `POST /chat`.
>   U4 (lista «Da verificare») non è stata riportata: la 0.5 mostra esito, stati, tabella e richieste ai fornitori.
> - **Rifatte sull'interfaccia 0.5**: M9/U3 (nessun handler inline, `web/cantiere.js`), S3, U2, U7, U8 (`Errore`), U10, U11,
>   U12, U13, U14. I nomi «Avvia lettura/Riprendi lettura» restano quelli della 0.5: analisi automatica, «Ferma», «Riprendi».
> - **A3 cambiata**: nella 0.5 i file si aggiungono anche durante il lavoro, quindi l'upload non occupa più il cantiere.
>   Il file in arrivo si scrive in un `.part`, invisibile alla preparazione, e si rinomina a ricezione finita.
> - **M6 sostituita**: resta la cache della 0.5 (controllo al massimo ogni secondo su nome, data e dimensione dei file).
> - **Nuova: pdfium un thread alla volta** (`PDFIUM` in `preparazione.py`, usato anche da `riordino.py`). Con la 0.5 preparazione
>   e riordino possono girare insieme, e due thread dentro pdfium fanno cadere l'app (`0xc0000374`).
> - **Nuova: test isolati** (`tests/conftest.py`). Un upload nei test poteva avviare l'analisi vera con l'account del portachiavi:
>   ora il portachiavi è in memoria per tutta la sessione e ogni test aspetta la fine dei suoi thread.
> - La tabella qui sotto descrive il lavoro originale sul branch: file e test citati possono avere nomi diversi nella 0.5.1.

Base: `main` (`0e2f2f0`, v0.3.0). Riferimenti agli id di `REPORT.md`. Ogni riga: file toccati, test aggiunto
(che prima della correzione falliva), esito. Partenza 86 test; arrivo 147 test (138 dopo le correzioni di codice, +9 con la UX), `ruff check` e
`ruff format --check` puliti. La parte UX è stata fatta per ultima, su richiesta, nei tre commit finali.

## Blocco 1

| Id | Correzione | File | Test | Esito |
|---|---|---|---|---|
| M9, U3 | Nessun handler inline: `data-act`/`data-change`/`data-input` + listener delegati; script inline spostato in `web/cantiere.js`; clic su PARTE D'OPERA apre la prova; `api()` legge il testo e prova il JSON dopo; upload mostra il `detail` del server | `web/index.html`, `web/cantiere.js`, `web/app.js` | `tests/test_frontend.py` (handler inline, azioni dichiarate, apostrofo, sintassi con `node`) | fatto, verificato nel browser |
| S6 | `Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'` (la demo statica `/demo/` mantiene `script-src 'unsafe-inline'`); handler generico `Exception` → JSON `{"detail"}` | `traccia/server.py` | `tests/test_server.py::test_csp_presente_e_errori_interni_in_json` | fatto |
| A1 | `lifespan`: `chat.jsonl` troncato o illeggibile salta solo quel cantiere | `traccia/server.py` | `tests/test_robustezza_file.py::test_chat_troncata_non_impedisce_l_avvio` | fatto |
| A6 | `elenco()` cattura `(OSError, ValueError)`; `info.json` e `tentativi.json` con `scrivi_json` (atomico); info/tentativi/riepilogo letti in modo tollerante | `traccia/server.py`, `traccia/lavoro.py`, `traccia/demo_cantiere.py` | `tests/test_robustezza_file.py` (JSON corrotto, scrittura atomica) | fatto |
| B8 | `consumi`, `configurazione.leggi`, `cestino.elenco` tollerano JSON corrotti o del tipo sbagliato | `traccia/consumi.py`, `traccia/configurazione.py`, `traccia/cestino.py` | `tests/test_robustezza_file.py` (preferenze `"testo"`, consumi `[]`, voce del cestino rotta) | fatto |
| M1 | `_stop_richiesto` alzato solo da `stop()`: errore di lotto → `error=True`, `stopped=False` | `traccia/agente.py` | `tests/test_agente_stati.py` | fatto |
| M2 | `traccia/registro.py`: `RotatingFileHandler` su `<cartella dati>/log/app.log`; `logging.exception` negli `except` muti; percorso in `/api/impostazioni` e Diagnostica | `traccia/registro.py`, `traccia/server.py`, `traccia/agente.py`, `traccia/aggiornamenti.py`, `web/app.js` | `tests/test_agente_stati.py` (traccia nel registro, percorso esposto) | fatto |
| B1, U9 | "agente"/"ChatGPT" in Metodo, Provenienza, pagine di prova, evento di lettura; ruolo chat scritto `assistente`, letto anche `claude`; via il `replace("Claude guarda ")` | `traccia/uscita.py`, `traccia/excel.py`, `traccia/provenienza.py`, `traccia/lavoro.py`, `traccia/chat.py`, `web/cantiere.js` (+ docstring) | `tests/test_testi_agente.py` | fatto; `cli.py` non toccato (vedi note) |
| U1 | A fase `pronto` i risultati («Scarica Excel e prove», conteggi) vengono subito sotto la barra; «documento in esame», contenitori e diario in un `<details>` ripiegato (riapribile); bottone secondario «Rileggi pagine mancanti» solo se restano pagine non lette; animazione delle pagine spenta a lavoro finito o a scheda nascosta, residui rimossi | `web/index.html`, `web/cantiere.js` | `tests/test_frontend.py::test_u1_…` | fatto, verificato nel browser |

## Blocco 2

| Id | Correzione | File | Test | Esito |
|---|---|---|---|---|
| A2 | `da_leggere` deduplicato per impronta; `salva_lettura` con temporaneo univoco e tolleranza a `FileExistsError`/`FileNotFoundError`/`PermissionError` | `traccia/agente.py`, `traccia/lavoro.py` | `tests/test_pagine_duplicate.py` (8 thread, due PDF identici → una chiamata) | fatto |
| A3 | `_PREPARING` segnato prima di `await _ricevi()` e rilasciato a preparazione finita (o subito se l'upload fallisce); bottoni non riabilitati durante l'upload | `traccia/server.py`, `web/app.js` | `tests/test_cantiere_prova_e_aggiunte.py::test_upload_aggiuntivo_occupa_il_cantiere_durante_la_ricezione` | fatto |
| A4 | ZIP corrotto/oltre i limiti → `.fallito` + file dichiarato non letto, gli altri proseguono, `.complete` scritto; nomi diversi solo per maiuscole → suffisso ` (n)` | `traccia/preparazione.py` | `tests/test_preparazione.py` (zip corrotto, maiuscole) | fatto |
| A5 | `ImageSequence` + `n_frames`: una pagina per fotogramma; `ritaglio()` cerca il fotogramma | `traccia/preparazione.py` | `tests/test_preparazione.py::test_tiff_multipagina_una_pagina_per_fotogramma` | fatto |
| M10 | File fallito alla pagina k>1: pagine parziali tolte, ritentato alla ri-preparazione, altrimenti "non letto" | `traccia/preparazione.py` | `tests/test_preparazione.py::test_file_preparato_a_meta_si_ritenta` | fatto |
| M8 | `data_iso` con `re.search`: ordinamento per data DDT funzionante | `traccia/normalizza.py` | `tests/test_normalizza.py::test_data_iso_anche_dentro_il_testo_della_colonna` | fatto |
| B4, U10 | Fase `errore` con `motivo` per zero pagine leggibili; pill rossa in home | `traccia/lavoro.py`, `traccia/server.py`, `web/cantiere.js` | `tests/test_server.py::test_zero_pagine_leggibili_da_fase_errore` | fatto |
| S4 | `requirements.lock` con hash (universale, marker per sistema) usato con `--require-hashes` da `avvia.py`, updater e CI; `pyproject.toml` con `pywebview`; lock nello zip di release | `requirements.lock`, `avvia.py`, `traccia/aggiornamenti.py`, `pyproject.toml`, `tools/package_release.py` | `tests/test_supply_chain.py` | fatto |
| S5 | `permissions: contents: read`, action a SHA, `pyinstaller==6.22.3`, `innosetup --version=6.7.1`, pytest/ruff fissi, job `pip-audit` | `.github/workflows/test.yml`, `.github/workflows/installers.yml` | `tests/test_supply_chain.py::test_workflow_pinnati_a_sha_con_permessi_minimi_e_versioni_fisse` | fatto |
| S1 | Piano firma release (minisign/cosign, Authenticode, notarizzazione): solo documento | `docs/FIRMA-RELEASE.md` | presenza verificata in `tests/test_supply_chain.py` | fatto (non implementato, come richiesto) |
| U2 | Tabella e catena «Collegamenti a ritroso» scorrono dentro il proprio contenitore (`.scrollx`, `tabindex=0`) con ombra ai bordi che segnala le colonne nascoste (`--scroll-shadow`, anche nel tema scuro) | `web/index.html`, `web/app.css` | `tests/test_frontend.py::test_u2_…` | fatto, verificato a 1000 px |
| U4 | Sezione «Da verificare (n)» in cima ai risultati: voci DA CONFERMARE/MANCANTI con stato, motivi, «Manca: DDT / certificato 3.1 / colata», «Vedi i collegamenti» (scorre alla riga) e «Chiedi in chat» con la domanda già scritta, mai inviata da sola | `web/index.html`, `web/cantiere.js`, `web/app.js` | `tests/test_frontend.py::test_u4_…` | fatto, verificato nel browser |
| U6 | Chat chiusa all'avvio a ogni larghezza; si riapre dal bottone in alto o da «Chiedi in chat» | `web/app.js` | `tests/test_frontend.py::test_u6_…` | fatto |

## Blocco 3

| Id | Correzione | File | Test | Esito |
|---|---|---|---|---|
| M3 | `_serializzato()`: lock solo per il portachiavi, `filelock.Timeout` → `AgentError`; rete fuori dal lock in `complete`, `access_token` (rinnovo serializzato da `_REFRESH`), `logout` | `traccia/chatgpt.py` | `tests/test_chatgpt.py::test_rete_fuori_dal_lock_e_timeout_del_lock_gestito` | fatto |
| M5 | Zip su file temporaneo + `FileResponse` con `BackgroundTask(os.remove)` | `traccia/server.py` | `tests/test_endpoint_risultato.py` | fatto |
| M6 | `functools.cache` su `versione_lettura` | `traccia/percorsi.py` | `tests/test_endpoint_risultato.py::test_versione_lettura_calcolata_una_volta` | fatto |
| U13 | Un solo ciclo di poll con backoff (2/5/15 s, `visibilitychange`) | `web/app.js`, `web/cantiere.js` | `tests/test_frontend.py::test_un_solo_timer_di_poll_con_backoff` | fatto (accoppiato a M6, non cambia l'aspetto) |
| M7 | `try/finally` su `.uscita-*`, massimo 10 versioni, `PermissionError` → `ExcelAperto` mostrato dall'agente | `traccia/uscita.py`, `traccia/agente.py` | `tests/test_uscita_versioni.py` | fatto |
| M4 | Puntatore a versione sparita → copia originale con avviso; `status()` non lancia più; rollback alla base | `avvia.py`, `traccia/aggiornamenti.py` | `tests/test_aggiornamenti.py::test_versione_installata_cancellata_a_mano_non_blocca_l_app` | fatto |
| S2 | Scala ridotta sopra 50 MP (anche per i ritagli), `MAX_PAGINE_FILE` | `traccia/preparazione.py` | `tests/test_limiti_e_istanza.py` | fatto |
| S3 | Token generato in `desktop.py`, consegnato in `#t=…`, `/api/sessione` spento; `sessione.json` (0600) per riaprire la finestra; `/api/salute` con impronta dell'istanza pretesa da `_stato_porta` | `traccia/desktop.py`, `traccia/server.py`, `web/app.js` | `tests/test_limiti_e_istanza.py` | fatto |
| B2 | Flag `ambiguo` al posto di `startswith("più ")` | `traccia/motore.py` | `tests/test_rifiniture.py::test_b2_…` | fatto |
| B3 | Miniature su temporaneo + `replace` | `traccia/server.py` | `tests/test_rifiniture.py::test_b3_…` | fatto |
| B5 | Risposta ricevuta dopo «Interrompi» salvata | `traccia/agente.py` | `tests/test_rifiniture.py::test_b5_…` | fatto |
| B6 | `HOST_CONSENTITI` nel codice, `testserver` ammesso dalla fixture autouse | `traccia/server.py`, `tests/conftest.py` | `tests/test_rifiniture.py::test_b6_…` | fatto |
| B7 | Messaggi `stato` esclusi dallo storico | `traccia/agente.py` | `tests/test_rifiniture.py::test_b7_…` (anche `agente.rispondi` con mock) | fatto |
| B9 | "Lette N di M, k da rileggere" conta solo le schede accettate | `traccia/agente.py` | `tests/test_rifiniture.py::test_b9_…` | fatto |
| S7 | `nome` con `max_length=200` | `traccia/server.py` | `tests/test_rifiniture.py::test_s7_…` | fatto |
| S10 | Whitelist su `tipo_proposto`, `tipo_materiale`, `servizio`; limiti a `trascrizione` (100k), `motivo` (1000), `avvisi` (20×300) | `traccia/controlli.py` | `tests/test_rifiniture.py::test_s10_…` | fatto; `componente` solo limitato in lunghezza (vedi note) |
| S11 | `segni[].zona` validata; ritagli solo per nome di file; `INDICE.xlsx` celle di testo | `traccia/controlli.py`, `traccia/uscita.py`, `traccia/riordino.py` | `tests/test_rifiniture.py::test_s11_…` | fatto |
| §2.5 | Test mancanti: `agente.rispondi` con mock, transizioni avvia/run/stop, `/scarica`, `/fascicolo-ordinato`, `/risultato`, `/miniature`, `/conversazioni`, `POST /chat`, lifespan, contenuto fogli Excel, concorrenza (pagine duplicate, upload+analizza), TIFF, ZIP corrotto, ordinamento, `avvia.prepare`, `_prepare_environment` | `tests/` | — | fatto |
| U7 | Nome del file, anteprima e scheda sempre della stessa pagina («In lettura: …», «Letta: …», «Lettura completata»); titolo «Ultima pagina letta» | `web/cantiere.js`, `web/index.html` | `tests/test_frontend.py::test_u7_…` | fatto |
| U8 | Pill «Agente fermo» / «Agente al lavoro» / «Errore» (via «Ferma» e «Da verificare»); bottone «Avvia lettura» → «Riprendi lettura» → «Rileggi pagine mancanti»; stessi nomi nei messaggi di `agente.py`, `uscita.py`, README e guida | `web/`, `traccia/agente.py`, `traccia/uscita.py`, `README.md`, `docs/guide.js` | `tests/test_frontend.py::test_u8_…` | fatto; valore PARTE D'OPERA non toccato (vedi note) |
| U11 | Icone SVG inline (`<symbol>`) al posto dei glifi Unicode in barra, chat, impostazioni; logo a catena al posto della «T» | `web/index.html`, `web/app.js`, `web/app.css` | `tests/test_frontend.py::test_u11_…` | fatto |
| U12 | Card cantieri, contenitori, caselle della catena, celle con prova e ritagli raggiungibili da tastiera (`role=button`/`<button>`, Invio/Spazio); anello `role=progressbar` con `aria-valuenow`; prova in `<dialog>` nativo (focus trap, Esc, backdrop) | `web/index.html`, `web/cantiere.js`, `web/app.js` | `tests/test_frontend.py::test_u12_…` | fatto, verificato (Invio su una casella apre la prova, Esc chiude) |
| U14 | Tolto `Inter` (mai caricato, e la CSP non permetterebbe Google Fonts): font di sistema dichiarato, anche in `docs/guide.css` | `web/index.html`, `web/app.css`, `docs/guide.css` | `tests/test_frontend.py::test_u14_…` | fatto |

## Punti saltati o contestati

- **UX**: fatta per ultima (tre commit, uno per blocco) sul design system esistente, senza librerie e rispettando la
  CSP (nessuno script o handler inline). Dalle demo è stata presa la checklist «Da verificare» (A) e lo scroll interno
  della tabella (B); non sono stati introdotti né lo stepper né l'ispettore laterale al posto della modale.
- **U8, valore PARTE D'OPERA** («TABELLA DI TRACCIABILITA' MATERIALI - HEB 200»): lo compone `motore.py` con
  titolo della distinta + etichetta della voce e finisce anche nell'Excel; cambiarlo è una scelta sul formato
  dell'uscita, non di interfaccia. Lasciato com'è; la lista «Da verificare» mostra etichetta e parte d'opera separate.
- **B1, flusso legacy**: `cli.py` filtra ancora lo storico chat con `ruolo == "claude"`; le risposte nuove si scrivono
  come `assistente` e non entrano nelle 3 righe di storico del flusso CLI. Non corretto perché `cli.py` è escluso dalle
  modifiche. Lettura e composizione del flusso legacy non cambiano.
- **S4, lockfile**: `pip-compile` risolve solo per la piattaforma corrente (su Windows mancherebbero `jeepney`,
  `pyobjc`, …) e con `--require-hashes` l'installazione su Mac/Linux fallirebbe. Usato `uv pip compile --universal`
  (uv era già installato): il lock ha i marker per i tre sistemi. Per rigenerarlo serve `uv` (documentato nel README).
- **M3, rinnovo del token**: il rinnovo non è più sotto il lock di file, quindi tra processi diversi non è
  serializzato. L'app impone una sola istanza (`app.lock`) e il flusso CLI non usa ChatGPT: in pratica non cambia.
- **S10, `componente`**: le istruzioni dicono "vite / dado / rondella" ma nei certificati reali compaiono altre
  parole; una whitelist stretta farebbe rileggere pagine (piano speso). Limitato solo in lunghezza.
- **S3**: avviando `uvicorn traccia.server:app` a mano `/api/sessione` resta attivo (nessun token consegnato dalla
  finestra): è la modalità di sviluppo. Con `avvia.py`/installer il token arriva nel frammento e l'endpoint dà 404.
- **Suite di test**: un test aggiunto all'inizio (CSP) lasciava una preparazione in sfondo che, con un altro test
  che rende PDF, faceva crashare `pypdfium2` (due thread che rendono insieme, `0xc0000374`). Corretto nel commit delle
  rifiniture; la suite ora è stabile in 4 esecuzioni consecutive.
- **Non toccati**: `istruzioni/`, `conoscenza/`, `cli.py`, `.claude/`, `CLAUDE.md`, `demo/` (che conserva gli script
  inline, coperti da una CSP dedicata). Il warning Pillow `getdata` in `preparazione._inchiostro` è preesistente.
- Nessun punto del report è risultato sbagliato leggendo il codice.
