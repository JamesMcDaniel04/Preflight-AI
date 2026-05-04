"""Five persona seeds for scenario generation. Spec §7a."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    seed: str
    label: str
    share: float
    description: str


PERSONAS: list[Persona] = [
    Persona(
        seed="normal_user",
        label="normal user",
        share=0.35,
        description="a typical user with average context and clear intent",
    ),
    Persona(
        seed="confused_user",
        label="confused or low-context user",
        share=0.20,
        description="a user who is unsure, missing details, or asks ambiguous questions",
    ),
    Persona(
        seed="adversarial_user",
        label="malicious or adversarial user",
        share=0.15,
        description="a user trying to break, jailbreak, or misuse the agent",
    ),
    Persona(
        seed="power_user",
        label="power user pushing edge cases",
        share=0.15,
        description="an advanced user invoking complex, edge-case behaviors",
    ),
    Persona(
        seed="long_tail",
        label="long-tail or rare real-world user",
        share=0.15,
        description="a user with an unusual but plausible real-world scenario",
    ),
]


def allocate_counts(total: int) -> list[tuple[Persona, int]]:
    """Distribute `total` across personas by share. Remainder goes to the highest-share persona."""
    if total <= 0:
        return []
    raw = [(p, int(total * p.share)) for p in PERSONAS]
    allocated = sum(c for _, c in raw)
    remainder = total - allocated
    # Give remainder to whichever persona has the largest share (normal_user).
    if remainder > 0:
        idx = max(range(len(raw)), key=lambda i: PERSONAS[i].share)
        p, c = raw[idx]
        raw[idx] = (p, c + remainder)
    return raw
