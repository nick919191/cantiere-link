"""Build an offline, standalone demo using the application's current markup and CSS."""
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
source = (HERE / "original-app.html").read_text(encoding="utf-8")
css = re.search(r"<style>(.*?)</style>", source, re.S).group(1)
symbols = source.split('<svg width="0"', 1)[1].split('</defs></svg>', 1)[0]
symbols = '<svg width="0"' + symbols + '</defs></svg>'
app = source.split('<div class="app">', 1)[1].split('<button class="btn fab', 1)[0]
app = '<div class="app">' + app
app = app.replace('Che cosa sta guardando Claude', 'Il documento in esame')
app = app.replace('Nessuna attività da qualche minuto: controlla che la finestra di Claude Code con <b>/avvia</b> sia aperta.', 'L’agente è in pausa.')
app = app.replace('<div class="sp"></div>\n  </div>', '<div class="sp"></div><span class="pill b">DEMO LOCALE</span><button class="icon-button" onclick="openSettings()" aria-label="Impostazioni">⚙</button><button class="icon-button" onclick="toggleChat()" aria-label="Apri o chiudi chat"><svg class="ic"><use href="#ic-chat"/></svg></button>\n  </div>', 1)
app = app.replace('L\'Excel è pronto', 'La tracciabilità è pronta')
app = app.replace('Scarica Excel e prove', 'Esporta tabella demo')
app = app.replace('Documenti riordinati e rinominati', 'Esplora documenti')
app = app.replace('ogni dato ha il collegamento alla pagina da cui viene.', 'dati sintetici per esplorare il flusso.')
app = app.replace('Lettura e riconoscimento sono automatici e possono contenere errori. Verifica sempre l\'Excel con i documenti originali.', 'Dati e risposte dimostrativi. Nell’app, verifica sempre i risultati con i documenti originali.')
app = app.replace('<h2 style="margin-top:34px">I tuoi lavori</h2>', '<div class="note">La demo mostra solo i nomi dei file selezionati: non li legge e non li invia.</div><h2 style="margin-top:34px">I tuoi lavori</h2>')
app = app.replace('<div class="card look">', '<div class="card look"><div class="document-tools"><span class="pill n">FACSIMILE</span><button class="text-button" onclick="openSource(activeDocument)">Apri pagina ↗</button></div>')
app = app.replace('<div class="res hidden" id="res">', '<div class="res hidden" id="res">')
template = (HERE / "shell.html").read_text(encoding="utf-8")
script = (HERE / "demo.js").read_text(encoding="utf-8")
extra_css = (HERE / "demo.css").read_text(encoding="utf-8")
output = ('<!doctype html>\n<html lang="it"><head><meta charset="utf-8">'
          '<meta name="viewport" content="width=device-width,initial-scale=1">'
          '<meta name="color-scheme" content="light dark">'
          '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data: blob:; connect-src \'none\'; font-src \'none\'; object-src \'none\'; base-uri \'none\'; form-action \'none\'">'
          '<title>Tracciabilità materiali — Demo</title><style>' + css + '\n' + extra_css + '</style></head><body>'
          + symbols + '<div class="desktop" id="desktop"><main class="workspace" id="workspace">' + app
          + '</main>' + template + '<script>' + script + '</script></body></html>')
(HERE / "tracciabilita-demo.html").write_text(output, encoding="utf-8")
print(HERE / "tracciabilita-demo.html")
