"""POST /api/agents/test endpoint.

These tests don't actually hit a network — they patch the adapter modules'
httpx.Client to return canned responses, so the route exercises the same code
path the real test-connection click would, deterministically.
"""
from __future__ import annotations

from .conftest import csrf_headers, signup


def _patch_httpx_response(monkeypatch, module, response_payload, *, status: int = 200):
    import json as _json
    from unittest.mock import MagicMock

    class _Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def post(self, url, json=None, headers=None):
            response = MagicMock()
            response.status_code = status
            if isinstance(response_payload, str):
                response.text = response_payload
                response.json = MagicMock(side_effect=ValueError("not json"))
            else:
                response.text = _json.dumps(response_payload)
                response.json = MagicMock(return_value=response_payload)
            return response

    monkeypatch.setattr(module.httpx, "Client", _Client)


def test_test_connection_succeeds_for_openai_compat(client, monkeypatch):
    from app.agents import http_openai_compat as openai_compat_mod

    from app.routes import agents as agents_route
    monkeypatch.setattr(openai_compat_mod, "assert_endpoint_safe", lambda url: None)
    monkeypatch.setattr(agents_route, "assert_endpoint_safe", lambda url: None)
    _patch_httpx_response(
        monkeypatch,
        openai_compat_mod,
        {"choices": [{"message": {"content": "pong"}}]},
    )

    signup(client, "endpoint-tester@example.com")
    headers = csrf_headers(client)
    headers["X-Agent-Auth-Header"] = "Bearer fake-token"
    resp = client.post(
        "/api/agents/test",
        json={"url": "https://api.example.test/v1/chat/completions", "format": "openai_compat"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["sample_response"] == "pong"
    assert data["latency_ms"] is not None


def test_test_connection_succeeds_for_simple_format(client, monkeypatch):
    from app.agents import http_simple as simple_mod
    from app.routes import agents as agents_route

    monkeypatch.setattr(simple_mod, "assert_endpoint_safe", lambda url: None)
    monkeypatch.setattr(agents_route, "assert_endpoint_safe", lambda url: None)
    _patch_httpx_response(monkeypatch, simple_mod, {"output": "echoed: ping"})

    signup(client, "simple-tester@example.com")
    headers = csrf_headers(client)
    resp = client.post(
        "/api/agents/test",
        json={"url": "https://api.example.test/agent", "format": "simple"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["sample_response"] == "echoed: ping"


def test_test_connection_returns_ok_false_on_endpoint_error(client, monkeypatch):
    from app.agents import http_openai_compat as openai_compat_mod

    from app.routes import agents as agents_route
    monkeypatch.setattr(openai_compat_mod, "assert_endpoint_safe", lambda url: None)
    monkeypatch.setattr(agents_route, "assert_endpoint_safe", lambda url: None)
    _patch_httpx_response(
        monkeypatch, openai_compat_mod, "internal error", status=500,
    )

    signup(client, "broken-endpoint@example.com")
    headers = csrf_headers(client)
    resp = client.post(
        "/api/agents/test",
        json={"url": "https://api.example.test/v1/chat/completions", "format": "openai_compat"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "HTTP 500" in (body["error"] or "")


def test_test_connection_rejects_ssrf_target(client):
    signup(client, "ssrf-tester@example.com")
    headers = csrf_headers(client)
    resp = client.post(
        "/api/agents/test",
        json={"url": "http://localhost:8000/", "format": "openai_compat"},
        headers=headers,
    )
    # Endpoint returns ok=false (not 4xx) so the UI can render the message.
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "localhost" in (body["error"] or "")


def test_test_connection_requires_auth(client):
    # No signup → no session → 401 from get_current_user.
    resp = client.post(
        "/api/agents/test",
        json={"url": "https://api.example.test/x", "format": "openai_compat"},
    )
    assert resp.status_code in {401, 403}
