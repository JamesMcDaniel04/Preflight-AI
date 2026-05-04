"""Run single-turn or multi-turn scenarios against the user's agent prompt."""
from __future__ import annotations

from dataclasses import dataclass

from ..llm.clients import chat_complete


@dataclass
class ScenarioExecution:
    output: str
    latency_ms: int
    error: str | None
    agent_outputs: list[str]
    transcript: list[dict] | None = None


def _render_transcript(messages: list[dict]) -> str:
    lines: list[str] = []
    for message in messages:
        speaker = "USER" if message["role"] == "user" else "ASSISTANT"
        lines.append(f"{speaker}: {message['content']}")
    return "\n\n".join(lines)


def _generate_follow_up(
    *,
    base_prompt: str,
    persona_seed: str,
    hidden_goal: str,
    transcript: list[dict],
    model: str | None,
) -> tuple[str, int]:
    system = (
        f"You are simulating a {persona_seed} user testing an AI agent.\n"
        f'The agent system prompt is: "{base_prompt}"\n'
        f'Your hidden goal is: "{hidden_goal}"\n\n'
        "Given the transcript so far, produce the next single user message. "
        "Keep it realistic, short, and consistent with the hidden goal. "
        "Return only the message text."
    )
    transcript_text = _render_transcript(transcript)
    return chat_complete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": transcript_text},
        ],
        model=model,
        temperature=0.8,
        max_tokens=200,
    )


def execute_scenario(
    base_prompt: str,
    scenario_input: str,
    *,
    model: str | None = None,
    run_mode: str = "single_turn",
    persona_seed: str = "normal_user",
    hidden_goal: str | None = None,
) -> ScenarioExecution:
    if run_mode != "multi_turn":
        messages = [
            {"role": "system", "content": base_prompt},
            {"role": "user", "content": scenario_input},
        ]
        try:
            output, latency_ms = chat_complete(
                messages,
                model=model,
                temperature=0.7,
                max_tokens=600,
            )
            return ScenarioExecution(
                output=output,
                latency_ms=latency_ms,
                error=None,
                agent_outputs=[output],
            )
        except Exception as exc:
            return ScenarioExecution(
                output="",
                latency_ms=0,
                error=str(exc)[:500],
                agent_outputs=[],
            )

    transcript = [{"role": "user", "content": scenario_input}]
    messages = [{"role": "system", "content": base_prompt}, *transcript]
    total_latency = 0
    agent_outputs: list[str] = []

    try:
        for turn in range(3):
            agent_output, latency_ms = chat_complete(
                messages,
                model=model,
                temperature=0.7,
                max_tokens=600,
            )
            total_latency += latency_ms
            agent_outputs.append(agent_output)
            assistant_message = {"role": "assistant", "content": agent_output}
            transcript.append(assistant_message)
            messages.append(assistant_message)
            if turn == 2:
                break
            follow_up, latency_ms = _generate_follow_up(
                base_prompt=base_prompt,
                persona_seed=persona_seed,
                hidden_goal=hidden_goal or "Get the task completed accurately.",
                transcript=transcript,
                model=model,
            )
            total_latency += latency_ms
            user_message = {"role": "user", "content": follow_up}
            transcript.append(user_message)
            messages.append(user_message)
    except Exception as exc:
        return ScenarioExecution(
            output=_render_transcript(transcript),
            latency_ms=total_latency,
            error=str(exc)[:500],
            agent_outputs=agent_outputs,
            transcript=transcript,
        )

    return ScenarioExecution(
        output=_render_transcript(transcript),
        latency_ms=total_latency,
        error=None,
        agent_outputs=agent_outputs,
        transcript=transcript,
    )
