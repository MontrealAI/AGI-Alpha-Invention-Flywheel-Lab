# SPDX-License-Identifier: Apache-2.0
"""Evidence, temporal and alternative-route tests; fixtures are not discoveries."""
import copy
import hashlib
import unittest

from bridge.adapters import BridgeError
from bridge.foresight import assess, discovery_context, register


AS_OF = "2026-11-21T12:00:00+00:00"


def catalogue():
    def source(title, kind, body):
        return {"url": "https://example.com/" + title, "title": title, "kind": kind,
                "published_at": "1962" if kind == "historical" else "2026-11-21",
                "observed_at": "2026-11-21T10:00:00Z",
                "snapshot": {"body": body, "sha256": hashlib.sha256(body.encode()).hexdigest(), "scope": "excerpt"}}
    sources = {
        "past": source("past", "historical", "An augmentation system may make new useful work possible."),
        "current": source("current", "current", "The local tool is available. Access was permitted. The workflow failed acceptance."),
    }
    return {"schema": "frontier-foresight/v1", "id": "test-frontier", "version": "1",
            "recorded_at": "2026-11-21T10:30:00Z", "sources": sources,
            "claims": {"vision": {"source": "past", "source_sha256": sources["past"]["snapshot"]["sha256"],
                                  "quote": "may make new useful work possible", "kind": "scenario",
                                  "statement": "Author-envisioned outcome, not present measurement."}},
            "conditions": {"access": {"description": "Authorized operational access exists."},
                           "future-model": {"description": "A hypothetical future model meets a future target."},
                           "local-tool": {"description": "An available tool meets the measured requirement."}},
            "outcomes": {"useful-work": {"description": "Deliver the accepted useful work.", "beneficiary": "Test operator",
                          "requires": ["access"], "foresight": ["vision"],
                          "rival_futures": ["The conventional complete route already supplies it."],
                          "routes": [{"id": "wait", "description": "Wait for a future model.", "requires": ["future-model"], "basis": ["vision"]},
                                     {"id": "construct", "description": "Investigate another missing mechanism.", "requires": ["local-tool"], "basis": []}]}}}


def observation(condition, *, ident=None, kind="observed", status="satisfied", source="current"):
    catalog = catalogue()
    record = catalog["sources"][source]
    return {"id": ident or condition + "-observation", "condition": condition, "source": source,
            "source_sha256": record["snapshot"]["sha256"], "quote": record["snapshot"]["body"],
            "kind": kind, "status": status, "observed_at": "2026-11-21T11:00:00Z",
            "expires_at": "2026-11-22T11:00:00Z"}


class ForesightTests(unittest.TestCase):
    def test_register_binds_exact_source_bytes_and_returns_detached_copy(self):
        original = catalogue()
        frozen = register(original)
        self.assertNotIn("catalog_sha256", original)
        self.assertEqual(register(frozen), frozen)
        original["conditions"]["access"]["description"] = "changed"
        self.assertNotEqual(original["conditions"], frozen["conditions"])
        changed = copy.deepcopy(frozen)
        changed["version"] = "2"
        with self.assertRaisesRegex(BridgeError, "identity changed"):
            register(changed)

    def test_bad_hash_or_fabricated_quotation_rejected(self):
        for mutation in ("body", "quote", "source_sha256"):
            catalog = catalogue()
            if mutation == "body":
                catalog["sources"]["past"]["snapshot"]["body"] += "changed"
            else:
                catalog["claims"]["vision"][mutation] = "Invented quotation" if mutation == "quote" else "a" * 64
            with self.subTest(mutation=mutation), self.assertRaises(BridgeError):
                register(catalog)
        row = observation("access")
        row["quote"] = "unrelated supplied task instructions"
        with self.assertRaisesRegex(BridgeError, "absent"):
            assess(catalogue(), [row], as_of=AS_OF)

    def test_future_model_is_only_one_route_prerequisite(self):
        result = assess(catalogue(), [observation("access"), observation("local-tool"),
                                    observation("future-model", kind="forecast")], as_of=AS_OF)
        outcome = result["outcomes"]["useful-work"]
        self.assertTrue(outcome["conditions_supported"])
        self.assertEqual(outcome["status"], "CONDITIONS_SUPPORTED")
        self.assertEqual(outcome["routes"][0]["unresolved_route_conditions"], ["future-model"])
        self.assertFalse(outcome["routes"][0]["conditions_supported"])
        self.assertTrue(outcome["routes"][1]["conditions_supported"])
        self.assertTrue(outcome["search_for_alternatives"])

    def test_unknown_or_conflicted_outcome_requirement_blocks_all_routes(self):
        rows = [observation("local-tool"), observation("future-model")]
        result = assess(catalogue(), rows, as_of=AS_OF)
        self.assertEqual(result["outcomes"]["useful-work"]["status"], "OUTCOME_CONDITIONS_UNRESOLVED")
        rows.extend([observation("access"), observation("access", ident="contrary", status="contradicted")])
        result = assess(catalogue(), rows, as_of=AS_OF)
        self.assertEqual(result["conditions"]["access"]["status"], "DISPUTED")
        self.assertFalse(any(r["conditions_supported"] for r in result["outcomes"]["useful-work"]["routes"]))

    def test_forecast_report_scenario_and_hypothesis_never_satisfy_now(self):
        for kind in ("forecast", "reported", "scenario", "intervention_hypothesis"):
            result = assess(catalogue(), [observation("access", kind=kind)], as_of=AS_OF)
            with self.subTest(kind=kind):
                self.assertEqual(result["conditions"]["access"]["status"], "UNKNOWN")
                self.assertEqual(result["evidence"]["access-observation"]["reason"], "NOT_OBSERVED")
        result = assess(catalogue(), [observation("access", status="unknown")], as_of=AS_OF)
        self.assertEqual(result["conditions"]["access"]["status"], "UNKNOWN")

    def test_expiry_future_observation_and_historical_quote_do_not_pass(self):
        for variant, reason in (("expired", "EXPIRED"), ("future", "FUTURE_OBSERVATION"), ("historical", "HISTORICAL_FORESIGHT")):
            row = observation("access", source="past" if variant == "historical" else "current")
            if variant == "expired":
                row["expires_at"] = AS_OF  # Expiry is exclusive.
            elif variant == "future":
                row["observed_at"] = "2026-11-21T13:00:00Z"
            result = assess(catalogue(), [row], as_of=AS_OF)
            with self.subTest(variant=variant):
                self.assertEqual(result["conditions"]["access"]["status"], "UNKNOWN")
                self.assertEqual(result["evidence"][row["id"]]["reason"], reason)

    def test_changed_or_retracted_source_invalidates_dependent_evidence(self):
        catalog = catalogue()
        rows = [observation("access"), observation("local-tool")]
        first = assess(catalog, rows, as_of=AS_OF)
        for status, sha, reason in (("active", "b" * 64, "SOURCE_CHANGED"),
                                    ("retracted", catalog["sources"]["current"]["snapshot"]["sha256"], "SOURCE_RETRACTED")):
            changed = assess(catalog, rows, as_of=AS_OF, source_states={"current": {"sha256": sha, "status": status}})
            with self.subTest(status=status):
                self.assertFalse(changed["outcomes"]["useful-work"]["conditions_supported"])
                self.assertEqual(changed["invalidated_sources"], {"current": reason})
                self.assertNotEqual(first["assessment_sha256"], changed["assessment_sha256"])
        self.assertTrue(first["outcomes"]["useful-work"]["conditions_supported"])

    def test_route_basis_retraction_blocks_only_dependent_route(self):
        catalog = catalogue()
        result = assess(catalog, [observation("access"), observation("local-tool"), observation("future-model")],
                        as_of=AS_OF, source_states={"past": {"sha256": "c" * 64, "status": "active"}})
        routes = result["outcomes"]["useful-work"]["routes"]
        self.assertEqual(routes[0]["invalidated_basis"], ["vision"])
        self.assertFalse(routes[0]["conditions_supported"])
        self.assertTrue(routes[1]["conditions_supported"])
        self.assertEqual(result["outcomes"]["useful-work"]["invalidated_foresight"], ["vision"])

    def test_empty_outcomes_permits_open_discovery_without_fixed_solution_menu(self):
        catalog = catalogue()
        catalog["outcomes"] = {}
        context = discovery_context(catalog, [], as_of=AS_OF)
        self.assertEqual(context["assessment"]["outcomes"], {})
        self.assertNotIn("snapshot", context["sources"]["past"])
        self.assertEqual(context["sources"]["past"]["snapshot_scope"], "excerpt")
        self.assertEqual(context["claims"]["vision"]["quote"], catalog["claims"]["vision"]["quote"])
        self.assertIn("beyond this authored catalogue", context["search_instruction"])

    def test_missing_route_is_a_search_target_and_empty_route_cannot_pass_vacuously(self):
        catalog = catalogue()
        catalog["outcomes"]["useful-work"]["routes"] = []
        result = assess(catalog, [observation("access")], as_of=AS_OF)
        self.assertEqual(result["outcomes"]["useful-work"]["status"], "MISSING_MEANS")
        catalog["outcomes"]["useful-work"]["requires"] = []
        catalog["outcomes"]["useful-work"]["routes"] = [{"id": "unsupported", "description": "No registered observation.", "requires": [], "basis": []}]
        result = assess(catalog, [], as_of=AS_OF)
        self.assertFalse(result["outcomes"]["useful-work"]["conditions_supported"])

    def test_unjustified_probability_invalid_ids_and_hindsight_are_rejected(self):
        catalog = catalogue()
        catalog["claims"]["vision"]["kind"] = "forecast"
        catalog["claims"]["vision"]["probability"] = .9
        with self.assertRaisesRegex(BridgeError, "explicit basis"):
            register(catalog)
        catalog["claims"]["vision"]["probability_basis"] = "Authored test assumption, not calibrated evidence."
        self.assertEqual(register(catalog)["claims"]["vision"]["probability"], .9)
        with self.assertRaisesRegex(BridgeError, "information set"):
            assess(catalogue(), [], as_of="2026-11-20T00:00:00Z")
        catalog = catalogue()
        catalog["outcomes"]["useful-work"]["requires"] = ["nonexistent"]
        with self.assertRaisesRegex(BridgeError, "registered IDs"):
            register(catalog)

    def test_malformed_types_and_duplicate_observations_fail_explicitly(self):
        for field in ("kind", "status"):
            row = observation("access")
            row[field] = []
            with self.subTest(field=field), self.assertRaises(BridgeError):
                assess(catalogue(), [row], as_of=AS_OF)
        row = observation("access")
        with self.assertRaisesRegex(BridgeError, "distinct"):
            assess(catalogue(), [row, row], as_of=AS_OF)


if __name__ == "__main__":
    unittest.main()
