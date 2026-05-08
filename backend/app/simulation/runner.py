"""Run single-turn or multi-turn scenarios against the user's agent.

The agent is abstracted behind an `AgentAdapter` (see `app.agents`). The runner
itself doesn't know whether the agent is a fresh OpenAI call (prompt mode) or
an HTTP POST to the user's deployed endpoint — it just calls `adapter.send`.

User-simulator follow-up messages always go through `chat_complete` because
that's *our* OpenAI call (we're synthesizing the test user's behavior), not
the user's agent.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..agents.base import AgentAdapter
from ..agents.prompt import PromptAdapter
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


def _build_messages_for_agent(
    *,
    adapter: AgentAdapter,
    base_prompt: str,
    transcript: list[dict],
) -> list[dict]:
    """Compose the messages list to send to the adapter.

    Prompt-only adapters need our system prompt prepended; HTTP adapters do not
    (the user's deployed agent already has its own system context).
    """
    if adapter.prepends_system:
        return [{"role": "system", "content": base_prompt}, *transcript]
    return list(transcript)


def execute_scenario(
    base_prompt: str,
    scenario_input: str,
    *,
    model: str | None = None,
    run_mode: str = "single_turn",
    persona_seed: str = "normal_user",
    hidden_goal: str | None = None,
    adapter: AgentAdapter | None = None,
) -> ScenarioExecution:
    """Run a single test scenario through the user's agent and capture output.

    `adapter` defaults to a PromptAdapter so existing call sites that don't
    know about adapters yet keep working with prompt-only behavior.
    """
    if adapter is None:
        adapter = PromptAdapter(model=model)

    transcript: list[dict] = [{"role": "user", "content": scenario_input}]

    if run_mode != "multi_turn":
        try:
            messages = _build_messages_for_agent(
                adapter=adapter, base_prompt=base_prompt, transcript=transcript
            )
            output, latency_ms = adapter.send(messages, max_tokens=600)
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

    total_latency = 0
    agent_outputs: list[str] = []
    try:
        for turn in range(3):
            messages = _build_messages_for_agent(
                adapter=adapter, base_prompt=base_prompt, transcript=transcript
            )
            agent_output, latency_ms = adapter.send(messages, max_tokens=600)
            total_latency += latency_ms
            agent_outputs.append(agent_output)
            transcript.append({"role": "assistant", "content": agent_output})
            if turn == 2:
                break
            follow_up, follow_latency = _generate_follow_up(
                base_prompt=base_prompt,
                persona_seed=persona_seed,
                hidden_goal=hidden_goal or "Get the task completed accurately.",
                transcript=transcript,
                model=model,
            )
            total_latency += follow_latency
            transcript.append({"role": "user", "content": follow_up})
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
