"""Transizioni dell'agente: errore di lotto = "errore", solo stop() = "interrotta". Registro degli errori su file."""

import time

import pytest
from fastapi.testclient import TestClient
from test_flusso import _crea_lavoro

from traccia import agente, chatgpt, registro, server


@pytest.fixture
def pronto(radice, monkeypatch):
    directory, _ = _crea_lavoro(radice)
    monkeypatch.setattr(agente, "_options", lambda: ("test-model", ""))
    monkeypatch.setattr(chatgpt, "status", lambda: {"plan_enabled": True})
    monkeypatch.setattr(agente, "_state", {**agente._state, "busy": False, "error": False, "stopped": False})
    agente._cancel.clear()
    agente._stop_richiesto.clear()
    return directory


def _attendi_fine():
    for _ in range(200):
        if not agente.stato()["busy"]:
            return agente.stato()
        time.sleep(0.05)
    pytest.fail("agente ancora occupato")


def test_errore_di_un_lotto_e_errore_non_interruzione(pronto, monkeypatch):
    def respond(*_args, **_kwargs):
        raise RuntimeError("rete caduta")

    monkeypatch.setattr(chatgpt, "response", respond)
    registro.configura()
    agente.avvia(pronto)
    stato = _attendi_fine()
    assert stato["error"] is True and stato["stopped"] is False
    assert "non completata" in stato["message"]
    testo = registro.percorso().read_text(encoding="utf-8")
    assert "RuntimeError: rete caduta" in testo and pronto.name in testo


def test_stop_dell_utente_e_interruzione_non_errore(pronto, monkeypatch):
    def respond(*_args, **_kwargs):
        agente.stop()
        raise chatgpt.AgentError("Operazione interrotta.")

    monkeypatch.setattr(chatgpt, "response", respond)
    agente.avvia(pronto)
    stato = _attendi_fine()
    assert stato["stopped"] is True and stato["error"] is False and stato["stopping"] is False


def test_impostazioni_espongono_il_percorso_del_registro(radice):
    client = TestClient(server.app)
    assert client.get("/api/impostazioni").json()["registro"].endswith("app.log")
