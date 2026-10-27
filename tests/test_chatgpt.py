import copy
import json
import threading
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from traccia import chatgpt


@pytest.fixture
def vault(radice, monkeypatch):
    data = {"active": None, "profiles": {}}
    monkeypatch.setattr(chatgpt, "_read", lambda: copy.deepcopy(data))

    def write(value):
        data.clear()
        data.update(copy.deepcopy(value))

    monkeypatch.setattr(chatgpt, "_write", write)
    monkeypatch.setattr(chatgpt, "_pending", None)
    return data


def tokens():
    return {
        "access_token": "test-access",
        "refresh_token": "test-refresh",
        "id_token": "test-id",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "openid chatgpt.tokens.use.direct",
    }


def attempt():
    return {
        "state": "expected-state",
        "nonce": "expected-nonce",
        "client_id": None,
        "subject": None,
        "verifier": "verifier",
        "redirect": "http://127.0.0.1:12345/auth/callback",
    }


def test_oauth_exchange_binds_issued_client_and_hides_secrets(vault, monkeypatch):
    calls = []

    def request(method, url, **kwargs):
        calls.append((url, kwargs["data"]))
        return tokens()

    monkeypatch.setattr(chatgpt, "_request", request)
    monkeypatch.setattr(chatgpt, "_identity", lambda *_args: {"sub": "account-1", "email": "demo@example.invalid"})
    chatgpt.complete(attempt(), {"state": "expected-state", "code": "code", "client_id": "issued-client"})
    assert calls[0][1]["client_id"] == "issued-client"
    assert calls[0][1]["redirect_uri"] == attempt()["redirect"]
    assert vault["active"] == "issued-client"
    public = json.dumps(chatgpt.status())
    assert "test-access" not in public and "test-refresh" not in public and "test-id" not in public
    assert chatgpt.status()["plan_enabled"]


def test_invalid_oauth_state_never_exchanges(vault, monkeypatch):
    monkeypatch.setattr(chatgpt, "_request", lambda *a, **k: pytest.fail("unexpected HTTP request"))
    with pytest.raises(chatgpt.AgentError):
        chatgpt.complete(attempt(), {"state": "wrong", "code": "code", "client_id": "issued"})
    with pytest.raises(chatgpt.AgentError):
        chatgpt.complete(attempt(), {"state": "expected-state", "code": "code"})
    with pytest.raises(chatgpt.AgentError):
        chatgpt.complete(
            attempt() | {"client_id": "one"}, {"state": "expected-state", "code": "code", "client_id": "two"}
        )


def test_signature_nonce_issuer_audience_are_verified(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key())) | {"kid": "test"}
    monkeypatch.setattr(chatgpt, "_discovery", lambda: {"jwks_uri": "https://auth.openai.com/jwks"})
    monkeypatch.setattr(chatgpt, "_request", lambda *_args, **_kwargs: {"keys": [key]})
    claims = {"iss": chatgpt.ISSUER, "sub": "one", "aud": "client", "exp": time.time() + 1000, "nonce": "nonce"}

    def signed(value):
        return jwt.encode(value, private, algorithm="RS256", headers={"kid": "test"})

    assert chatgpt._identity(signed(claims), "client", "nonce")["sub"] == "one"
    for modified in (
        claims | {"nonce": "wrong"},
        claims | {"iss": "https://invalid.example"},
        claims | {"aud": "other"},
        claims | {"exp": 1},
    ):
        with pytest.raises(chatgpt.AgentError):
            chatgpt._identity(signed(modified), "client", "nonce")


def test_refresh_rotates_together_and_keeps_registration(vault, monkeypatch):
    vault.update(
        active="client", profiles={"client": chatgpt._credentials(tokens()) | {"subject": "one", "expires_at": 0}}
    )
    calls = []

    def request(*_args, **kwargs):
        calls.append(kwargs["data"])
        return {"access_token": "new", "refresh_token": "rotated", "token_type": "Bearer", "expires_in": 3600}

    monkeypatch.setattr(chatgpt, "_request", request)
    assert chatgpt.access_token() == "new"
    assert vault["profiles"]["client"]["refresh_token"] == "rotated"
    assert "chatgpt.tokens.use.direct" in vault["profiles"]["client"]["scopes"]
    assert calls[0]["client_id"] == "client" and "scope" not in calls[0]


def test_missing_plan_permission_blocks_inference(vault):
    vault.update(active="client", profiles={"client": chatgpt._credentials(tokens() | {"scope": "openid"})})
    with pytest.raises(chatgpt.AgentError):
        chatgpt.access_token()


def test_logout_clears_tokens_even_if_remote_revocation_fails(vault, monkeypatch):
    vault.update(active="client", profiles={"client": chatgpt._credentials(tokens()) | {"subject": "one"}})
    monkeypatch.setattr(chatgpt, "_discovery", lambda: {"revocation_endpoint": "https://auth.openai.com/revoke"})

    def fail(*_args, **_kwargs):
        raise chatgpt.AgentError("Network unavailable")

    monkeypatch.setattr(chatgpt, "_request", fail)
    result = chatgpt.logout()
    assert not result["revoked"]
    assert vault["profiles"]["client"] == {"subject": "one"}


def test_stream_requires_completion_and_never_returns_partial(monkeypatch):
    events = [{"type": "response.output_text.delta", "delta": "partial"}]
    captured = []

    class Stream:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def iter_lines(self):
            return iter("data: " + json.dumps(e) for e in events)

    monkeypatch.setattr(chatgpt, "access_token", lambda: "fake-token")

    def stream(*_args, **kwargs):
        captured.append(kwargs["json"])
        return Stream()

    monkeypatch.setattr(chatgpt.httpx, "stream", stream)
    with pytest.raises(chatgpt.AgentError):
        chatgpt.response("test", [{"role": "user", "content": "test"}], "model", "", threading.Event())
    events.append({"type": "response.completed"})
    assert chatgpt.response("test", [], "model", "", threading.Event()) == "partial"
    assert captured[0]["store"] is False and captured[0]["stream"] is True
    events.append({"type": "response.failed"})
    with pytest.raises(chatgpt.AgentError):
        chatgpt.response("test", [], "model", "", threading.Event())


def test_failed_exchange_keeps_registration_for_retry(vault, monkeypatch):
    def failure(*args, **kwargs):
        raise chatgpt.AgentError("Connessione interrotta")

    monkeypatch.setattr(chatgpt, "_request", failure)
    with pytest.raises(chatgpt.AgentError):
        chatgpt.complete(attempt(), {"state": "expected-state", "code": "code", "client_id": "issued"})
    assert chatgpt.status()["retry"] == "issued"
    assert vault["active"] is None
    assert not chatgpt.status()["connected"]


def test_account_cannot_change_during_signin(vault, monkeypatch):
    monkeypatch.setattr(chatgpt, "_pending", {"state": "pending"})
    with pytest.raises(chatgpt.AgentError):
        chatgpt.logout()
    with pytest.raises(chatgpt.AgentError):
        chatgpt.select("other")


class _PortachiaviWindows:
    """Come Gestione credenziali: rifiuta le voci oltre 1280 caratteri."""

    def __init__(self):
        self.voci = {}

    def get_password(self, service, user):
        return self.voci.get((service, user))

    def set_password(self, service, user, value):
        if len(value) > 1280:
            raise OSError(1783, "CredWrite")
        self.voci[(service, user)] = value

    def delete_password(self, service, user):
        del self.voci[(service, user)]


def test_token_lunghi_si_salvano_a_parti_e_si_rileggono(monkeypatch):
    portachiavi = _PortachiaviWindows()
    monkeypatch.setattr(chatgpt, "_vault", lambda: portachiavi)
    data = {"active": "a", "profiles": {"a": {"access": "x" * 2000, "refresh": "y" * 1500, "id": "z" * 1800}}}
    chatgpt._write(data)
    assert chatgpt._read() == data
    chatgpt._write({"active": None, "profiles": {}})
    assert chatgpt._read() == {"active": None, "profiles": {}}
    assert (chatgpt.SERVICE, "profiles.1") not in portachiavi.voci


def test_formato_precedente_in_una_voce_resta_leggibile(monkeypatch):
    portachiavi = _PortachiaviWindows()
    monkeypatch.setattr(chatgpt, "_vault", lambda: portachiavi)
    portachiavi.voci[(chatgpt.SERVICE, "profiles")] = json.dumps({"active": None, "profiles": {"p": {}}})
    assert chatgpt._read() == {"active": None, "profiles": {"p": {}}}
