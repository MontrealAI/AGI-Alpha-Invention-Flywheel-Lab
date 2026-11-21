# SPDX-License-Identifier: Apache-2.0
"""Authored extraction fixtures; no claims of live model or historical discovery."""
import copy
import hashlib
import json
from types import SimpleNamespace
import unittest

from bridge.adapters import BridgeError
from bridge.foresight import assess
from bridge.foresight_extract import extract


TIME = "2026-11-21T12:00:00+00:00"
QUOTES = ["Shared memory could support collaborative design.",
          "Reliable machines may permit automatic computation.",
          "An invented interface might reduce coordination costs."]


def sources():
    body = " ".join(QUOTES)
    return {"historical-document": {"url": "https://example.com/foresight", "title": "Authored source fixture",
            "kind": "historical", "published_at": "1962", "observed_at": TIME,
            "snapshot": {"body": body, "sha256": hashlib.sha256(body.encode()).hexdigest(), "scope": "excerpt"}}}


def response():
    return {"claims": [{"id": "claim-" + str(index), "source": "historical-document", "quote": quote,
                        "kind": kind, "statement": quote}
                       for index, (quote, kind) in enumerate(zip(QUOTES, ["scenario", "forecast", "intervention_hypothesis"]))],
            "abstain": False, "rationale": "Authored supported claims for protocol testing."}


class Fixture:
    def __init__(self, value):
        self.value, self.calls = value, []
        self.connection = SimpleNamespace(remote=False, models={"fixture": SimpleNamespace(
            json_schema=True, json_mode=True, streaming=False)})

    def provider(self, _ident):
        return self.connection

    def generate(self, request):
        self.calls.append(request)
        if isinstance(self.value, Exception):
            raise self.value
        return {"text": json.dumps(self.value), "usage": {"input_tokens": 100, "output_tokens": 80},
                "qualification": "AUTHORED_FIXTURE_NOT_LIVE_MODEL", "reported_model": "fixture",
                "cost": {"amount": None, "complete_cost_known": False}}

    def redact(self, text):
        return text


def run(runtime, documents=None):
    return extract(runtime, {"provider": "local", "model": "fixture"}, sources() if documents is None else documents,
                   recorded_at=TIME, catalog_id="fixture-extraction", version="1")


class ForesightExtractionTests(unittest.TestCase):
    def test_checked_catalogue_preserves_sources_and_never_promotes_visions_to_readiness(self):
        original = sources()
        runtime = Fixture(response())
        result = run(runtime, original)
        self.assertEqual(result["status"], "extracted")
        self.assertEqual(result["trace"]["provenance"], "AUTHORED_FIXTURE_NOT_LIVE_MODEL")
        self.assertIsNone(result["trace"]["actual_complete_cost_usd"])
        self.assertEqual(result["trace"]["claim_count"], 3)
        catalog = result["catalog"]
        self.assertEqual(catalog["conditions"], {})
        self.assertEqual(catalog["outcomes"], {})
        self.assertEqual({row["kind"] for row in catalog["claims"].values()},
                         {"scenario", "forecast", "intervention_hypothesis"})
        for row in catalog["claims"].values():
            self.assertEqual(row["source_sha256"], original[row["source"]]["snapshot"]["sha256"])
            self.assertIn(row["quote"], original[row["source"]]["snapshot"]["body"])
        self.assertEqual(assess(catalog, [], as_of=TIME)["conditions"], {})
        original["historical-document"]["snapshot"]["body"] = "changed caller input"
        self.assertNotEqual(catalog["sources"], original)
        self.assertIn("json_schema", runtime.calls[0])
        self.assertIn("untrusted data", runtime.calls[0]["prompt"])

    def test_fabrications_type_upgrades_duplicates_and_shortfalls_produce_no_catalogue(self):
        for variant in ("quote", "source", "observation", "probability", "duplicate-id", "duplicate-statement", "two-claims"):
            value = response()
            if variant == "quote":
                value["claims"][0]["quote"] = "This assertion never appeared in the source."
            elif variant == "source":
                value["claims"][0]["source"] = "unregistered-source"
            elif variant == "observation":
                value["claims"][0]["kind"] = "observation"
            elif variant == "probability":
                value["claims"][0]["probability"] = .99
            elif variant == "duplicate-id":
                value["claims"][1]["id"] = value["claims"][0]["id"]
            elif variant == "duplicate-statement":
                value["claims"][1]["statement"] = value["claims"][0]["statement"]
            else:
                value["claims"].pop()
            runtime = Fixture(value)
            result = run(runtime)
            with self.subTest(variant=variant):
                self.assertEqual(result["status"], "invalid_response")
                self.assertIsNone(result["catalog"])
                self.assertIn("error", result["trace"])
                self.assertEqual(result["trace"]["usage"]["output_tokens"], 80)
                self.assertEqual(len(runtime.calls), 1)

    def test_abstention_failed_transport_and_invalid_inputs_never_silently_retry(self):
        abstain = run(Fixture({"claims": [], "abstain": True, "rationale": "Insufficient supported claims."}))
        self.assertEqual(abstain["status"], "abstained")
        self.assertIsNone(abstain["catalog"])
        runtime = Fixture(BridgeError("PROVIDER_CONNECTION", "Fixture interruption"))
        failed = run(runtime)
        self.assertEqual(failed["status"], "model_error")
        self.assertEqual(failed["trace"]["dispatch"], "unknown")
        self.assertIsNone(failed["trace"]["actual_complete_cost_usd"])
        self.assertEqual(len(runtime.calls), 1)
        for variant in ("remote", "hash"):
            runtime, documents = Fixture(response()), sources()
            if variant == "remote":
                runtime.connection.remote = True
            else:
                documents["historical-document"]["snapshot"]["sha256"] = "0" * 64
            with self.subTest(variant=variant), self.assertRaises(BridgeError):
                run(runtime, documents)
            self.assertEqual(runtime.calls, [])


if __name__ == "__main__":
    unittest.main()
