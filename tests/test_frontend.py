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


def test_un_solo_timer_di_poll_con_backoff():
    app, cantiere = _testo("app.js"), _testo("cantiere.js")
    assert "setInterval(" not in app and "setInterval(" not in cantiere
    assert "visibilitychange" in app and "document.hidden" in app


def test_u1_a_lavoro_finito_i_risultati_salgono_e_la_lettura_si_ripiega():
    """U1: a fase "pronto" la vista di lettura si nasconde/ripiega sotto i risultati, niente residui di animazione."""
    html, cantiere = _testo("index.html"), _testo("cantiere.js")
    assert '<details class="flow-details" id="dettagli"' in html
    assert ".finito .look{display:none}" in html and ".finito .flow-details{order:3}" in html
    assert 'classList.toggle("finito",' in cantiere and '$("dettagli").open=false' in cantiere
    assert "Rileggi pagine mancanti" in cantiere and 'ab.classList.toggle("s",finito)' in cantiere
    assert 'querySelectorAll(".flyer").forEach(f=>f.remove())' in cantiere
    assert 'stato.fase==="pronto"||document.hidden){metti(x);return}' in cantiere


def test_u2_tabella_e_catena_scorrono_dentro_il_contenitore_con_ombra():
    html = _testo("index.html")
    assert 'class="card chain scrollx" tabindex="0"' in html and 'class="card tabwrap scrollx" tabindex="0"' in html
    regola = re.search(r"\.scrollx\{([^}]*)\}", html).group(1)
    assert "overflow-x:auto" in regola and "background-attachment:local,local,scroll,scroll" in regola
    assert "--scroll-shadow" in regola and "--scroll-shadow:" in _testo("app.css")  # anche nel tema scuro


def test_u4_sezione_da_verificare_con_motivi_e_domanda_pronta():
    html, cantiere, app = _testo("index.html"), _testo("cantiere.js"), _testo("app.js")
    assert html.index('id="verifica-card"') < html.index("<h2>Collegamenti a ritroso</h2>")
    assert 'v.stato==="DA CONFERMARE"||v.stato==="MANCANTE"' in cantiere
    assert 'data-act="ask-about"' in cantiere and 'data-act="goto-row"' in cantiere and "v.note.join" in cantiere
    assert "Nessuna voce da verificare" in cantiere
    # la domanda viene scritta nella casella, mai inviata da sola
    riga_ask_about = app.split("function askAbout")[1].split("\n")[0]
    assert "$('question').value=el.dataset.text" in riga_ask_about and "ask(" not in riga_ask_about


def test_u6_chat_chiusa_all_avvio_a_ogni_larghezza():
    app = _testo("app.js")
    assert "innerWidth<=800)toggleChat(false)" not in app
    assert re.search(r"route\(\);toggleChat\(false\);", app)


def test_u7_anteprima_nome_file_e_scheda_si_riferiscono_alla_stessa_pagina():
    cantiere = _testo("cantiere.js")
    assert "function nomePagina(pid,testo)" in cantiere
    scheda = re.search(r'if\(e\.tipo==="scheda"&&e\.pid\)\{(.*?)\}\n', cantiere).group(1)
    assert "mostraPagina(e.pid,true)" in scheda and '$("lookfile").textContent="Letta: "+nomePagina(e.pid)' in scheda
    assert 'if(finito)$("lookfile").textContent=`Lettura completata' in cantiere
    assert "guarda /" not in cantiere and "Sta guardando" not in cantiere


def test_u8_etichette_agente_e_bottone_di_lettura():
    app, cantiere, html = _testo("app.js"), _testo("cantiere.js"), _testo("index.html")
    assert "'Agente fermo'" in app and "'Da verificare'" not in app and "'Ferma'" not in app
    assert 'stato.lette?"Riprendi lettura":"Avvia lettura"' in cantiere
    for nome in ("index.html", "app.js", "cantiere.js"):
        assert "Analizza / riprendi" not in _testo(nome), nome
    assert ">Avvia lettura</button>" in html
    from traccia import agente, uscita

    for modulo in (agente, uscita):
        assert "Analizza / riprendi" not in (
            percorsi.CODICE / "traccia" / f"{modulo.__name__.split('.')[-1]}.py"
        ).read_text(encoding="utf-8")


def test_u11_icone_svg_al_posto_dei_glifi_unicode():
    html, app = _testo("index.html"), _testo("app.js")
    for glifo in "◐◎✧⌘⌁↻⏻⚙＋↶⌄":
        assert glifo not in html, glifo
        assert glifo not in app, glifo
    assert 'data-act="home">T</div>' not in html and 'href="#ic-link"' in html
    for icona in (
        "ic-gear",
        "ic-plus",
        "ic-history",
        "ic-chevron",
        "ic-send",
        "ic-general",
        "ic-account",
        "ic-models",
        "ic-keys",
        "ic-diag",
        "ic-update",
        "ic-power",
    ):
        assert f'<symbol id="{icona}"' in html and f'href="#{icona}"' in html + app, icona


def test_u12_tastiera_progressbar_e_dialog_nativo():
    html, cantiere, app = _testo("index.html"), _testo("cantiere.js"), _testo("app.js")
    assert (
        'role="progressbar" aria-label="Avanzamento del lavoro"' in html
        and '$("prog").setAttribute("aria-valuenow",p)' in cantiere
    )
    assert '<dialog class="modal" id="modal" aria-labelledby="mtitle">' in html
    assert "m.showModal()" in cantiere and '$("modal").classList' not in cantiere and "$('modal').classList" not in app
    assert '<div class="card lav" role="button" tabindex="0"' in cantiere
    assert '<button type="button" class="card bin"' in cantiere and '<button type="button" class="pg"' in cantiere
    assert cantiere.count('role="button" tabindex="0" data-act="open-proof"') == 3  # catena, tabella, ritagli
    assert "e.target.matches('[data-act][role=\"button\"]')" in app and "e.target.click()" in app


def test_u14_nessun_font_dichiarato_e_mai_caricato():
    for nome in ("index.html", "app.css"):
        assert not re.search(r"\bInter\b", _testo(nome)), nome
    assert not re.search(r"\bInter\b", (percorsi.CODICE / "docs" / "guide.css").read_text(encoding="utf-8"))
