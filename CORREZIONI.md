# Correzioni tracciabilità 2026-11 (motore 0.7.0)

Branch `fix/tracciabilita-codogno` da `integrazione/0.5-correzioni` (0.5.1, motore 0.6.1). Base: `REPORT_miglioramenti_cantierelink.md`
(13 correzioni C1-C13 dal cantiere Codogno, 138 pagine) e le 5 decisioni prese da Nicola il 01/11/2026. Un commit per
punto; `pytest -q` (200 test, da 165) e `ruff check traccia tests` verdi a ogni commit. Misura a costo zero: le letture
di Codogno già in archivio ricomposte con il codice nuovo (senza rileggere nulla).

| Punto | Correzioni | File toccati | Commit | Test |
|---|---|---|---|---|
| 1 | C1 ragioni sociali per nucleo, sigla e P.IVA; C8 copie dei DDT unite, seconda pagina con numero letto diverso | `traccia/normalizza.py` (`nuclei`, `stessa_azienda`, `piva`), `traccia/prove.py` (`Aziende`, `_stesso_ddt`, `_costruttore`), `traccia/motore.py` (`_stessa`), `istruzioni/famiglie/ddt.md` (`piva_emittente`, `piva_destinatario`), `istruzioni/famiglie/dop_costruttore.md` (`piva`) | `c4fcb28` | `test_normalizza.py::test_nucleo_…`, `::test_partita_iva`; `test_prove.py` (4 test: indirizzo, P.IVA, copie, seconda pagina) |
| 2 | C2 lamiere scritte come misure | `traccia/normalizza.py` (`profilo`, `_forma_lamiera`) | `74a082a` | `test_normalizza.py::test_lamiere_scritte_come_misure_non_sono_tubi` (stringhe reali + inventate) |
| 3 | C3 validatore tollerante, `altro`, scheda parziale, terzo tentativo con pagina intera; C4 tetto "non letto" mirato | `traccia/controlli.py` (`valida(correggi=…)`), `traccia/famiglie.py`, `traccia/veloce.py` (`_lotto`, `parziale`), `traccia/lavoro.py` (letture `.parziale.json`, `completa`), `traccia/prove.py` (`non_lette_dettagli`, `parziali`), `traccia/mappa.py` (`famiglia_in_archivio`), `traccia/motore.py` (`non_lette_vicine`), `traccia/uscita.py`, `istruzioni/lettura.md` (`altro`) | `58b2b46` | `test_controlli.py` (nuovo, 4 test); `test_veloce.py` (tipo sconosciuto, citazione scartata, terzo tentativo, parziale); `test_motore.py` (tetto mirato, lettura a metà) |
| 4 | C5 colata sul DDT (decisione 3: una voce per colata); C6 ponte prima del profilo; C13 lista del commerciante (decisione 5) | `traccia/normalizza.py` (`colata_normale`, `stessa_colata`, `colate_dichiarate`, `cita_ddt`), `traccia/prove.py` (righe DDT `colate`/`placche`/`certificato`, righe della lettera), `traccia/motore.py` (`VOCE_PER_COLATA`, `_cerca_per_colata`, `_cerca_per_ponte`, `_affine`, `colate_dichiarate`, `ponti`), `istruzioni/famiglie/ddt.md`, `istruzioni/famiglie/lettera_accompagnamento.md` | `9636457` | `test_normalizza.py::test_colata_…`; `test_prove.py` (righe con colate, lettera); `test_motore.py` (colata sul DDT, una voce per colata, ponte prima del profilo, lista del commerciante) |
| 5 | C9 ruoli terzista (conto lavorazione, reso); C11 DoP EN 1090 del fornitore intermedio | `traccia/prove.py` (`_tipi`, `dop_fornitore_intermedio`), `traccia/motore.py` (`_cantiere`, `_dop_intermedia`, CE/DoP CENTRO), `traccia/controlli.py`, `traccia/uscita.py`, `istruzioni/famiglie/ddt.md` (`causale`, tipi), `istruzioni/famiglie/dop_costruttore.md` (`ddt_citato`) | `af91cf9` | `test_prove.py` (terzista e reso, reso dal riferimento, DoP intermedia) |
| 6 | C7 segno a mano (decisione 1) e dubbio «segni» con pagina intera, `segno_a_mano` nel riconoscimento; decisione 2 (nessun tetto dai DDT); C10 DoP P3 fabbricante + organismo; C12 certificato con DDT citato assente | `traccia/motore.py` (`_scegli_segnata`, `_dop_del_certificato`, `_voci_dai_certificati`), `traccia/veloce.py` (`piu_colate_per_profilo`, correzione `segni`), `traccia/mappa.py`, `traccia/uscita.py`, `istruzioni/famiglie/certificato_31.md` | `a3aac0d` | `test_motore.py` (segno, packing assente, P3, certificato con DDT assente); `test_veloce.py::test_piu_colate_…`; `test_mappa.py::test_riconoscimento_…` |
| 7 | Regressione sul fascicolo reale anonimizzato | `tests/dati/codogno.json`, `tests/test_regressioni.py` | `31adec0` | `test_codogno_ruoli_e_perimetro_dei_ddt`, `test_codogno_voci_con_certificato_e_colata`, `test_codogno_tetto_non_letto_…` |
| 8 | Conoscenza, istruzioni, motore 0.7.0, questo file | `conoscenza/01_famiglie.md`, `02_catena.md`, `05_regole_di_stato.md`, `traccia/motore.py` (docstring, `VERSIONE`), `traccia/uscita.py` (Metodo), `CORREZIONI.md` | `118c60d` | suite intera |
| 9 | Dalla 1ª rilettura vera: campi a elenco (`a; b`) scartati dal controllo, profilo senza misura, righe di sole colate, lista letta come DDT o come certificato, croce come segno, emittente = destinatario | `traccia/controlli.py` (`CAMPI_ELENCO`), `traccia/prove.py` (`_chiave_riga`, `_liste_lette_come_ddt`, `_liste_lette_come_certificati`), `traccia/motore.py` (`SEGNI_CHE_SCELGONO`), `traccia/normalizza.py` (`contiene_numero`, `progressivo`) | `e644aa9` | `test_controlli`, `test_normalizza`, `test_prove`, `test_motore` |
| 10 | Dalla 2ª rilettura: elenco anche nella citazione, colate dalle liste del commerciante una voce per colata (il preciso vince sul generico), misure con spazi senza parola, evento di diagnostica per la scheda mancante | `traccia/controlli.py`, `traccia/motore.py` (`_colate_da_lettere`), `traccia/normalizza.py`, `traccia/veloce.py` | `dd57044` | idem |
| 11 | Dalla 3ª rilettura: schede recuperate da JSON non valido (causa delle "schede mancanti"), DDT letto male (emittente = destinatario) non vale come presente per C12 | `traccia/veloce.py` (`schede_dalla_risposta`), `traccia/prove.py` (`incoerente`), `traccia/motore.py` | `9e2552d` | `test_veloce`, `test_motore` |

## Codogno riletto con la 0.7.0 (01/11/2026, tre passate, 101 chiamate ChatGPT in più)

| | App 0.6.1 | 0.7.0 dopo la rilettura |
|---|---|---|
| Pagine lette | 214 su 224 (10 non lette) | 224 su 224 |
| Voci | 11, tutte DA CONFERMARE | 26: 25 PROVATO, 1 DA CONFERMARE (Arvedi, DDT 6559 di Molteni da chiedere) |
| Voci con certificato / con colata | 3 / 0 | 26 / 26 |
| DDT commerciante -> costruttore | 2 + De Lucchi sbagliato | 8027, 602, 2902, G01/3332, G02/51159; 587 e 595 al zincatore, 5.877 reso |
| Travi FVS | senza colata (due colate) | colata dalla freccia a mano, PROVATO con avviso |
| Lamiere SETAL / Mondialsteel / Gabrielli | "TUBO", senza certificato | una voce per colata, certificato per colata e timbro |

Differenze rispetto all'analisi a vista (12 voci): Mondialsteel è in 13 voci (una per colata, decisione 3) invece di una;
il tubo 76,1x5 MANCANTE non c'è (i DDT al terzista non fanno voci); CE/DoP ACCIAIERIA delle travi CELSA resta "Non
presente" perché il lettore non ha messo la sigla "CE 0099 CELSA01BCN" nei riferimenti; il certificato della
lamiera 12 è letto "16524497899" (a vista 16524497809). Il DDT 6559 (p. 20) è letto con emittente SACIF e
destinatario con la P.IVA di SACIF: segnalato come incoerente e tenuto fuori perimetro.

## Codogno, letture 0.5.1 ricomposte con il motore 0.7.0 (costo zero, prima della rilettura)

| | Motore 0.6.1 (app) | Motore 0.7.0 (ricomposizione) |
|---|---|---|
| DDT commerciante -> costruttore riconosciuti | 2 su 6 (8027 senza la pag. 2, 2902 ×2 copie) + De Lucchi sbagliato | 4 (8027 con la pag. 2, 602, 2902 unito, G02/51159); 587 costruttore -> terzista, 5.877 reso |
| Voci | 11, tutte DA CONFERMARE | 25 (3 travi, 5 lamiere SETAL per colata, 13 lamiere Mondialsteel per colata, 1 Gabrielli 51159, 1 Arvedi da certificato, 2 De Lucchi tolte) |
| Voci con certificato / con colata | 3 / 0 | 24 / 20 |
| Voci "TUBO 12x2450" | 2 | 0 |
| DDT COSTRUTTORE | Non presente | DDT 587 (tramite De Lucchi); DDT 5.877 (reso al cantiere) |
| CE/DoP CENTRO | Non presente | DoP EN 1090 FVS 9588.25 sulle 3 voci del DDT 8027 |
| Stati | 0/0/11/0 | 0/0/25/0 con le 10 pagine non lette; senza di esse 18 PROVATO (test di regressione) |

Gli stati restano DA CONFERMARE finché il DDT Gabrielli 3332 (p. 40) e la lista 51159 (p. 122) non vengono letti: sono
nello stesso file delle voci, quindi il tetto mirato (C4) li conta. Mancano ancora dalle letture 0.5.1 i segni a
mano sui certificati FVS (p. 7, 11, 15) e la lista Gabrielli (p. 42 letta come certificato, p. 122 non letta): con la
rilettura 0.7.0 (istruzioni cambiate) le travi FVS prendono la colata dal segno e il DDT 51159 si divide per placca.

## Scelte e note

- **Decisioni applicate**: 1 segno a mano sceglie la colata (PROVATO con avviso); 2 nessun tetto per la packing
  assente (il test della 0.6 `test_packing_assente_al_massimo_dedotto` codificava il tetto: riscritto per la nuova
  regola, non per farlo passare); 3 una voce per colata dichiarata (`VOCE_PER_COLATA = True` in `motore.py`: con
  `False` una voce per DDT + profilo con le colate elencate); 4 `PENNA_VALE_COME_PROVA = False` invariato; 5 lista
  del commerciante come `lettera_accompagnamento` con righe `placca, colata, certificato`.
- **Mondialsteel 602**: dichiara 13 colate placca per placca per la lamiera 10 mm: con la decisione 3 sono 13 voci
  (nell'analisi a vista era una voce con 13 colate). Per questo le voci sono 25 e non 10-12.
- **P.IVA**: due campi sul DDT (`piva_emittente`, `piva_destinatario`) invece di uno, perché un DDT stampa la P.IVA
  di entrambe le parti; `piva` sulla DoP EN 1090. Le letture 0.5.1 non li hanno: l'alias per P.IVA agisce dopo la
  rilettura.
- **Scheda parziale**: con il validatore tollerante gli errori bloccanti restano solo forma, famiglia, testata e
  righe malformate; dal percorso della lettura veloce (`espandi`) sono rari. La scheda parziale (`<chiave>.parziale.json`)
  vale finché arriva una lettura completa, e la pagina resta "da leggere" fino a `MAX_TENTATIVI`.
- **Riconoscimento DeepSeek**: `mappa.prompt_tipo()` chiede ora `segno_a_mano`, quindi cambia `mappa.versione()`:
  alla prossima analisi tutte le pagine vengono riconosciute di nuovo da DeepSeek (costo basso, ~0,2 $ su 224 pagine,
  stimato dal prezzo in `mappa.py`). L'OCR Mistral resta in cache.
- **Istruzioni cambiate** (`ddt.md`, `dop_costruttore.md`, `lettera_accompagnamento.md`, `certificato_31.md`,
  `lettura.md`): cambia `versione_lettura`, quindi la prossima analisi rilegge con ChatGPT tutte le pagine utili
  (Codogno: circa 75). Le 10 pagine non lette vanno sbloccate azzerando `tentativi.json` del lavoro.
- **Formato prove**: resta `prove/2`; aggiunte solo chiavi (`aziende`, `non_lette_dettagli`, `parziali`,
  `dop_fornitore_intermedio`, righe DDT `colate`/`placche`/`certificato`, DDT `causale`/`tramite`/`riferimenti`/`copie`).
  Le 12 colonne dell'Excel sono invariate; PARTE D'OPERA porta "(dai DDT)" o "(da un certificato)".
- **Non fatto**: il tubo 76,1x5 che compare solo nei DDT del costruttore (587/595) non genera una voce MANCANTE
  (i DDT al terzista non alimentano le voci, come chiesto); l'analisi a vista lo elencava. Una regola "materiale
  consegnato dal costruttore senza DDT di fornitura" è una scelta da prendere a parte.

## Viollier con la 0.7.0 e correzioni 0.7.1 (01/11/2026, analisi fatta dall'utente nell'app, 62 chiamate)

Primo fascicolo con il ciclo di lavorazione del costruttore (31 pagine di packing, 86 pagine, 31 file). Confronto con
`Tracciabilita_SCL_Viollier.xlsx` (30 righe): tutte presenti. Le letture erano giuste; i difetti stavano nel motore e
nella normalizzazione, verificati sulle immagini delle pagine. Correzioni (motore 0.7.1), tutte a costo zero perché
non cambiano le istruzioni di lettura:

| Caso | Prima | Causa | Correzione | Dopo |
|---|---|---|---|---|
| Tecnosider PL15, DDT SP21-05850 | MANCANTE "chiedere CO19604" | certificato letto `C019604` (O/0) | `numero_normale` equipara O e 0 vicino a una cifra | DEDOTTO (cert e DDT presenti, timbro a penna illeggibile) |
| CELSA PL10*70, DDT 3209 | DA CONFERMARE "profilo non sul certificato" | `70X10 L.6.00m` letto come tubo; timbro `3209 - 1` non riconosciuto come 3209/1 | `_affine`: piatto = due misure senza parola; `numero_normale`: ` - 1` finale è suffisso di serie; nel percorso del certificato dichiarato si provano anche le righe affini | PROVATO |
| Beltrame 283664, "DDT 1002" | voce fantasma DA CONFERMARE | `1062` a penna letto `1002` | `prove._timbri_a_penna_per_data`: DDT con stessa data e numero che differisce per una cifra (`quasi_uguale`), emittente se serve; `data_iso` accetta `18/5/22` | nessuna voce, certificato nei documenti non usati |
| Olifer L50*5, DDT 1062 | MANCANTE "chiedere GI2300/2021" | ciclo scrive GI2300/2021, certificato G1200/2021 | certificato dichiarato assente: vale quello timbrato per lo stesso DDT con il profilo, tetto DEDOTTO e avviso | DEDOTTO (colata scelta: le altre barrate) |
| 6 voci portali doppie | 12 voci | titolo del ciclo diverso da pagina a pagina | `voci_dal_fascicolo` raggruppa per file di packing, non per titolo; titoli uniti con " / " | 6 voci |
| DDT 1062 righe `ANGOLARE A LATI UGUALI` + `LT=50 LT=50 SP=5` | chiave = testo grezzo | misure per campo in un campo separato | `profilo` legge LT/LA/AL + SP per gli angolari; `_chiave_riga` preferisce una forma riconosciuta (`riconosciuta`) | ANGOLARE 50 50 5 |

Viollier: da 38 voci (2 PROVATO, 8 DEDOTTO, 3 DA CONFERMARE, 25 MANCANTE) a 32 (2, 7, 1, 22). I 22 MANCANTE sono
certificati e DDT che il ciclo dichiara e che nel fascicolo non ci sono (foglio Richieste: CELESTRI, NEGRI, FVS,
FTL ROSSI). Codogno ricomposto con la 0.7.1: invariato (25 PROVATO, 1 DA CONFERMARE). Test: 220 (da 213).
Non sistemato: il timbro a penna sul certificato Tecnosider (`SP21-0580`, letto `PR21-0580`) non fa ponte, la voce
resta DEDOTTO invece di PROVATO; il DDT 10871 di FTL Rossi con il certificato CELSA 202032266 non è nel ciclo e resta
fuori, come nell'atteso.

## Valentino con la 0.7.1 e correzioni 0.7.2 (01/11/2026, analisi fatta dall'utente nell'app, 139 chiamate)

Fascicolo senza packing: 15 DDT del commerciante (POLETTI) al costruttore (NOSSA), 11 DDT del costruttore al
cliente, 61 pagine di certificati con timbri a penna del commerciante. L'atteso SCL (`Tracciabilita_SCL_Valentino.xlsx`)
qui non aiuta: 1 riga vera e 11 righe "materiali da DDT", stato HUMAN_REVIEW. Verifica fatta sui documenti.

Letture: giuste nel contenuto, ma i numeri di DDT scritti a penna sui timbri sono letti male quasi sempre (`0843` per
6843, `1204` per 7104, `283` per 2983, `581` per 5681...), e con loro spesso anche la data. In compenso il
costruttore ha salvato ogni certificato con il DDT nel nome del file (`certificato ddt 6843 140425.pdf`,
`CERTIFICATO DDT 6600 DEL 100425.pdf`, cartella `DDT1062` in Viollier). Correzioni (motore 0.7.2):

| Caso | Prima | Causa | Correzione | Dopo |
|---|---|---|---|---|
| U 100/140/180/200/240 dai DDT Poletti | 5 MANCANTE "nessun certificato" | `FERRO U 200` non normalizzato: chiave `U 200`, certificato `UPN 200` | `profilo`: `U nnn` da solo è `UPN nnn` | PROVATO (UPN 200, timbro stampato), DEDOTTO (180, 240) |
| 17 voci "più certificati possibili" / DDT a penna illeggibile | DA CONFERMARE o certificato sbagliato | nessun ponte leggibile | **ponte dal nome del file**: file o cartella del certificato che cita il DDT (`ddt_nel_nome`), vale DEDOTTO con avviso; tra più certificati con ponte vince il timbro, poi il profilo esatto, poi il piatto con la larghezza scritta rispetto alla lamiera | 7 voci DEDOTTO in più |
| `RIF. COMM NC 2501`, `CERTIFICATI: U 200` | voci MANCANTE | righe del DDT che non sono materiale | `e_riferimento`: trattate come servizio | nessuna voce |
| Certificato 47189 su 2 pagine | 2 certificati con lo stesso numero, "identificazione non univoca" | produttore letto `AFV Accisierie` e `AFV Acclaierie` | stesso numero nello stesso file = stesso certificato | 1 certificato |
| `Largo Piatto spigolo vivo 200,00*10,00` (O.R.I. Martin) | chiave grezza, voce fantasma "DDT 353" | parola LARGO e asterisco come separatore | `_PAROLA_PIATTO` con LARGO/LARGHI; `*` tra cifre = `X` | PIATTO 200x10, nessuna voce fantasma |

Valentino: da 73 voci (0 PROVATO, 7 DEDOTTO, 36 DA CONFERMARE, 30 MANCANTE) a 62 (1, 13, 25, 23). Viollier e Codogno
ricomposti con la 0.7.2: invariati. Test: 225 (da 220).

Che cosa resta DA CONFERMARE, e perché è giusto così:
- 17 voci "più colate per il profilo sul certificato": i DDT Poletti non stampano la colata e i certificati Duferco
  elencano 2-5 colate per lo stesso profilo; il timbro a penna dice al massimo il profilo. Serve il costruttore.
- 6 voci "più certificati possibili" senza alcun ponte (piatti dei DDT 4078, 1778, 9609): il file dei certificati cita
  un altro DDT o nessuno. La cartella `PIASTRE RINFORZO ASCENSORE` ha `CERTIFICATO DDT 9606` per il DDT 9.609:
  probabile refuso del costruttore, non assunto.
- DDT 3066 (travi intervento 3) non è nel fascicolo pur avendo la cartella dei certificati; DDT 4475 è una scansione
  bianca: le voci "dal certificato" chiedono quei DDT.
- 23 MANCANTE: tubi, tondi, lamiere e altri materiali dei DDT senza alcun certificato nel fascicolo.

## Gstaad con la 0.7.2 e correzioni 0.7.3 (01/11/2026, analisi fatta dall'utente nell'app, 209 chiamate)

Primo fascicolo con packing (1 pagina, 19 righe), lettere del distributore (Reyher, 11) e bulloneria. 252 pagine in
57 file, molti doppi (gli stessi PDF in `1. Certificates`, `2. DDT` e `4. DDT`). Attenzione: nella cartella `2. DDT`
i file sono rinominati sfalsati di uno (`DDT 3562.pdf` contiene il DDT 3506, `DDT 5004.pdf` il 4870, `DDT 10188
VITERIA EUGANEA_M12.pdf` il 5004 su due pagine): l'app ha letto il contenuto giusto, i nomi sono sbagliati. Nessun
atteso di confronto: verifica sui documenti. Correzioni (motore 0.7.3):

| Caso | Prima | Causa | Correzione | Dopo |
|---|---|---|---|---|
| Bulloneria Reyher (`I 4017 8.8U CE nut M 12 x 50`, `HEX BOLT-ISO4017 ... M12X50`, `Scheibe ISO 7090 - 10`, `7089 steel 12 (13 x 24 x 2,5)`) | 5 MANCANTE, rondelle lette come tubi | solo parole italiane | `profilo`: codici ISO/DIN con prefisso, BOLT/NUT/WASHER/SCHEIBE, `M 12 x 50` con spazi; la misura con lunghezza è una vite anche se c'è scritto "nut" | 1 PROVATO, 4 DEDOTTO |
| `PIATTI IN LAMIERA SPESSORE 10 MM` (packing) | 3 MANCANTE | la parola PIATTI escludeva il ramo lamiera | `SPESSORE n MM` nel ramo piatto -> `LAMIERA n` | 2 DEDOTTO, 1 DA CONFERMARE (due colate) |
| DDT 4563 letto due volte (`20.05.26` e `20/05/2026`, emittente vuoto su una copia) | DDT "non nel fascicolo" | `data_iso` solo con le barre; la copia vuota restava vuota | date con punti e trattini; la copia letta meglio riempie i campi vuoti | 1 DDT |
| Timbro FVS a penna `480` del 29/05/26 per il DDT 4870, `1503` del 20/05/26 per il 4563 | voci fantasma, certificati non agganciati | cifre mancanti, `quasi_uguale` non basta | timbro a penna: stesso giorno e stesso emittente del timbro -> quel DDT, con avviso (`ddt_letto`) | agganciati |
| Copia del certificato Duferco 4323 con il numero non letto (ha il timbro stampato e la colata evidenziata) | HEA 140 DA CONFERMARE "più certificati timbrati" | due certificati per uno | copie unite: stesso numero (o non letto) e una colata in comune; stesso numero e stessa data | PROVATO |
| Certificati Reyher: la lettera cita il protocollo `RN2000689815`, che sta nel nome del file del certificato, non il numero del certificato | nessun ponte | la lettera valeva solo nello stesso file con il numero | protocollo della lettera nel nome del file del certificato = ponte, anche da un altro file | BULLONI M12X50 PROVATO |
| 12 voci "dal certificato" (timbri di vendite precedenti del commerciante, copie riusate) | 12 DA CONFERMARE fantasma | C12 su ogni timbro non riconosciuto | un certificato già ancorato a un DDT del fascicolo (timbro o nome del file) non genera voci dagli altri timbri | 1 (Megasider 1870, davvero assente) |
| Dadi M12 di Viteria | "più certificati possibili" (dadi Reyher) | certificato intestato a un altro commerciante preso per esclusione | intestato a un altro commerciante del fascicolo -> scartato | MANCANTE (giusto: nessun certificato, la lettera Viteria dà solo la colata) |
| UNP 160 del DDT 4563: due certificati CELSA timbrati per lo stesso DDT | DA CONFERMARE | pari merito | spareggio: vince il certificato con il segno a mano su una sola colata del profilo, poi il timbro, poi il profilo esatto | DEDOTTO (04461778, spunta su CE259891) |
| `TUBO 100x100x3` preso per il `100x100x5` | affinità per la sola prima misura | `_affine`: per i tubi le misure in comune devono coincidere (`150x100` e `150x100x6` sì, `100x100x3` e `100x100x5` no) | |

Gstaad: da 31 voci (3 PROVATO, 4 DEDOTTO, 15 DA CONFERMARE, 9 MANCANTE) a 20 (5, 11, 3, 1). Valentino con la 0.7.3:
da 62 (1, 13, 25, 23) a 60 (1, 15, 20, 24): due voci fantasma in meno, i timbri Poletti `283`/`593` ripresi per data
come DDT 2983, una LAMIERA 4 passa a MANCANTE perché il suo certificato risulta timbrato per un altro DDT (giusto).
Viollier e Codogno invariati. Test: 234 (da 225).

Resta DA CONFERMARE: Megasider 3674ZG26 (DDT FVS 1870 non nel fascicolo, piatti non dichiarati), LAMIERA 8 del DDT
2323 (certificato 235408 con due colate, timbro a penna senza numero), PROFILO 100X100X5 (certificato Pirefiltubi
senza numero, timbro `480` del 24/03/26 illeggibile). MANCANTE: dadi M12 Viteria.

## progresso con la 0.7.3 e correzioni 0.7.4 (01/11/2026, verifica a tavolino, nessuna lettura)

Fascicolo letto dall'utente nell'app (265 chiamate, 174 pagine, 8 mai accettate dopo 4 tentativi: due DDT, tre
certificati, una DoP, una pagina della DoP del costruttore). Registro di controllo del costruttore come packing (19
righe), plico di 164 pagine con DDT Vanoli, OMAR, Viterie Orobiche, Hilti, "Elenco materiali di commessa" di OMAR.
Verifica fatta guardando le immagini delle pagine contro `risultato.json`, senza rileggere nulla. Correzioni
(motore 0.7.4), tutte verificate per ricomposizione dei cinque cantieri:

| Caso | Prima | Causa | Correzione | Dopo |
|---|---|---|---|---|
| IPE 400, DDT Vanoli `1/12000` con `CERT.COL. DU123329BJ0`; certificato Duferco 354/2021 con la riga IPE 400 colata `123329B` | DA CONFERMARE "più certificati possibili" | la tabella scrive `12000/`, il DDT `1/12000`: `stesso_numero` non li lega; la riga del DDT `IPE MM. 400` non ha chiave | `ddt_di` accetta anche `cita_ddt` (coda dopo un separatore, anche con zeri davanti); `_TRAVI` salta `MM.`; `numero_normale` toglie la barra finale | DDT agganciato, colata trovata; resta DA CONFERMARE solo per il tetto "fascicolo non letto completamente" (p0022, p0068 nello stesso file) |
| TUBO 100x100x5 (DDT `1/12166`, p0022 non letta) | MANCANTE | riga del certificato Sideralba `PROFILATI CAVI ... 5 100 100 12000` senza chiave | `PROFILATI CAVI` è una parola da tubo; misure per colonne (spessore, altezza, larghezza, lunghezza) → `TUBO 100x100x5`; celle `|` come spazi | DA CONFERMARE "per esclusione; DDT 12166 non nel fascicolo" (giusto finché p0022 non è letta) |
| BARRA FILETTATA M12x1000, DDT `8603/` | MANCANTE, chiede "DDT 8603/" | DDT `2021-S_DVE-0008603` non agganciato; `BARRA FILETTATA 8.8 D.12X1MT`, `THREADED RODS M12X1.000` e `BARRA FILETTATA Zn 8.8 M12x1000` con tre chiavi diverse | coda con zeri davanti; chiave `BARRA FILETTATA M12x1000` (D./M, MT, punto delle migliaia) | DEDOTTO (certificato intestato al commerciante, senza timbro con il DDT); DA CONFERMARE per il tetto delle pagine non lette |
| BARRA FILETTATA M16x1000, DADI M12/M16, LAMINATO ELLE 60x40x6 (materiale da magazzino: fornitore = costruttore, DDT vuoto) | MANCANTE | `LAMINATO ELLE` → `LAMIERA 6`; `MA16`, `16MA`, `M- 12` senza chiave; `THREADED RODS 16X1000` | angolare prima delle lamiere; dadi con MA/`M-`; barre filettate | DA CONFERMARE "abbinato per esclusione; nessun DDT dichiarato" (il certificato c'è) |
| `FINITURA GREZZO` | voce MANCANTE | riga di finitura della tabella | `e_riferimento` anche per finitura, prestazione, servizio, zincatura, trasporto, imballo, verniciatura, sabbiatura, noleggio; applicato anche alle righe della packing (scartate) | nessuna voce |
| Lamiere `Lamiera in S275JR` dell'elenco OMAR | "nel fascicolo solo le pagine n/N: la riga del profilo non c'è" (la riga c'è: la chiave non ha lo spessore) | la famiglia packing non legge spessore e colata | motivo esplicito "la tabella del costruttore non dà la misura del profilo"; i campi nelle istruzioni sono rimandati (cambiano la versione di lettura: ~600 pagine) | DA CONFERMARE con il motivo giusto |
| colata dichiarata con la sigla del produttore (`SICL2103435A` per `CL21/03435A`, `OL142191` per `142191`) | non legata | confronto per uguaglianza | `stessa_colata`: la più corta (almeno cinque cifre) è la coda dell'altra | pronta per quando p0022 sarà letta |

progresso: da 23 voci (0/0/11/12) a **22 (0 PROVATO, 0 DEDOTTO, 17 DA CONFERMARE, 5 MANCANTE)**. I 5 MANCANTE: tasselli
e ancorante Hilti (prodotti con DoP/ETA, non con 3.1) e due rondelle senza certificato. Codogno, Viollier, Valentino e
Gstaad ricomposti con la 0.7.4: invariati. Test: 237 (da 234).

Da decidere (non fatto): materiale "da magazzino" del costruttore (cercare nei DDT del fascicolo con tetto DEDOTTO?);
prodotti con DoP/ETA senza 3.1 (colonna CE/DoP, richiesta della DoP invece di "certificato mancante"); l'elenco del
fornitore intermedio (OMAR) come ponte tra il suo DDT 1013 e i certificati per spessore (unirebbe le voci 1-4 e 5-8);
il DDT che cita la colata come ponte (oggi DEDOTTO senza timbro); le 8 pagine rifiutate dal validatore
(`riferimenti[].tipo` fuori lista, citazione non trovata su tabelle scansionate): sbloccarle costa 8 letture.

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

## Codogno dopo la Verifica finale 0.8.0 e correzione 0.7.5 (02/11/2026)

La Verifica finale (3 pagine, 34k token) ha corretto il DDT 6559 letto a rovescio (emittente F.lli Molteni, destinatario
SACIF): con il DDT riconosciuto le sue righe sono diventate voci e il conteggio è sceso da 25/0/1/0 a 25/0/0/2.

| Caso | Prima | Causa | Correzione | Dopo |
|---|---|---|---|---|
| `T NERO SALDATO S355J2 0 219,1 X 12,5` sul DDT 6559; certificato Arvedi 977915 `TUBO ELETTROSALDATO SCORDONATO 219,1x12,5x12000` timbrato Molteni per il DDT 6559 | MANCANTE | la Ø letta `0`: `profilo` non riconosce il tubo, nessuna chiave da abbinare | una cifra sola davanti a `diametro X spessore`, con parola da tubo o la `T` del commerciante, è la Ø → `TUBO 219.1x12.5`, affine a `TUBO 219.1x12.5x12000` | PROVATO (timbro con il DDT) |
| `T TONDO 0 60 X 5`, `T TONDO 0 88.9 X 6.3` | una voce `TONDO 0` MANCANTE | letti come tondo pieno | con la Ø e lo spessore il tondo è un tubo tondo | due voci `TUBO 60x5`, `TUBO 88.9x6.3` MANCANTE (nel fascicolo non c'è il 3.1: richiesta giusta a F.lli Molteni) |

Codogno: **26 PROVATO, 0, 0, 2 MANCANTE** (28 voci). Gstaad, Viollier, Valentino e progresso ricomposti con la 0.7.5:
invariati. Test: 254 (da 251).

