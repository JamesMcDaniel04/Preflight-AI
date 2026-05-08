from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    runs: Mapped[list["SimulationRun"]] = relationship(back_populates="owner")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    base_prompt: Mapped[str] = mapped_column(Text)
    success_criteria: Mapped[str] = mapped_column(Text)
    scenario_count: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(64))
    run_mode: Mapped[str] = mapped_column(String(24), default="single_turn")
    test_profile: Mapped[str] = mapped_column(String(32), default="general")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    last_milestone_emitted: Mapped[int] = mapped_column(Integer, default=0)
    ship_threshold: Mapped[float] = mapped_column(Float, default=0.85)
    hold_threshold: Mapped[float] = mapped_column(Float, default=0.70)
    partial_results_cache: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped[User] = relationship(back_populates="runs")
    scenarios: Mapped[list["Scenario"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    report: Mapped["SimulationReport | None"] = relationship(
        back_populates="run", uselist=False, cascade="all, delete-orphan"
    )


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.id"), index=True)
    rerun_of_scenario_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("scenarios.id"), nullable=True, index=True
    )
    persona_seed: Mapped[str] = mapped_column(String(64))
    input: Mapped[str] = mapped_column(Text)
    hidden_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heuristic_flag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classified_as: Mapped[str | None] = mapped_column(String(16), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    include_in_report: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[SimulationRun] = relationship(back_populates="scenarios")
    rerun_of: Mapped["Scenario | None"] = relationship(remote_side=[id])


class SimulationReport(Base):
    __tablename__ = "simulation_reports"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulation_runs.id"), primary_key=True
    )
    success_rate: Mapped[float] = mapped_column(Float)
    total_runs: Mapped[int] = mapped_column(Integer)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    unclear_rate: Mapped[float] = mapped_column(Float, default=0.0)
    failure_clusters: Mapped[list] = mapped_column(JSON, default=list)
    most_dangerous_failure: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verdict: Mapped[str] = mapped_column(String(16))
    verdict_reason: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    run: Mapped[SimulationRun] = relationship(back_populates="report")
