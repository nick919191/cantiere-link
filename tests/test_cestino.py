import pytest
from fastapi.testclient import TestClient
from test_flusso import _crea_lavoro as create_fixture

from traccia import cestino, server


def _crea_lavoro(radice):
    directory, schemas = create_fixture(radice)
    (directory / "info.json").write_text('{"nome":"Cantiere sintetico"}', encoding="utf-8")
    return directory, schemas


def test_trash_preserves_files_and_restores(radice):
    directory, _ = _crea_lavoro(radice)
    before = {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    entry = cestino.sposta(directory.name)
    assert not directory.exists()
    assert cestino.elenco()[0]["id"] == entry["id"]
    assert {
        p.relative_to(radice / "cestino" / entry["id"] / "contenuto").as_posix(): p.read_bytes()
        for p in (radice / "cestino" / entry["id"] / "contenuto").rglob("*")
        if p.is_file()
    } == before
    cestino.ripristina(entry["id"])
    assert cestino.elenco() == []
    assert {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob("*") if p.is_file()} == before


def test_trash_does_not_overwrite_another_job(radice):
    directory, _ = _crea_lavoro(radice)
    entry = cestino.sposta(directory.name)
    directory.mkdir()
    sentinel = directory / "info.json"
    sentinel.write_text("keep")
    with pytest.raises(ValueError):
        cestino.ripristina(entry["id"])
    assert sentinel.read_text() == "keep"
    assert cestino.elenco()


def test_trash_rejects_traversal(radice):
    for path in ("../outside", "C:/outside", "..", ""):
        with pytest.raises(ValueError):
            cestino.sposta(path)
        with pytest.raises(ValueError):
            cestino.ripristina(path)


def test_trash_api_protects_busy_jobs_and_csrf(radice, monkeypatch):
    directory, _ = _crea_lavoro(radice)
    client = TestClient(server.app)
    assert client.delete("/api/lavori/prova").status_code == 403
    client.headers["X-Traccia-Token"] = client.get("/api/sessione").json()["token"]
    monkeypatch.setattr(server.agente, "stato", lambda: {"busy": True, "job": "prova"})
    assert client.delete("/api/lavori/prova").status_code == 409
    assert directory.exists()
    monkeypatch.setattr(server.agente, "stato", lambda: {"busy": False})
    server._PREPARING.add("prova")
    try:
        assert client.delete("/api/lavori/prova").status_code == 409
    finally:
        server._PREPARING.discard("prova")
    moved = client.delete("/api/lavori/prova")
    assert moved.status_code == 200
    assert client.get("/api/lavori").json() == []
    assert client.post("/api/cestino/" + moved.json()["id"] + "/ripristina").status_code == 200
    assert directory.exists()


def test_trash_allowed_while_agent_works_on_another_job(radice, monkeypatch):
    directory, _ = _crea_lavoro(radice)
    client = TestClient(server.app)
    client.headers["X-Traccia-Token"] = client.get("/api/sessione").json()["token"]
    monkeypatch.setattr(server.agente, "stato", lambda: {"busy": True, "job": "altro-cantiere"})
    assert client.delete("/api/lavori/prova").status_code == 200
    assert not directory.exists()
