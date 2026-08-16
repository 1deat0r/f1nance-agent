"""The agent's model client — chat completions with tool calling.

This is the Phase-6 runtime's model substrate: a stdlib ``urllib`` client that
sends a full message list and a tool schema, and reads back ``tool_calls``,
over the OpenAI-compatible chat-completions protocol. It extends the desk's
single-shot live executor (``f1nance.desk.live``) with the tool-calling shape;
the DeepSeek defaults and the ``ModelError`` discipline are shared.

Design notes:

- ``complete`` returns the raw assistant message dict (``role``, ``content``,
  ``tool_calls``, and any provider extras such as ``reasoning_content``).
  Callers build the echo with ``echo_assistant_message`` and the tool results
  with ``tool_result_message`` — the client never mutates messages.
- ``reasoning_content`` is read but never echoed back: deepseek-v4-pro is a
  reasoning model and rejects reasoning content on input.
- ``parse_tool_calls`` is pure and offline-testable: it turns the wire format
  into ``ToolCall`` dataclasses with parsed ``arguments``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from ..desk.live import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    ModelError,
)
from ..env import load_env


@dataclass(frozen=True)
class ToolCall:
    """One tool call requested by the model, with parsed arguments."""

    id: str
    name: str
    arguments: dict

    @classmethod
    def from_wire(cls, raw: dict) -> "ToolCall":
        """Build from a wire ``tool_call`` entry, parsing ``arguments``."""
        call_id = str(raw.get("id", ""))
        fn = raw.get("function") or {}
        name = str(fn.get("name", ""))
        args_raw = fn.get("arguments", "{}")
        if isinstance(args_raw, str):
            try:
                arguments = json.loads(args_raw) if args_raw.strip() else {}
            except json.JSONDecodeError as exc:
                raise ModelError(
                    f"tool call {call_id!r} had malformed JSON arguments: "
                    f"{args_raw[:120]!r}"
                ) from exc
        elif isinstance(args_raw, dict):
            arguments = args_raw
        else:
            raise ModelError(
                f"tool call arguments must be a JSON string or object, "
                f"got {type(args_raw).__name__}"
            )
        if not isinstance(arguments, dict):
            raise ModelError(
                f"tool call arguments must decode to an object, "
                f"got {type(arguments).__name__}"
            )
        if not name:
            raise ModelError(f"tool call {call_id!r} had no function name")
        return cls(id=call_id, name=name, arguments=arguments)


def parse_tool_calls(message: dict) -> list:
    """Extract and parse ``tool_calls`` from an assistant message dict.

    Returns a list of :class:`ToolCall`. Raises :class:`ModelError` if the
    ``tool_calls`` field is present but not a list, so a malformed response is
    reported honestly rather than silently treated as empty.
    """
    raw = message.get("tool_calls") or []
    if not isinstance(raw, list):
        raise ModelError(f"tool_calls must be a list, got {type(raw).__name__}")
    return [ToolCall.from_wire(tc) for tc in raw]


def echo_assistant_message(message: dict) -> dict:
    """Return the OpenAI message to append for an assistant turn.

    Strips ``reasoning_content`` (and any other provider-only keys): reasoning
    content is not accepted back on input by deepseek-v4-pro, and the loop only
    needs role/content/tool_calls for a faithful echo-back.
    """
    out: dict = {"role": "assistant", "content": message.get("content")}
    if message.get("tool_calls"):
        out["tool_calls"] = message["tool_calls"]
    return out


def tool_result_message(tool_call_id: str, content: str) -> dict:
    """The tool result message for one completed tool call."""
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


class AgentClient:
    """An OpenAI-compatible chat-completions client over stdlib ``urllib``.

    ``complete`` sends ``messages`` (and an optional ``tools`` schema) and
    returns the raw assistant message dict, or raises :class:`ModelError` with
    the honest detail on failure — it never fabricates a response.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 0.0,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature

    def complete(self, messages: list, tools: Optional[list] = None) -> dict:
        url = f"{self.base_url}/chat/completions"
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise ModelError(f"model call returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ModelError(f"model call failed (network): {exc.reason}") from exc
        try:
            data = json.loads(body)
            return data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ModelError(f"unexpected model response shape: {body[:200]!r}") from exc


def agent_env_client() -> AgentClient:
    """Build an :class:`AgentClient` from the environment.

    Key precedence ``F1NANCE_API_KEY`` then ``DEEPSEEK_API_KEY``; base URL and
    model default to the DeepSeek endpoint F1NANCE runs on and are overridable
    via ``F1NANCE_BASE_URL`` / ``F1NANCE_MODEL``. Raises :class:`ModelError`
    when no key is set — the agent will not guess a credential.
    """
    load_env()  # f1nance/.env (gitignored) supplies the key if not already set
    api_key = os.environ.get("F1NANCE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ModelError(
            "no API key for the agent: set F1NANCE_API_KEY or DEEPSEEK_API_KEY"
        )
    return AgentClient(
        base_url=os.environ.get("F1NANCE_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key,
        model=os.environ.get("F1NANCE_MODEL", DEFAULT_MODEL),
        timeout=float(os.environ.get("F1NANCE_MODEL_TIMEOUT", str(DEFAULT_TIMEOUT))),
        max_tokens=int(
            os.environ.get("F1NANCE_MODEL_MAX_TOKENS", str(DEFAULT_MAX_TOKENS))
        ),
    )


__all__ = [
    "AgentClient",
    "ModelError",
    "ToolCall",
    "agent_env_client",
    "echo_assistant_message",
    "parse_tool_calls",
    "tool_result_message",
]
