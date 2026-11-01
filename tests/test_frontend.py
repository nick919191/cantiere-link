"""Controlli statici sull'interfaccia: nessun handler inline (CSP) e azioni dichiarate coerenti."""

import re
import shutil
import subprocess

import pytest

from traccia import percorsi

WEB = percorsi.WEB
SORGENTI = ["index.html", "app.js", "cantiere.js"]


def _testo(nome):
    return (WEB / nome).read_text(encoding="utf-8")


def test_nessun_handler_inline_ne_script_inline():
    for nome in SORGENTI:
        testo = _testo(nome)
        assert not re.search(r"\son(click|change|input|load|error|keydown)=", testo), nome
    assert not re.search(r"<script(?![^>]*\ssrc=)[^>]*>", _testo("index.html"))


def test_le_azioni_usate_sono_tutte_dichiarate():
    app = _testo("app.js")
    blocco = {}
    for nome in ("AZIONI", "CAMBI", "INPUT"):
        corpo = re.search(rf"const {nome}=\{{(.*?)\}};\n", app, re.S).group(1)
        blocco[nome] = set(re.findall(r"(?:^|[\s{,])'?([\w-]+)'?:", corpo))
    usate = {"data-act": set(), "data-change": set(), "data-input": set()}
    for nome in SORGENTI:
        for attributo, valore in re.findall(r'(data-act|data-change|data-input)="([\w-]+)"', _testo(nome)):
            usate[attributo].add(valore)
    assert usate["data-act"] <= blocco["AZIONI"], usate["data-act"] - blocco["AZIONI"]
    assert usate["data-change"] <= blocco["CAMBI"], usate["data-change"] - blocco["CAMBI"]
    assert usate["data-input"] <= blocco["INPUT"], usate["data-input"] - blocco["INPUT"]
    # i select delle impostazioni passano il nome dell'azione come parametro
    for azione in re.findall(r"selectSetting\([^)]*?,'([\w-]+)'\)", app):
        assert azione in blocco["CAMBI"], azione


def test_apostrofo_nel_titolo_della_prova_non_rompe_il_markup():
    """Il titolo "PARTE D'OPERA · voce 1" va in un attributo data-*, con l'apostrofo escapato (bug M9/U3)."""
    cantiere = _testo("cantiere.js")
    assert 'data-title="${esc(c)} · voce ${v.n}"' in cantiere
    assert "apri('${u}'" not in cantiere


@pytest.mark.skipif(shutil.which("node") is None, reason="node non disponibile")
def test_sintassi_javascript():
    for nome in ("app.js", "cantiere.js"):
        subprocess.run(["node", "--check", str(WEB / nome)], check=True)
