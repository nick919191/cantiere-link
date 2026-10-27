"""Rimozione recuperabile dei cantieri. Gli originali si spostano insieme al fascicolo."""

import json
import re
import time
import uuid

from filelock import FileLock

from . import configurazione, percorsi


def directory():
    folder = percorsi.RADICE / "cestino"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def elenco():
    return [
        json.loads((p / "voce.json").read_text(encoding="utf-8"))
        for p in sorted(directory().iterdir(), reverse=True)
        if p.is_dir() and (p / "contenuto").is_dir() and (p / "voce.json").is_file()
    ]


def sposta(job):
    source = percorsi.lavoro(job)
    if (
        source.is_symlink()
        or source.resolve().parent != percorsi.lavori().resolve()
        or not (source / "info.json").is_file()
    ):
        raise ValueError("Cantiere non trovato o percorso non valido.")
    with FileLock(directory() / "cestino.lock", timeout=5):
        info = json.loads((source / "info.json").read_text(encoding="utf-8"))
        key = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:12]
        target = directory() / key
        target.mkdir()
        entry = {"id": key, "lavoro": job, "nome": info.get("nome", job), "eliminato": time.strftime("%d/%m/%Y %H:%M")}
        configurazione.scrivi_json(target / "voce.json", entry)
        source.rename(target / "contenuto")
        return entry


def ripristina(key):
    if not re.fullmatch(r"\d{8}-\d{6}-[a-f0-9]{12}", key):
        raise ValueError("Voce del cestino non valida.")
    with FileLock(directory() / "cestino.lock", timeout=5):
        entry = directory() / key
        if entry.is_symlink() or entry.resolve().parent != directory().resolve() or not (entry / "contenuto").is_dir():
            raise ValueError("Voce del cestino non trovata.")
        info = json.loads((entry / "voce.json").read_text(encoding="utf-8"))
        destination = percorsi.lavoro(info["lavoro"])
        if destination.exists():
            raise ValueError("Un cantiere con lo stesso identificativo è già presente. Nessun file è stato sostituito.")
        percorsi.lavori().mkdir(parents=True, exist_ok=True)
        (entry / "contenuto").rename(destination)
        return info
