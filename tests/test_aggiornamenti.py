import hashlib
import json
import stat
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import avvia
from traccia import VERSIONE_APP, configurazione, server
from traccia import aggiornamenti as upd


@pytest.fixture
def updates(radice, monkeypatch):
    monkeypatch.setattr(
        upd, "_state", {"busy": False, "checking": False, "message": "", "available": None, "checked_at": None}
    )
    return upd.directory()


def release(number="0.4.0"):
    repo = upd.metadata()["repository"]
    name = f"cantiere-link-{number}.zip"
    return {
        "tag_name": "v" + number,
        "draft": False,
        "prerelease": False,
        "body": "<script>untrusted</script>",
        "assets": [
            {
                "name": name,
                "state": "uploaded",
                "digest": "sha256:" + "a" * 64,
                "size": 500,
                "browser_download_url": f"https://github.com/{repo}/releases/download/v{number}/{name}",
            }
        ],
    }


def make_archive(path, extra=None):
    files = {
        "release.json": json.dumps(upd.metadata()).encode(),
        "pyproject.toml": b'[project]\nversion="0.4.0"\n',
        "requirements.txt": b"",
        "traccia/desktop.py": b"",
        "web/index.html": b"<!doctype html>",
        "avvia.py": b"",
        "LICENSE": b"MIT",
    }
    manifest = "\n".join(hashlib.sha256(data).hexdigest() + "  " + name for name, data in files.items()) + "\n"
    files["MANIFEST.sha256"] = manifest.encode()
    with zipfile.ZipFile(path, "w") as zipped:
        for name, data in files.items():
            zipped.writestr("cantiere-link-0.4.0/" + name, data)
        if extra:
            zipped.writestr(*extra)
    return {"version": "0.4.0", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": path.stat().st_size}


def wait_install():
    deadline = time.monotonic() + 5
    while upd.status()["busy"] and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not upd.status()["busy"]


def test_semantic_versions_and_release_identity(updates):
    assert upd.version("1.10.0") > upd.version("1.9.9")
    repo = upd.metadata()["repository"]
    parsed = upd.parse_release(release(), repo)
    assert parsed["version"] == "0.4.0"
    assert upd.parse_release(release(VERSIONE_APP), repo) is None
    assert upd.parse_release(release() | {"prerelease": True}, repo) is None
    bad = release()
    bad["assets"][0]["browser_download_url"] = "https://evil.invalid/release.zip"
    with pytest.raises(upd.UpdateError):
        upd.parse_release(bad, repo)
    bad = release()
    bad["assets"][0]["digest"] = None
    with pytest.raises(upd.UpdateError):
        upd.parse_release(bad, repo)
    with pytest.raises(upd.UpdateError):
        upd.version("v0.4.0-beta")


def test_disabled_checks_do_not_contact_github(updates, monkeypatch):
    monkeypatch.setattr(upd, "_fetch", lambda: pytest.fail("network not allowed"))
    assert not upd.check()["automatic"]


def test_daily_cache_manual_check_and_failure(updates, monkeypatch):
    calls = []

    def fetch():
        calls.append(1)
        return None, "Nessuna release"

    monkeypatch.setattr(upd, "_fetch", fetch)
    configurazione.aggiorna({"update_checks": True})
    upd.check()
    upd.check()
    assert len(calls) == 1
    upd.check(force=True)
    assert len(calls) == 2

    def offline():
        raise upd.UpdateError("Offline")

    monkeypatch.setattr(upd, "_fetch", offline)
    assert upd.check(force=True)["message"] == "Offline"
    assert not upd.pointer()["active"]


def test_extraction_manifest_and_package_identity(updates, tmp_path):
    archive = tmp_path / "release.zip"
    item = make_archive(archive)
    target = tmp_path / "extracted"
    target.mkdir()
    upd.extract(archive, target, item)
    assert (target / "web/index.html").is_file()
    assert not (target / ".venv").exists()
    corrupt = tmp_path / "corrupt.zip"
    make_archive(corrupt, ("cantiere-link-0.4.0/unlisted.py", b"print(1)"))
    with pytest.raises(upd.UpdateError):
        upd.extract(corrupt, tmp_path / "bad", item)


@pytest.mark.parametrize(
    "name",
    [
        "../escape.py",
        "cantiere-link-0.4.0/../../escape.py",
        "cantiere-link-0.4.0/C:/escape",
        "cantiere-link-0.4.0/.venv/x",
        "cantiere-link-0.4.0/lavori/secret.pdf",
        "cantiere-link-0.4.0/CON.txt",
        "cantiere-link-0.4.0/LICENSE.",
        "cantiere-link-0.4.0/license",
    ],
)
def test_archive_rejects_paths_and_windows_aliases(updates, tmp_path, name):
    archive = tmp_path / "release.zip"
    item = make_archive(archive, (name, b"bad"))
    with pytest.raises(upd.UpdateError):
        upd.extract(archive, tmp_path / "rejected", item)
    assert not (tmp_path / "escape.py").exists()


def test_symlink_rejected(updates, tmp_path):
    archive = tmp_path / "release.zip"
    make_archive(archive)
    with zipfile.ZipFile(archive, "a") as zipped:
        info = zipfile.ZipInfo("cantiere-link-0.4.0/link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zipped.writestr(info, "../../outside")
    with pytest.raises(upd.UpdateError):
        upd.extract(archive, tmp_path / "rejected", {"version": "0.4.0"})


def setup_install(monkeypatch, tmp_path):
    archive = tmp_path / "release.zip"
    item = make_archive(archive)
    monkeypatch.setattr(upd, "_fetch", lambda: (item, "available"))
    monkeypatch.setattr(upd, "_download", lambda value, path: path.write_bytes(archive.read_bytes()))
    return item


def test_install_activates_only_after_environment_ready_and_preserves_data(updates, tmp_path, monkeypatch):
    item = setup_install(monkeypatch, tmp_path)
    original = tmp_path / "lavori" / "documento.pdf"
    original.parent.mkdir()
    original.write_bytes(b"originale")

    def environment(path):
        assert not upd.pointer()["active"]
        assert (path / "web/index.html").exists()

    monkeypatch.setattr(upd, "_prepare_environment", environment)
    upd.install(item["version"])
    wait_install()
    assert upd.pointer()["active"]
    assert upd.status()["restart"]
    target = avvia.selected(folder=configurazione.directory())
    assert target.name == upd.pointer()["active"]
    assert original.read_bytes() == b"originale"
    upd.rollback()
    assert upd.pointer()["active"] is None
    assert avvia.selected(folder=configurazione.directory()) == avvia.BASE
    assert original.read_bytes() == b"originale"


def test_failed_environment_keeps_previous_version(updates, tmp_path, monkeypatch):
    item = setup_install(monkeypatch, tmp_path)

    def failure(path):
        raise OSError("pip failure")

    monkeypatch.setattr(upd, "_prepare_environment", failure)
    upd.install(item["version"])
    wait_install()
    assert upd.pointer()["active"] is None
    assert "non riuscita" in upd.status()["message"]
    assert not upd.status()["restart"]


def test_changed_release_requires_another_choice(updates, monkeypatch):
    monkeypatch.setattr(upd, "_fetch", lambda: ({"version": "0.5.0"}, "new"))
    monkeypatch.setattr(upd, "_download", lambda *args: pytest.fail("must not download a different version"))
    upd.install("0.4.0")
    wait_install()
    assert not upd.pointer()["active"]
    assert "cambiata" in upd.status()["message"]


def test_update_routes_csrf_and_busy_agent(updates, monkeypatch):
    client = TestClient(server.app)
    assert client.post("/api/aggiornamenti/installa", json={"version": "0.4.0"}).status_code == 403
    client.headers["X-Traccia-Token"] = client.get("/api/sessione").json()["token"]
    monkeypatch.setattr(server.agente, "stato", lambda: {"busy": True})
    assert client.post("/api/aggiornamenti/installa", json={"version": "0.4.0"}).status_code == 409
    assert (
        client.put("/api/aggiornamenti/preferenze", json={"automatic": False, "dismissed": "0.4.0"}).status_code == 200
    )
    assert client.get("/api/aggiornamenti").json()["dismissed"] == "0.4.0"
    assert client.get("/guida/").status_code == 200
    assert client.get("/guida/guide.js").status_code == 200
    assert client.get("/LICENSE").status_code == 200


def test_bootstrap_rejects_pointer_outside_installations(updates):
    configurazione.scrivi_json(updates / "attiva.json", {"active": "../../outside"})
    with pytest.raises(ValueError):
        avvia.selected(folder=configurazione.directory())


def test_native_installer_selects_platform_asset(updates, monkeypatch):
    monkeypatch.setattr(upd.sys, "frozen", True, raising=False)
    monkeypatch.setattr(upd.sys, "platform", "win32")
    assert upd.asset_name("0.4.0") == "CantiereLink-Setup-0.4.0.exe"
    item = release()
    asset = item["assets"][0]
    asset["name"] = "CantiereLink-Setup-0.4.0.exe"
    asset["browser_download_url"] = (
        f"https://github.com/{upd.metadata()['repository']}/releases/download/v0.4.0/{asset['name']}"
    )
    assert upd.parse_release(item, upd.metadata()["repository"])["filename"].endswith(".exe")
    monkeypatch.setattr(upd.sys, "platform", "darwin")
    monkeypatch.setattr(upd.platform, "machine", lambda: "arm64")
    assert upd.asset_name("0.4.0") == "CantiereLink-0.4.0-macos-arm64.dmg"


def test_native_download_never_runs_installer_without_second_action(updates, tmp_path, monkeypatch):
    monkeypatch.setattr(upd.sys, "frozen", True, raising=False)
    monkeypatch.setattr(upd.sys, "platform", "win32")
    content = b"test installer, never executable"
    item = {
        "version": "0.4.0",
        "filename": "CantiereLink-Setup-0.4.0.exe",
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    monkeypatch.setattr(upd, "_fetch", lambda: (item, "new"))
    monkeypatch.setattr(upd, "_download", lambda value, path: path.write_bytes(content))
    calls = []
    monkeypatch.setattr(upd.os, "startfile", lambda path: calls.append(path), raising=False)
    upd.install("0.4.0")
    wait_install()
    assert calls == []
    assert upd.status()["installer_ready"]
    upd.open_installer()
    assert len(calls) == 1
    Path(calls[0]).write_bytes(b"changed")
    with pytest.raises(upd.UpdateError):
        upd.open_installer()
    assert len(calls) == 1
