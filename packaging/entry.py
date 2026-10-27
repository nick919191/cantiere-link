"""Ingresso per gli installer: include Python e apre l’interfaccia nel browser locale."""

import os
import sys
from pathlib import Path

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from traccia.desktop import main

if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    if "--smoke-test" in sys.argv:
        import json

        import keyring
        import openpyxl
        import pypdfium2

        from traccia import VERSIONE_APP, percorsi
        from traccia.server import app

        assert app and pypdfium2.PdfDocument and openpyxl.Workbook
        for name in ("web/index.html", "docs/index.html", "release.json", "istruzioni/lettura.md"):
            assert (percorsi.CODICE / name).is_file(), name
        backend = type(keyring.get_keyring()).__module__
        assert backend.startswith(("keyring.backends.Windows", "keyring.backends.macOS"))
        output = Path(sys.argv[sys.argv.index("--smoke-test") + 1])
        output.write_text(
            json.dumps({"version": VERSIONE_APP, "resources": True, "keyring": backend}), encoding="utf-8"
        )
    else:
        try:
            main()
        except Exception as error:
            from traccia import configurazione

            folder = configurazione.directory()
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "ultimo-errore.txt").write_text(str(error), encoding="utf-8")
            if os.name == "nt":
                import ctypes

                ctypes.windll.user32.MessageBoxW(
                    None,
                    "Avvio non riuscito. Consulta ultimo-errore.txt nella cartella dati dell’app.",
                    "CantiereLink",
                    16,
                )
            sys.exit(1)
