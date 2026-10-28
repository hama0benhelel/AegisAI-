"""Provider protocol regressions: malformed envelopes must fail closed."""
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app import llm, semantic_router


class ProviderEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.user = {"id": uuid4(), "tenant_id": uuid4()}
        self.payload = {
            "intent": "q_and_a", "answer": "Valeur de référence : 1,203 m3.",
            "sources": [{"reading_id": "source-a", "value": 1.203, "unit": "m3"}],
            "mode": "grounded_template", "llm_used": False,
        }

    def request(self):
        return SimpleNamespace(state=SimpleNamespace(trace_id=str(uuid4())))

    def malformed(self):
        for envelope in (None, [], "unexpected", {"choices": {}},
                         {"choices": []}, {"choices": [None]},
                         {"choices": [{"finish_reason": "stop", "message": []}]},
                         {"choices": [{"finish_reason": "stop", "message": {"content": []}}]}):
            yield envelope

    def test_generation_rejects_malformed_envelopes_and_finishes_journal(self):
        for envelope in self.malformed():
            with self.subTest(envelope=envelope), patch.dict(os.environ, {
                "LLM_ENABLED": "true", "GROQ_API_KEY": "local-test-key",
            }), patch.object(llm, "reserve_call", return_value=uuid4()), \
                 patch.object(llm, "finish_call") as finish, \
                 patch.object(llm, "urlopen") as http:
                http.return_value.__enter__.return_value.read.return_value = json.dumps(envelope).encode()
                result = llm.render_with_llm(self.request(), self.user, self.payload)
                self.assertFalse(result["llm_used"])
                self.assertEqual(result["llm_reason"], "invalid_output")
                self.assertEqual(result["sources"], self.payload["sources"])
                self.assertIn(self.payload["answer"], result["answer"])
                http.assert_called_once()
                finish.assert_called_once()
                self.assertEqual(finish.call_args.args[2:4], ("fallback", "invalid_output"))

    def test_router_rejects_malformed_envelopes_and_finishes_journal(self):
        for envelope in self.malformed():
            opener = MagicMock()
            opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(envelope).encode()
            with self.subTest(envelope=envelope), patch.dict(os.environ, {
                "LLM_ENABLED": "true", "GROQ_API_KEY": "local-test-key",
            }), patch.object(semantic_router, "reserve_call", return_value=uuid4()), \
                 patch.object(semantic_router, "finish_call") as finish, \
                 patch.object(semantic_router, "build_opener", return_value=opener):
                result = semantic_router.resolve_message(
                    "quele est mon consomations d'eau hier", self.request(), self.user
                )
                self.assertEqual(result["decision"], "clarify")
                self.assertEqual(result["reason"], "invalid_output")
                opener.open.assert_called_once()
                finish.assert_called_once()
                self.assertEqual(finish.call_args.args[2:4], ("fallback", "invalid_output"))

    def test_daily_totals_bypass_generation_even_with_provider_enabled(self):
        payload = {**self.payload, "period": {"kind": "yesterday"}}
        with patch.dict(os.environ, {"LLM_ENABLED": "true", "GROQ_API_KEY": "local-test-key"}), \
             patch.object(llm, "reserve_call") as reserve, patch.object(llm, "urlopen") as http:
            result = llm.render_with_llm(self.request(), self.user, payload)
        self.assertEqual(result["answer"], payload["answer"])
        self.assertEqual(result["sources"], payload["sources"])
        self.assertEqual(result["llm_reason"], "deterministic_daily_summary")
        reserve.assert_not_called()
        http.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
