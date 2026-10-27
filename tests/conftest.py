import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def radice(tmp_path, monkeypatch):
    from traccia import percorsi

    monkeypatch.setattr(percorsi, "RADICE", tmp_path)
    monkeypatch.setenv("TRACCIA_CONFIG", str(tmp_path / "config"))
    from traccia import configurazione

    configurazione.aggiorna({"update_checks": False})
    return tmp_path
