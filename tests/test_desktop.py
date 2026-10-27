import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from traccia import desktop, percorsi


class _Altra(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"application": "scl"}')

    def log_message(self, *args):
        pass


@pytest.fixture
def altra_app():
    server = HTTPServer(("127.0.0.1", 0), _Altra)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_port
    server.shutdown()
    server.server_close()


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_porta_occupata_da_altra_app_passa_alla_successiva(altra_app, monkeypatch):
    monkeypatch.delenv("TRACCIA_PORTA", raising=False)
    monkeypatch.setattr(percorsi, "PORTA", altra_app)
    monkeypatch.setattr(desktop, "_stato_porta", lambda p: "altra" if p == altra_app else "libera")
    assert desktop._scegli_porta() == (altra_app + 1, False)


def test_stato_porta_riconosce_altra_app_e_porta_libera(altra_app):
    assert desktop._stato_porta(altra_app) == "altra"
    assert desktop._stato_porta(_porta_libera()) == "libera"


def test_app_gia_aperta_su_porta_di_riserva_viene_riusata(monkeypatch):
    monkeypatch.delenv("TRACCIA_PORTA", raising=False)
    monkeypatch.setattr(percorsi, "PORTA", 9000)
    monkeypatch.setattr(
        desktop, "_stato_porta", lambda p: {9000: "altra", 9001: "libera", 9003: "nostra"}.get(p, "libera")
    )
    assert desktop._scegli_porta() == (9003, True)


def test_porta_esplicita_non_cerca_alternative(monkeypatch):
    monkeypatch.setenv("TRACCIA_PORTA", "9000")
    monkeypatch.setattr(percorsi, "PORTA", 9000)
    monkeypatch.setattr(desktop, "_stato_porta", lambda p: "altra")
    with pytest.raises(RuntimeError, match="9000"):
        desktop._scegli_porta()
