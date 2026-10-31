import httpx
import pytest

from traccia import chiavi
from traccia.chatgpt import AgentError


def test_modello_predefinito_e_scelto(radice):
    assert chiavi.modello("deepseek") == "deepseek-flash"
    assert chiavi.modello("mistral") == "mistral-ocr-latest"
    assert chiavi.imposta_modello("deepseek", "deepseek-pro")["modello"] == "deepseek-pro"
    assert chiavi.modello("deepseek") == "deepseek-pro"
    assert chiavi.imposta_modello("deepseek", "")["modello"] == "deepseek-flash"  # vuoto = predefinito
    with pytest.raises(AgentError):
        chiavi.imposta_modello("deepseek", "nome con spazi; e altro")
    with pytest.raises(AgentError):
        chiavi.stato("sconosciuto")


def test_chiave_rifiutata_non_si_salva(radice, monkeypatch):
    salvate = []

    class Vault:
        def set_password(self, *a):
            salvate.append(a)

    monkeypatch.setattr(chiavi, "_vault", lambda: Vault())
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(401))
    with pytest.raises(AgentError, match="non accetta"):
        chiavi.salva("deepseek", "sbagliata")
    assert salvate == []
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, json={"data": [{"id": "deepseek-flash"}]}))
    chiavi.salva("deepseek", "buona")
    assert salvate == [("tracciabilita-materiali.deepseek", "api_key", "buona")]
