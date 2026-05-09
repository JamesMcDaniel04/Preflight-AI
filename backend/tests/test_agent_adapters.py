"""Adapter unit tests.

We patch `httpx.Client` (the class) at the adapter-module level so the actual
network never gets touched. Each adapter is exercised end to end: build the
request, parse the response, and surface common failure modes (non-2xx, bad
JSON, SSRF rejection, retry on transient failure).
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import httpx
import pytest

from app.agents import http_openai_compat as openai_compat_mod
from app.agents import http_simple as simple_mod
from app.agents.base import reset_agent_auth_header, set_agent_auth_header
from app.agents.factory import build_adapter
from app.agents.http_openai_compat import HttpOpenAICompatAdapter
from app.agents.http_simple import HttpSimpleAdapter
from app.agents.safety import UnsafeEndpointError, assert_endpoint_safe


def _stub_response(*, status: int, body: object) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    if isinstance(body, str):
        response.text = body
        response.json = MagicMock(side_effect=ValueError("not json"))
    else:
        import json as _json

        response.text = _json.dumps(body)
        response.json = MagicMock(return_value=body)
    return response


@contextmanager
def patched_client(monkeypatch, module, *, response: MagicMock):
    """Patch the adapter module's httpx.Client to return a canned response."""
    captured: dict[str, object] = {}

    class _Client:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["body"] = json
            captured["headers"] = headers
            return response

    monkeypatch.setattr(module.httpx, "Client", _Client)
    yield captured


# ---- safety ----

def test_assert_endpoint_safe_blocks_localhost():
    with pytest.raises(UnsafeEndpointError):
        assert_endpoint_safe("http://localhost:8000/agent")


def test_assert_endpoint_safe_blocks_loopback_ip():
    with pytest.raises(UnsafeEndpointError):
        assert_endpoint_safe("https://127.0.0.1/agent")


def test_assert_endpoint_safe_blocks_private_ip():
    with pytest.raises(UnsafeEndpointError):
        assert_endpoint_safe("http://10.0.0.5/agent")


def test_assert_endpoint_safe_blocks_aws_imds():
    with pytest.raises(UnsafeEndpointError):
        assert_endpoint_safe("http://169.254.169.254/latest/meta-data/")


def test_assert_endpoint_safe_rejects_non_http_scheme():
    with pytest.raises(UnsafeEndpointError):
        assert_endpoint_safe("ftp://example.com/agent")


# ---- simple format ----

def test_http_simple_sends_last_user_message_and_parses_output(monkeypatch):
    monkeypatch.setattr(simple_mod, "assert_endpoint_safe", lambda url: None)
    response = _stub_response(status=200, body={"output": "hi from simple"})
    with patched_client(monkeypatch, simple_mod, response=response) as cap:
        adapter = HttpSimpleAdapter(url="https://example.test/agent")
        text, latency = adapter.send(
            [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "what's up"},
            ]
        )
    assert text == "hi from simple"
    assert latency >= 0
    assert cap["body"] == {"message": "what's up"}


def test_http_simple_accepts_alternative_field_names(monkeypatch):
    monkeypatch.setattr(simple_mod, "assert_endpoint_safe", lambda url: None)
    response = _stub_response(status=200, body={"reply": "via reply field"})
    with patched_client(monkeypatch, simple_mod, response=response):
        adapter = HttpSimpleAdapter(url="https://example.test/agent")
        text, _ = adapter.send([{"role": "user", "content": "hello"}])
    assert text == "via reply field"


def test_http_simple_raises_on_non_2xx(monkeypatch):
    monkeypatch.setattr(simple_mod, "assert_endpoint_safe", lambda url: None)
    response = _stub_response(status=500, body="server boom")
    with patched_client(monkeypatch, simple_mod, response=response):
        adapter = HttpSimpleAdapter(url="https://example.test/agent")
        with pytest.raises(RuntimeError, match="HTTP 500"):
            adapter.send([{"role": "user", "content": "hello"}])


def test_http_simple_raises_on_missing_output_field(monkeypatch):
    monkeypatch.setattr(simple_mod, "assert_endpoint_safe", lambda url: None)
    response = _stub_response(status=200, body={"unrelated": "field"})
    with patched_client(monkeypatch, simple_mod, response=response):
        adapter = HttpSimpleAdapter(url="https://example.test/agent")
        with pytest.raises(RuntimeError, match="missing a recognized text field"):
            adapter.send([{"role": "user", "content": "hello"}])


def test_http_simple_forwards_auth_header(monkeypatch):
    monkeypatch.setattr(simple_mod, "assert_endpoint_safe", lambda url: None)
    response = _stub_response(status=200, body={"output": "ok"})
    token = set_agent_auth_header("Bearer test-token")
    try:
        with patched_client(monkeypatch, simple_mod, response=response) as cap:
            adapter = HttpSimpleAdapter(url="https://example.test/agent")
            adapter.send([{"role": "user", "content": "hi"}])
        assert cap["headers"]["Authorization"] == "Bearer test-token"
    finally:
        reset_agent_auth_header(token)


# ---- openai-compatible format ----

def test_openai_compat_builds_messages_body_and_parses_choice(monkeypatch):
    monkeypatch.setattr(openai_compat_mod, "assert_endpoint_safe", lambda url: None)
    response = _stub_response(
        status=200,
        body={"choices": [{"message": {"content": "compat reply"}}]},
    )
    with patched_client(monkeypatch, openai_compat_mod, response=response) as cap:
        adapter = HttpOpenAICompatAdapter(
            url="https://example.test/v1/chat/completions",
            model="my-model",
        )
        text, _ = adapter.send(
            [
                {"role": "system", "content": "ignored upstream"},
                {"role": "user", "content": "explain"},
            ],
            max_tokens=128,
        )
    assert text == "compat reply"
    assert cap["body"]["model"] == "my-model"
    assert cap["body"]["max_tokens"] == 128
    assert cap["body"]["messages"] == [
        {"role": "system", "content": "ignored upstream"},
        {"role": "user", "content": "explain"},
    ]


def test_openai_compat_falls_back_to_choice_text(monkeypatch):
    """Some OpenAI-shape endpoints (legacy completions) return `text` not `message.content`."""
    monkeypatch.setattr(openai_compat_mod, "assert_endpoint_safe", lambda url: None)
    response = _stub_response(status=200, body={"choices": [{"text": "legacy reply"}]})
    with patched_client(monkeypatch, openai_compat_mod, response=response):
        adapter = HttpOpenAICompatAdapter(url="https://example.test/x", model=None)
        text, _ = adapter.send([{"role": "user", "content": "hi"}])
    assert text == "legacy reply"


def test_openai_compat_raises_on_missing_choices(monkeypatch):
    monkeypatch.setattr(openai_compat_mod, "assert_endpoint_safe", lambda url: None)
    response = _stub_response(status=200, body={"error": "nope"})
    with patched_client(monkeypatch, openai_compat_mod, response=response):
        adapter = HttpOpenAICompatAdapter(url="https://example.test/x", model="m")
        with pytest.raises(RuntimeError, match="choices"):
            adapter.send([{"role": "user", "content": "hi"}])


def test_openai_compat_raises_on_non_json_body(monkeypatch):
    monkeypatch.setattr(openai_compat_mod, "assert_endpoint_safe", lambda url: None)
    response = _stub_response(status=200, body="<html>oops</html>")
    with patched_client(monkeypatch, openai_compat_mod, response=response):
        adapter = HttpOpenAICompatAdapter(url="https://example.test/x", model="m")
        with pytest.raises(RuntimeError, match="non-JSON"):
            adapter.send([{"role": "user", "content": "hi"}])


# ---- retry ----

def test_adapter_retries_on_timeout(monkeypatch):
    """Transient httpx.TimeoutException retries and eventually succeeds."""
    monkeypatch.setattr(simple_mod, "assert_endpoint_safe", lambda url: None)
    monkeypatch.setattr(simple_mod.time, "sleep", lambda _: None)  # don't actually sleep

    calls = {"n": 0}
    success_response = _stub_response(status=200, body={"output": "ok"})

    class _Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def post(self, url, json=None, headers=None):
            calls["n"] += 1
            if calls["n"] < 2:
                raise httpx.TimeoutException("timed out")
            return success_response

    monkeypatch.setattr(simple_mod.httpx, "Client", _Client)
    adapter = HttpSimpleAdapter(url="https://example.test/agent")
    text, _ = adapter.send([{"role": "user", "content": "hi"}])
    assert text == "ok"
    assert calls["n"] == 2


# ---- factory ----

def test_factory_returns_prompt_adapter_by_default():
    adapter = build_adapter(
        connection_type="prompt",
        model="gpt-4o-mini",
        endpoint_url=None,
        endpoint_format=None,
    )
    assert adapter.prepends_system is True


def test_factory_returns_simple_adapter(monkeypatch):
    monkeypatch.setattr(simple_mod, "assert_endpoint_safe", lambda url: None)
    adapter = build_adapter(
        connection_type="http_endpoint",
        model=None,
        endpoint_url="https://example.test/agent",
        endpoint_format="simple",
    )
    assert isinstance(adapter, HttpSimpleAdapter)
    assert adapter.prepends_system is False


def test_factory_returns_openai_compat_adapter(monkeypatch):
    monkeypatch.setattr(openai_compat_mod, "assert_endpoint_safe", lambda url: None)
    adapter = build_adapter(
        connection_type="http_endpoint",
        model="m",
        endpoint_url="https://example.test/x",
        endpoint_format="openai_compat",
    )
    assert isinstance(adapter, HttpOpenAICompatAdapter)
    assert adapter.prepends_system is False


def test_factory_rejects_unknown_format(monkeypatch):
    monkeypatch.setattr(simple_mod, "assert_endpoint_safe", lambda url: None)
    with pytest.raises(ValueError, match="unknown endpoint_format"):
        build_adapter(
            connection_type="http_endpoint",
            model=None,
            endpoint_url="https://example.test/x",
            endpoint_format="bogus",
        )


def test_factory_requires_url_for_http_endpoint():
    with pytest.raises(ValueError, match="endpoint_url"):
        build_adapter(
            connection_type="http_endpoint",
            model=None,
            endpoint_url=None,
            endpoint_format="simple",
        )
