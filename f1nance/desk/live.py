"""The live executor — a model call behind the desk's ``Executor`` seam.

This is the bridge from the offline, scripted desk to a live runtime.
``model_executor`` turns ``(Seat, Brief)`` into a ``Finding`` by calling an
OpenAI-compatible chat endpoint over stdlib ``urllib``. No Hermes imports, no
numpy/pandas — the same portability discipline as the rest of ``f1nance``. At
Phase 6 this is the executor the standalone agent runs; today it is how the
Hermes-bootstrapped desk goes live.

The seam is unchanged: ``Desk.run(brief, executor)`` does not care whether the
executor is ``scripted_executor`` (pre-authored findings) or
``model_executor`` (a real model call). Coordination logic is identical either
way, which is the whole point of injecting the executor.

Components:

- ``ModelClient`` — a minimal chat-completions client (base_url, api_key,
  model, timeout, max_tokens) over ``urllib``. Raises ``ModelError`` on any
  HTTP/network failure with the honest detail — never fabricates a response.
- ``build_prompt`` — the ``(system, user)`` prompt for one seat + brief. Pure,
  offline-testable.
- ``parse_finding`` — model text → a validated ``Finding``. Tolerant of code
  fences and surrounding prose, strict about the guardrail fields (a missing
  loss case or a confidence outside [0, 1] raises). Pure, offline-testable.
- ``model_executor`` — the ``Executor``: call the client, parse, and retry
  (bounded) with a corrective prompt on malformed output.
- ``env_client`` — build a ``ModelClient`` from environment variables
  (``F1NANCE_*`` with ``DEEPSEEK_*`` fallback).

No ``response_format`` is requested: the prompt demands JSON-only output and
``parse_finding`` extracts it defensively, so the executor does not depend on
a server-side JSON mode the endpoint may not support.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Callable

from .brief import Brief, Finding
from .desk import Executor
from .seats import Seat

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_TIMEOUT = 60.0
# deepseek-v4-pro is a reasoning model: it spends ``reasoning_content`` tokens
# BEFORE writing ``content``, and ``max_tokens`` caps the two jointly. A small
# cap truncates the chain-of-thought and returns empty content (verified live
# with 1000 → ``finish_reason: length``, ``content: ''``). This cap must leave
# room for both; it is a ceiling, not a reservation — a short answer stops at
# ``finish_reason: stop`` and costs only what it generated.
DEFAULT_MAX_TOKENS = 8192

# The desk accepts ``high``/``medium``/``low`` confidence labels as
# 0.8/0.5/0.2; the model is asked for a number but the parser stays lenient.
_CONFIDENCE_LABELS = {"high": 0.8, "medium": 0.5, "low": 0.2}


class ModelError(Exception):
    """A live-executor failure: missing key, HTTP/network error, or output
    that could not be parsed into a valid finding."""


class ModelClient:
    """A minimal OpenAI-compatible chat-completions client over stdlib urllib.

    ``complete`` returns the assistant message text, or raises ``ModelError``
    with the honest detail on failure — it never fabricates a response.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.0,
                "max_tokens": self.max_tokens,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
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
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ModelError(f"unexpected model response shape: {body[:200]!r}") from exc


def build_prompt(seat: Seat, brief: Brief) -> tuple[str, str]:
    """Build the ``(system, user)`` prompt for one seat answering one brief.

    The system prompt fixes the seat's identity and mandate, then layers the
    non-negotiable F1NANCE guardrails (no fabrication, risk before return,
    confidence calibration, suitability) and a strict JSON-only output
    contract. The user prompt is the brief itself. Pure — no I/O.
    """
    system = (
        f"You are the {seat.label} seat of F1NANCE, a financial-agent desk.\n"
        f"Mandate: {seat.mandate}\n"
        f"Domain: {seat.domain}\n"
        f"Roles served: {', '.join(seat.roles)}\n"
        f"Engines you run on: {', '.join(seat.engines)}\n"
        "\n"
        "You answer ONE brief with a single finding. Guardrails (non-negotiable):\n"
        "1. No fabrication — never invent a price, quote, return, or data point; "
        "if evidence is missing, say so.\n"
        "2. Risk before return — name the loss case and its approximate size "
        "before the upside.\n"
        "3. Confidence calibration — confidence reflects evidence, not bravado.\n"
        "4. Suitability — respect the brief's horizon, risk capacity, and "
        "constraints; do not propose activity for its own sake.\n"
        "\n"
        "Respond with ONLY a JSON object — no prose, no markdown code fences — "
        "with exactly these keys:\n"
        '{"thesis": string, "stance": "bullish"|"bearish"|"neutral", '
        '"confidence": number (0.0 to 1.0), "loss_case": string, '
        '"falsify": string, "actions": [string, ...]}'
    )
    user_lines = [
        "Brief:",
        f"- Objective: {brief.objective}",
        f"- Context: {brief.context or '(none)'}",
        f"- Horizon: {brief.horizon or '(unspecified)'}",
        f"- Risk capacity: {brief.risk_capacity or '(unspecified)'}",
        "- Constraints: "
        + (", ".join(brief.constraints) if brief.constraints else "(none)"),
    ]
    return system, "\n".join(user_lines)


def _extract_json(text: str) -> object:
    """Pull the first JSON object out of model text.

    Tries a direct parse of the whole string first (the clean case), then
    falls back to a balanced-brace scan so a code fence or surrounding prose
    does not defeat it. Raises ``ValueError`` when there is no object at all.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("model output is empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in model output")
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unterminated JSON object in model output")


def _coerce_confidence(value) -> float:
    """Coerce a model-emitted confidence to a float, or raise.

    Accepts numbers, numeric strings (``"0.7"``), and the desk's
    high/medium/low labels (0.8/0.5/0.2).
    """
    if isinstance(value, str):
        label = value.strip().lower()
        if label in _CONFIDENCE_LABELS:
            return _CONFIDENCE_LABELS[label]
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"confidence {value!r} is not a number") from None


def parse_finding(seat: Seat, text: str) -> Finding:
    """Parse model text into a validated ``Finding`` for ``seat``.

    Tolerant of fences and prose (``_extract_json``), strict about the
    guardrail fields: a missing thesis/loss_case/falsify, an invalid stance,
    or a confidence outside [0, 1] raises ``ValueError`` via the ``Finding``
    constructor — the no-fabrication discipline, applied to the model's own
    output.
    """

    def need(data: dict, key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"model output missing a non-empty {key!r}")
        return value.strip()

    data = _extract_json(text)
    if not isinstance(data, dict):
        raise ValueError("model output is not a JSON object")
    actions = data.get("actions", ())
    if not isinstance(actions, list):
        actions = [actions] if actions else []
    actions = tuple(str(a).strip() for a in actions if str(a).strip())
    return Finding(
        seat=seat.name,
        thesis=need(data, "thesis"),
        stance=need(data, "stance"),
        confidence=_coerce_confidence(data.get("confidence")),
        loss_case=need(data, "loss_case"),
        falsify=need(data, "falsify"),
        actions=actions,
    )


def model_executor(client, max_attempts: int = 3) -> Executor:
    """Return an ``Executor`` that produces each seat's ``Finding`` via the model.

    ``client`` is any object with a ``complete(system, user) -> str`` method
    (normally a ``ModelClient``). On malformed output the executor retries with
    a corrective prompt, up to ``max_attempts``, then raises ``ModelError`` —
    it never fills in a finding the model could not produce. Client errors
    (HTTP/network) propagate immediately; they are not retried.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def executor(seat: Seat, brief: Brief) -> Finding:
        system, user = build_prompt(seat, brief)
        last_err: Exception | None = None
        for _ in range(max_attempts):
            text = client.complete(system, user)
            try:
                return parse_finding(seat, text)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                last_err = exc
                user = (
                    f"{user}\n\n"
                    f"Your previous response could not be parsed: {exc}. "
                    "Respond with ONLY a JSON object (no prose, no code fences) "
                    "with exactly these keys: thesis, stance, confidence, "
                    "loss_case, falsify, actions."
                )
        raise ModelError(
            f"seat {seat.name!r}: could not parse a valid finding after "
            f"{max_attempts} attempts: {last_err}"
        )

    return executor


def env_client() -> ModelClient:
    """Build a ``ModelClient`` from the environment.

    Key precedence: ``F1NANCE_API_KEY`` then ``DEEPSEEK_API_KEY``. Base URL and
    model default to the DeepSeek endpoint F1NANCE runs on and are overridable
    via ``F1NANCE_BASE_URL`` / ``F1NANCE_MODEL``. Raises ``ModelError`` when no
    key is set — the executor will not guess a credential.
    """
    api_key = os.environ.get("F1NANCE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ModelError(
            "no API key for the live executor: set F1NANCE_API_KEY or "
            "DEEPSEEK_API_KEY"
        )
    return ModelClient(
        base_url=os.environ.get("F1NANCE_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key,
        model=os.environ.get("F1NANCE_MODEL", DEFAULT_MODEL),
        timeout=float(os.environ.get("F1NANCE_MODEL_TIMEOUT", str(DEFAULT_TIMEOUT))),
        max_tokens=int(os.environ.get("F1NANCE_MODEL_MAX_TOKENS", str(DEFAULT_MAX_TOKENS))),
    )


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "ModelClient",
    "ModelError",
    "build_prompt",
    "env_client",
    "model_executor",
    "parse_finding",
]
