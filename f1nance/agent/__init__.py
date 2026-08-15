"""F1NANCE agent — the Phase-6 standalone runtime.

This is the agent proper: the tool-calling loop that turns F1NANCE from a bag
of engine CLIs into a single agent running on its own substrate. It is
Hermes-independent by design — standard library only, no Hermes imports — and
it is what lets F1NANCE leave the chassis (see ROADMAP.md → Phase 6).

Modules:

- ``paths`` — canonical locations for SOUL.md and the provenance store.
- ``client`` — ``AgentClient``, an OpenAI-compatible chat-completions client
  with tool calling over stdlib ``urllib`` (reuses the desk's ``ModelError``
  and DeepSeek defaults).
- ``tools`` — the ``Tool``/``ToolRegistry`` and the built-in toolset: the
  finance engines (data, portfolio, quant, execution, desk) plus the
  provenance store, exposed as callable tools.
- ``system`` — the system-prompt builder (SOUL + active store facts + the
  working contract).
- ``loop`` — the ``Agent`` conversation loop (model → tool calls → results →
  model → answer).
"""

from .client import (
    AgentClient,
    ModelError,
    ToolCall,
    agent_env_client,
    parse_tool_calls,
)
from .loop import Agent, MaxStepsError, run_agent
from .system import build_system_prompt, load_system_prompt
from .tools import Tool, ToolRegistry, build_registry

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentClient",
    "MaxStepsError",
    "ModelError",
    "Tool",
    "ToolCall",
    "ToolRegistry",
    "agent_env_client",
    "build_registry",
    "build_system_prompt",
    "load_system_prompt",
    "parse_tool_calls",
    "run_agent",
    "__version__",
]
