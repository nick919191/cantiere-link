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


PREDEFINITE = {"model": "", "reasoning": "low", "theme": "system", "modello_mistral": "", "modello_deepseek": ""}


def _valide(value: dict) -> dict:
    """Scarta i campi del tipo sbagliato: un file modificato a mano non deve impedire l'avvio."""
    pulito = dict(value)
    for name, default in PREDEFINITE.items():
        if type(pulito.get(name)) is not type(default):
            pulito[name] = default
    if pulito["theme"] not in ("system", "light", "dark"):
        pulito["theme"] = PREDEFINITE["theme"]
    if pulito["reasoning"] not in ("", "low", "medium", "high"):
        pulito["reasoning"] = PREDEFINITE["reasoning"]
    return pulito


def leggi() -> dict:
    with LOCK:
        path = directory() / "preferenze.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (OSError, ValueError):
            value = {}
        if not isinstance(value, dict):
            value = {}
        if not isinstance(value.get("host_id"), str) or not value.get("host_id"):
            value["host_id"] = "urn:uuid:" + str(uuid.uuid4())
            scrivi_json(path, value)
        # "low": sulle pagine semplici il risultato è lo stesso e si risparmiano i token di ragionamento
        return _valide({**PREDEFINITE, **value})


def aggiorna(value: dict) -> dict:
    with LOCK:
        current = leggi()
        for name in (
            "model",
            "reasoning",
            "theme",
            "modello_mistral",
            "modello_deepseek",
            "update_checks",
            "update_prerelease",
            "dismissed_update",
        ):
            if name in value:
                current[name] = value[name]
        if current["theme"] not in ("system", "light", "dark"):
            raise ValueError("tema non valido")
        if current["reasoning"] not in ("", "low", "medium", "high"):
            raise ValueError("ragionamento non valido")
        if not isinstance(current["model"], str) or len(current["model"]) > 150:
            raise ValueError("modello non valido")
        scrivi_json(directory() / "preferenze.json", current)
        return current
