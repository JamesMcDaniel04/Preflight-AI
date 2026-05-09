from __future__ import annotations

from app import tasks
from app.models import Scenario, SimulationReport, SimulationRun, User

from .conftest import fake_chat_complete, fake_embed, scoped_session, signup


def test_api_smoke_run_report_and_rerun(client, temp_db, monkeypatch):
    from app.analysis import clustering as clustering_mod
    from app.analysis import dangerous as dangerous_mod
    from app.llm import classifier as classifier_mod
    from app.llm import clients as clients_mod
    from app.routes import runs as runs_route
    from app.simulation import generator as generator_mod
    from app.simulation import runner as runner_mod

    monkeypatch.setattr(tasks, "session_scope", lambda: scoped_session(temp_db))
    monkeypatch.setattr(clients_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(clients_mod, "embed", fake_embed)
    monkeypatch.setattr(classifier_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(generator_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(generator_mod, "embed", fake_embed)
    monkeypatch.setattr(clustering_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(clustering_mod, "embed", fake_embed)
    monkeypatch.setattr(dangerous_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(runner_mod, "chat_complete", fake_chat_complete)
    from app.agents import prompt as prompt_adapter_mod
    monkeypatch.setattr(prompt_adapter_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(
        runs_route,
        "_start_pipeline",
        lambda run_id, *, openai_key, anthropic_key, agent_auth_header=None: tasks.run_pipeline(
            run_id,
            use_stub_generator=True,
            openai_key=openai_key,
            anthropic_key=anthropic_key,
            agent_auth_header=agent_auth_header,
        ),
    )

    headers = signup(client, "owner@example.com")
    create = client.post(
        "/api/runs",
        json={
            "base_prompt": "You are a helpful assistant.",
            "success_criteria": "Returns a complete answer.",
            "scenario_count": 10,
            "model": "gpt-4o-mini",
            "run_mode": "single_turn",
            "ship_threshold": 0.85,
            "hold_threshold": 0.70,
        },
        headers={**headers, "X-OpenAI-Key": "sk-user-openai"},
    )
    assert create.status_code == 200, create.text
    run_id = create.json()["run_id"]

    status = client.get(f"/api/runs/{run_id}/status")
    assert status.status_code == 200
    assert status.json()["run_mode"] == "single_turn"
    assert status.json()["scenario_count"] == 10

    report = client.get(f"/api/runs/{run_id}/report")
    assert report.status_code == 200, report.text
    payload = report.json()
    assert payload["run_mode"] == "single_turn"
    assert payload["ship_threshold"] == 0.85
    assert payload["hold_threshold"] == 0.70
    assert payload["most_dangerous_failure"]["scenario_id"]

    rerun = client.post(
        f"/api/runs/{run_id}/scenarios/{payload['most_dangerous_failure']['scenario_id']}/rerun",
        headers={**headers, "X-OpenAI-Key": "sk-user-openai"},
    )
    assert rerun.status_code == 200, rerun.text
    assert rerun.json()["new_scenario_id"]

    report_after = client.get(f"/api/runs/{run_id}/report").json()
    assert report_after["total_runs"] == payload["total_runs"]
    assert report_after["verdict"] == payload["verdict"]

    session = temp_db()
    rerun_rows = (
        session.query(Scenario)
        .filter(Scenario.run_id == run_id, Scenario.include_in_report.is_(False))
        .all()
    )
    session.close()
    assert len(rerun_rows) == 1
    assert rerun_rows[0].rerun_of_scenario_id == payload["most_dangerous_failure"]["scenario_id"]


def test_multi_turn_pipeline_persists_transcript_and_milestones(temp_db, monkeypatch):
    from app.analysis import clustering as clustering_mod
    from app.analysis import dangerous as dangerous_mod
    from app.llm import classifier as classifier_mod
    from app.llm import clients as clients_mod
    from app.simulation import generator as generator_mod
    from app.simulation import runner as runner_mod

    monkeypatch.setattr(tasks, "session_scope", lambda: scoped_session(temp_db))
    monkeypatch.setattr(clients_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(clients_mod, "embed", fake_embed)
    monkeypatch.setattr(classifier_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(generator_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(generator_mod, "embed", fake_embed)
    monkeypatch.setattr(clustering_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(clustering_mod, "embed", fake_embed)
    monkeypatch.setattr(dangerous_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(runner_mod, "chat_complete", fake_chat_complete)
    from app.agents import prompt as prompt_adapter_mod
    monkeypatch.setattr(prompt_adapter_mod, "chat_complete", fake_chat_complete)

    session = temp_db()
    session.add(User(email="multi@example.com", password_hash="hashed"))
    session.commit()
    user = session.query(User).first()
    session.add(
        SimulationRun(
            owner_user_id=user.id,
            base_prompt="You are a helpful assistant.",
            success_criteria="Do not fabricate missing information.",
            scenario_count=5,
            model="gpt-4o-mini",
            run_mode="multi_turn",
            ship_threshold=0.9,
            hold_threshold=0.6,
            status="pending",
        )
    )
    session.commit()
    run = session.query(SimulationRun).first()
    run_id = run.id
    session.close()

    tasks.run_pipeline(run_id)

    session = temp_db()
    refreshed = session.get(SimulationRun, run_id)
    report = session.get(SimulationReport, run_id)
    scenarios = (
        session.query(Scenario)
        .filter(Scenario.run_id == run_id, Scenario.include_in_report.is_(True))
        .all()
    )
    session.close()

    assert refreshed.status == "complete"
    assert {"25", "50", "75"} <= set((refreshed.partial_results_cache or {}).keys())
    assert report is not None
    assert report.total_runs == 5
    assert all(s.transcript_json for s in scenarios)
    assert all("USER:" in (s.output or "") for s in scenarios)


def test_http_endpoint_pipeline_drives_user_url(client, temp_db, monkeypatch):
    """Run the full pipeline with connection_type=http_endpoint.

    Mocks both the agent endpoint (httpx) and the OpenAI calls (scenario gen,
    classifier, embeddings, dangerous-failure detection). Asserts:
      - The user's URL was posted to N times (one per scenario).
      - Auth header was forwarded to the user's endpoint.
      - The report records connection_type='http_endpoint' and the URL.
    """
    from app.agents import http_simple as simple_mod
    from app.analysis import clustering as clustering_mod
    from app.analysis import dangerous as dangerous_mod
    from app.llm import classifier as classifier_mod
    from app.llm import clients as clients_mod
    from app.routes import runs as runs_route
    from app.simulation import generator as generator_mod
    from app.simulation import runner as runner_mod

    # Wire all OpenAI calls to fakes — generator, classifier, clustering,
    # dangerous-failure, follow-up generator. The agent itself uses the
    # patched httpx client below, NOT chat_complete.
    monkeypatch.setattr(tasks, "session_scope", lambda: scoped_session(temp_db))
    monkeypatch.setattr(clients_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(clients_mod, "embed", fake_embed)
    monkeypatch.setattr(classifier_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(generator_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(generator_mod, "embed", fake_embed)
    monkeypatch.setattr(clustering_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(clustering_mod, "embed", fake_embed)
    monkeypatch.setattr(dangerous_mod, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(runner_mod, "chat_complete", fake_chat_complete)

    # Run the pipeline synchronously in-test (skip Celery + thread).
    monkeypatch.setattr(
        runs_route,
        "_start_pipeline",
        lambda run_id, *, openai_key, anthropic_key, agent_auth_header=None: tasks.run_pipeline(
            run_id,
            use_stub_generator=True,
            openai_key=openai_key,
            anthropic_key=anthropic_key,
            agent_auth_header=agent_auth_header,
        ),
    )

    # Bypass SSRF for the test URL.
    monkeypatch.setattr(simple_mod, "assert_endpoint_safe", lambda url: None)
    from app.agents import safety as safety_mod
    monkeypatch.setattr(safety_mod, "assert_endpoint_safe", lambda url: None)

    # Capture every call to the user's endpoint.
    posts: list[dict] = []

    class _FakeHttpClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def post(self, url, json=None, headers=None):
            posts.append({"url": url, "body": json, "headers": dict(headers or {})})
            from unittest.mock import MagicMock
            response = MagicMock()
            response.status_code = 200
            response.text = '{"output":"agent reply"}'
            response.json = MagicMock(return_value={"output": "agent reply"})
            return response

    monkeypatch.setattr(simple_mod.httpx, "Client", _FakeHttpClient)

    # Drive the pipeline through the API — confirms route → adapter wiring.
    headers = signup(client, "http-endpoint-tester@example.com")
    create = client.post(
        "/api/runs",
        json={
            "base_prompt": "Internal context — agent is at the URL below.",
            "success_criteria": "Returns a complete answer.",
            "scenario_count": 5,
            "model": "gpt-4o-mini",
            "run_mode": "single_turn",
            "connection_type": "http_endpoint",
            "endpoint_url": "https://api.example.test/agent/chat",
            "endpoint_format": "simple",
            "ship_threshold": 0.85,
            "hold_threshold": 0.70,
        },
        headers={
            **headers,
            "X-OpenAI-Key": "sk-user-openai",
            "X-Agent-Auth-Header": "Bearer agent-token-xyz",
        },
    )
    assert create.status_code == 200, create.text
    run_id = create.json()["run_id"]

    report = client.get(f"/api/runs/{run_id}/report")
    assert report.status_code == 200, report.text
    payload = report.json()
    assert payload["connection_type"] == "http_endpoint"
    assert payload["endpoint_url"] == "https://api.example.test/agent/chat"
    assert payload["endpoint_format"] == "simple"

    # The fake endpoint was hit once per scenario.
    assert len(posts) == 5
    for entry in posts:
        assert entry["url"] == "https://api.example.test/agent/chat"
        assert entry["headers"].get("Authorization") == "Bearer agent-token-xyz"
        assert "message" in entry["body"]
