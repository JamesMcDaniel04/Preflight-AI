from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..cost import estimate
from ..db import get_db
from ..models import Scenario, SimulationReport, SimulationRun
from ..schemas import (
    CreateRunRequest,
    CreateRunResponse,
    DangerousFailure,
    FailureCluster,
    PartialResults,
    ReportResponse,
    RunStatus,
    RunSummary,
)
from ..tasks import MILESTONES, run_pipeline

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _start_pipeline(run_id: str) -> None:
    """Run pipeline in a thread so it doesn't block the FastAPI event loop.

    Slice 1 swaps this for a Celery dispatch — the call signature stays the same.
    """
    import threading
    threading.Thread(target=run_pipeline, args=(run_id,), daemon=True).start()


@router.post("", response_model=CreateRunResponse)
def create_run(req: CreateRunRequest, db: Session = Depends(get_db)) -> CreateRunResponse:
    run = SimulationRun(
        base_prompt=req.base_prompt,
        success_criteria=req.success_criteria,
        scenario_count=req.scenario_count,
        model=req.model,
        status="pending",
        progress_pct=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    cost, secs = estimate(req.scenario_count)
    _start_pipeline(run.id)
    return CreateRunResponse(run_id=run.id, estimated_cost_usd=round(cost, 4), estimated_seconds=secs)


def _compute_partial_results(db: Session, run: SimulationRun) -> PartialResults | None:
    if run.last_milestone_emitted == 0 or run.status == "complete":
        return None
    scenarios = (
        db.query(Scenario)
        .filter(Scenario.run_id == run.id, Scenario.classified_as.is_not(None))
        .all()
    )
    if not scenarios:
        return None
    success = sum(1 for s in scenarios if s.classified_as == "success")
    failures = [s for s in scenarios if s.classified_as == "failure"]
    success_rate = success / len(scenarios)
    counter = Counter(s.failure_reason or "unlabeled" for s in failures)
    top = counter.most_common(1)[0][0] if counter else None
    return PartialResults(
        scenarios_complete=len(scenarios),
        success_rate_so_far=round(success_rate, 4),
        failure_count_so_far=len(failures),
        top_emerging_failure=top,
    )


@router.get("/{run_id}/status", response_model=RunStatus)
def get_status(run_id: str, db: Session = Depends(get_db)) -> RunStatus:
    run = db.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    partial = _compute_partial_results(db, run)
    return RunStatus(
        run_id=run.id,
        status=run.status,
        progress_pct=run.progress_pct,
        partial_results=partial,
        error=run.error,
    )


@router.get("/{run_id}/report", response_model=ReportResponse)
def get_report(run_id: str, db: Session = Depends(get_db)) -> ReportResponse:
    run = db.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    report = db.get(SimulationReport, run_id)
    if not report:
        raise HTTPException(status_code=409, detail="report not ready")

    return ReportResponse(
        run_id=run.id,
        base_prompt=run.base_prompt,
        success_criteria=run.success_criteria,
        model=run.model,
        success_rate=report.success_rate,
        total_runs=report.total_runs,
        avg_latency_ms=report.avg_latency_ms,
        unclear_rate=report.unclear_rate,
        failure_clusters=[FailureCluster(**c) for c in (report.failure_clusters or [])],
        most_dangerous_failure=(
            DangerousFailure(**report.most_dangerous_failure)
            if report.most_dangerous_failure
            else None
        ),
        verdict=report.verdict,
        verdict_reason=report.verdict_reason,
        generated_at=report.generated_at,
    )


@router.get("", response_model=list[RunSummary])
def list_runs(db: Session = Depends(get_db)) -> list[RunSummary]:
    runs = (
        db.query(SimulationRun)
        .order_by(SimulationRun.created_at.desc())
        .limit(20)
        .all()
    )
    out: list[RunSummary] = []
    for r in runs:
        report = db.get(SimulationReport, r.id)
        out.append(
            RunSummary(
                run_id=r.id,
                created_at=r.created_at,
                base_prompt_preview=r.base_prompt[:120],
                scenario_count=r.scenario_count,
                model=r.model,
                status=r.status,
                progress_pct=r.progress_pct,
                success_rate=report.success_rate if report else None,
                verdict=report.verdict if report else None,
            )
        )
    return out
