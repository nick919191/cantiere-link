# Firma delle release — piano (S1)

Stato: **non implementato**. Oggi l'updater si fida soltanto di GitHub: lo SHA256 atteso è `asset.digest`
dell'API GitHub e il `MANIFEST.sha256` dentro lo zip è auto-attestante. Chi controlla l'account o il repository
può quindi distribuire codice a tutte le installazioni. Gli installer `.exe`/`.dmg` non sono firmati.

Questo documento fissa il piano da completare prima di una release stabile. Nessun passo è stato eseguito.

## 1. Firma indipendente degli asset (minisign)

- Generare una coppia di chiavi **minisign** su una macchina offline del manutentore. La chiave privata
  non entra mai nel repository né nei secret di GitHub Actions.
- A ogni release firmare a mano `cantiere-link-<versione>.zip`, `CantiereLink-Setup-<versione>.exe` e i `.dmg`:
  `minisign -S -m <file>` produce `<file>.minisig`, da allegare alla release accanto al file.
- La **chiave pubblica** entra nel codice (`traccia/aggiornamenti.py`, costante `CHIAVE_PUBBLICA_RELEASE`) e nel
  README. Cambiarla richiede una release firmata con la chiave precedente (rotazione esplicita).
- L'updater, dopo il controllo dello SHA256, scarica `<file>.minisig` dallo stesso `releases/download/…` e
  verifica la firma con la chiave pubblica incorporata (implementazione Ed25519 con `cryptography`, già
  dipendenza): firma assente o non valida → "Pacchetto non firmato dal manutentore. Nessuna versione attivata."
- Il `MANIFEST.sha256` resta come controllo di integrità dei singoli file, ma non è più la sola prova.

Alternativa equivalente: **cosign** (Sigstore) con firma keyless; richiede però rete verso Rekor/Fulcio anche
in verifica, quindi minisign è preferito per un'app locale.

## 2. Firma dei binari

- **Windows**: certificato Authenticode (EV o OV) e `signtool sign /fd SHA256 /td SHA256 /tr <timestamp>`
  sull'`.exe` di PyInstaller **e** sul setup di Inno Setup (`SignTool` in `packaging/windows.iss`).
  Il certificato sta in un HSM/token del manutentore, non in CI: la firma è un passo manuale dopo la build.
- **macOS**: firma con Developer ID (`codesign --deep --options runtime`), notarizzazione
  (`xcrun notarytool submit … --wait`) e `xcrun stapler staple` sull'app e sul `.dmg`.
- Finché i binari non sono firmati, README e guida devono continuare a dichiararlo (già così in 0.3.0).

## 3. Riproducibilità della build

- `requirements.lock` con hash (`uv pip compile --universal --generate-hashes`) è usato da `avvia.py`,
  dall'updater in modalità sorgenti e dai workflow con `--require-hashes` (fatto in questo branch).
- Le GitHub Actions sono pinnate a SHA e `pyinstaller`/`innosetup` hanno versione fissa (fatto).
- Da fare: pubblicare in release lo SHA256 di ogni asset in una nota firmata (minisign) e confrontare in CI
  l'hash dello zip sorgenti con quello calcolato da `tools/package_release.py` su un secondo runner.

## 4. Ordine consigliato

1. Chiavi minisign + verifica in-app (una release di transizione accetta anche asset non firmati, con avviso).
2. Firma Authenticode dell'installer Windows.
3. Developer ID + notarizzazione macOS.
4. Rendere la firma obbligatoria nell'updater e togliere l'avviso "installer non firmato" da README e guida.
