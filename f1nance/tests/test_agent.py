"""Offline tests for the F1NANCE standalone agent — no network, no model, no Hermes.

Phase 6 wires the engines into an agent. These tests cover the pure parts and
the seams so the only thing exercised live is the real ``AgentClient`` (a
stdlib ``urllib`` call): tool-call parsing, the message echo/result helpers,
the environment client, the engine-backed tool handlers, the registry's honest
error dispatch, the system-prompt builder, and the tool-calling loop with a
fake client.
"""

import io
import json
import os
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from f1nance.agent import (
    Agent,
    AgentClient,
    MaxStepsError,
    ModelError,
    Tool,
    ToolRegistry,
    agent_env_client,
    build_registry,
    build_system_prompt,
    run_agent,
)
from f1nance.agent.client import (
    echo_assistant_message,
    parse_tool_calls,
    tool_result_message,
)
from f1nance.agent.system import WORKING_CONTRACT
from f1nance.core.memory import MemoryStore
from f1nance.data import Dataset
from f1nance.desk import scripted_executor


def _json(obj) -> str:
    return json.dumps(obj, default=str)


class _TempStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = MemoryStore(f"{self._tmp.name}/store.json")

    def _registry(self, **kwargs):
        return build_registry(store=self.store, **kwargs)


# -- client ------------------------------------------------------------------

TOOL_CALL_MESSAGE = {
    "role": "assistant",
    "content": None,
    "reasoning_content": "thinking out loud",
    "tool_calls": [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "market_price", "arguments": '{"symbol": "AAPL"}'},
        }
    ],
}


class ParseToolCallsTest(unittest.TestCase):
    def test_parses_string_arguments(self):
        calls = parse_tool_calls(TOOL_CALL_MESSAGE)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].id, "call_1")
        self.assertEqual(calls[0].name, "market_price")
        self.assertEqual(calls[0].arguments, {"symbol": "AAPL"})

    def test_dict_arguments_pass_through(self):
        msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "c", "function": {"name": "n", "arguments": {"x": 1}}}
            ],
        }
        self.assertEqual(parse_tool_calls(msg)[0].arguments, {"x": 1})

    def test_no_tool_calls_returns_empty(self):
        self.assertEqual(parse_tool_calls({"role": "assistant", "content": "hi"}), [])

    def test_malformed_arguments_raises(self):
        msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "c", "function": {"name": "n", "arguments": "{not json"}}
            ],
        }
        with self.assertRaises(ModelError):
            parse_tool_calls(msg)

    def test_tool_calls_not_a_list_raises(self):
        with self.assertRaises(ModelError):
            parse_tool_calls({"role": "assistant", "tool_calls": "oops"})


class EchoTest(unittest.TestCase):
    def test_strips_reasoning_content(self):
        out = echo_assistant_message(TOOL_CALL_MESSAGE)
        self.assertNotIn("reasoning_content", out)
        self.assertEqual(out["role"], "assistant")
        self.assertEqual(len(out["tool_calls"]), 1)

    def test_no_tool_calls_drops_key(self):
        out = echo_assistant_message({"role": "assistant", "content": "hi"})
        self.assertNotIn("tool_calls", out)
        self.assertEqual(out, {"role": "assistant", "content": "hi"})

    def test_tool_result_message(self):
        self.assertEqual(
            tool_result_message("c1", "{}"),
            {"role": "tool", "tool_call_id": "c1", "content": "{}"},
        )


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


class AgentClientTest(unittest.TestCase):
    def _client(self):
        return AgentClient("https://api.deepseek.com/v1", "key", "deepseek-v4-pro")

    def test_complete_returns_message(self):
        body = json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": "hi"}}]}
        ).encode()
        with patch(
            "f1nance.agent.client.urllib.request.urlopen",
            return_value=_FakeResponse(body),
        ):
            msg = self._client().complete([{"role": "user", "content": "hi"}])
        self.assertEqual(msg["content"], "hi")

    def test_complete_sends_tools(self):
        body = json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        ).encode()
        with patch(
            "f1nance.agent.client.urllib.request.urlopen",
            return_value=_FakeResponse(body),
        ) as mock_open:
            self._client().complete([], tools=[{"type": "function"}])
        request = mock_open.call_args[0][0]
        payload = json.loads(request.data.decode())
        self.assertEqual(payload["tools"], [{"type": "function"}])
        self.assertEqual(payload["model"], "deepseek-v4-pro")

    def test_http_error_raises(self):
        err = urllib.error.HTTPError(
            "https://api.deepseek.com/v1", 401, "Unauthorized", {}, io.BytesIO(b"nope")
        )
        with patch("f1nance.agent.client.urllib.request.urlopen", side_effect=err):
            with self.assertRaises(ModelError) as ctx:
                self._client().complete([{"role": "user", "content": "x"}])
        self.assertIn("401", str(ctx.exception))

    def test_unexpected_shape_raises(self):
        body = b'{"choices": []}'
        with patch(
            "f1nance.agent.client.urllib.request.urlopen",
            return_value=_FakeResponse(body),
        ):
            with self.assertRaises(ModelError):
                self._client().complete([])


class AgentEnvClientTest(unittest.TestCase):
    def test_missing_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ModelError):
                agent_env_client()

    def test_f1nance_key_preferred(self):
        env = {"F1NANCE_API_KEY": "f", "DEEPSEEK_API_KEY": "d"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(agent_env_client().api_key, "f")

    def test_deepseek_fallback(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "d"}, clear=True):
            client = agent_env_client()
        self.assertEqual(client.api_key, "d")
        self.assertEqual(client.base_url, "https://api.deepseek.com/v1")
        self.assertEqual(client.model, "deepseek-v4-pro")


# -- tools -------------------------------------------------------------------

class RegistryTest(_TempStore):
    def test_full_toolset(self):
        registry = self._registry()
        names = registry.names()
        self.assertIn("market_price", names)
        self.assertIn("portfolio_value", names)
        self.assertIn("quant_capm", names)
        self.assertIn("fixedincome_price", names)
        self.assertIn("fixedincome_ytm", names)
        self.assertIn("fixedincome_risk", names)
        self.assertIn("fixedincome_curve", names)
        self.assertIn("derivatives_price", names)
        self.assertIn("derivatives_greeks", names)
        self.assertIn("derivatives_implied_vol", names)
        self.assertIn("derivatives_binomial", names)
        self.assertIn("riskmanagement_limits", names)
        self.assertIn("riskmanagement_stress", names)
        self.assertIn("riskmanagement_reverse_stress", names)
        self.assertIn("riskmanagement_var_backtest", names)
        self.assertIn("manda_accretion", names)
        self.assertIn("manda_synergies", names)
        self.assertIn("manda_breakeven", names)
        self.assertIn("manda_lbo", names)
        self.assertIn("execution_order", names)
        self.assertIn("desk_run", names)
        self.assertIn("memory_record", names)
        self.assertEqual(len(names), 34)

    def test_schemas_are_well_formed(self):
        for schema in self._registry().schemas():
            fn = schema["function"]
            self.assertTrue(fn["name"])
            self.assertTrue(fn["description"])
            self.assertEqual(fn["parameters"]["type"], "object")

    def test_unknown_tool_returns_error(self):
        out = json.loads(self._registry().dispatch("nope", {}))
        self.assertIn("error", out)

    def test_handler_failure_returns_error(self):
        def boom(args):
            raise ValueError("kaboom")

        registry = ToolRegistry([Tool("boom", "d", {"type": "object", "properties": {}}, boom)])
        out = json.loads(registry.dispatch("boom", {}))
        self.assertEqual(out["error"], "ValueError: kaboom")


class PortfolioToolTest(_TempStore):
    def test_value(self):
        spec = {
            "base_currency": "USD",
            "cash": {"USD": 10000},
            "positions": [
                {"asset": "AAPL", "quantity": 100, "price": 210.0,
                 "currency": "USD", "asset_class": "equity", "cost_basis": 180.0}
            ],
        }
        out = json.loads(self._registry().dispatch("portfolio_value", {"spec": spec}))
        self.assertAlmostEqual(out["nav"], 31000.0)
        self.assertAlmostEqual(out["exposure"]["long"], 21000 / 31000)
        self.assertAlmostEqual(out["cash_weight"], 10000 / 31000)

    def test_risk(self):
        prices = [100, 101, 102, 101, 103, 105]
        out = json.loads(
            self._registry().dispatch("portfolio_risk", {"prices": prices})
        )
        self.assertEqual(out["observations"], 6)
        self.assertIsNotNone(out["annualized_volatility"])
        self.assertIsNotNone(out["max_drawdown"])

    def test_risk_rejects_empty(self):
        out = json.loads(self._registry().dispatch("portfolio_risk", {"prices": []}))
        self.assertIn("error", out)

    def test_attribution(self):
        spec = {
            "portfolio_weights": {"A": 0.6, "B": 0.4},
            "benchmark_weights": {"A": 0.5, "B": 0.5},
            "portfolio_returns": {"A": 0.10, "B": 0.05},
            "benchmark_returns": {"A": 0.08, "B": 0.06},
        }
        out = json.loads(
            self._registry().dispatch("portfolio_attribution", {"spec": spec})
        )
        self.assertIn("active_return", out)
        self.assertIn("selection", out)


class QuantToolTest(_TempStore):
    def test_capm(self):
        asset = [0.02, -0.01, 0.03, 0.01]
        market = [0.01, 0.00, 0.02, 0.005]
        out = json.loads(
            self._registry().dispatch(
                "quant_capm", {"asset_returns": asset, "market_returns": market}
            )
        )
        self.assertIn("alpha", out)
        self.assertIn("exposures", out)
        self.assertIn("r_squared", out)

    def test_backtest(self):
        spec = {
            "returns": {"A": [0.01, 0.02, -0.01], "B": [0.00, 0.01, 0.01]},
            "weights": [{"A": 0.5, "B": 0.5}] * 3,
        }
        out = json.loads(
            self._registry().dispatch("quant_backtest", {"spec": spec})
        )
        self.assertIn("total_return", out)


class ExecutionToolTest(_TempStore):
    def test_order(self):
        spec = {
            "instrument": "AAPL", "side": "buy", "quantity": 100,
            "order_type": "limit", "limit_price": 190.0, "market_price": 192.0,
        }
        out = json.loads(self._registry().dispatch("execution_order", {"spec": spec}))
        self.assertEqual(out["order"]["side"], "buy")
        self.assertIn("marketable", out)

    def test_impact(self):
        out = json.loads(
            self._registry().dispatch(
                "execution_impact", {"notional": 2000000.0, "adv": 50000000.0}
            )
        )
        self.assertIn("total_cost", out)

    def test_ledger_persists(self):
        path = f"{self._tmp.name}/ledger.jsonl"
        spec = {
            "instrument": "AAPL", "side": "buy", "quantity": 100,
            "order_type": "market", "rationale": "test", "confidence": "high",
            "risk": "loss", "falsify": "if",
        }
        reg = build_registry(store=self.store, ledger_path=path)
        out = json.loads(reg.dispatch("execution_ledger", {"spec": spec}))
        self.assertEqual(out["status"], "pending")
        import os as _os
        self.assertTrue(_os.path.exists(path))


class DerivativesToolTest(_TempStore):
    def test_price(self):
        out = json.loads(
            self._registry().dispatch(
                "derivatives_price",
                {"call_put": "call", "S": 42, "K": 40, "T": 0.5,
                 "r": 0.10, "sigma": 0.20},
            )
        )
        self.assertAlmostEqual(out["price"], 4.759422, places=5)
        self.assertEqual(out["call_put"], "call")

    def test_greeks(self):
        out = json.loads(
            self._registry().dispatch(
                "derivatives_greeks",
                {"call_put": "put", "S": 100, "K": 100, "T": 1,
                 "r": 0.05, "sigma": 0.20},
            )
        )
        self.assertIn("delta", out)
        self.assertIn("gamma", out)
        self.assertIn("vega", out)
        self.assertIn("theta", out)
        self.assertIn("rho", out)

    def test_implied_vol(self):
        out = json.loads(
            self._registry().dispatch(
                "derivatives_implied_vol",
                {"price": 10.450584, "call_put": "call", "S": 100, "K": 100,
                 "T": 1, "r": 0.05},
            )
        )
        self.assertAlmostEqual(out["implied_volatility"], 0.20, places=5)

    def test_binomial_american(self):
        out = json.loads(
            self._registry().dispatch(
                "derivatives_binomial",
                {"call_put": "put", "S": 42, "K": 40, "T": 0.5, "r": 0.10,
                 "sigma": 0.20, "steps": 200, "american": True},
            )
        )
        self.assertTrue(out["american"])
        self.assertGreater(out["price"], 0.0)

    def test_price_error_is_honest(self):
        out = json.loads(
            self._registry().dispatch(
                "derivatives_price",
                {"call_put": "call", "S": 100, "K": 100, "T": 1,
                 "r": 0.05, "sigma": 0.0},
            )
        )
        self.assertIn("error", out)


class RiskManagementToolTest(_TempStore):
    def test_limits(self):
        spec = {
            "limits": [{"name": "gross", "metric": "max_gross_exposure", "threshold": 1.5}],
            "metrics": {"max_gross_exposure": 1.8},
        }
        out = json.loads(self._registry().dispatch("riskmanagement_limits", {"spec": spec}))
        self.assertEqual(out["breach_count"], 1)
        self.assertEqual(out["breached"], ["gross"])
        self.assertTrue(out["results"][0]["breached"])

    def test_stress(self):
        spec = {
            "exposures": {"equity": 3_000_000.0},
            "nav": 5_000_000.0,
            "scenarios": [{"name": "crash", "shocks": {"equity": -0.30}}],
        }
        out = json.loads(self._registry().dispatch("riskmanagement_stress", {"spec": spec}))
        self.assertAlmostEqual(out["scenarios"][0]["pnl"], -900_000.0)
        self.assertAlmostEqual(out["scenarios"][0]["pnl_pct"], -0.18)

    def test_reverse_stress(self):
        spec = {"exposures": {"equity": 3_000_000.0}, "factor": "equity", "target_loss": 600_000.0}
        out = json.loads(self._registry().dispatch("riskmanagement_reverse_stress", {"spec": spec}))
        self.assertAlmostEqual(out["shock"], -0.20)

    def test_var_backtest(self):
        var = [0.05] * 100
        returns = [-0.10] * 8 + [0.01] * 92
        out = json.loads(
            self._registry().dispatch(
                "riskmanagement_var_backtest",
                {"var_forecasts": var, "realized_returns": returns},
            )
        )
        self.assertEqual(out["exceptions"], 8)
        self.assertAlmostEqual(out["kupiec_lr"], 1.615808, places=5)
        self.assertFalse(out["kupiec_reject"])

    def test_limits_error_is_honest(self):
        spec = {"limits": [{"name": "gross", "metric": "missing", "threshold": 1.5}],
                "metrics": {}}
        out = json.loads(self._registry().dispatch("riskmanagement_limits", {"spec": spec}))
        self.assertIn("error", out)


class MandAToolTest(_TempStore):
    def test_accretion(self):
        out = json.loads(
            self._registry().dispatch(
                "manda_accretion",
                {"acquirer_ni": 500, "acquirer_shares": 100, "target_ni": 120,
                 "purchase_price": 2000, "cash_portion": 1000, "stock_portion": 1000,
                 "acquirer_share_price": 50, "tax_rate": 0.25,
                 "cost_synergies": 80, "new_debt_rate": 0.05},
            )
        )
        self.assertAlmostEqual(out["pro_forma_eps"], 642.5 / 120.0)
        self.assertAlmostEqual(out["accretion_pct"], 0.070833333, places=5)
        self.assertTrue(out["accretive"])

    def test_synergies(self):
        out = json.loads(
            self._registry().dispatch(
                "manda_synergies",
                {"cost_synergies": 100, "tax_rate": 0.25, "discount_rate": 0.10,
                 "ramp_years": 2, "integration_costs": 50, "premium_paid": 400},
            )
        )
        self.assertAlmostEqual(out["gross_value"], 75.0 * 9.5454545, places=3)
        self.assertTrue(out["covered"])

    def test_breakeven(self):
        out = json.loads(
            self._registry().dispatch(
                "manda_breakeven",
                {"premium_paid": 400, "integration_costs": 50, "tax_rate": 0.25,
                 "discount_rate": 0.10, "ramp_years": 2},
            )
        )
        self.assertAlmostEqual(out["required_cost_synergies"], 62.857143, places=5)

    def test_lbo(self):
        out = json.loads(
            self._registry().dispatch(
                "manda_lbo",
                {"enterprise_value": 1000, "existing_net_debt": 200, "fees": 30,
                 "entry_debt": 700, "ebitda_0": 100, "ebitda_growth": 0.05,
                 "years": 5, "fcf_margin": 0.60, "exit_multiple": 8.0,
                 "interest_rate": 0.06, "tax_rate": 0.25},
            )
        )
        self.assertAlmostEqual(out["equity_check"], 330.0)
        self.assertAlmostEqual(out["moic"], 1.599858, places=4)
        self.assertAlmostEqual(out["irr"], 0.09856, places=4)

    def test_accretion_error_is_honest(self):
        out = json.loads(
            self._registry().dispatch(
                "manda_accretion",
                {"acquirer_ni": 500, "acquirer_shares": 100, "target_ni": 120,
                 "purchase_price": 2000, "cash_portion": 900, "stock_portion": 900,
                 "acquirer_share_price": 50, "tax_rate": 0.25},
            )
        )
        self.assertIn("error", out)


class MemoryToolTest(_TempStore):
    def test_record_and_export(self):
        reg = self._registry()
        reg.dispatch("memory_record", {"content": "fact A", "kind": "memory"})
        out = json.loads(reg.dispatch("memory_export", {}))
        self.assertEqual(out["memory"], ["fact A"])

    def test_supersede_and_retract(self):
        reg = self._registry()
        first = json.loads(
            reg.dispatch("memory_record", {"content": "old", "kind": "memory"})
        )
        reg.dispatch(
            "memory_record",
            {"content": "new", "kind": "memory", "supersedes": [first["id"]]},
        )
        out = json.loads(reg.dispatch("memory_export", {}))
        self.assertEqual(out["memory"], ["new"])
        reg.dispatch("memory_retract", {"fact_id": first["id"]})
        out = json.loads(reg.dispatch("memory_export", {}))
        self.assertEqual(out["memory"], ["new"])

    def test_record_rejects_bad_kind(self):
        out = json.loads(
            self._registry().dispatch(
                "memory_record", {"content": "x", "kind": "nonsense"}
            )
        )
        self.assertIn("error", out)


class DeskToolTest(_TempStore):
    def test_desk_run_scripted(self):
        findings = {
            "pm": {"thesis": "trim", "stance": "bearish", "confidence": 0.7,
                   "loss_case": "drift", "falsify": "cap"},
            "trader": {"thesis": "hold", "stance": "neutral", "confidence": 0.5,
                       "loss_case": "whipsaw", "falsify": "vol"},
        }
        reg = build_registry(
            store=self.store, desk_executor=scripted_executor(findings)
        )
        out = json.loads(
            reg.dispatch(
                "desk_run", {"objective": "trim AAPL", "seats": ["pm", "trader"]}
            )
        )
        self.assertEqual(out["stance"], "mixed")
        self.assertEqual(len(out["findings"]), 2)
        self.assertEqual(set(f["seat"] for f in out["findings"]), {"pm", "trader"})


class MarketToolTest(_TempStore):
    def test_price_summary(self):
        ds = Dataset(
            source="stooq", as_of="2026-01-02", fetched_at="2026-01-02T00:00:00Z",
            degraded=True, cached=False,
            data={"bars": [{"date": "2026-01-01", "close": 10.0},
                           {"date": "2026-01-02", "close": 11.0}]},
        )
        with patch("f1nance.agent.tools.get_price_history", return_value=ds):
            out = json.loads(
                self._registry().dispatch("market_price", {"symbol": "aapl"})
            )
        self.assertEqual(out["symbol"], "AAPL")
        self.assertEqual(out["source"], "stooq")
        self.assertTrue(out["degraded"])
        self.assertEqual(out["bars"]["count"], 2)


# -- system ------------------------------------------------------------------

class SystemPromptTest(_TempStore):
    def test_includes_soul_facts_and_contract(self):
        soul = "# SOUL\n\nYou are F1NANCE.\n"
        prompt = build_system_prompt(soul, {"memory": ["fact A"], "directive": ["d1"]})
        self.assertIn("You are F1NANCE.", prompt)
        self.assertIn("fact A", prompt)
        self.assertIn("d1", prompt)
        self.assertIn(WORKING_CONTRACT.strip()[:20], prompt)

    def test_empty_store_placeholder(self):
        prompt = build_system_prompt("# SOUL\n", {})
        self.assertIn("No durable facts", prompt)

    def test_load_system_prompt(self):
        soul_path = f"{self._tmp.name}/SOUL.md"
        with open(soul_path, "w") as fh:
            fh.write("# SOUL\n\nSoul text.\n")
        self.store.add("a memory", "memory", "test")
        from f1nance.agent.system import load_system_prompt
        prompt = load_system_prompt(soul_path=soul_path, store=self.store)
        self.assertIn("Soul text.", prompt)
        self.assertIn("a memory", prompt)


# -- loop --------------------------------------------------------------------

class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages, tools=None):
        self.calls.append((list(messages), tools))
        if not self.responses:
            raise ModelError("no responses left")
        return self.responses.pop(0)


def _tool(name, handler, params=None):
    return Tool(name, "test tool", params or {"type": "object", "properties": {}}, handler)


class LoopTest(_TempStore):
    def test_plain_answer(self):
        client = FakeClient([{"role": "assistant", "content": "hello"}])
        agent = Agent(client, self._registry(), "sys")
        self.assertEqual(agent.run("hi"), "hello")

    def test_dispatches_tool_then_answers(self):
        tool_msg = {
            "role": "assistant", "content": None,
            "tool_calls": [
                {"id": "c1", "function": {"name": "memory_export", "arguments": "{}"}}
            ],
        }
        client = FakeClient([tool_msg, {"role": "assistant", "content": "done"}])
        agent = Agent(client, self._registry(), "sys", max_steps=5)
        out = agent.run("what do I remember?")
        self.assertEqual(out, "done")
        # the tool result was fed back as a tool message
        tool_msgs = [m for m in client.calls[1][0] if m["role"] == "tool"]
        self.assertEqual(len(tool_msgs), 1)
        self.assertEqual(tool_msgs[0]["tool_call_id"], "c1")

    def test_carries_history(self):
        client = FakeClient([{"role": "assistant", "content": "ok"}])
        agent = Agent(client, self._registry(), "sys")
        agent.run("second", history=[{"role": "user", "content": "first"},
                                     {"role": "assistant", "content": "reply"}])
        first_call = client.calls[0][0]
        self.assertEqual(first_call[0], {"role": "system", "content": "sys"})
        self.assertEqual(first_call[1], {"role": "user", "content": "first"})

    def test_max_steps_raises(self):
        tool_msg = {
            "role": "assistant", "content": None,
            "tool_calls": [
                {"id": "c1", "function": {"name": "memory_export", "arguments": "{}"}}
            ],
        }
        client = FakeClient([tool_msg, tool_msg, tool_msg])
        agent = Agent(client, self._registry(), "sys", max_steps=2)
        with self.assertRaises(MaxStepsError):
            agent.run("hi")

    def test_max_steps_positive(self):
        with self.assertRaises(ValueError):
            Agent(FakeClient([]), self._registry(), "sys", max_steps=0)

    def test_run_agent_convenience(self):
        client = FakeClient([{"role": "assistant", "content": "ans"}])
        out = run_agent(client, self._registry(), "sys", "q")
        self.assertEqual(out, "ans")


if __name__ == "__main__":
    unittest.main()
