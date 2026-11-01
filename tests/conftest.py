import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True, scope="session")
def senza_account_ne_chiavi_vere():
    """I test non vedono mai account e chiavi del portachiavi di questo computer: un upload avvia l'analisi da sola,
    e con l'account collegato partirebbero chiamate vere sul piano dell'utente. Vale per tutta la sessione, non per il
    singolo test: un thread in sottofondo può finire dopo che il test ha ripristinato le sue sostituzioni."""
    from traccia import chatgpt, chiavi, ocr

    patch = pytest.MonkeyPatch()
    voci = {}

    class Portachiavi:
        def get_password(self, servizio, nome):
            return voci.get((servizio, nome))

        def set_password(self, servizio, nome, valore):
            voci[(servizio, nome)] = valore

        def delete_password(self, servizio, nome):
            voci.pop((servizio, nome), None)

    patch.setattr(chatgpt, "_vault", Portachiavi)
    patch.setattr(ocr, "_chiave", lambda: "")
    patch.setattr(chiavi, "chiave", lambda servizio: "")
    yield
    patch.undo()


@pytest.fixture(autouse=True)
def nessun_thread_oltre_il_test():
    """Preparazione e analisi girano in sottofondo: si aspetta che finiscano, così non finiscono dentro il test dopo."""
    yield
    fine = time.monotonic() + 30
    while time.monotonic() < fine and any(
        t.name == "agente-cantiere" or "prepare_job" in t.name for t in threading.enumerate()
    ):
        time.sleep(0.02)


@pytest.fixture(autouse=True)
def host_di_test(monkeypatch):
    """Il TestClient usa l'host "testserver": lo si ammette qui, non nel middleware di produzione (B6)."""
    from traccia import server

    monkeypatch.setattr(server, "HOST_CONSENTITI", server.HOST_CONSENTITI | {"testserver"})


@pytest.fixture
def radice(tmp_path, monkeypatch):
    from traccia import percorsi

    monkeypatch.setattr(percorsi, "RADICE", tmp_path)
    monkeypatch.setenv("TRACCIA_CONFIG", str(tmp_path / "config"))
    from traccia import configurazione

    configurazione.aggiorna({"update_checks": False})
    return tmp_path
