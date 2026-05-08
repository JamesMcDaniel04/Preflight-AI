from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class CreateRunRequest(BaseModel):
    base_prompt: str = Field(min_length=10, max_length=4000)
    success_criteria: str = Field(min_length=5, max_length=2000)
    scenario_count: int = Field(default=100, ge=5, le=500)
    model: str = "gpt-4o-mini"
    run_mode: Literal["single_turn", "multi_turn"] = "single_turn"
    test_profile: str = "general"
    connection_type: Literal["prompt", "http_endpoint"] = "prompt"
    endpoint_url: str | None = Field(default=None, max_length=2000)
    endpoint_format: Literal["simple", "openai_compat"] | None = None
    ship_threshold: float = Field(default=0.85, ge=0.50, le=1.00)
    hold_threshold: float = Field(default=0.70, ge=0.0, le=0.99)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "CreateRunRequest":
        if self.ship_threshold <= self.hold_threshold:
            raise ValueError("ship_threshold must be greater than hold_threshold")
        return self

    @model_validator(mode="after")
    def validate_connection(self) -> "CreateRunRequest":
        if self.connection_type == "http_endpoint":
            if not self.endpoint_url:
                raise ValueError("endpoint_url is required when connection_type='http_endpoint'")
            if not self.endpoint_format:
                raise ValueError("endpoint_format is required when connection_type='http_endpoint'")
        return self


class TestConnectionRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    format: Literal["simple", "openai_compat"] = "openai_compat"
    model: str | None = "user-agent"


class TestConnectionResponse(BaseModel):
    ok: bool
    latency_ms: int | None = None
    sample_response: str | None = None
    error: str | None = None


class ProfileSummary(BaseModel):
    """Public-facing description of a test profile, used by the frontend dropdown."""
    id: str
    label: str
    description: str
    default_base_prompt: str
    default_success_criteria: str
    has_scoring_rules: bool


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
    run_mode: str
    scenario_count: int
    status: str
    progress_pct: int
    partial_results: PartialResults | None = None
    error: str | None = None


class FailureCluster(BaseModel):
    label: str
    count: int
    example_scenario_id: str | None = None
    example_input: str
    example_output: str


class DangerousFailure(BaseModel):
    scenario_id: str | None = None
    input: str
    output: str
    reason: str


class RerunResponse(BaseModel):
    new_scenario_id: str
    input: str
    output: str
    transcript: list[dict] | None = None
    latency_ms: int
    classified_as: str
    failure_reason: str | None = None
    heuristic_flag: str | None = None


class ReportResponse(BaseModel):
    run_id: str
    base_prompt: str
    success_criteria: str
    model: str
    run_mode: str
    test_profile: str
    connection_type: str = "prompt"
    endpoint_url: str | None = None
    endpoint_format: str | None = None
    ship_threshold: float
    hold_threshold: float
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
    run_mode: str
    test_profile: str = "general"
    connection_type: str = "prompt"
    endpoint_url: str | None = None
    status: str
    progress_pct: int
    success_rate: float | None = None
    verdict: str | None = None


class UserSummary(BaseModel):
    id: str
    email: EmailStr

    @classmethod
    def from_model(cls, user) -> "UserSummary":
        return cls(id=user.id, email=user.email)


class AuthResponse(BaseModel):
    user: UserSummary | None


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
