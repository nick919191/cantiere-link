"""Preferenze locali; nessuna credenziale viene salvata nel progetto o nel browser."""

import json
import os
import sys
import threading
import uuid
from pathlib import Path

LOCK = threading.RLock()


def directory() -> Path:
    override = os.environ.get("TRACCIA_CONFIG")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "TracciabilitaMateriali"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "TracciabilitaMateriali"
    return Path.home() / ".local" / "share" / "tracciabilita-materiali"


def scrivi_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with tmp.open("x", encoding="utf-8") as handle:
        os.chmod(tmp, 0o600)
        json.dump(value, handle, ensure_ascii=False, indent=2)
    tmp.replace(path)


def leggi() -> dict:
    with LOCK:
        path = directory() / "preferenze.json"
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not value.get("host_id"):
            value["host_id"] = "urn:uuid:" + str(uuid.uuid4())
            scrivi_json(path, value)
        # "low": sulle pagine semplici il risultato è lo stesso e si risparmiano i token di ragionamento
        return {"model": "", "reasoning": "low", "theme": "system", "chat_width": 390, **value}


def aggiorna(value: dict) -> dict:
    with LOCK:
        current = leggi()
        for name in ("model", "reasoning", "theme", "chat_width", "update_checks", "dismissed_update"):
            if name in value:
                current[name] = value[name]
        if current["theme"] not in ("system", "light", "dark"):
            raise ValueError("tema non valido")
        if current["reasoning"] not in ("", "low", "medium", "high"):
            raise ValueError("ragionamento non valido")
        if not isinstance(current["model"], str) or len(current["model"]) > 150:
            raise ValueError("modello non valido")
        current["chat_width"] = max(310, min(600, int(current["chat_width"])))
        scrivi_json(directory() / "preferenze.json", current)
        return current
