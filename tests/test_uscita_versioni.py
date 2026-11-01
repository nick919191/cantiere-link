"""componi: niente cartelle .uscita-* residue, massimo 10 versioni conservate, Excel aperto segnalato (M7)."""

import pathlib
import time

import pytest
from test_flusso import _crea_lavoro, _leggi_tutto

from traccia import agente, chatgpt, uscita
from traccia.uscita import componi


@pytest.fixture
def letto(radice):
    cartella, schede = _crea_lavoro(radice)
    _leggi_tutto(cartella, schede)
    return cartella


def _provvisorie(cartella):
    return [p.name for p in cartella.iterdir() if p.name.startswith(".uscita-")]


def test_errore_durante_la_composizione_non_lascia_cartelle_provvisorie(letto, monkeypatch):
    def rotto(*_args, **_kwargs):
        raise OSError("disco pieno")

    monkeypatch.setattr(uscita, "scrivi", rotto)
    with pytest.raises(OSError):
        componi(letto)
    assert _provvisorie(letto) == [] and not (letto / "uscita").exists()


def test_versioni_conservate_al_massimo(letto, monkeypatch):
    monkeypatch.setattr(uscita, "VERSIONI_CONSERVATE", 2)
    for _ in range(5):
        componi(letto)
        time.sleep(0.01)
    versioni = sorted(p.name for p in (letto / "versioni").iterdir())
    assert len(versioni) == 2 and all(len(v) == 16 + 8 for v in versioni)  # nomi ordinabili per data
    assert (letto / "uscita" / "tracciabilita.xlsx").exists() and _provvisorie(letto) == []


def test_excel_aperto_da_messaggio_chiaro(letto, monkeypatch):
    componi(letto)
    vero = pathlib.Path.rename

    def bloccato(self, target):
        if self.name == "uscita":
            raise PermissionError(32, "file in uso da un altro processo")
        return vero(self, target)

    monkeypatch.setattr(pathlib.Path, "rename", bloccato)
    with pytest.raises(uscita.ExcelAperto, match="Chiudi l’Excel"):
        componi(letto)
    assert _provvisorie(letto) == [] and (letto / "uscita" / "tracciabilita.xlsx").exists()

    # l'agente mostra quel messaggio all'utente invece di "Operazione non completata"
    monkeypatch.setattr(agente, "_options", lambda: ("m", ""))
    monkeypatch.setattr(chatgpt, "status", lambda: {"plan_enabled": True})
    monkeypatch.setattr(agente, "_state", {**agente._state, "busy": False})
    monkeypatch.setattr(
        agente, "componi", lambda _c: (_ for _ in ()).throw(uscita.ExcelAperto("Chiudi l’Excel aperto"))
    )
    agente.avvia(letto)
    for _ in range(100):
        if not agente.stato()["busy"]:
            break
        time.sleep(0.05)
    assert "Chiudi l’Excel" in agente.stato()["message"] and agente.stato()["error"]
