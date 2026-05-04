from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    base_prompt: str = Field(min_length=10, max_length=4000)
    success_criteria: str = Field(min_length=5, max_length=2000)
    scenario_count: int = Field(default=100, ge=5, le=500)
    model: str = "gpt-4o-mini"


class CreateRunResponse(BaseModel):
    run_id: str
    estimated_cost_usd: float
    estimated_seconds: int


class PartialResults(BaseModel):
    scenarios_complete: int
    success_rate_so_far: float
    failure_count_so_far: int
    top_emerging_failure: str | None = None


class RunStatus(BaseModel):
    run_id: str
    status: str
    progress_pct: int
    partial_results: PartialResults | None = None
    error: str | None = None


class FailureCluster(BaseModel):
    label: str
    count: int
    example_input: str
    example_output: str


class DangerousFailure(BaseModel):
    input: str
    output: str
    reason: str


class ReportResponse(BaseModel):
    run_id: str
    base_prompt: str
    success_criteria: str
    model: str
    success_rate: float
    total_runs: int
    avg_latency_ms: float
    unclear_rate: float
    failure_clusters: list[FailureCluster]
    most_dangerous_failure: DangerousFailure | None
    verdict: str
    verdict_reason: str
    generated_at: datetime


class RunSummary(BaseModel):
    run_id: str
    created_at: datetime
    base_prompt_preview: str
    scenario_count: int
    model: str
    status: str
    progress_pct: int
    success_rate: float | None = None
    verdict: str | None = None
