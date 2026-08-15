"""The agent loop — model → tool calls → results → answer.

This is the heart of the Phase-6 runtime: a synchronous, tool-calling
conversation loop. It sends the system prompt + history + the user message to
the model with the tool registry's schemas; if the model returns tool calls it
executes them (each result fed back as a ``tool`` message), and repeats; when
the model returns plain content, that content is the answer.

The loop is deliberately small and honest:

- A tool failure is returned to the model as ``{"error": ...}`` (via the
  registry's dispatch), so the model can report the blocker and adapt — the
  loop never fabricates a result and never swallows a failure silently.
- If the model does not settle into a final answer within ``max_steps``
  tool-calling turns, the loop raises :class:`MaxStepsError` rather than
  returning a truncated or invented answer.
"""

from __future__ import annotations

from typing import Optional

from .client import echo_assistant_message, parse_tool_calls, tool_result_message
from .tools import ToolRegistry


class MaxStepsError(Exception):
    """The agent did not settle into an answer within the step budget."""


class Agent:
    """A tool-calling agent over a model client and a tool registry."""

    def __init__(
        self,
        client,
        registry: ToolRegistry,
        system_prompt: str,
        max_steps: int = 16,
    ):
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        self.client = client
        self.registry = registry
        self.system_prompt = system_prompt
        self.max_steps = max_steps

    def run(self, user_message: str, history: Optional[list] = None) -> str:
        """Run one turn and return the final answer text.

        ``history`` is an optional list of prior ``{"role", "content"}`` turns
        (only ``user`` and ``assistant`` roles are carried forward; anything
        else is ignored so the message sequence stays clean).
        """
        messages: list = [{"role": "system", "content": self.system_prompt}]
        for turn in history or []:
            if turn.get("role") in ("user", "assistant"):
                messages.append(
                    {"role": turn["role"], "content": turn.get("content", "")}
                )
        messages.append({"role": "user", "content": user_message})
        tools = self.registry.schemas()

        for _ in range(self.max_steps):
            message = self.client.complete(messages, tools=tools)
            tool_calls = parse_tool_calls(message)
            if not tool_calls:
                return message.get("content") or ""
            messages.append(echo_assistant_message(message))
            for call in tool_calls:
                result = self.registry.dispatch(call.name, call.arguments)
                messages.append(tool_result_message(call.id, result))

        raise MaxStepsError(
            f"agent did not settle after {self.max_steps} tool-calling steps"
        )


def run_agent(
    client,
    registry: ToolRegistry,
    system_prompt: str,
    user_message: str,
    history: Optional[list] = None,
    max_steps: int = 16,
) -> str:
    """One-shot convenience: build an Agent and run a single message."""
    return Agent(client, registry, system_prompt, max_steps=max_steps).run(
        user_message, history=history
    )


__all__ = ["Agent", "MaxStepsError", "run_agent"]
