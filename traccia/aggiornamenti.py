"""Versioni GitHub stabili, installate separatamente e attivate solo su richiesta."""

import hashlib
import json
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import httpx
from filelock import FileLock

from . import VERSIONE_APP, configurazione, percorsi

_lock = threading.RLock()
_state = {"busy": False, "checking": False, "message": "", "available": None, "checked_at": None}
MAX_ARCHIVE = 250 * 1024 * 1024
MAX_EXPANDED = 200 * 1024 * 1024
INTERVAL = 24 * 60 * 60


class UpdateError(Exception):
    pass


def metadata():
    return json.loads((percorsi.CODICE / "release.json").read_text(encoding="utf-8"))


def package_kind():
    return "installer" if getattr(sys, "frozen", False) else "source"


def asset_name(number):
    if package_kind() == "source":
        return f"{metadata()['asset_prefix']}-{number}.zip"
    if sys.platform == "win32":
        return f"CantiereLink-Setup-{number}.exe"
    if sys.platform == "darwin":
        return f"CantiereLink-{number}-macos-{platform.machine()}.dmg"
    raise UpdateError("Installer non disponibile per questo sistema.")


def directory():
    path = configurazione.directory() / "aggiornamenti"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def pointer():
    return _read(directory() / "attiva.json", {"active": None, "previous": None})


def _installed(key):
    if not key or not re.fullmatch(r"v\d+\.\d+\.\d+-[a-f0-9]{12}", key):
        raise UpdateError("Versione installata non valida.")
    parent = (directory() / "installazioni").resolve()
    root = (parent / key).resolve()
    if root.parent != parent:
        raise UpdateError("Percorso della versione non valido.")
    mark = _read(root / ".installata.json", {})
    if mark.get("repository") != metadata()["repository"]:
        raise UpdateError("Versione non appartenente al repository configurato.")
    return root, mark


def status():
    with _lock:
        result = dict(_state)
    native = package_kind() == "installer"
    saved = {} if native else pointer()
    active = _installed(saved["active"])[1] if saved.get("active") else None
    result.update(
        version=VERSIONE_APP,
        repository=metadata()["repository"],
        automatic=configurazione.leggi().get("update_checks", True),
        dismissed=configurazione.leggi().get("dismissed_update", ""),
        next_version=active.get("version") if active else None,
        restart=bool(active and active["version"] != VERSIONE_APP)
        or bool(saved.get("restart_base") and percorsi.CODICE.parent.name == "installazioni"),
        can_rollback=bool(saved.get("active") or saved.get("previous")),
        kind=package_kind(),
        installer_ready=False,
    )
    if result["available"] and active and result["available"]["version"] == active["version"]:
        result["available"] = None
    installer = _read(directory() / "installer.json", {})
    if native and installer and version(installer["version"]) > version(VERSIONE_APP):
        result["installer_ready"] = True
        result["next_version"] = installer["version"]
        result["message"] = "Installer pronto. Premi Apri installer, completa la procedura e riapri CantiereLink."
        result["available"] = None
    return result


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?\d+\.\d+\.\d+", value):
        raise UpdateError("La release deve avere una versione stabile, per esempio v0.4.0.")
    return tuple(int(x) for x in value.removeprefix("v").split("."))


def parse_release(data, repo):
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name", "")
    if version(tag) <= version(VERSIONE_APP):
        return None
    number = tag.removeprefix("v")
    name = asset_name(number)
    asset = next((x for x in data.get("assets", []) if x.get("name") == name), None)
    if not asset or asset.get("state") != "uploaded":
        raise UpdateError("Nuova release trovata, ma il pacchetto installabile non è disponibile.")
    digest = asset.get("digest", "") or ""
    if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        raise UpdateError("La release non ha un’impronta SHA256 verificabile su GitHub.")
    expected = f"https://github.com/{repo}/releases/download/{tag}/{name}"
    if asset.get("browser_download_url") != expected:
        raise UpdateError("Il pacchetto non proviene dal repository configurato.")
    if not isinstance(asset.get("size"), int) or not 0 < asset["size"] <= MAX_ARCHIVE:
        raise UpdateError("Dimensione del pacchetto non consentita.")
    return {
        "version": number,
        "url": expected,
        "sha256": digest[7:].lower(),
        "size": asset["size"],
        "notes": str(data.get("body") or "Nessuna nota di rilascio.")[:12000],
        "page": f"https://github.com/{repo}/releases/tag/{tag}",
        "filename": name,
    }


def _fetch():
    repo = metadata()["repository"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise UpdateError("Repository degli aggiornamenti non configurato.")
    try:
        response = httpx.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            timeout=20,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "CantiereLink"},
        )
        if response.status_code == 404:
            return None, "Nessuna release pubblica disponibile. Il repository potrebbe non essere ancora pubblicato."
        if response.status_code in (403, 429):
            raise UpdateError("Controllo temporaneamente limitato da GitHub. Riprova più tardi.")
        response.raise_for_status()
        item = parse_release(response.json(), repo)
        return item, "Nuova versione disponibile." if item else "Stai usando una versione aggiornata."
    except (httpx.HTTPError, ValueError) as exc:
        raise UpdateError(
            "Impossibile controllare gli aggiornamenti. La versione installata resta utilizzabile."
        ) from exc


def check(force=False):
    with _lock:
        if _state["busy"] or _state["checking"]:
            return status()
        cache = _read(directory() / "controllo.json", {})
        if not force and (
            not configurazione.leggi().get("update_checks", True) or time.time() - cache.get("time", 0) < INTERVAL
        ):
            if cache.get("version") == VERSIONE_APP and cache.get("repository") == metadata()["repository"]:
                _state.update(
                    available=cache.get("available"), checked_at=cache.get("time"), message=cache.get("message", "")
                )
            return status()
        _state.update(checking=True)
    try:
        available, message = _fetch()
        now = time.time()
        with _lock:
            _state.update(available=available, message=message, checked_at=now)
        configurazione.scrivi_json(
            directory() / "controllo.json",
            {
                "time": now,
                "available": available,
                "version": VERSIONE_APP,
                "repository": metadata()["repository"],
                "message": message,
            },
        )
    except UpdateError as exc:
        with _lock:
            _state.update(message=str(exc), available=None)
    finally:
        with _lock:
            _state["checking"] = False
    return status()


def _download(item, path):
    url = item["url"]
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        for _ in range(5):
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname
                not in {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}
                or parsed.username
                or parsed.password
                or parsed.port not in (None, 443)
            ):
                raise UpdateError("Indirizzo di download non consentito.")
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = response.headers.get("location", "")
                    continue
                response.raise_for_status()
                total, digest = 0, hashlib.sha256()
                with path.open("xb") as output:
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > MAX_ARCHIVE or total > item["size"]:
                            raise UpdateError("Il pacchetto supera la dimensione dichiarata.")
                        digest.update(chunk)
                        output.write(chunk)
                if total != item["size"] or digest.hexdigest() != item["sha256"]:
                    raise UpdateError("Verifica del pacchetto fallita. Nessuna versione è stata attivata.")
                return
    raise UpdateError("Troppi reindirizzamenti durante il download.")


def extract(archive, target, item):
    prefix = f"{metadata()['asset_prefix']}-{item['version']}"
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if len(entries) > 4000 or sum(x.file_size for x in entries) > MAX_EXPANDED:
            raise UpdateError("Archivio troppo grande.")
        seen = set()
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (
                "\\" in entry.filename
                or ":" in entry.filename
                or path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or path.parts[0] != prefix
                or stat.S_ISLNK(entry.external_attr >> 16)
            ):
                raise UpdateError("Archivio con percorsi non validi.")
            relative = PurePosixPath(*path.parts[1:])
            if not relative.parts or entry.is_dir():
                continue
            key = relative.as_posix().casefold()
            if key in seen or any(p.rstrip(" .") != p for p in relative.parts):
                raise UpdateError("Archivio con nomi ambigui.")
            if any(
                p.casefold() in {".git", ".venv", "lavori", "archivio", ".env", ".installata.json"}
                or p.split(".")[0].upper()
                in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}
                for p in relative.parts
            ):
                raise UpdateError("L’archivio contiene dati o nomi non distribuibili.")
            seen.add(key)
            destination = target.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(zipped.read(entry))
            if destination.suffix in {".sh", ".command"}:
                destination.chmod(0o755)
    release = _read(target / "release.json", {})
    info = tomllib.loads((target / "pyproject.toml").read_text(encoding="utf-8"))
    if release != metadata() or info["project"]["version"] != item["version"]:
        raise UpdateError("Identità o versione del pacchetto non corrispondente alla release.")
    for required in ("traccia/desktop.py", "web/index.html", "requirements.txt", "avvia.py", "LICENSE"):
        if not (target / required).is_file():
            raise UpdateError("Il pacchetto non contiene tutti i file necessari.")
    manifest = (target / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines()
    hashes = {}
    for row in manifest:
        digest, name = row.split("  ", 1)
        if name in hashes or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise UpdateError("Manifest del pacchetto non valido.")
        hashes[name] = digest
    files = {
        p.relative_to(target).as_posix(): p for p in target.rglob("*") if p.is_file() and p.name != "MANIFEST.sha256"
    }
    if files.keys() != hashes.keys() or any(
        hashlib.sha256(p.read_bytes()).hexdigest() != hashes[n] for n, p in files.items()
    ):
        raise UpdateError("I file del pacchetto non corrispondono al manifest.")


def _prepare_environment(root):
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    commands = [
        [sys.executable, "-m", "venv", str(root / ".venv")],
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(root / "requirements.txt")],
        [str(python), "-c", "from traccia.server import app; assert app"],
    ]
    for command in commands:
        subprocess.run(
            command, cwd=root, check=True, timeout=600, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags
        )
    (root / ".venv/requirements.sha256").write_text(
        hashlib.sha256((root / "requirements.txt").read_bytes()).hexdigest()
    )


def install(expected_version):
    with _lock:
        if _state["busy"]:
            raise UpdateError("Un aggiornamento è già in preparazione.")
        _state.update(busy=True, message="Verifica della release…")

    def work():
        try:
            with FileLock(directory() / "install.lock", timeout=0):
                item, _ = _fetch()
                if not item or item["version"] != expected_version:
                    raise UpdateError("La release è cambiata: controlla di nuovo le novità prima di installare.")
                if package_kind() == "installer":
                    downloads = directory() / "download"
                    downloads.mkdir(exist_ok=True)
                    name = item["sha256"][:12] + "-" + item["filename"]
                    target = downloads / name
                    if not target.exists():
                        with tempfile.TemporaryDirectory(prefix=".download-", dir=directory()) as temporary:
                            pending = Path(temporary) / "installer"
                            _download(item, pending)
                            pending.rename(target)
                    if hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
                        raise UpdateError(
                            "L’installer salvato non supera la verifica. Nessun programma è stato eseguito."
                        )
                    configurazione.scrivi_json(directory() / "installer.json", item | {"saved_name": name})
                    return
                key = f"v{item['version']}-{item['sha256'][:12]}"
                parent = directory() / "installazioni"
                parent.mkdir(exist_ok=True)
                destination = parent / key
                if not destination.exists():
                    with tempfile.TemporaryDirectory(prefix=".preparazione-", dir=directory()) as temporary:
                        temporary = Path(temporary)
                        archive = temporary / "release.zip"
                        _download(item, archive)
                        staged = temporary / "source"
                        staged.mkdir()
                        extract(archive, staged, item)
                        # Ambiente virtuale creato nel percorso finale: contiene percorsi assoluti.
                        staged.rename(destination)
                mark = destination / ".installata.json"
                if not mark.exists():
                    with _lock:
                        _state["message"] = "Preparazione della nuova versione e delle dipendenze…"
                    _prepare_environment(destination)
                    configurazione.scrivi_json(
                        mark,
                        {"repository": metadata()["repository"], "version": item["version"], "sha256": item["sha256"]},
                    )
                else:
                    _installed(key)
                old = pointer()
                configurazione.scrivi_json(directory() / "attiva.json", {"active": key, "previous": old.get("active")})
                with _lock:
                    _state.update(
                        available=None, message="Aggiornamento pronto. Chiudi l’app e riapri il consueto Avvia."
                    )
        except Exception as exc:
            with _lock:
                _state["message"] = (
                    str(exc)
                    if isinstance(exc, UpdateError)
                    else "Installazione non riuscita. La versione in uso resta disponibile; puoi riprovare."
                )
        finally:
            with _lock:
                _state["busy"] = False

    threading.Thread(target=work, name="aggiornamento", daemon=False).start()
    return status()


def rollback():
    if package_kind() == "installer":
        raise UpdateError("Per la versione installata, usa l’installer della release precedente.")
    with _lock, FileLock(directory() / "install.lock", timeout=0):
        if _state["busy"]:
            raise UpdateError("Attendi la fine dell’aggiornamento.")
        saved = pointer()
        if not saved.get("active") and not saved.get("previous"):
            raise UpdateError("Nessuna versione precedente disponibile.")
        if saved.get("previous"):
            _installed(saved["previous"])
        configurazione.scrivi_json(
            directory() / "attiva.json",
            {
                "active": saved.get("previous"),
                "previous": saved.get("active"),
                "restart_base": not bool(saved.get("previous")),
            },
        )
        _state["message"] = (
            "Versione precedente selezionata. Chiudi l’app e riapri Avvia. I documenti non sono stati modificati."
        )
    return status()


def open_installer():
    if package_kind() != "installer":
        raise UpdateError("Questa installazione usa i sorgenti.")
    value = _read(directory() / "installer.json", {})
    if not value or version(value["version"]) <= version(VERSIONE_APP):
        raise UpdateError("Nessun nuovo installer pronto.")
    expected_name = value["sha256"][:12] + "-" + asset_name(value["version"])
    if value.get("saved_name") != expected_name:
        raise UpdateError("Nome dell’installer non valido.")
    target = directory() / "download" / expected_name
    if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != value["sha256"]:
        raise UpdateError("Verifica dell’installer fallita.")
    if sys.platform == "win32":
        os.startfile(str(target))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
