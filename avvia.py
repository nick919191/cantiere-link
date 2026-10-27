"""Avvio stabile: sceglie la versione installata senza spostare i cantieri."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def config_dir():
    if os.environ.get("TRACCIA_CONFIG"):
        return Path(os.environ["TRACCIA_CONFIG"])
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "TracciabilitaMateriali"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/TracciabilitaMateriali"
    return Path.home() / ".local/share/tracciabilita-materiali"


def selected(base=BASE, folder=None):
    folder = folder or config_dir()
    pointer = folder / "aggiornamenti/attiva.json"
    if not pointer.exists():
        return base
    value = json.loads(pointer.read_text(encoding="utf-8"))
    if not value.get("active"):
        return base
    key = value["active"]
    if not isinstance(key, str) or Path(key).name != key or "/" in key or "\\" in key:
        raise ValueError("Riferimento alla versione non valido.")
    parent = (folder / "aggiornamenti/installazioni").resolve()
    target = (parent / key).resolve()
    if target.parent != parent:
        raise ValueError("Cartella della versione non valida.")
    marker = json.loads((target / ".installata.json").read_text(encoding="utf-8"))
    trusted = json.loads((base / "release.json").read_text(encoding="utf-8"))
    if marker["repository"] != trusted["repository"]:
        raise ValueError("La versione appartiene a un altro repository.")
    return target


def prepare(root):
    executable = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    if not executable.exists():
        subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True, **flags)
    digest = hashlib.sha256((root / "requirements.txt").read_bytes()).hexdigest()
    stamp = root / ".venv/requirements.sha256"
    if not stamp.exists() or stamp.read_text().strip() != digest:
        print("Preparazione delle dipendenze di CantiereLink…", flush=True)
        subprocess.run(
            [
                str(executable),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(root / "requirements.txt"),
            ],
            cwd=root,
            check=True,
            **flags,
        )
        stamp.write_text(digest, encoding="utf-8")
    return executable


def main():
    if sys.version_info < (3, 12):  # noqa: UP036
        raise RuntimeError("Serve Python 3.12 o successivo.")
    if "--versione-originale" in sys.argv:
        root = BASE
    else:
        root = selected()
    executable = prepare(root)
    print("CantiereLink: tieni aperta questa finestra durante il lavoro. Ctrl+C arresta l’app.", flush=True)
    return subprocess.call([str(executable), "-m", "traccia.desktop"], cwd=root)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Avvio non riuscito: {exc}\nPer usare la copia originale: python avvia.py --versione-originale")
        sys.exit(1)
