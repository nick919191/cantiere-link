"""S2: pagine enormi e file con troppe pagine. S3: token consegnato dalla finestra, impronta dell'istanza."""

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from traccia import desktop, preparazione, server
from traccia.preparazione import prepara


def _pdf(dimensioni):
    doc = pdfium.PdfDocument.new()
    for w, h in dimensioni:
        doc.new_page(w, h)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_pagina_enorme_resa_entro_il_limite_di_pixel(radice):
    cartella = radice / "lavori" / "grande"
    (cartella / "ingresso").mkdir(parents=True)
    (cartella / "ingresso" / "a1.pdf").write_bytes(_pdf([(14400, 14400)]))
    elenco = prepara(cartella)
    assert elenco[0]["pid"] == "p0001"
    with Image.open(cartella / "pagine" / "p0001.png") as img:
        assert img.width * img.height <= preparazione.MAX_PIXEL_PAGINA * 1.01 and img.width > 1000
    info = preparazione.info_pagina(cartella, "p0001")
    taglio = preparazione.ritaglio(cartella, info, [0, 0, 1000, 1000])
    with Image.open(io.BytesIO(taglio)) as img:
        assert img.width * img.height <= preparazione.MAX_PIXEL_PAGINA * 1.01


def test_troppe_pagine_dichiara_il_file_non_leggibile(radice, monkeypatch):
    monkeypatch.setattr(preparazione, "MAX_PAGINE_FILE", 2)
    cartella = radice / "lavori" / "lungo"
    (cartella / "ingresso").mkdir(parents=True)
    (cartella / "ingresso" / "lungo.pdf").write_bytes(_pdf([(200, 200)] * 3))
    (cartella / "ingresso" / "corto.pdf").write_bytes(_pdf([(200, 200)] * 2))
    elenco = prepara(cartella)
    assert [v["file"] for v in elenco if v["pid"]] == ["corto.pdf", "corto.pdf"]
    assert next(v for v in elenco if not v["pid"])["file"] == "lungo.pdf"


@pytest.fixture
def token_finestra(monkeypatch):
    monkeypatch.setattr(server, "_TOKEN", server._TOKEN)
    monkeypatch.setattr(server, "_TOKEN_DALLA_FINESTRA", False)
    server.imposta_token("token-della-finestra")
    yield "token-della-finestra"


def test_sessione_chiusa_quando_il_token_arriva_dalla_finestra(radice, token_finestra):
    client = TestClient(server.app)
    assert client.get("/api/sessione").status_code == 404
    assert client.post("/api/agente/interrompi").status_code == 403
    assert client.post("/api/agente/interrompi", headers={"X-Traccia-Token": token_finestra}).status_code == 200
    salute = client.get("/api/salute").json()
    assert salute["istanza"] == desktop._impronta(token_finestra) and token_finestra not in json.dumps(salute)
    assert desktop._url_finestra(8765, token_finestra) == "http://127.0.0.1:8765/#t=token-della-finestra"


class _FintaApp(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "application": "tracciabilita-materiali", "istanza": "abc"}).encode())

    def log_message(self, *args):
        pass


def test_istanza_riconosciuta_solo_con_l_impronta_giusta():
    finta = HTTPServer(("127.0.0.1", 0), _FintaApp)
    threading.Thread(target=finta.serve_forever, daemon=True).start()
    try:
        porta = finta.server_port
        assert desktop._stato_porta(porta) == "altra"  # senza sessione salvata non ci si fida di nessuno
        assert desktop._stato_porta(porta, "zzz") == "altra"
        assert desktop._stato_porta(porta, "abc") == "nostra"
    finally:
        finta.shutdown()
        finta.server_close()


def test_sessione_salvata_tollera_file_assente_o_rotto(radice):
    assert desktop._sessione_salvata() == {}
    desktop._sessione_file().parent.mkdir(parents=True, exist_ok=True)
    desktop._sessione_file().write_text("{ rotto", encoding="utf-8")
    assert desktop._sessione_salvata() == {}
    desktop._sessione_file().write_text('{"porta": 8765, "token": "t"}', encoding="utf-8")
    assert desktop._sessione_salvata()["token"] == "t"
