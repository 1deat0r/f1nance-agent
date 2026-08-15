"""Command-line entry point for the F1NANCE standalone agent.

Run with::

    f1nance/.venv/bin/python -m f1nance.agent                  # interactive REPL
    f1nance/.venv/bin/python -m f1nance.agent chat -q "…"      # one-shot
    f1nance/.venv/bin/python -m f1nance.agent --list-tools     # dump tool schemas
    f1nance/.venv/bin/python -m f1nance.agent --system         # print the system prompt

Options::

    --store PATH      provenance store (default f1nance/core/store.json)
    --soul PATH       SOUL.md (default f1nance/SOUL.md)
    --ledger PATH     execution ledger persistence (default in-memory)
    --max-steps N     tool-calling step cap (default 16)
    --record          append each completed exchange to the store as a decision
    --list-tools      print the tool registry as JSON and exit
    --system          print the built system prompt and exit

Environment (same contract as the desk's live executor)::

    F1NANCE_API_KEY | DEEPSEEK_API_KEY   (required for live runs)
    F1NANCE_BASE_URL, F1NANCE_MODEL, F1NANCE_MODEL_MAX_TOKENS
    F1NANCE_STORE, F1NANCE_LEDGER

``chat`` reads the question from ``-q/--question``; without it, the question is
read from stdin (so it can be piped). Without a subcommand, the agent runs an
interactive line-by-line REPL.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from .client import AgentClient, ModelError, agent_env_client
from .loop import Agent, MaxStepsError, run_agent
from .paths import default_store_path
from .system import load_system_prompt
from .tools import build_registry

from ..core.memory import MemoryStore

BANNER = """\
F1NANCE — standalone agent (f1nance/agent)
  model: {model}   tools: {n_tools}   store: {store}
Type a question, or /quit to exit.
"""


def _emit(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _common(parent: argparse.ArgumentParser) -> None:
    parent.add_argument("--store", default=None, help="provenance store path")
    parent.add_argument("--soul", default=None, help="SOUL.md path")
    parent.add_argument("--ledger", default=None, help="execution ledger path")
    parent.add_argument("--max-steps", type=int, default=16, help="tool-calling step cap")


def _record_decision(store: MemoryStore, question: str, answer: str) -> None:
    q = question.strip().replace("\n", " ")
    a = answer.strip().replace("\n", " ")
    content = f"answered: {q[:160]} -> {a[:320]}"
    with store.mutate():
        store.add(content, "decision", "agent")


def _repl(agent: Agent, client: AgentClient, store: MemoryStore, n_tools: int, record: bool) -> None:
    print(BANNER.format(model=client.model, n_tools=n_tools, store=store.path))
    history: list = []
    while True:
        try:
            line = input("f1nance> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        line = line.strip()
        if not line:
            continue
        if line in ("/quit", "/exit"):
            break
        try:
            answer = agent.run(line, history=history)
        except (ModelError, MaxStepsError) as exc:
            print(f"\n[{type(exc).__name__}] {exc}\n")
            continue
        print(f"\n{answer}\n")
        history.append({"role": "user", "content": line})
        history.append({"role": "assistant", "content": answer})
        if record:
            _record_decision(store, line, answer)


def main(argv: Optional[list] = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    _common(common)

    parser = argparse.ArgumentParser(
        prog="f1nance.agent",
        description="F1NANCE standalone agent (Phase-6 runtime).",
        parents=[common],
    )
    parser.add_argument("--list-tools", action="store_true", help="dump tool schemas and exit")
    parser.add_argument("--system", action="store_true", help="print the system prompt and exit")
    parser.add_argument("--record", action="store_true", help="record exchanges as decisions")

    sub = parser.add_subparsers(dest="cmd")
    chat = sub.add_parser("chat", parents=[common], help="one-shot question")
    chat.add_argument("-q", "--question", default=None, help="the question (else read stdin)")
    chat.add_argument("--record", action="store_true", help="record the exchange as a decision")

    args = parser.parse_args(argv)

    store = MemoryStore(args.store or default_store_path())
    registry = build_registry(store=store, ledger_path=args.ledger)

    if args.list_tools:
        _emit(registry.schemas())
        return 0

    system_prompt = load_system_prompt(soul_path=args.soul, store=store)

    if args.system:
        print(system_prompt, end="")
        return 0

    try:
        client = agent_env_client()
    except ModelError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    agent = Agent(client, registry, system_prompt, max_steps=args.max_steps)

    if args.cmd == "chat":
        question = args.question
        if question is None:
            question = sys.stdin.read().strip()
        if not question:
            print("ERROR: no question given (-q or stdin)", file=sys.stderr)
            return 1
        try:
            answer = run_agent(
                client, registry, system_prompt, question, max_steps=args.max_steps
            )
        except (ModelError, MaxStepsError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(answer)
        if args.record:
            _record_decision(store, question, answer)
        return 0

    _repl(agent, client, store, len(registry.tools), record=args.record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
