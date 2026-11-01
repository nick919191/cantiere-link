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
    """Titoli e nomi dei file vanno in un attributo data-*, con l'apostrofo escapato (bug M9/U3)."""
    cantiere = _testo("cantiere.js")
    assert 'data-nome="${esc(corto(d.file))}"' in cantiere and 'data-title="Ritaglio: ${esc(e.testo)}"' in cantiere
    assert "apriOriginale('" not in cantiere and "apri('" not in cantiere


@pytest.mark.skipif(shutil.which("node") is None, reason="node non disponibile")
def test_sintassi_javascript():
    for nome in ("app.js", "cantiere.js"):
        subprocess.run(["node", "--check", str(WEB / nome)], check=True)


def test_un_solo_timer_di_poll_con_backoff():
    app, cantiere = _testo("app.js"), _testo("cantiere.js")
    assert "setInterval(" not in app and "setInterval(" not in cantiere
    assert "visibilitychange" in app and "document.hidden" in app


def test_u2_tabella_scorre_dentro_il_contenitore_con_ombra():
    html = _testo("index.html")
    assert 'class="card tabwrap scrollx" tabindex="0"' in html
    regola = re.search(r"\.scrollx\{([^}]*)\}", html).group(1)
    assert "overflow-x:auto" in regola and "background-attachment:local,local,scroll,scroll" in regola
    assert "--scroll-shadow" in regola and "--scroll-shadow:" in _testo("app.css")  # anche nel tema scuro


def test_u7_nome_del_file_e_scheda_si_riferiscono_alla_stessa_pagina():
    cantiere = _testo("cantiere.js")
    assert "function nomePagina(pid,testo)" in cantiere
    assert '$("lookfile").textContent=(e.tipo==="scheda"?"Letta: ":"")+nomePagina(e.pid,e.testo)' in cantiere


def test_u8_etichette_agente():
    app = _testo("app.js")
    assert "'Errore'" in app and "'Da verificare'" not in app
    for nome in ("index.html", "app.js", "cantiere.js"):
        assert "Analizza / riprendi" not in _testo(nome), nome


def test_u10_cantiere_senza_pagine_leggibili_mostra_il_motivo():
    cantiere = _testo("cantiere.js")
    assert 'if(l.fase==="errore")return [l.motivo||"Nessuna pagina leggibile","r"]' in cantiere
    assert 'errore:stato.motivo||"Nessuna pagina leggibile"' in cantiere


def test_u11_icone_svg_al_posto_dei_glifi_unicode():
    html, app = _testo("index.html"), _testo("app.js")
    for glifo in "◐◎⌁↻⏻⚙＋⇄":
        assert glifo not in html, glifo
        assert glifo not in app, glifo
    assert 'data-act="home">T</div>' not in html and 'href="#ic-link"' in html
    for icona in ("ic-gear", "ic-plus", "ic-general", "ic-account", "ic-diag", "ic-update", "ic-power"):
        assert f'<symbol id="{icona}"' in html and f'href="#{icona}"' in html + app, icona


def test_u12_tastiera_progressbar_e_dialog_nativo():
    html, cantiere, app = _testo("index.html"), _testo("cantiere.js"), _testo("app.js")
    assert 'role="progressbar" aria-label="Avanzamento del lavoro"' in html
    assert '$("prog").setAttribute("aria-valuenow",p)' in cantiere
    assert '<dialog class="modal" id="modal" aria-labelledby="mtitle">' in html
    assert "m.showModal()" in cantiere and '$("modal").classList' not in cantiere and "$('modal').classList" not in app
    assert '<tr class="lav" role="button" tabindex="0"' in cantiere
    assert '<button type="button" class="card bin"' in cantiere and '<button type="button" class="pg"' in cantiere
    assert 'role="button" tabindex="0" data-act="open-proof"' in cantiere
    assert 'role="button" tabindex="0" data-act="view-page"' in cantiere
    assert '<td class="cella" tabindex="0"' in cantiere
    assert "e.target.matches('[data-act][role=\"button\"]')" in app and "e.target.click()" in app


def test_u14_nessun_font_dichiarato_e_mai_caricato():
    for nome in ("index.html", "app.css"):
        assert not re.search(r"\bInter\b", _testo(nome)), nome
    assert not re.search(r"\bInter\b", (percorsi.CODICE / "docs" / "guide.css").read_text(encoding="utf-8"))
