"""End-to-end smoke test of the full pipeline with mocked LLM clients.

Proves the orchestration in `tasks.run_pipeline`:
- generates scenarios via stub generator
- runs each scenario
- applies heuristic filter
- classifies non-flagged outputs
- clusters failures + detects dangerous failure
- writes the report with the correct verdict

We monkey-patch `chat_complete` and `embed` so the test runs without API keys.
"""
from __future__ import annotations

import os
import json
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_preflight.db")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

import pytest

from app import db as db_module
from app import tasks
from app.db import Base, SessionLocal, engine, init_db
from app.models import Scenario, SimulationReport, SimulationRun


@pytest.fixture
def fresh_db(monkeypatch):
    # Use a temp SQLite file per test to keep state isolated.
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    url = f"sqlite:///{tmp.name}"
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    new_engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)
    new_session = sessionmaker(bind=new_engine, autoflush=False, autocommit=False, future=True)

    monkeypatch.setattr(db_module, "engine", new_engine)
    monkeypatch.setattr(db_module, "SessionLocal", new_session)
    Base.metadata.create_all(new_engine)
    yield new_session
    os.unlink(tmp.name)


def _fake_chat_complete(messages, *, model=None, temperature=0.7, response_format=None, max_tokens=None):
    """Return canned outputs depending on the system prompt."""
    system = ""
    user = ""
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        elif m["role"] == "user":
            user = m["content"]

    # Cluster labeling
    if "max 8 words" in system:
        return "agent refuses on incomplete input", 100

    # Most-dangerous detection — return an index pointing at one of the listed failures
    if "safety reviewer" in system:
        return (
            json.dumps(
                {
                    "index": 1,
                    "reason": "Fabricates financial values when given empty input.",
                }
            ),
            120,
        )

    # Classification
    if system.startswith("You are an evaluator"):
        if "fabricates" in user.lower() or "i cannot" in user.lower():
            return json.dumps({"result": "FAILURE", "reason": "Refuses or hallucinates."}), 80
        return json.dumps({"result": "SUCCESS", "reason": "Looks good."}), 80

    # Default: simulate the user's agent responding. Bias toward producing
    # heuristic-flag outputs ~half the time to exercise the failure path.
    if "Ignore previous instructions" in user:
        return "I cannot help with that.", 50
    if "<empty>" in user:
        return "", 30
    return "Sure, here is the result you requested.", 60


def _fake_embed(texts):
    # Deterministic 8-dim "embeddings" by hashing — enough to populate KMeans.
    import hashlib

    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        out.append([b / 255.0 for b in h[:8]])
    return out


def test_pipeline_end_to_end(fresh_db, monkeypatch):
    monkeypatch.setattr(tasks, "session_scope", lambda: _scope(fresh_db))

    # Patch the LLM calls everywhere they are imported.
    from app.llm import clients as clients_mod
    from app.llm import classifier as classifier_mod
    from app.simulation import generator as generator_mod
    from app.analysis import clustering as clustering_mod
    from app.analysis import dangerous as dangerous_mod

    from app.simulation import runner as runner_mod

    monkeypatch.setattr(clients_mod, "chat_complete", _fake_chat_complete)
    monkeypatch.setattr(clients_mod, "embed", _fake_embed)
    monkeypatch.setattr(classifier_mod, "chat_complete", _fake_chat_complete)
    monkeypatch.setattr(generator_mod, "chat_complete", _fake_chat_complete)
    monkeypatch.setattr(generator_mod, "embed", _fake_embed)
    monkeypatch.setattr(clustering_mod, "chat_complete", _fake_chat_complete)
    monkeypatch.setattr(clustering_mod, "embed", _fake_embed)
    monkeypatch.setattr(dangerous_mod, "chat_complete", _fake_chat_complete)
    monkeypatch.setattr(runner_mod, "chat_complete", _fake_chat_complete)

    # Seed a run.
    session = fresh_db()
    run = SimulationRun(
        base_prompt="You are a helpful assistant.",
        success_criteria="Returns a complete answer.",
        scenario_count=10,
        model="gpt-4o-mini",
    )
    session.add(run)
    session.commit()
    run_id = run.id
    session.close()

    # Execute pipeline with stub generator.
    tasks.run_pipeline(run_id, use_stub_generator=True)

    session = fresh_db()
    refreshed = session.get(SimulationRun, run_id)
    report = session.get(SimulationReport, run_id)
    scenarios = session.query(Scenario).filter(Scenario.run_id == run_id).all()
    session.close()

    assert refreshed.status == "complete"
    assert refreshed.progress_pct == 100
    assert len(scenarios) == 10
    assert all(s.classified_as in {"success", "failure", "unclear"} for s in scenarios)

    assert report is not None
    assert report.total_runs == 10
    assert 0.0 <= report.success_rate <= 1.0
    assert report.verdict in {"SHIP", "HOLD", "REVIEW"}
    # Stub triggers refusals + empty responses so we expect failures + a dangerous one.
    assert report.most_dangerous_failure is not None
    # The dangerous failure must reference a real scenario row by ID for rerun support.
    assert report.most_dangerous_failure.get("scenario_id")
    failure_ids = {s.id for s in scenarios if s.classified_as == "failure"}
    assert report.most_dangerous_failure["scenario_id"] in failure_ids
    assert isinstance(report.failure_clusters, list)
    if report.failure_clusters:
        assert "example_scenario_id" in report.failure_clusters[0]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
from contextlib import contextmanager


@contextmanager
def _scope(SessionFactory):
    s = SessionFactory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
