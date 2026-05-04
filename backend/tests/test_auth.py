from __future__ import annotations

from app.routes import runs as runs_route

from .conftest import signup


def test_auth_signup_login_logout_and_cookie_flags(client):
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"] is None
    assert "preflight_csrf=" in me.headers.get("set-cookie", "")
    assert "HttpOnly" not in me.headers.get("set-cookie", "")

    missing_csrf = client.post(
        "/api/auth/signup",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert missing_csrf.status_code == 403

    headers = signup(client, "user@example.com")
    me_after = client.get("/api/auth/me")
    assert me_after.json()["user"]["email"] == "user@example.com"

    login = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password123"},
        headers=headers,
    )
    assert login.status_code == 200
    assert "HttpOnly" in login.headers.get("set-cookie", "")

    bad_login = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "wrong-pass"},
        headers=headers,
    )
    assert bad_login.status_code == 401

    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert logout.json()["user"] is None


def test_duplicate_email_and_run_ownership(client, second_client, monkeypatch):
    headers = signup(client, "owner@example.com")
    duplicate = client.post(
        "/api/auth/signup",
        json={"email": "owner@example.com", "password": "password123"},
        headers=headers,
    )
    assert duplicate.status_code == 409

    monkeypatch.setattr(
        runs_route,
        "_start_pipeline",
        lambda run_id, *, openai_key, anthropic_key: None,
    )
    create = client.post(
        "/api/runs",
        json={
            "base_prompt": "You are a helpful assistant.",
            "success_criteria": "Return a complete answer.",
            "scenario_count": 5,
            "model": "gpt-4o-mini",
            "run_mode": "single_turn",
            "ship_threshold": 0.85,
            "hold_threshold": 0.70,
        },
        headers={**headers, "X-OpenAI-Key": "sk-user-openai"},
    )
    assert create.status_code == 200
    run_id = create.json()["run_id"]

    other_headers = signup(second_client, "other@example.com")
    status = second_client.get(f"/api/runs/{run_id}/status")
    assert status.status_code == 404
    rerun = second_client.post(
        f"/api/runs/{run_id}/scenarios/not-real/rerun",
        headers={**other_headers, "X-OpenAI-Key": "sk-user-openai"},
    )
    assert rerun.status_code == 404


def test_byok_requirements_and_threshold_validation(client, monkeypatch):
    headers = signup(client, "keys@example.com")
    monkeypatch.setattr(
        runs_route,
        "_start_pipeline",
        lambda run_id, *, openai_key, anthropic_key: None,
    )

    missing_openai = client.post(
        "/api/runs",
        json={
            "base_prompt": "You are a helpful assistant.",
            "success_criteria": "Return a complete answer.",
            "scenario_count": 5,
            "model": "gpt-4o-mini",
            "run_mode": "single_turn",
            "ship_threshold": 0.85,
            "hold_threshold": 0.70,
        },
        headers=headers,
    )
    assert missing_openai.status_code == 400

    bad_thresholds = client.post(
        "/api/runs",
        json={
            "base_prompt": "You are a helpful assistant.",
            "success_criteria": "Return a complete answer.",
            "scenario_count": 5,
            "model": "gpt-4o-mini",
            "run_mode": "single_turn",
            "ship_threshold": 0.60,
            "hold_threshold": 0.70,
        },
        headers={**headers, "X-OpenAI-Key": "sk-user-openai"},
    )
    assert bad_thresholds.status_code == 422

    anthropic_missing_openai = client.post(
        "/api/runs",
        json={
            "base_prompt": "You are a helpful assistant.",
            "success_criteria": "Return a complete answer.",
            "scenario_count": 5,
            "model": "claude-3-5-sonnet-latest",
            "run_mode": "single_turn",
            "ship_threshold": 0.85,
            "hold_threshold": 0.70,
        },
        headers={**headers, "X-Anthropic-Key": "sk-ant-user"},
    )
    assert anthropic_missing_openai.status_code == 400

    anthropic_ok = client.post(
        "/api/runs",
        json={
            "base_prompt": "You are a helpful assistant.",
            "success_criteria": "Return a complete answer.",
            "scenario_count": 5,
            "model": "claude-3-5-sonnet-latest",
            "run_mode": "single_turn",
            "ship_threshold": 0.85,
            "hold_threshold": 0.70,
        },
        headers={
            **headers,
            "X-OpenAI-Key": "sk-user-openai",
            "X-Anthropic-Key": "sk-ant-user",
        },
    )
    assert anthropic_ok.status_code == 200
