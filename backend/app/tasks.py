"""End-to-end pipeline for one simulation run.

Slice 0–1: invoked via `asyncio.create_task` from the route handler (see main.py).
Slice 2+: same `run_pipeline` is wrapped by a Celery task.

Keeping the orchestration framework-agnostic means we can move it under Celery
without rewriting the business logic.
"""
from __future__ import annotations

import logging
from datetime import datetime
from statistics import mean

from .analysis.clustering import cluster_failures
from .analysis.dangerous import detect_most_dangerous
from .analysis.verdict import compute_verdict
from .db import session_scope
from .llm.classifier import classify_with_llm, heuristic_flag
from .llm.clients import set_openai_key, reset_openai_key
from .models import Scenario, SimulationReport, SimulationRun
from .simulation.generator import generate_scenarios
from .simulation.runner import run_scenario

log = logging.getLogger(__name__)

MILESTONES = (25, 50, 75)


def _emit_milestone_if_needed(session, run: SimulationRun) -> None:
    crossed = max((m for m in MILESTONES if run.progress_pct >= m), default=0)
    if crossed and crossed > run.last_milestone_emitted:
        run.last_milestone_emitted = crossed
        session.commit()


def _set_progress(session, run_id: str, completed: int, total: int) -> None:
    pct = int((completed / total) * 100) if total else 0
    run = session.get(SimulationRun, run_id)
    if not run:
        return
    run.progress_pct = pct
    _emit_milestone_if_needed(session, run)


def run_pipeline(
    run_id: str, *, use_stub_generator: bool = False, openai_key: str | None = None
) -> None:
    """Execute the full simulation pipeline for a given run.

    `openai_key`, when provided, overrides the env-var key for the duration of
    this run via a contextvar — every nested LLM call picks it up.
    """
    token = set_openai_key(openai_key) if openai_key else None
    try:
        _run_pipeline_inner(run_id, use_stub_generator=use_stub_generator)
    finally:
        if token is not None:
            reset_openai_key(token)


def _run_pipeline_inner(run_id: str, *, use_stub_generator: bool = False) -> None:
    with session_scope() as session:
        run = session.get(SimulationRun, run_id)
        if not run:
            log.error("run %s not found", run_id)
            return
        run.status = "running"
        base_prompt = run.base_prompt
        success_criteria = run.success_criteria
        target_n = run.scenario_count
        model = run.model
        session.commit()

    try:
        pairs = generate_scenarios(base_prompt, target_n, model=model, use_stub=use_stub_generator)
        if not pairs:
            raise RuntimeError("scenario generation produced 0 inputs")

        # Persist scenarios up front so the frontend can see them appear.
        scenario_ids: list[str] = []
        with session_scope() as session:
            for persona, text in pairs:
                s = Scenario(run_id=run_id, persona_seed=persona.seed, input=text)
                session.add(s)
                session.flush()
                scenario_ids.append(s.id)

        total = len(scenario_ids)
        completed = 0

        for sid in scenario_ids:
            with session_scope() as session:
                s = session.get(Scenario, sid)
                if s is None:
                    continue
                input_text = s.input

            output, latency_ms, err = run_scenario(base_prompt, input_text, model=model)
            flag = heuristic_flag(output) if not err else "empty_response"

            classified: str
            reason: str | None
            if err:
                classified = "failure"
                reason = f"runtime error: {err}"
            elif flag is not None:
                classified = "failure"
                reason = flag
            else:
                try:
                    classified, reason = classify_with_llm(output, success_criteria, model=model)
                except Exception as e:  # don't let one classifier hiccup kill the whole run
                    classified = "unclear"
                    reason = f"classifier error: {str(e)[:200]}"

            with session_scope() as session:
                s = session.get(Scenario, sid)
                if s is None:
                    continue
                s.output = output
                s.latency_ms = latency_ms
                s.heuristic_flag = flag
                s.classified_as = classified
                s.failure_reason = reason if classified != "success" else None
                s.error = err

                completed += 1
                _set_progress(session, run_id, completed, total)

        # Build the report.
        with session_scope() as session:
            scenarios: list[Scenario] = (
                session.query(Scenario).filter(Scenario.run_id == run_id).all()
            )
            success = sum(1 for s in scenarios if s.classified_as == "success")
            unclear = sum(1 for s in scenarios if s.classified_as == "unclear")
            failure_objs = [s for s in scenarios if s.classified_as == "failure"]
            success_rate = success / len(scenarios) if scenarios else 0.0
            unclear_rate = unclear / len(scenarios) if scenarios else 0.0
            latencies = [s.latency_ms for s in scenarios if s.latency_ms]
            avg_latency = float(mean(latencies)) if latencies else 0.0

            failure_dicts = [
                {
                    "id": s.id,
                    "input": s.input,
                    "output": s.output or "",
                    "failure_reason": s.failure_reason,
                }
                for s in failure_objs
            ]
            try:
                clusters = cluster_failures(failure_dicts)
            except Exception as e:
                log.exception("clustering failed: %s", e)
                clusters = []

            try:
                dangerous = detect_most_dangerous(base_prompt, failure_dicts) if failure_dicts else None
            except Exception as e:
                log.exception("dangerous detection failed: %s", e)
                dangerous = None

            verdict, verdict_reason = compute_verdict(
                success_rate, has_dangerous_failure=bool(dangerous), unclear_rate=unclear_rate
            )

            report = SimulationReport(
                run_id=run_id,
                success_rate=success_rate,
                total_runs=len(scenarios),
                avg_latency_ms=avg_latency,
                unclear_rate=unclear_rate,
                failure_clusters=clusters,
                most_dangerous_failure=dangerous,
                verdict=verdict,
                verdict_reason=verdict_reason,
                generated_at=datetime.utcnow(),
            )
            session.merge(report)

            run = session.get(SimulationRun, run_id)
            if run:
                run.status = "complete"
                run.progress_pct = 100
                run.last_milestone_emitted = 100

    except Exception as e:
        log.exception("pipeline failed for run %s", run_id)
        with session_scope() as session:
            run = session.get(SimulationRun, run_id)
            if run:
                run.status = "failed"
                run.error = str(e)[:1000]
