"""Dipendenze con hash, updater e avvio con --require-hashes, workflow pinnati (S1, S4, S5)."""

import re
import tomllib

import avvia
from traccia import aggiornamenti as upd
from traccia import percorsi

WORKFLOWS = percorsi.CODICE / ".github" / "workflows"


def test_lockfile_con_hash_copre_tutte_le_dipendenze_dichiarate():
    lock = (percorsi.CODICE / "requirements.lock").read_text(encoding="utf-8")
    pacchetti = re.findall(r"^([a-z0-9][a-z0-9._-]*)==", lock, re.M)
    assert len(pacchetti) >= 20
    for nome in pacchetti:
        blocco = re.search(rf"^{re.escape(nome)}==.*?(?=^\S|\Z)", lock, re.M | re.S).group(0)
        assert "--hash=sha256:" in blocco, nome
    dichiarate = re.findall(r"^([A-Za-z0-9_.-]+)", (percorsi.CODICE / "requirements.txt").read_text("utf-8"), re.M)
    normalizzati = {p.replace("_", "-").lower() for p in pacchetti}
    assert {d.lower() for d in dichiarate} <= normalizzati
    progetto = tomllib.loads((percorsi.CODICE / "pyproject.toml").read_text(encoding="utf-8"))
    nomi_pyproject = {re.match(r"[A-Za-z0-9_.-]+", d).group(0).lower() for d in progetto["project"]["dependencies"]}
    assert {d.lower() for d in dichiarate} == nomi_pyproject  # pywebview incluso: i due elenchi coincidono


def _spia(monkeypatch, modulo):
    comandi = []

    def run(command, *_args, **_kwargs):
        comandi.append(command)

    monkeypatch.setattr(modulo.subprocess, "run", run)
    return comandi


def test_avvio_e_updater_installano_dal_lockfile_con_hash(tmp_path, monkeypatch):
    radice = tmp_path / "versione"
    (radice / ".venv" / "Scripts").mkdir(parents=True)
    (radice / ".venv" / "bin").mkdir()
    (radice / ".venv" / "Scripts" / "python.exe").write_bytes(b"")
    (radice / ".venv" / "bin" / "python").write_bytes(b"")
    (radice / "requirements.txt").write_text("fastapi>=0.115\n", encoding="utf-8")
    (radice / "requirements.lock").write_text("fastapi==0.162.0 --hash=sha256:aa\n", encoding="utf-8")

    comandi = _spia(monkeypatch, avvia)
    avvia.prepare(radice)
    (install,) = [c for c in comandi if "install" in c]
    assert "--require-hashes" in install and str(radice / "requirements.lock") in install
    assert "requirements.txt" not in " ".join(install)
    stamp = (radice / ".venv" / "requirements.sha256").read_text(encoding="utf-8")
    assert stamp == avvia.hashlib.sha256((radice / "requirements.lock").read_bytes()).hexdigest()
    comandi.clear()
    avvia.prepare(radice)
    assert comandi == []  # lockfile invariato: nessuna reinstallazione

    comandi = _spia(monkeypatch, upd)
    upd._prepare_environment(radice)
    (install,) = [c for c in comandi if "install" in c]
    assert "--require-hashes" in install and str(radice / "requirements.lock") in install

    # senza lockfile (release precedente) si torna a requirements.txt
    (radice / "requirements.lock").unlink()
    comandi.clear()
    upd._prepare_environment(radice)
    (install,) = [c for c in comandi if "install" in c]
    assert "--require-hashes" not in install and str(radice / "requirements.txt") in install


def test_workflow_pinnati_a_sha_con_permessi_minimi_e_versioni_fisse():
    for workflow in WORKFLOWS.glob("*.yml"):
        testo = workflow.read_text(encoding="utf-8")
        assert re.search(r"^permissions:\n  contents: read", testo, re.M), workflow.name
        usi = re.findall(r"uses:\s*(\S+)", testo)
        assert usi and all(re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", u) for u in usi), (workflow.name, usi)
        assert "--require-hashes -r requirements.lock" in testo, workflow.name
    installers = (WORKFLOWS / "installers.yml").read_text(encoding="utf-8")
    assert re.search(r"pyinstaller==\d+\.\d+\.\d+", installers) and "innosetup --version=" in installers
    assert "pip_audit" in (WORKFLOWS / "test.yml").read_text(encoding="utf-8")
    assert '"requirements.lock",' in (percorsi.CODICE / "tools" / "package_release.py").read_text(encoding="utf-8")
    assert (percorsi.CODICE / "docs" / "FIRMA-RELEASE.md").exists()
