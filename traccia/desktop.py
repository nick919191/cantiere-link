"""Avvio locale su Windows e macOS; nessun eseguibile esterno dell’agente richiesto."""

import os
import threading
import webbrowser

import httpx
import uvicorn
from filelock import FileLock, Timeout

from . import configurazione, percorsi


def main():
    url = f"http://127.0.0.1:{percorsi.PORTA}"
    try:
        response = httpx.get(url + "/api/salute", timeout=2)
        try:
            identity = response.json()
        except ValueError:
            identity = {}
        if isinstance(identity, dict) and identity.get("application") == "tracciabilita-materiali":
            webbrowser.open(url)
            return
        raise RuntimeError("La porta è occupata da un’altra applicazione. Imposta TRACCIA_PORTA.")
    except (httpx.ConnectError, httpx.TimeoutException):
        pass
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

            instance = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=percorsi.PORTA, access_log=False))
            app.state.shutdown = lambda: setattr(instance, "should_exit", True)
            instance.run()
    except Timeout as exc:
        raise RuntimeError("Un’istanza dell’app è già in esecuzione.") from exc


if __name__ == "__main__":
    main()
