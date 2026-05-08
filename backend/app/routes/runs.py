from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, verify_csrf
from ..cost import estimate
from ..db import get_db
from ..llm.clients import (
    reset_anthropic_key,
    reset_openai_key,
    set_anthropic_key,
    set_openai_key,
    validate_model_access,
)
from ..models import Scenario, SimulationReport, SimulationRun, User
from ..schemas import (
    CreateRunRequest,
    CreateRunResponse,
    DangerousFailure,
    FailureCluster,
    PartialResults,
    ProfileSummary,
    ReportResponse,
    RerunResponse,
    RunStatus,
    RunSummary,
)
from ..simulation.profiles import list_profiles
from ..simulation.runner import execute_scenario
from ..tasks import classify_execution, run_pipeline


router = APIRouter(prefix="/api/runs", tags=["runs"])


def _owned_run_or_404(db: Session, run_id: str, user_id: str) -> SimulationRun:
    run = (
        db.query(SimulationRun)
        .filter(SimulationRun.id == run_id, SimulationRun.owner_user_id == user_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


def _start_pipeline(
    run_id: str,
    *,
    openai_key: str | None,
    anthropic_key: str | None,
) -> None:
    try:
        from celery_app import run_pipeline_task

        run_pipeline_task.apply_async(args=[run_id, openai_key, anthropic_key])
        return
    except Exception:
        import threading

        threading.Thread(
            target=run_pipeline,
            args=(run_id,),
            kwargs={"openai_key": openai_key, "anthropic_key": anthropic_key},
            daemon=True,
        ).start()


def _partial_from_cache(run: SimulationRun) -> PartialResults | None:
    if run.status == "complete":
        return None
    cache = run.partial_results_cache or {}
    if not cache:
        return None
    latest = max((int(key) for key in cache.keys()), default=0)
    if latest <= 0:
        return None
    return PartialResults(**cache[str(latest)])


@router.post("", response_model=CreateRunResponse)
def create_run(
    req: CreateRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: str = Depends(verify_csrf),
    x_openai_key: str | None = Header(default=None, alias="X-OpenAI-Key"),
    x_anthropic_key: str | None = Header(default=None, alias="X-Anthropic-Key"),
) -> CreateRunResponse:
    try:
        validate_model_access(
            req.model,
            openai_key=x_openai_key,
            anthropic_key=x_anthropic_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run = SimulationRun(
        owner_user_id=user.id,
        base_prompt=req.base_prompt,
        success_criteria=req.success_criteria,
        scenario_count=req.scenario_count,
        model=req.model,
        run_mode=req.run_mode,
        test_profile=req.test_profile or "general",
        ship_threshold=req.ship_threshold,
        hold_threshold=req.hold_threshold,
        status="pending",
        progress_pct=0,
        partial_results_cache={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    cost, secs = estimate(req.scenario_count)
    _start_pipeline(
        run.id,
        openai_key=x_openai_key,
        anthropic_key=x_anthropic_key,
    )
    return CreateRunResponse(
        run_id=run.id,
        estimated_cost_usd=round(cost, 4),
        estimated_seconds=secs,
    )


@router.get("/{run_id}/status", response_model=RunStatus)
def get_status(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RunStatus:
    run = _owned_run_or_404(db, run_id, user.id)
    return RunStatus(
        run_id=run.id,
        run_mode=run.run_mode,
        scenario_count=run.scenario_count,
        status=run.status,
        progress_pct=run.progress_pct,
        partial_results=_partial_from_cache(run),
        error=run.error,
    )


@router.get("/{run_id}/report", response_model=ReportResponse)
def get_report(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportResponse:
    run = _owned_run_or_404(db, run_id, user.id)
    report = db.get(SimulationReport, run_id)
    if not report:
        raise HTTPException(status_code=409, detail="report not ready")
    return ReportResponse(
        run_id=run.id,
        base_prompt=run.base_prompt,
        success_criteria=run.success_criteria,
        model=run.model,
        run_mode=run.run_mode,
        test_profile=run.test_profile,
        ship_threshold=run.ship_threshold,
        hold_threshold=run.hold_threshold,
        success_rate=report.success_rate,
        total_runs=report.total_runs,
        avg_latency_ms=report.avg_latency_ms,
        unclear_rate=report.unclear_rate,
        failure_clusters=[FailureCluster(**item) for item in (report.failure_clusters or [])],
        most_dangerous_failure=(
            DangerousFailure(**report.most_dangerous_failure)
            if report.most_dangerous_failure
            else None
        ),
        verdict=report.verdict,
        verdict_reason=report.verdict_reason,
        generated_at=report.generated_at,
    )


@router.post("/{run_id}/scenarios/{scenario_id}/rerun", response_model=RerunResponse)
def rerun_scenario(
    run_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: str = Depends(verify_csrf),
    x_openai_key: str | None = Header(default=None, alias="X-OpenAI-Key"),
    x_anthropic_key: str | None = Header(default=None, alias="X-Anthropic-Key"),
) -> RerunResponse:
    run = _owned_run_or_404(db, run_id, user.id)
    try:
        validate_model_access(
            run.model,
            openai_key=x_openai_key,
            anthropic_key=x_anthropic_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    original = (
        db.query(Scenario)
        .filter(
            Scenario.id == scenario_id,
            Scenario.run_id == run_id,
            Scenario.include_in_report.is_(True),
            Scenario.rerun_of_scenario_id.is_(None),
        )
        .first()
    )
    if not original:
        raise HTTPException(status_code=404, detail="scenario not found in this run")

    new = Scenario(
        run_id=run_id,
        rerun_of_scenario_id=original.id,
        persona_seed=original.persona_seed,
        input=original.input,
        hidden_goal=original.hidden_goal,
        include_in_report=False,
    )
    db.add(new)
    db.commit()
    db.refresh(new)

    openai_token = set_openai_key(x_openai_key) if x_openai_key else None
    anthropic_token = set_anthropic_key(x_anthropic_key) if x_anthropic_key else None
    try:
        execution = execute_scenario(
            run.base_prompt,
            original.input,
            model=run.model,
            run_mode=run.run_mode,
            persona_seed=original.persona_seed,
            hidden_goal=original.hidden_goal,
        )
        if execution.error:
            flag = "empty_response"
            classified = "failure"
            reason = f"runtime error: {execution.error}"
        else:
            flag, classified, reason = classify_execution(
                execution,
                run.success_criteria,
                model=run.model,
                test_profile=run.test_profile or "general",
            )
    finally:
        if anthropic_token is not None:
            reset_anthropic_key(anthropic_token)
        if openai_token is not None:
            reset_openai_key(openai_token)

    new.output = execution.output
    new.transcript_json = execution.transcript
    new.latency_ms = execution.latency_ms
    new.heuristic_flag = flag
    new.classified_as = classified
    new.failure_reason = reason if classified != "success" else None
    new.error = execution.error
    db.commit()

    return RerunResponse(
        new_scenario_id=new.id,
        input=new.input,
        output=new.output or "",
        transcript=new.transcript_json,
        latency_ms=new.latency_ms or 0,
        classified_as=new.classified_as or "unclear",
        failure_reason=new.failure_reason,
        heuristic_flag=new.heuristic_flag,
    )


@router.get("", response_model=list[RunSummary])
def list_runs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RunSummary]:
    runs = (
        db.query(SimulationRun)
        .filter(SimulationRun.owner_user_id == user.id)
        .order_by(SimulationRun.created_at.desc())
        .limit(20)
        .all()
    )
    out: list[RunSummary] = []
    for run in runs:
        report = db.get(SimulationReport, run.id)
        out.append(
            RunSummary(
                run_id=run.id,
                created_at=run.created_at,
                base_prompt_preview=run.base_prompt[:120],
                scenario_count=run.scenario_count,
                model=run.model,
                run_mode=run.run_mode,
                test_profile=run.test_profile or "general",
                status=run.status,
                progress_pct=run.progress_pct,
                success_rate=report.success_rate if report else None,
                verdict=report.verdict if report else None,
            )
        )
    return out
