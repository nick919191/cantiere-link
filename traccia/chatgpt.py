"""Sign in with ChatGPT per app locali. Token soltanto nel portachiavi di sistema.

Il browser riceve solo stato e modelli, mai access token, refresh token o ID token.
Il file lock serializza gli aggiornamenti dei token anche tra processi.
"""

import base64
import hashlib
import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import jwt
import keyring
from filelock import FileLock

from . import configurazione as cfg

ISSUER = "https://auth.openai.com"
TOKEN = ISSUER + "/api/accounts/oauth/token"
RESOURCE = "https://api.openai.com/v1"
SCOPE = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
SERVICE = "tracciabilita-materiali.chatgpt"
CHUNK = 1000
_LOCK = threading.RLock()
_pending = None
_message = ""


class AgentError(Exception):
    """Errore pubblico, privo di credenziali e risposte HTTP grezze."""


def _vault():
    backend = keyring.get_keyring()
    if not type(backend).__module__.startswith(
        ("keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.SecretService")
    ):
        raise AgentError("Portachiavi sicuro non disponibile. Abilita il portachiavi del sistema e riprova.")
    return backend


def _read() -> dict:
    try:
        vault = _vault()
        raw = vault.get_password(SERVICE, "profiles")
        data = json.loads(raw) if raw else {"active": None, "profiles": {}}
        if "chunks" in data:
            parts = [vault.get_password(SERVICE, f"profiles.{i}") for i in range(data["chunks"])]
            if None in parts:
                raise ValueError("parte mancante")
            data = json.loads("".join(parts))
        return data
    except AgentError:
        raise
    except Exception as exc:
        raise AgentError("Impossibile leggere il portachiavi del sistema.") from exc


def _write(data: dict) -> None:
    """Il valore è diviso in parti: Gestione credenziali di Windows accetta circa 1280 caratteri per voce."""
    try:
        vault = _vault()
        raw = json.dumps(data)
        parts = [raw[i : i + CHUNK] for i in range(0, len(raw), CHUNK)] or [""]
        for i, part in enumerate(parts):
            vault.set_password(SERVICE, f"profiles.{i}", part)
        vault.set_password(SERVICE, "profiles", json.dumps({"chunks": len(parts)}))
        i = len(parts)
        while vault.get_password(SERVICE, f"profiles.{i}") is not None:
            vault.delete_password(SERVICE, f"profiles.{i}")
            i += 1
    except AgentError:
        raise
    except Exception as exc:
        raise AgentError("Impossibile salvare la connessione nel portachiavi del sistema.") from exc


def _filelock():
    cfg.directory().mkdir(parents=True, exist_ok=True)
    return FileLock(cfg.directory() / "account.lock", timeout=30)


def _request(method: str, url: str, **kwargs) -> dict:
    try:
        response = httpx.request(method, url, timeout=30, follow_redirects=False, **kwargs)
        if response.status_code == 429:
            raise AgentError("Limite di utilizzo raggiunto. Controlla il tuo piano in ChatGPT.")
        if response.status_code in (401, 403):
            raise AgentError("Accesso non disponibile. Ricollega l’account e autorizza l’utilizzo del piano.")
        if response.is_error:
            raise AgentError("Il servizio non ha completato la richiesta. Riprova o ricollega l’account.")
        return response.json() if response.content else {}
    except (httpx.HTTPError, ValueError) as exc:
        raise AgentError("Connessione al servizio non riuscita. Controlla la rete e riprova.") from exc


def _discovery() -> dict:
    data = _request("GET", ISSUER + "/.well-known/openid-configuration")
    if data.get("issuer") != ISSUER:
        raise AgentError("Identità del servizio non valida.")
    return data


def _trusted_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "auth.openai.com" or parsed.fragment:
        raise AgentError("Indirizzo del servizio non valido.")
    return url


def _identity(token: str, client_id: str, nonce: str | None = None) -> dict:
    try:
        discovery = _discovery()
        keys = _request("GET", _trusted_url(discovery["jwks_uri"]))
        header = jwt.get_unverified_header(token)
        key = next(k for k in keys["keys"] if k.get("kid") == header.get("kid"))
        claims = jwt.decode(
            token,
            jwt.PyJWK.from_dict(key).key,
            algorithms=["RS256", "ES256"],
            audience=client_id,
            issuer=ISSUER,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
        if nonce is not None and not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise ValueError("nonce")
        if not claims["sub"]:
            raise ValueError("subject")
        return claims
    except (jwt.PyJWTError, KeyError, StopIteration, ValueError, TypeError) as exc:
        raise AgentError("La verifica dell’identità ChatGPT non è riuscita. Ripeti l’accesso.") from exc


def _credentials(tokens: dict, old: dict | None = None) -> dict:
    old = old or {}
    if not isinstance(tokens.get("access_token"), str) or tokens.get("token_type", "").lower() != "bearer":
        raise AgentError("Credenziali del servizio non valide.")
    try:
        expires = float(tokens["expires_in"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AgentError("Scadenza delle credenziali non valida.") from exc
    return {
        **old,
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", old.get("refresh_token", "")),
        "id_token": tokens.get("id_token", old.get("id_token", "")),
        "scopes": tokens["scope"].split() if "scope" in tokens else old.get("scopes", []),
        "expires_at": time.time() + expires,
    }


def status() -> dict:
    try:
        with _LOCK, _filelock():
            data = _read()
        profile = data["profiles"].get(data["active"], {})
        return {
            "connected": bool(profile.get("access_token")),
            "plan_enabled": bool(profile.get("access_token"))
            and "chatgpt.tokens.use.direct" in profile.get("scopes", []),
            "active": data["active"],
            "retry": data.get("retry"),
            "email": profile.get("email", ""),
            "profiles": [
                {"id": cid, "email": p.get("email", ""), "connected": bool(p.get("access_token"))}
                for cid, p in data["profiles"].items()
            ],
            "pending": _pending is not None,
            "message": _message,
        }
    except AgentError as exc:
        return {"connected": False, "plan_enabled": False, "profiles": [], "pending": False, "message": str(exc)}


def start(profile_id: str | None = None) -> dict:
    global _pending, _message
    with _LOCK, _filelock():
        if _pending:
            raise AgentError("Un accesso è già in corso. Completa la finestra aperta nel browser.")
        data = _read()
        old = data["profiles"].get(profile_id) if profile_id else None
        if profile_id and old is None:
            raise AgentError("Account salvato non trovato.")
        attempt = {
            "state": secrets.token_urlsafe(32),
            "nonce": secrets.token_urlsafe(32),
            "verifier": secrets.token_urlsafe(48),
            "client_id": profile_id,
            "subject": (old or {}).get("subject"),
            "expires": time.monotonic() + 180,
        }

        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):  # noqa: N802
                nonlocal attempt
                global _message
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                valid = (
                    parsed.path == "/auth/callback"
                    and all(len(v) == 1 for v in query.values())
                    and secrets.compare_digest(query.get("state", [""])[0], attempt["state"])
                )
                code, message = 400, "Richiesta non valida. Torna all’app e ripeti l’accesso."
                if valid:
                    attempt["done"] = True
                    try:
                        complete(attempt, {k: v[0] for k, v in query.items()})
                        code, message = 200, "Account collegato. Puoi chiudere questa scheda e tornare all’app."
                        _message = "Account collegato."
                    except AgentError as exc:
                        message = str(exc)
                        _message = message
                self.send_response(code)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(message.encode())

        listener = HTTPServer(("127.0.0.1", 0), Callback)
        listener.timeout = 0.5
        attempt["redirect"] = f"http://127.0.0.1:{listener.server_port}/auth/callback"
        _pending = attempt
        _message = "Completa l’accesso nel browser."
        params = {
            "client_id": profile_id or "dynamic_agent_client",
            "response_type": "code",
            "redirect_uri": attempt["redirect"],
            "scope": SCOPE,
            "resource": RESOURCE,
            "state": attempt["state"],
            "nonce": attempt["nonce"],
            "code_challenge_method": "S256",
            "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(attempt["verifier"].encode()).digest())
            .rstrip(b"=")
            .decode(),
            "ext_agent_host_id": cfg.leggi()["host_id"],
        }
        if not profile_id:
            params["agent_name_hint"] = "CantiereLink"
        elif old.get("email"):
            params["login_hint"] = old["email"]

        def serve():
            global _pending, _message
            try:
                while not attempt.get("done") and time.monotonic() < attempt["expires"]:
                    listener.handle_request()
                if not attempt.get("done"):
                    _message = "Accesso scaduto. Premi di nuovo Continua con ChatGPT."
            finally:
                listener.server_close()
                _pending = None

        threading.Thread(target=serve, daemon=True).start()
        try:
            opened = webbrowser.open(ISSUER + "/api/accounts/authorize?" + urlencode(params))
        except Exception:
            opened = False
        if not opened:
            attempt["done"] = True
            _message = "Impossibile aprire il browser predefinito. Configuralo e riprova."
            raise AgentError(_message)
        return {"started": True}


def complete(attempt: dict, query: dict) -> None:
    if not secrets.compare_digest(query.get("state", ""), attempt["state"]):
        raise AgentError("Accesso non valido.")
    if query.get("error"):
        raise AgentError("Accesso annullato o non autorizzato.")
    issued = query.get("client_id") or attempt.get("client_id")
    if not issued or issued == "dynamic_agent_client" or not query.get("code"):
        raise AgentError("Registrazione incompleta. Ripeti l’accesso.")
    if attempt.get("client_id") and issued != attempt["client_id"]:
        raise AgentError("Registrazione diversa dall’account selezionato.")
    with _LOCK, _filelock():
        data = _read()
        # Conserva la registrazione anche se lo scambio del codice fallisce.
        old = data["profiles"].setdefault(issued, {"client_id": issued})
        data["retry"] = issued
        _write(data)
        tokens = _request(
            "POST",
            TOKEN,
            data={
                "grant_type": "authorization_code",
                "client_id": issued,
                "code": query["code"],
                "code_verifier": attempt["verifier"],
                "redirect_uri": attempt["redirect"],
                "resource": RESOURCE,
            },
        )
        identity = _identity(tokens.get("id_token", ""), issued, attempt["nonce"])
        expected = attempt.get("subject") or old.get("subject")
        if expected and identity["sub"] != expected:
            raise AgentError("L’account restituito è diverso da quello selezionato.")
        record = _credentials(tokens)
        record.update(client_id=issued, subject=identity["sub"], email=identity.get("email", ""))
        data["profiles"][issued] = record
        data["active"] = issued
        data.pop("retry", None)
        _write(data)


def access_token() -> str:
    with _LOCK, _filelock():
        data = _read()
        profile = data["profiles"].get(data["active"], {})
        if not profile.get("access_token") or "chatgpt.tokens.use.direct" not in profile.get("scopes", []):
            raise AgentError("Collega ChatGPT e autorizza l’utilizzo del piano prima di avviare l’agente.")
        if profile.get("expires_at", 0) < time.time() + 60:
            if not profile.get("refresh_token"):
                raise AgentError("Sessione scaduta. Ricollega ChatGPT.")
            tokens = _request(
                "POST",
                TOKEN,
                data={
                    "grant_type": "refresh_token",
                    "client_id": data["active"],
                    "refresh_token": profile["refresh_token"],
                    "resource": RESOURCE,
                },
            )
            if tokens.get("id_token") and _identity(tokens["id_token"], data["active"])["sub"] != profile["subject"]:
                raise AgentError("Identità della sessione non valida.")
            profile = _credentials(tokens, profile)
            data["profiles"][data["active"]] = profile
            _write(data)
        if "chatgpt.tokens.use.direct" not in profile["scopes"]:
            raise AgentError("Autorizza l’utilizzo del piano ChatGPT.")
        return profile["access_token"]


def select(profile_id: str) -> None:
    with _LOCK, _filelock():
        if _pending:
            raise AgentError("Completa o attendi la scadenza dell’accesso in corso prima di cambiare account.")
        data = _read()
        if profile_id not in data["profiles"]:
            raise AgentError("Account non trovato.")
        data["active"] = profile_id
        _write(data)


def logout() -> dict:
    global _message
    confirmed = True
    with _LOCK, _filelock():
        if _pending:
            raise AgentError("Completa o attendi la scadenza dell’accesso in corso prima di scollegare l’account.")
        data = _read()
        profile = data["profiles"].get(data["active"], {})
        if profile.get("refresh_token"):
            confirmed = False
            for _ in range(2):
                try:
                    url = _trusted_url(_discovery()["revocation_endpoint"])
                    _request(
                        "POST",
                        url,
                        data={
                            "token": profile["refresh_token"],
                            "token_type_hint": "refresh_token",
                            "client_id": data["active"],
                        },
                    )
                    confirmed = True
                    break
                except (AgentError, KeyError):
                    time.sleep(0.25)
        for key in ("access_token", "refresh_token", "id_token", "scopes", "expires_at"):
            profile.pop(key, None)
        _write(data)
    _message = (
        "Account scollegato."
        if confirmed
        else (
            "Account scollegato localmente. Revoca remota non confermata: scollega l’app nelle impostazioni di ChatGPT."
        )
    )
    return {"message": _message, "revoked": confirmed}


def models() -> list[dict]:
    data = _request("GET", RESOURCE + "/models", headers={"Authorization": "Bearer " + access_token()})
    return [
        {
            "slug": m["slug"],
            "display_name": m.get("display_name", m["slug"]),
            "reasoning": m.get("supported_reasoning_levels", []),
        }
        for m in data.get("models", [])
        if m.get("visibility") == "list" and m.get("slug")
    ]


def response(instructions: str, inputs: list, model: str, reasoning: str, cancelled: threading.Event) -> str:
    payload = {"model": model, "instructions": instructions, "input": inputs, "store": False, "stream": True}
    if reasoning:
        payload["reasoning"] = {"effort": reasoning}
    try:
        with httpx.stream(
            "POST",
            RESOURCE + "/responses",
            json=payload,
            headers={"Authorization": "Bearer " + access_token()},
            timeout=180,
        ) as stream:
            if stream.status_code == 429:
                raise AgentError("Limite ChatGPT raggiunto. Gestisci l’utilizzo del piano e riprendi più tardi.")
            if stream.status_code != 200:
                raise AgentError("Richiesta non accettata. Controlla account, modello e livello di ragionamento.")
            parts, size, completed = [], 0, False
            for line in stream.iter_lines():
                if cancelled.is_set():
                    raise AgentError("Operazione interrotta.")
                if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                    continue
                event = json.loads(line[5:])
                if event.get("type") == "response.output_text.delta":
                    value = event.get("delta", "")
                    size += len(value)
                    if size > 2_000_000:
                        raise AgentError("Risposta troppo grande. Suddividi il documento.")
                    parts.append(value)
                elif event.get("type") in ("error", "response.failed", "response.incomplete"):
                    raise AgentError("Risposta non completata. Controlla i limiti del piano e riprova.")
                elif event.get("type") == "response.completed":
                    completed = True
            if not completed:
                raise AgentError("Risposta interrotta: nessun risultato parziale è stato applicato.")
            return "".join(parts)
    except (httpx.HTTPError, ValueError) as exc:
        raise AgentError("Connessione interrotta: nessun risultato parziale è stato applicato.") from exc
