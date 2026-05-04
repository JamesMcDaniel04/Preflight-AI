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
    monkeypatch.setattr(
        runs_route,
        "_start_pipeline",
        lambda run_id, *, openai_key, anthropic_key: tasks.run_pipeline(
            run_id,
            use_stub_generator=True,
            openai_key=openai_key,
            anthropic_key=anthropic_key,
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
