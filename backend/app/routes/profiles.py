"""Public read-only endpoint serving the test profile catalog.

Lives outside `/api/runs` so the frontend can render the profile dropdown on
the Submit screen without needing to be authenticated yet.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..schemas import ProfileSummary
from ..simulation.profiles import list_profiles

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("", response_model=list[ProfileSummary])
def get_profiles() -> list[ProfileSummary]:
    return [
        ProfileSummary(
            id=p.id,
            label=p.label,
            description=p.description,
            default_base_prompt=p.default_base_prompt,
            default_success_criteria=p.default_success_criteria,
            has_scoring_rules=bool(p.scoring_rules),
        )
        for p in list_profiles()
    ]
