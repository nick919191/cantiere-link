"""Chiavi API dei servizi di lettura (Mistral, DeepSeek) e modello scelto per ciascuno.

Le chiavi stanno solo nel portachiavi di sistema, mai nel progetto, nelle preferenze o nel browser. Il modello sta
nelle preferenze: chi scarica l'app parte dal modello predefinito e può cambiarlo nelle impostazioni.
"""

import re

import httpx
import keyring

from . import configurazione
from .chatgpt import AgentError

SERVIZI = {
    "mistral": {
        "nome": "Mistral",
        "portachiavi": "tracciabilita-materiali.mistral",  # nome storico: le chiavi già salvate restano valide
        "modelli": "https://api.mistral.ai/v1/models",
        "predefinito": "mistral-ocr-latest",
        "console": "console.mistral.ai",
    },
    "deepseek": {
        "nome": "DeepSeek",
        "portachiavi": "tracciabilita-materiali.deepseek",
        "modelli": "https://api.deepseek.com/models",
        "predefinito": "deepseek-flash",
        "console": "platform.deepseek.com",
    },
}
NOME_MODELLO = re.compile(r"^[\w.:/-]{1,100}$")


def _servizio(servizio: str) -> dict:
    if servizio not in SERVIZI:
        raise AgentError("Servizio sconosciuto.")
    return SERVIZI[servizio]


def _vault():
    backend = keyring.get_keyring()
    if not type(backend).__module__.startswith(
        ("keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.SecretService")
    ):
        raise AgentError("Portachiavi sicuro non disponibile. Abilita il portachiavi del sistema e riprova.")
    return backend


def chiave(servizio: str) -> str:
    try:
        return _vault().get_password(_servizio(servizio)["portachiavi"], "api_key") or ""
    except AgentError:
        return ""


def configurato(servizio: str) -> bool:
    return bool(chiave(servizio))


def modello(servizio: str) -> str:
    """Modello scelto nelle impostazioni, oppure quello predefinito."""
    scelto = configurazione.leggi().get(f"modello_{servizio}", "")
    return scelto or _servizio(servizio)["predefinito"]


def stato(servizio: str) -> dict:
    s = _servizio(servizio)
    return {
        "servizio": servizio,
        "configurato": configurato(servizio),
        "modello": modello(servizio),
        "predefinito": s["predefinito"],
    }


def _modelli_disponibili(servizio: str, valore: str) -> list[str]:
    """Elenco dei modelli del servizio con questa chiave; errore chiaro se la chiave non va."""
    s = _servizio(servizio)
    try:
        r = httpx.get(s["modelli"], headers={"Authorization": "Bearer " + valore}, timeout=20)
    except httpx.HTTPError as exc:
        raise AgentError(f"{s['nome']} non raggiungibile: controlla la connessione e riprova.") from exc
    if r.status_code in (401, 403):
        raise AgentError(f"{s['nome']} non accetta questa chiave. Controllala su {s['console']}.")
    if r.status_code != 200:
        raise AgentError(f"{s['nome']} ha risposto con un errore ({r.status_code}). Riprova più tardi.")
    try:
        return [m.get("id", "") for m in r.json().get("data", []) if isinstance(m, dict)]
    except ValueError:
        return []


def salva(servizio: str, valore: str) -> dict:
    """Controlla la chiave con il servizio prima di salvarla: una chiave sbagliata non entra nel portachiavi."""
    valore = valore.strip()
    if not valore:
        raise AgentError(f"Inserisci la chiave {_servizio(servizio)['nome']}.")
    _modelli_disponibili(servizio, valore)
    _vault().set_password(_servizio(servizio)["portachiavi"], "api_key", valore)
    return stato(servizio)


def rimuovi(servizio: str) -> dict:
    try:
        _vault().delete_password(_servizio(servizio)["portachiavi"], "api_key")
    except keyring.errors.PasswordDeleteError:
        pass
    return stato(servizio)


def prova(servizio: str) -> dict:
    """Prova la chiave salvata e dice se il modello scelto è nell'elenco del servizio."""
    valore = chiave(servizio)
    if not valore:
        raise AgentError(f"Nessuna chiave {_servizio(servizio)['nome']} salvata.")
    disponibili = _modelli_disponibili(servizio, valore)
    scelto = modello(servizio)
    return stato(servizio) | {
        "ok": True,
        "modello_trovato": scelto in disponibili if disponibili else None,
        "modelli": sorted(m for m in disponibili if m)[:60],
    }


def imposta_modello(servizio: str, nome: str) -> dict:
    """Vuoto = torna al modello predefinito."""
    _servizio(servizio)
    nome = (nome or "").strip()
    if nome and not NOME_MODELLO.match(nome):
        raise AgentError("Nome del modello non valido: solo lettere, numeri e . : / - _")
    configurazione.aggiorna({f"modello_{servizio}": nome})
    return stato(servizio)
