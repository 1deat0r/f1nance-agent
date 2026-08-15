"""Offline tests for the desk's live executor — no network, no model, no Hermes.

The live executor is the bridge from the scripted desk to a model-backed desk.
These tests cover the pure parts (``build_prompt``, ``parse_finding``) and the
retry/dispatch seam (``model_executor`` with a fake client), so the real
``ModelClient`` (a stdlib ``urllib`` call) is the only thing exercised live.
"""

import json
import os
import unittest
from unittest.mock import patch

from f1nance.desk import Brief, Desk
from f1nance.desk.live import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    ModelClient,
    ModelError,
    build_prompt,
    env_client,
    model_executor,
    parse_finding,
)
from f1nance.desk.seats import DESK_SEATS

VALID = json.dumps(
    {
        "thesis": "trim the concentrated position to the 15% cap",
        "stance": "bearish",
        "confidence": 0.7,
        "loss_case": "AAPL keeps outperforming; ~-5% drag",
        "falsify": "concentration < 20% without action",
        "actions": ["trim to 15%"],
    }
)


class StubClient:
    """A client stub that pops from a queue of canned responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, system, user):
        self.calls.append((system, user))
        if not self.responses:
            raise ModelError("no responses left")
        return self.responses.pop(0)


class RepeatingClient:
    """A client stub that always returns the same response."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.response


class BuildPromptTest(unittest.TestCase):
    def test_system_names_seat_and_mandate(self):
        seat = DESK_SEATS["pm"]
        system, user = build_prompt(seat, Brief("rebalance"))
        self.assertIn(seat.label, system)
        self.assertIn(seat.mandate, system)
        self.assertIn(seat.domain, system)

    def test_system_encodes_guardrails_and_json_contract(self):
        system, _ = build_prompt(DESK_SEATS["pm"], Brief("rebalance"))
        self.assertIn("No fabrication", system)
        self.assertIn("Risk before return", system)
        self.assertIn("thesis", system)
        self.assertIn("loss_case", system)
        self.assertIn("falsify", system)
        self.assertIn("confidence", system)

    def test_user_carries_brief(self):
        brief = Brief(
            "size AAPL",
            context="position at 22%",
            horizon="12m",
            risk_capacity="moderate",
            constraints=("no name > 20%",),
        )
        _, user = build_prompt(DESK_SEATS["pm"], brief)
        self.assertIn("size AAPL", user)
        self.assertIn("position at 22%", user)
        self.assertIn("12m", user)
        self.assertIn("moderate", user)
        self.assertIn("no name > 20%", user)


class ParseFindingTest(unittest.TestCase):
    def test_clean_json(self):
        f = parse_finding(DESK_SEATS["pm"], VALID)
        self.assertEqual(f.seat, "pm")
        self.assertEqual(f.stance, "bearish")
        self.assertAlmostEqual(f.confidence, 0.7)
        self.assertEqual(f.actions, ("trim to 15%",))

    def test_fenced_json(self):
        f = parse_finding(DESK_SEATS["trader"], f"```json\n{VALID}\n```")
        self.assertEqual(f.seat, "trader")
        self.assertEqual(f.stance, "bearish")

    def test_prose_wrapped_json(self):
        text = f"Here is my analysis. {VALID} Hope this helps."
        f = parse_finding(DESK_SEATS["pm"], text)
        self.assertEqual(f.stance, "bearish")

    def test_confidence_label(self):
        data = json.loads(VALID)
        data["confidence"] = "high"
        f = parse_finding(DESK_SEATS["pm"], json.dumps(data))
        self.assertAlmostEqual(f.confidence, 0.8)

    def test_confidence_numeric_string(self):
        data = json.loads(VALID)
        data["confidence"] = "0.4"
        f = parse_finding(DESK_SEATS["pm"], json.dumps(data))
        self.assertAlmostEqual(f.confidence, 0.4)

    def test_missing_field_raises(self):
        data = json.loads(VALID)
        del data["loss_case"]
        with self.assertRaises(ValueError):
            parse_finding(DESK_SEATS["pm"], json.dumps(data))

    def test_invalid_stance_raises(self):
        data = json.loads(VALID)
        data["stance"] = "euphoric"
        with self.assertRaises(ValueError):
            parse_finding(DESK_SEATS["pm"], json.dumps(data))

    def test_confidence_out_of_range_raises(self):
        data = json.loads(VALID)
        data["confidence"] = 1.5
        with self.assertRaises(ValueError):
            parse_finding(DESK_SEATS["pm"], json.dumps(data))

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            parse_finding(DESK_SEATS["pm"], "just some prose, no braces")

    def test_non_object_raises(self):
        with self.assertRaises(ValueError):
            parse_finding(DESK_SEATS["pm"], '["not", "an", "object"]')


class ModelExecutorTest(unittest.TestCase):
    def _brief(self):
        return Brief("size the AAPL position", seats=("pm", "trader"))

    def test_valid_first_try(self):
        client = StubClient([VALID])
        finding = model_executor(client)(DESK_SEATS["pm"], self._brief())
        self.assertEqual(finding.seat, "pm")
        self.assertEqual(len(client.calls), 1)

    def test_retries_after_malformed_output(self):
        client = StubClient(["not json at all", VALID])
        finding = model_executor(client)(DESK_SEATS["pm"], self._brief())
        self.assertEqual(finding.seat, "pm")
        self.assertEqual(len(client.calls), 2)
        # the corrective retry carries the parse error back to the model
        self.assertIn("could not be parsed", client.calls[1][1])

    def test_gives_up_after_max_attempts(self):
        client = StubClient(["bad"] * 3)
        with self.assertRaises(ModelError):
            model_executor(client, max_attempts=3)(DESK_SEATS["pm"], self._brief())
        self.assertEqual(len(client.calls), 3)

    def test_client_error_propagates_without_retry(self):
        class Boom:
            def complete(self, system, user):
                raise ModelError("HTTP 401")

        with self.assertRaises(ModelError) as ctx:
            model_executor(Boom())(DESK_SEATS["pm"], self._brief())
        self.assertIn("HTTP 401", str(ctx.exception))

    def test_max_attempts_must_be_positive(self):
        with self.assertRaises(ValueError):
            model_executor(StubClient([VALID]), max_attempts=0)

    def test_desk_run_with_model_executor(self):
        client = RepeatingClient(VALID)
        verdict = Desk().run(self._brief(), model_executor(client))
        self.assertEqual(verdict.seats, ("pm", "trader"))
        self.assertEqual(verdict.stance, "bearish")
        self.assertEqual(verdict.agreement, 1.0)
        self.assertEqual(len(verdict.findings), 2)
        self.assertEqual(len(client.calls), 2)


class EnvClientTest(unittest.TestCase):
    def test_missing_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ModelError):
                env_client()

    def test_f1nance_key_preferred(self):
        env = {"F1NANCE_API_KEY": "f-key", "DEEPSEEK_API_KEY": "d-key"}
        with patch.dict(os.environ, env, clear=True):
            client = env_client()
        self.assertEqual(client.api_key, "f-key")

    def test_deepseek_key_fallback(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "d-key"}, clear=True):
            client = env_client()
        self.assertEqual(client.api_key, "d-key")

    def test_defaults(self):
        env = {"DEEPSEEK_API_KEY": "d-key"}
        with patch.dict(os.environ, env, clear=True):
            client = env_client()
        self.assertEqual(client.base_url, DEFAULT_BASE_URL)
        self.assertEqual(client.model, DEFAULT_MODEL)

    def test_overrides(self):
        env = {
            "DEEPSEEK_API_KEY": "d-key",
            "F1NANCE_BASE_URL": "https://example.test/v1",
            "F1NANCE_MODEL": "some-model",
        }
        with patch.dict(os.environ, env, clear=True):
            client = env_client()
        self.assertEqual(client.base_url, "https://example.test/v1")
        self.assertEqual(client.model, "some-model")

    def test_model_client_type(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "d-key"}, clear=True):
            self.assertIsInstance(env_client(), ModelClient)


if __name__ == "__main__":
    unittest.main()
