import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    base_prompt: Mapped[str] = mapped_column(Text)
    success_criteria: Mapped[str] = mapped_column(Text)
    scenario_count: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|running|complete|failed
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    last_milestone_emitted: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    scenarios: Mapped[list["Scenario"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    report: Mapped["SimulationReport | None"] = relationship(
        back_populates="run", uselist=False, cascade="all, delete-orphan"
    )


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.id"), index=True)
    persona_seed: Mapped[str] = mapped_column(String(64))
    input: Mapped[str] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heuristic_flag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classified_as: Mapped[str | None] = mapped_column(String(16), nullable=True)  # success|failure|unclear
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[SimulationRun] = relationship(back_populates="scenarios")


class SimulationReport(Base):
    __tablename__ = "simulation_reports"

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.id"), primary_key=True)
    success_rate: Mapped[float] = mapped_column(Float)
    total_runs: Mapped[int] = mapped_column(Integer)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    unclear_rate: Mapped[float] = mapped_column(Float, default=0.0)
    failure_clusters: Mapped[list] = mapped_column(JSON, default=list)
    most_dangerous_failure: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verdict: Mapped[str] = mapped_column(String(16))  # SHIP|HOLD|REVIEW
    verdict_reason: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped[SimulationRun] = relationship(back_populates="report")
