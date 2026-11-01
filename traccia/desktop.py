"""Avvio locale su Windows e macOS; nessun eseguibile esterno dell’agente richiesto."""

import hashlib
import json
import os
import secrets
import socket
import threading
import webbrowser

import httpx
import uvicorn
from filelock import FileLock, Timeout

from . import configurazione, percorsi

PORTE_DI_RISERVA = 20


def _sessione_file():
    return configurazione.directory() / "sessione.json"


def _sessione_salvata() -> dict:
    """Porta e token dell'istanza avviata da questo utente (file leggibile solo da lui); {} se assente o rotto."""
    try:
        valore = json.loads(_sessione_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return valore if isinstance(valore, dict) and isinstance(valore.get("token"), str) else {}


def _impronta(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _url_finestra(porta: int, token: str) -> str:
    """Il token viaggia nel frammento: non arriva al server nella richiesta e non resta nei log."""
    return f"http://127.0.0.1:{porta}/#t={token}"


def _stato_porta(porta: int, istanza: str | None = None) -> str:
    """'libera', 'nostra' (l’app è già aperta su quella porta, con l'impronta attesa) o 'altra'."""
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
    if (
        isinstance(identity, dict)
        and identity.get("application") == "tracciabilita-materiali"
        and istanza is not None
        and identity.get("istanza") == istanza
    ):
        return "nostra"
    return "altra"  # anche chi dichiara di essere l'app ma non ha l'impronta di questo utente


def _scegli_porta(istanza: str | None = None) -> tuple[int, bool]:
    """Porta da usare e se l’app vi è già aperta. Con TRACCIA_PORTA si usa solo quella."""
    if os.environ.get("TRACCIA_PORTA"):
        candidate = [percorsi.PORTA]
    else:
        candidate = list(range(percorsi.PORTA, percorsi.PORTA + PORTE_DI_RISERVA))
    stati = {}
    for porta in candidate:
        stati[porta] = _stato_porta(porta, istanza)
        if stati[porta] == "nostra":
            return porta, True
    for porta in candidate:
        if stati[porta] == "libera":
            return porta, False
    if len(candidate) == 1:
        raise RuntimeError(f"La porta {percorsi.PORTA} è occupata da un’altra applicazione. Cambia TRACCIA_PORTA.")
    raise RuntimeError(f"Le porte da {candidate[0]} a {candidate[-1]} sono tutte occupate da altre applicazioni.")


def _finestra():
    """Modulo pywebview, se installato e non escluso con CANTIERELINK_BROWSER=1 (allora si usa il browser)."""
    if os.environ.get("CANTIERELINK_BROWSER") or os.environ.get("CANTIERELINK_NO_BROWSER"):
        return None
    try:
        import webview
    except Exception:
        return None
    return webview


def _attendi(url: str) -> bool:
    for _ in range(40):
        try:
            if httpx.get(url + "/api/salute", timeout=1).is_success:
                return True
        except httpx.HTTPError:
            pass
        threading.Event().wait(0.5)
    return False


def _apri(url: str, webview) -> None:
    """Interfaccia in una finestra propria (pywebview) oppure nel browser predefinito."""
    if webview is None:
        if not os.environ.get("CANTIERELINK_NO_BROWSER"):
            webbrowser.open(url)
        return
    webview.settings["ALLOW_DOWNLOADS"] = True  # Excel e fascicolo ordinato: senza, i pulsanti di scarico sono muti
    webview.create_window("CantiereLink", url, width=1380, height=860, min_size=(900, 600))
    webview.start()


def main():
    precedente = _sessione_salvata()
    porta, gia_aperta = _scegli_porta(_impronta(precedente["token"]) if precedente else None)
    url = f"http://127.0.0.1:{porta}"
    webview = _finestra()
    if gia_aperta:
        _apri(_url_finestra(porta, precedente["token"]), webview)
        return
    configurazione.directory().mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(configurazione.directory() / "app.lock", timeout=0):
            from . import server
            from .server import app

            token = secrets.token_urlsafe(32)
            server.imposta_token(token)
            configurazione.scrivi_json(_sessione_file(), {"porta": porta, "token": token})
            url_finestra = _url_finestra(porta, token)
            instance = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, access_log=False))

            def shutdown():
                instance.should_exit = True
                if webview is not None:
                    for window in list(webview.windows):
                        window.destroy()

            app.state.shutdown = shutdown
            if webview is None:
                threading.Thread(target=lambda: _attendi(url) and _apri(url_finestra, None), daemon=True).start()
                instance.run()
                return
            # Con la finestra propria il server gira in un thread: la finestra deve stare nel thread principale.
            server_thread = threading.Thread(target=instance.run, name="server-locale", daemon=True)
            server_thread.start()
            if not _attendi(url):
                raise RuntimeError("Il servizio locale non è partito. Consulta la cartella dati dell’app.")
            _apri(url_finestra, webview)  # ritorna alla chiusura della finestra
            instance.should_exit = True
            server_thread.join(timeout=10)
    except Timeout as exc:
        raise RuntimeError("Un’istanza dell’app è già in esecuzione.") from exc


if __name__ == "__main__":
    main()
