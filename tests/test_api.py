"""API regression tests. All OpenAI clients are mocked; no paid requests."""

from copy import deepcopy
import json
import logging
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from openai import APIConnectionError, APITimeoutError

from backend import ai_service
from backend.main import app
from backend.explanations import evidence_catalog, render_selection
from backend.simulation import simulate_scenario


REFERENCE_SELECTIONS = [
    {"measure_id": "M7", "district": "Nura"},
    {"measure_id": "M8", "district": "Nura"},
    {"measure_id": "M10", "district": "Nura"},
    {"measure_id": "M12", "district": None},
    {"measure_id": "M5", "district": "Saryarka"},
]
SELECTION = {
    "summary": "score", "strengths": ["gain_Nura"], "risks": ["model"],
    "tradeoffs": ["budget"], "consequences": ["resolved_Nura_S1", "resolved_Nura_S2"],
    "recommendations": ["compare"],
}
ANALYSIS = render_selection(SELECTION, evidence_catalog(simulate_scenario(REFERENCE_SELECTIONS)))
TEST_KEY = "unit-test-placeholder-not-a-real-key"


class APITests(unittest.TestCase):
    def setUp(self):
        # Ignore any developer key; mock the client even in missing-key tests.
        self.enterContext(patch.dict(os.environ, {"OPENAI_API_KEY": ""}))
        self.factory = self.enterContext(patch("backend.ai_service.OpenAI"))
        self.sdk = self.factory.return_value.__enter__.return_value
        self.client = self.enterContext(TestClient(app))

    def reference_result(self):
        response = self.client.post("/api/simulate", json={"selections": REFERENCE_SELECTIONS})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def analyze(self, result):
        response = self.client.post("/api/analyze", json={"simulation_result": result})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def enable_mock_ai(self):
        os.environ["OPENAI_API_KEY"] = TEST_KEY
        self.sdk.responses.parse.return_value = SimpleNamespace(
            status="completed", output_parsed=ai_service.EvidenceSelection(**SELECTION)
        )

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_initial_state(self):
        response = self.client.get("/api/initial-state")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["budget"], 100)
        self.assertEqual(data["required_decisions"], 5)
        self.assertAlmostEqual(data["baseline_score"], 52.55768)
        self.assertEqual(len(data["districts"]), 5)
        self.assertEqual(len(data["measures"]), 14)
        self.assertEqual(len(data["indicator_metadata"]), 10)
        self.factory.assert_not_called()

    def test_reference_simulation_without_ai(self):
        result = self.reference_result()
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["total_cost"], 95)
        self.assertEqual(result["remaining_budget"], 5)
        self.assertAlmostEqual(result["baseline_score"], 52.55768)
        self.assertAlmostEqual(result["final_score"], 56.54307)
        self.assertEqual(result["applied_synergies"], [{
            "measures": ["M10", "M12"], "district": "Nura", "effects": {"B1": 2},
        }])
        self.factory.assert_not_called()

    def test_invalid_simulation(self):
        for selections in ([], [REFERENCE_SELECTIONS[0]] * 5):
            with self.subTest(selections=selections):
                response = self.client.post("/api/simulate", json={"selections": selections})
                self.assertEqual(response.status_code, 200)
                result = response.json()
                self.assertFalse(result["valid"])
                self.assertTrue(result["errors"])
                self.assertIsNone(result["final_score"])
                self.assertIsNone(result["indicators_after"])

    def test_malformed_api_requests(self):
        for path, body in (
            ("/api/simulate", {}),
            ("/api/simulate", {"selections": "invalid"}),
            ("/api/simulate", {"selections": [None]}),
            ("/api/analyze", {}),
            ("/api/analyze", {"simulation_result": []}),
        ):
            with self.subTest(path=path, body=body):
                response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, 422)
                self.assertTrue(response.json()["detail"])
        response = self.client.post("/api/simulate", content="{", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)
        self.factory.assert_not_called()

    def test_analysis_missing_key(self):
        os.environ.pop("OPENAI_API_KEY", None)
        error = self.analyze(self.reference_result())
        self.assertEqual(error["error"]["code"], "missing_api_key")
        self.factory.assert_not_called()

    def test_analysis_success_and_unchanged_numerical_payload(self):
        self.enable_mock_ai()
        result = self.reference_result()
        original = deepcopy(result)
        self.assertEqual(self.analyze(result), ANALYSIS)
        arguments = self.sdk.responses.parse.call_args.kwargs
        payload = json.loads(arguments["input"][0]["content"])
        self.assertEqual(payload["simulation_result"], {
            key: original[key] for key in ai_service.RESULT_FIELDS
        })
        self.assertAlmostEqual(payload["simulation_result"]["district_score_deltas"]["Nura"], 3.7825)
        self.assertEqual(payload["simulation_result"]["indicator_deltas"]["Nura"]["S1"], 10)
        self.assertEqual(len(payload["simulation_result"]["measure_contributions"]), 5)
        self.assertNotIn(TEST_KEY, json.dumps(payload))
        self.assertIs(arguments["text_format"], ai_service.EvidenceSelection)
        self.assertFalse(arguments["store"])
        self.assertIn("Never calculate, recalculate", arguments["instructions"])
        self.assertEqual(result, original)
        self.assertEqual(ai_service.analyze_simulation(result), ANALYSIS)
        self.assertEqual(result, original)  # Check the direct call, not just JSON copies.
        self.assertEqual(self.reference_result(), original)

    def check_ai_failure(self, failure, code):
        self.enable_mock_ai()
        result = self.reference_result()
        original = deepcopy(result)
        self.sdk.responses.parse.side_effect = failure
        # Capture application/SDK logs, excluding TestClient's routine access logs.
        with self.assertNoLogs("backend", level=logging.DEBUG), self.assertNoLogs("openai", level=logging.DEBUG):
            error = self.analyze(result)
            direct_error = ai_service.analyze_simulation(result)
        self.assertEqual(error["error"]["code"], code)
        self.assertEqual(direct_error, error)
        self.assertNotIn(TEST_KEY, json.dumps(error))
        self.assertEqual(result, original)
        self.assertEqual(self.reference_result(), original)
        self.factory.assert_called_with(api_key=TEST_KEY, timeout=30.0, max_retries=0)

    def test_openai_request_failure_preserves_simulation(self):
        failure = APIConnectionError(
            message=TEST_KEY, request=httpx.Request("POST", "https://api.openai.com/v1/responses")
        )
        self.check_ai_failure(failure, "openai_request_failed")

    def test_openai_timeout_preserves_simulation(self):
        failure = APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        self.check_ai_failure(failure, "openai_timeout")

    def test_ai_refusal_and_incomplete_response(self):
        self.enable_mock_ai()
        result = self.reference_result()
        for status in ("completed", "incomplete"):
            with self.subTest(status=status):
                self.sdk.responses.parse.return_value = SimpleNamespace(status=status, output_parsed=None)
                self.assertEqual(self.analyze(result)["error"]["code"], "invalid_ai_response")

    def test_invalid_ai_output(self):
        self.enable_mock_ai()
        self.sdk.responses.parse.side_effect = ValueError(TEST_KEY)
        error = self.analyze(self.reference_result())
        self.assertEqual(error["error"]["code"], "invalid_ai_response")
        self.assertNotIn(TEST_KEY, json.dumps(error))

    def test_invalid_analysis_input_never_calls_openai(self):
        self.enable_mock_ai()
        for result in ({}, {"valid": True}, {"valid": False}):
            with self.subTest(result=result):
                self.assertEqual(self.analyze(result)["error"]["code"], "invalid_simulation")
        self.factory.assert_not_called()

    def test_unexpected_service_failure_is_controlled(self):
        result = self.reference_result()
        with patch("backend.main.analyze_simulation", side_effect=RuntimeError(TEST_KEY)):
            error = self.analyze(result)
        self.assertEqual(error["error"]["code"], "analysis_unavailable")
        self.assertNotIn(TEST_KEY, json.dumps(error))
        self.assertEqual(self.reference_result(), result)

    def test_frontend_cors_preflight(self):
        response = self.client.options("/api/analyze", headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "*")


if __name__ == "__main__":
    unittest.main()
