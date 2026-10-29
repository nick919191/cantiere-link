import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def senza_chiave_mistral(monkeypatch):
    """I test non usano mai la chiave Mistral del portachiavi di questo computer: con la chiave
    l'agente passerebbe alla lettura veloce e farebbe chiamate vere a pagamento."""
    from traccia import ocr

    monkeypatch.setattr(ocr, "_chiave", lambda: "")


@pytest.fixture
def radice(tmp_path, monkeypatch):
    from traccia import percorsi

    monkeypatch.setattr(percorsi, "RADICE", tmp_path)
    monkeypatch.setenv("TRACCIA_CONFIG", str(tmp_path / "config"))
    from traccia import configurazione

    configurazione.aggiorna({"update_checks": False})
    return tmp_path
