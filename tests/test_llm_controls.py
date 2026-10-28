import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from uuid import uuid4

from app import llm


class LLMControlsTests(unittest.TestCase):
    def setUp(self):
        self.user = {
            "id": uuid4(),
            "tenant_id": uuid4(),
            "role": "viewer",
        }
        self.request = SimpleNamespace(
            state=SimpleNamespace(trace_id=str(uuid4()))
        )
        self.call_id = uuid4()
        self.payload = {
            "intent": "q_and_a",
            "answer": "La mesure est de 35 m3.",
            "mode": "grounded_template",
            "llm_used": False,
            "sources": [{
                "reading_id": "source-A",
                "value": 35,
                "unit": "m3",
            }],
        }

        self.env = patch.dict(
            "os.environ",
            {"LLM_ENABLED": "true", "GROQ_API_KEY": "fake-test-key"},
        )
        self.env.start()
        self.addCleanup(self.env.stop)

        self.reserve = patch.object(
            llm, "reserve_call", return_value=self.call_id
        ).start()
        self.finish = patch.object(llm, "finish_call").start()
        self.http = patch.object(llm, "urlopen").start()
        self.addCleanup(patch.stopall)

    def provider_response(self, source="source-A", finish="stop"):
        data = {
            "choices": [{
                "finish_reason": finish,
                "message": {
                    "content": json.dumps({
                        "answer": "La mesure disponible est de 35 m3.",
                        "source_ids": [source],
                    })
                },
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 30,
                "total_tokens": 130,
            },
        }
        self.http.return_value.__enter__.return_value.read.return_value = (
            json.dumps(data).encode()
        )

    def render(self, payload=None):
        return llm.render_with_llm(
            self.request, self.user,
            self.payload if payload is None else payload,
        )

    def test_success_preserves_sources_and_records_usage(self):
        self.provider_response()
        result = self.render()

        self.assertTrue(result["llm_used"])
        self.assertEqual(result["sources"], self.payload["sources"])
        self.assertEqual(result["cited_source_ids"], ["source-A"])
        self.assertEqual(result["llm_call_id"], str(self.call_id))

        args = self.finish.call_args.args
        self.assertEqual(args[2], "success")
        self.assertEqual(args[5]["total_tokens"], 130)

        sent = json.loads(self.http.call_args.args[0].data)
        self.assertNotIn("tools", sent)
        self.assertEqual(sent["max_completion_tokens"], 768)
        self.http.assert_called_once()

    def test_disabled_never_calls_provider(self):
        with patch.dict("os.environ", {"LLM_ENABLED": "false"}):
            result = self.render()
        self.assertEqual(result["llm_status"], "disabled")
        self.reserve.assert_not_called()
        self.http.assert_not_called()

    def test_confirmation_never_calls_provider(self):
        result = self.render({
            **self.payload,
            "intent": "recommendation_request",
            "needs_confirmation": True,
        })
        self.assertTrue(result["needs_confirmation"])
        self.reserve.assert_not_called()
        self.http.assert_not_called()

    def test_local_quota_returns_template_without_provider(self):
        self.reserve.return_value = None
        result = self.render()
        self.assertFalse(result["llm_used"])
        self.assertEqual(result["llm_reason"], "local_quota")
        self.http.assert_not_called()
        self.finish.assert_not_called()

    def test_provider_429_falls_back_without_retry(self):
        self.http.side_effect = HTTPError(
            llm.ENDPOINT, 429, "Rate limit", {}, None
        )
        result = self.render()
        self.assertEqual(result["llm_reason"], "provider_http_429")
        self.assertIn(self.payload["answer"], result["answer"])
        self.assertFalse(result["llm_used"])
        self.http.assert_called_once()
        self.assertEqual(self.finish.call_args.args[2], "fallback")
        self.assertEqual(self.finish.call_args.args[5], {})

    def test_timeout_falls_back(self):
        self.http.side_effect = TimeoutError()
        result = self.render()
        self.assertEqual(result["llm_reason"], "provider_unavailable")
        self.assertFalse(result["llm_used"])

    def test_unknown_source_is_rejected(self):
        self.provider_response(source="invented-source-B")
        result = self.render()
        self.assertEqual(result["llm_reason"], "invalid_output")
        self.assertFalse(result["llm_used"])
        self.assertEqual(result["sources"], self.payload["sources"])

    def test_truncated_response_is_rejected(self):
        self.provider_response(finish="length")
        result = self.render()
        self.assertEqual(result["llm_reason"], "invalid_output")
        self.assertFalse(result["llm_used"])

    def test_invalid_json_is_rejected(self):
        self.http.return_value.__enter__.return_value.read.return_value = (
            b"not-json"
        )
        result = self.render()
        self.assertEqual(result["llm_reason"], "invalid_output")


class QuotaReservationTests(unittest.TestCase):
    def test_limits_block_insert(self):
        user = {"id": uuid4(), "tenant_id": uuid4()}
        request = SimpleNamespace(
            state=SimpleNamespace(trace_id=str(uuid4()))
        )

        for counts in (
            {"recent": 5, "daily": 5},
            {"recent": 0, "daily": 100},
        ):
            with self.subTest(counts=counts):
                conn = MagicMock()
                conn.execute.return_value.fetchone.return_value = counts

                with patch.object(llm, "connect") as connect:
                    connect.return_value.__enter__.return_value = conn
                    result = llm.reserve_call(
                        request, user, {"intent": "q_and_a"}
                    )

                self.assertIsNone(result)
                statements = [
                    call.args[0] for call in conn.execute.call_args_list
                ]
                self.assertTrue(any(
                    "pg_advisory_xact_lock" in query for query in statements
                ))
                self.assertFalse(any(
                    "INSERT INTO bws_ai.llm_calls" in query
                    for query in statements
                ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
