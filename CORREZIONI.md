# Correzioni della review 2026-10 — branch `fix/review-2026-10`

Base: `main` (`0e2f2f0`, v0.3.0). Riferimenti agli id di `REPORT.md`. Ogni riga: file toccati, test aggiunto
(che prima della correzione falliva), esito. Partenza 86 test; arrivo 138 test, `ruff check` e `ruff format --check` puliti.

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
| U1 | Fine lavoro leggibile | — | — | **saltata (UX)** |

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
| U2, U4, U6 | Struttura risultati, "Da verificare", chat chiusa | — | — | **saltate (UX)** |

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
| U7, U8, U11, U12, U14 | Etichette, icone, accessibilità, font | — | — | **saltate (UX)** |

## Punti saltati o contestati

- **UX (U1, U2, U4, U6, U7, U8, U11, U12, U14)**: saltate su richiesta; si fanno in un passaggio successivo. Vincolo
  per quel passaggio: con la CSP attiva niente script o handler inline (usare `data-act` e i listener in `app.js`).
  U13 è stata fatta perché accoppiata a M6 e invisibile (solo cadenza del poll).
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
