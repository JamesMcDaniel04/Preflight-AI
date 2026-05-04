"""End-to-end pipeline for one simulation run."""
from __future__ import annotations

import logging
from datetime import datetime
from statistics import mean

from .analysis.clustering import cluster_failures
from .analysis.dangerous import detect_most_dangerous
from .analysis.verdict import compute_verdict
from .db import session_scope
from .llm.classifier import classify_with_llm, heuristic_flag
from .llm.clients import (
    reset_anthropic_key,
    reset_openai_key,
    set_anthropic_key,
    set_openai_key,
)
from .models import Scenario, SimulationReport, SimulationRun
from .simulation.generator import GeneratedScenario, generate_scenarios
from .simulation.runner import ScenarioExecution, execute_scenario


log = logging.getLogger(__name__)

MILESTONES = (25, 50, 75)


def classify_execution(
    execution: ScenarioExecution,
    success_criteria: str,
    *,
    model: str | None = None,
) -> tuple[str | None, str, str | None]:
    for agent_output in execution.agent_outputs:
        flag = heuristic_flag(agent_output)
        if flag is not None:
            return flag, "failure", flag
    try:
        classified, reason = classify_with_llm(execution.output, success_criteria, model=model)
    except Exception as exc:
        return None, "unclear", f"classifier error: {str(exc)[:200]}"
    return None, classified, reason


def _partial_snapshot(session, run_id: str) -> dict | None:
    scenarios: list[Scenario] = (
        session.query(Scenario)
        .filter(
            Scenario.run_id == run_id,
            Scenario.include_in_report.is_(True),
            Scenario.classified_as.is_not(None),
        )
        .all()
    )
    if not scenarios:
        return None
    success = sum(1 for s in scenarios if s.classified_as == "success")
    failures = [s for s in scenarios if s.classified_as == "failure"]
    top = None
    if failures:
        counts: dict[str, int] = {}
        for failure in failures:
            key = failure.failure_reason or "unlabeled"
            counts[key] = counts.get(key, 0) + 1
        top = max(counts, key=counts.get)
    return {
        "scenarios_complete": len(scenarios),
        "success_rate_so_far": round(success / len(scenarios), 4),
        "failure_count_so_far": len(failures),
        "top_emerging_failure": top,
    }


def _maybe_cache_milestone(session, run: SimulationRun) -> None:
    crossed = max((m for m in MILESTONES if run.progress_pct >= m), default=0)
    if not crossed or crossed <= run.last_milestone_emitted:
        return
    cache = dict(run.partial_results_cache or {})
    snapshot = _partial_snapshot(session, run.id)
    if snapshot:
        cache[str(crossed)] = snapshot
        run.partial_results_cache = cache
    run.last_milestone_emitted = crossed


def _set_progress(session, run_id: str, completed: int, total: int) -> None:
    run = session.get(SimulationRun, run_id)
    if not run:
        return
    run.progress_pct = int((completed / total) * 100) if total else 0
    _maybe_cache_milestone(session, run)


def _persist_generated_scenarios(
    run_id: str,
    generated: list[GeneratedScenario],
) -> list[str]:
    scenario_ids: list[str] = []
    with session_scope() as session:
        for item in generated:
            scenario = Scenario(
                run_id=run_id,
                persona_seed=item.persona.seed,
                input=item.opening_message,
                hidden_goal=item.hidden_goal,
                include_in_report=True,
            )
            session.add(scenario)
            session.flush()
            scenario_ids.append(scenario.id)
    return scenario_ids


def run_pipeline(
    run_id: str,
    *,
    use_stub_generator: bool = False,
    openai_key: str | None = None,
    anthropic_key: str | None = None,
) -> None:
    openai_token = set_openai_key(openai_key) if openai_key else None
    anthropic_token = set_anthropic_key(anthropic_key) if anthropic_key else None
    try:
        _run_pipeline_inner(run_id, use_stub_generator=use_stub_generator)
    finally:
        if anthropic_token is not None:
            reset_anthropic_key(anthropic_token)
        if openai_token is not None:
            reset_openai_key(openai_token)


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
        run_mode = run.run_mode
        ship_threshold = run.ship_threshold
        hold_threshold = run.hold_threshold

    try:
        generated = generate_scenarios(
            base_prompt,
            target_n,
            model=model,
            run_mode=run_mode,
            use_stub=use_stub_generator,
        )
        if not generated:
            raise RuntimeError("scenario generation produced 0 inputs")

        scenario_ids = _persist_generated_scenarios(run_id, generated)
        total = len(scenario_ids)
        completed = 0

        for scenario_id in scenario_ids:
            with session_scope() as session:
                scenario = session.get(Scenario, scenario_id)
                if scenario is None:
                    continue
                execution = execute_scenario(
                    base_prompt,
                    scenario.input,
                    model=model,
                    run_mode=run_mode,
                    persona_seed=scenario.persona_seed,
                    hidden_goal=scenario.hidden_goal,
                )
                if execution.error:
                    flag = "empty_response"
                    classified = "failure"
                    reason = f"runtime error: {execution.error}"
                else:
                    flag, classified, reason = classify_execution(
                        execution,
                        success_criteria,
                        model=model,
                    )

                scenario.output = execution.output
                scenario.transcript_json = execution.transcript
                scenario.latency_ms = execution.latency_ms
                scenario.heuristic_flag = flag
                scenario.classified_as = classified
                scenario.failure_reason = reason if classified != "success" else None
                scenario.error = execution.error

                completed += 1
                _set_progress(session, run_id, completed, total)

        with session_scope() as session:
            scenarios: list[Scenario] = (
                session.query(Scenario)
                .filter(Scenario.run_id == run_id, Scenario.include_in_report.is_(True))
                .all()
            )
            success = sum(1 for s in scenarios if s.classified_as == "success")
            unclear = sum(1 for s in scenarios if s.classified_as == "unclear")
            failures = [s for s in scenarios if s.classified_as == "failure"]
            success_rate = success / len(scenarios) if scenarios else 0.0
            unclear_rate = unclear / len(scenarios) if scenarios else 0.0
            latencies = [s.latency_ms for s in scenarios if s.latency_ms is not None]
            avg_latency = float(mean(latencies)) if latencies else 0.0

            failure_dicts = [
                {
                    "id": s.id,
                    "input": s.input,
                    "output": s.output or "",
                    "failure_reason": s.failure_reason,
                }
                for s in failures
            ]
            try:
                clusters = cluster_failures(failure_dicts)
            except Exception as exc:
                log.exception("clustering failed: %s", exc)
                clusters = []

            try:
                dangerous = (
                    detect_most_dangerous(base_prompt, failure_dicts) if failure_dicts else None
                )
            except Exception as exc:
                log.exception("dangerous detection failed: %s", exc)
                dangerous = None

            verdict, verdict_reason = compute_verdict(
                success_rate,
                has_dangerous_failure=bool(dangerous),
                unclear_rate=unclear_rate,
                ship_threshold=ship_threshold,
                hold_threshold=hold_threshold,
            )

            session.merge(
                SimulationReport(
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
            )

            run = session.get(SimulationRun, run_id)
            if run:
                run.status = "complete"
                run.progress_pct = 100
                run.last_milestone_emitted = 100

    except Exception as exc:
        log.exception("pipeline failed for run %s", run_id)
        with session_scope() as session:
            run = session.get(SimulationRun, run_id)
            if run:
                run.status = "failed"
                run.error = str(exc)[:1000]
