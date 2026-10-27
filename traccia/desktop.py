"""Avvio locale su Windows e macOS; nessun eseguibile esterno dell’agente richiesto."""

import os
import socket
import threading
import webbrowser

import httpx
import uvicorn
from filelock import FileLock, Timeout

from . import configurazione, percorsi

PORTE_DI_RISERVA = 20


def _stato_porta(porta: int) -> str:
    """'libera', 'nostra' (l’app è già aperta su quella porta) o 'altra'."""
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=0.5):
            pass
    except OSError:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", porta))
            return "libera"
        except OSError:
            return "altra"
    try:
        identity = httpx.get(f"http://127.0.0.1:{porta}/api/salute", timeout=2).json()
    except (httpx.HTTPError, ValueError):
        return "altra"
    if isinstance(identity, dict) and identity.get("application") == "tracciabilita-materiali":
        return "nostra"
    return "altra"


def _scegli_porta() -> tuple[int, bool]:
    """Porta da usare e se l’app vi è già aperta. Con TRACCIA_PORTA si usa solo quella."""
    if os.environ.get("TRACCIA_PORTA"):
        candidate = [percorsi.PORTA]
    else:
        candidate = list(range(percorsi.PORTA, percorsi.PORTA + PORTE_DI_RISERVA))
    stati = {}
    for porta in candidate:
        stati[porta] = _stato_porta(porta)
        if stati[porta] == "nostra":
            return porta, True
    for porta in candidate:
        if stati[porta] == "libera":
            return porta, False
    if len(candidate) == 1:
        raise RuntimeError(f"La porta {percorsi.PORTA} è occupata da un’altra applicazione. Cambia TRACCIA_PORTA.")
    raise RuntimeError(f"Le porte da {candidate[0]} a {candidate[-1]} sono tutte occupate da altre applicazioni.")


def main():
    porta, gia_aperta = _scegli_porta()
    url = f"http://127.0.0.1:{porta}"
    if gia_aperta:
        webbrowser.open(url)
        return
    configurazione.directory().mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(configurazione.directory() / "app.lock", timeout=0):

            def open_browser():
                for _ in range(30):
                    try:
                        if httpx.get(url + "/api/salute", timeout=1).is_success:
                            if not os.environ.get("CANTIERELINK_NO_BROWSER"):
                                webbrowser.open(url)
                            return
                    except httpx.HTTPError:
                        pass
                    threading.Event().wait(0.5)

            threading.Thread(target=open_browser, daemon=True).start()
            from .server import app

            instance = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, access_log=False))
            app.state.shutdown = lambda: setattr(instance, "should_exit", True)
            instance.run()
    except Timeout as exc:
        raise RuntimeError("Un’istanza dell’app è già in esecuzione.") from exc


if __name__ == "__main__":
    main()
