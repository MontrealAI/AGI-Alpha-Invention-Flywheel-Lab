"""FRONTIER Ω source-matched, offline adversarial tests. No money/model/network."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from frontier_omega.core import (
    Reservoir, COSTS, FRONTIER_SCHEMA, TRIAL_SCHEMA, load_file, parse, sha
)

SEED = Path(__file__).resolve().parents[1] / "examples/frontier-omega/public-opportunities-20261116.json"


def fixture_event(ident="capability-old", on="2026-10-12"):
    return {"schema": FRONTIER_SCHEMA, "id": ident, "title": "Authored baseline snapshot",
            "observed_on": on, "description": "A frozen local fixture for modelled comparisons only.",
            "tags": ["formal-verification"], "source_urls": ["https://example.org/fixture"],
            "availability": "REPORTED"}


def trial(ident, frontier, *, costs=10_000_000, independent=True, passed=True,
          terms="a", protocol="b", scope="AUTHORED_SCENARIO"):
    buckets = {k: 0 for k in COSTS}
    buckets["construction"] = costs
    return {"schema": TRIAL_SCHEMA, "id": ident,
            "problem_id": "compiled-crypto-assurance", "frontier_id": frontier,
            "run_on": "2026-11-11", "terms_sha256": terms * 64,
            "acceptance_sha256": "c" * 64, "protocol_sha256": protocol * 64,
            "evidence_sha256": sha({"fixture": ident}), "scope": scope,
            "passed": passed, "independent_check": independent,
            "price_microUSD": 12_000_000, "acceptance_probability_bps": 9000,
            "costs_microUSD": buckets, "expected_loss_microUSD": 0,
            "alternative": {"name": "Competent specialist", "qualified": True,
                            "complete_cost_microUSD": 15_000_000}}


class FrontierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = Reservoir(Path(self.temp.name) / "private")

    def seed(self):
        return self.engine.seed(load_file(SEED))

    def test_inventory_contains_six_actual_problem_dossiers(self):
        outcome = self.seed()
        self.assertEqual(outcome["problems_added"], 6)
        self.assertEqual(outcome["frontiers_added"], 5)
        self.assertGreaterEqual(outcome["retests_queued"], 6)
        report = self.engine.report()
        self.assertEqual(report["counts"]["problems"], 6)
        self.assertTrue(all(not row["economic_value_verified"] for row in report["inventory"]))
        self.assertEqual(report["claims"]["financial_authority"], "NONE")
        self.assertEqual(self.engine.audit()["audit"], "PASS")

    def test_reimport_idempotent_and_not_a_duplicate_trigger(self):
        first = self.seed()
        second = self.seed()
        self.assertEqual(second, {"problems_added": 0, "frontiers_added": 0, "retests_queued": 0})
        self.assertEqual(len(self.engine.rows("triggers")), first["retests_queued"])

    def test_all_public_dossiers_are_hypotheses_not_buyers(self):
        self.seed()
        for p in self.engine.rows("problems"):
            self.assertEqual(p["demand"]["status"], "PUBLIC_SIGNAL")
            self.assertTrue(any(a["name"] == "No purchase" for a in p["alternatives"]))
            self.assertGreaterEqual(len(p["alternatives"]), 3)
            self.assertTrue(p["source_urls"])
            self.assertGreaterEqual(len(p["demand"]["basis"]), 30)
            self.assertFalse(p.get("purchase_authorized", False))

    def test_tag_trigger_is_immutable_and_read_only(self):
        self.seed()
        for row in self.engine.rows("triggers"):
            self.assertEqual(row["decision"], "INVESTIGATE_ONLY")
            self.assertIs(row["execution_authorized"], False)
            self.assertIs(row["customer_payment_established"], False)

    def test_unmatched_capability_does_not_trigger(self):
        self.seed()
        base = len(self.engine.rows("triggers"))
        e = fixture_event("unrelated-test")
        e["tags"] = ["unrelated-capability"]
        self.assertEqual(self.engine.add(e)["retests_queued"], 0)
        self.assertEqual(len(self.engine.rows("triggers")), base)

    def test_problem_import_replays_prior_capability_observations(self):
        data = load_file(SEED)
        e = data["frontiers"][0]
        self.engine.add(e)
        p = next(row for row in data["problems"] if "computer-use" in row["tags"])
        receipt = self.engine.add(p)
        self.assertEqual(receipt["retests_queued"], 1)

    def test_reused_id_with_modified_content_refused(self):
        self.seed()
        item = deepcopy(self.engine.rows("problems")[0])
        item["title"] += " revised"
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_RECORD_ID"):
            self.engine.add(item)

    def test_duplicate_json_keys_or_nonfinite_data_refused(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.assertRaises(ValueError):
                parse(raw)

    def test_buyer_promise_not_inferred_from_source(self):
        data = load_file(SEED)
        problem = deepcopy(data["problems"][0])
        problem["demand"]["status"] = "SIGNED_COMMITMENT"
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_DEMAND"):
            self.engine.add(problem)

    def test_public_demand_cannot_impersonate_accepted_buyer_terms(self):
        p = load_file(SEED)["problems"][0]
        p["demand"]["ceiling_microUSD"] = 50_000_000
        with self.assertRaisesRegex(ValueError, "PUBLIC_SIGNAL_CANNOT"):
            self.engine.add(p)
        p = load_file(SEED)["problems"][0]
        p["demand"]["consent_verification"] = "VERIFIED"
        with self.assertRaisesRegex(ValueError, "CANNOT_BE_ASSERTED"):
            self.engine.add(p)

    def test_reported_buyer_price_ceiling_blocks_a_false_crossing(self):
        p = load_file(SEED)["problems"][0]
        self.assertEqual(p["id"], "compiled-crypto-assurance")
        p["demand"].update({"status": "CUSTOMER_REPORTED_UNVERIFIED",
                             "ceiling_microUSD": 5_000_000,
                             "terms_sha256": "a" * 64,
                             "deadline": "2026-12-31"})
        self.engine.add(p)
        self.engine.add(fixture_event("capability-old", "2026-10-12"))
        self.engine.add(fixture_event("capability-new", "2026-11-10"))
        self.engine.add(trial("old-trial", "capability-old", costs=14_000_000))
        self.engine.add(trial("new-trial", "capability-new", costs=3_000_000))
        report = self.engine.compare("compiled-crypto-assurance", "capability-old", "capability-new")
        self.assertEqual(report["verdict"], "REPORTED_BUYER_CEILING_EXCEEDED")
        self.assertFalse(report["workorder_authorized"])
        self.assertFalse(report["reported_crossing"])

    def test_no_purchase_is_required_strong_comparator(self):
        data = load_file(SEED)
        p = deepcopy(data["problems"][0])
        p["alternatives"] = p["alternatives"][:-1]
        with self.assertRaisesRegex(ValueError, "NO_PURCHASE"):
            self.engine.add(p)

    def test_source_urls_require_ordinary_public_https(self):
        data = load_file(SEED)
        p = deepcopy(data["problems"][0])
        for bad in ("http://example.org", "https://user:secret@example.org", "file:///etc/passwd"):
            p["source_urls"] = [bad]
            with self.assertRaises(ValueError):
                self.engine.add(p)

    def comparison_setup(self):
        self.seed()
        self.engine.add(fixture_event("capability-old", "2026-10-12"))
        return self.engine.rows("frontiers")

    def test_positive_reported_crossing_is_not_external_proof_or_spending_authority(self):
        self.comparison_setup()
        self.engine.add(trial("old-trial", "capability-old", costs=14_000_000))
        self.engine.add(trial("new-trial", "alphaproof-code-20261110", costs=3_000_000))
        result = self.engine.compare("compiled-crypto-assurance", "capability-old", "alphaproof-code-20261110")
        self.assertEqual(result["verdict"], "REPORTED_CROSSING_UNVERIFIED")
        self.assertTrue(result["reported_crossing"])
        self.assertFalse(result["economic_crossing_established"])
        self.assertFalse(result["workorder_authorized"])
        self.assertTrue(result["current_strong_alternative_qualified"])

    def test_comparison_requires_same_frozen_contract_acceptance_and_protocol(self):
        self.comparison_setup()
        self.engine.add(trial("old-trial", "capability-old", costs=14_000_000))
        self.engine.add(trial("new-trial", "alphaproof-code-20261110", costs=3_000_000, terms="d"))
        result = self.engine.compare("compiled-crypto-assurance", "capability-old", "alphaproof-code-20261110")
        self.assertEqual(result["verdict"], "MATCHED_HISTORICAL_AND_NEW_TEST_REQUIRED")

    def test_new_evidence_can_be_positive_but_failed_checker_cannot_cross(self):
        self.comparison_setup()
        self.engine.add(trial("old-trial", "capability-old", costs=14_000_000))
        self.engine.add(trial("new-trial", "alphaproof-code-20261110", costs=3_000_000, passed=False))
        result = self.engine.compare("compiled-crypto-assurance", "capability-old", "alphaproof-code-20261110")
        self.assertFalse(result["reported_crossing"])

    def test_missing_reported_independent_check_cannot_cross(self):
        self.comparison_setup()
        self.engine.add(trial("old-trial", "capability-old", costs=14_000_000))
        self.engine.add(trial("new-trial", "alphaproof-code-20261110", costs=3_000_000, independent=False))
        self.assertFalse(self.engine.compare(
            "compiled-crypto-assurance", "capability-old", "alphaproof-code-20261110")["reported_crossing"])

    def test_matching_prior_and_new_positive_does_not_create_false_crossing(self):
        self.comparison_setup()
        self.engine.add(trial("old-trial", "capability-old", costs=3_000_000))
        self.engine.add(trial("new-trial", "alphaproof-code-20261110", costs=3_000_000))
        result = self.engine.compare("compiled-crypto-assurance", "capability-old", "alphaproof-code-20261110")
        self.assertEqual(result["verdict"], "NO_POSITIVE_MATCHED_CROSSING")

    def test_old_date_cannot_be_after_new_date(self):
        self.comparison_setup()
        with self.assertRaisesRegex(ValueError, "HISTORICAL_FRONTIER_ORDER"):
            self.engine.compare("compiled-crypto-assurance", "alphaproof-code-20261110", "capability-old")

    def test_broken_input_measurements_cannot_be_imported(self):
        self.comparison_setup()
        candidate = trial("bad-trial", "capability-old")
        candidate["costs_microUSD"]["construction"] = -1
        with self.assertRaisesRegex(ValueError, "NONNEGATIVE"):
            self.engine.add(candidate)
        candidate = trial("bad-trial", "capability-old")
        candidate["acceptance_probability_bps"] = 10001
        with self.assertRaisesRegex(ValueError, "PROBABILITY"):
            self.engine.add(candidate)

    def test_two_arms_on_same_frozen_protocol_cannot_replace_selected_result(self):
        self.comparison_setup()
        self.engine.add(trial("first-trial", "capability-old"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.engine.add(trial("second-trial", "capability-old", costs=1))

    def test_local_hash_audit_detects_tampering(self):
        self.seed()
        with self.engine.tx() as c:
            c.execute("UPDATE problems SET body='{}' WHERE id='compiled-crypto-assurance'")
        with self.assertRaisesRegex(ValueError, "INTEGRITY"):
            self.engine.audit()

    def test_retest_trigger_source_binding_detects_tampering(self):
        self.seed()
        with self.engine.tx() as c:
            c.execute("UPDATE triggers SET frontier_hash=? WHERE rowid=1", ("0" * 64,))
        with self.assertRaisesRegex(ValueError, "SOURCE_BINDING"):
            self.engine.audit()

    def test_private_browser_dashboard_is_accessible_and_source_grounded(self):
        from frontier_omega.dashboard import write_dashboard
        self.seed()
        result = write_dashboard(self.engine)
        view = Path(result["private_dashboard"])
        text = view.read_text()
        self.assertIn("FRONTIER", text)
        self.assertIn("Opportunity inventory", text)
        self.assertIn("compiled", text.lower())
        self.assertIn("PUBLIC SIGNAL", text)
        self.assertIn("No dossiers match", text)
        self.assertIn('rel="noopener noreferrer"', text)
        self.assertEqual(result["external_assets"], 0)
        self.assertEqual(view.stat().st_mode & 0o077, 0)
        self.assertGreater(result["bytes"], 2000)

    def test_dashboard_escapes_untrusted_dossier_text(self):
        from frontier_omega.dashboard import dashboard
        d = load_file(SEED)["problems"][0]
        d["title"] = '<img src=x onerror=alert(1)>'
        self.engine.add(d)
        html_text = dashboard(self.engine.report())
        self.assertIn("&lt;img", html_text)
        self.assertNotIn("<img src=x", html_text)

    def test_dashboard_cannot_write_outside_private_reservoir(self):
        from frontier_omega.dashboard import write_dashboard
        with self.assertRaisesRegex(ValueError, "PRIVATE_OUTPUT_FILENAME_REQUIRED"):
            write_dashboard(self.engine, "../PUBLIC.html")

    def test_private_inbox_watch_ingests_records_without_remote_actions(self):
        problem = load_file(SEED)["problems"][0]
        inbox = self.engine.root / "inbox"
        (inbox / "new.json").write_text(json.dumps(problem))
        output = self.engine.watch(interval=0.05, cycles=1)
        self.assertEqual(output["status"]["problems"], 1)
        self.assertEqual(output["receipts"][0]["kind"], "problems")
        self.assertEqual(self.engine.rows("problems")[0]["id"], problem["id"])
        self.assertFalse((inbox / "new.json").exists())
        self.assertEqual(len(list((self.engine.root / "processed").glob("*.json"))), 1)

    def test_inbox_rejects_invalid_and_keeps_evidence_local(self):
        bad = self.engine.root / "inbox" / "bad.json"
        bad.write_text('{"schema":"no"}')
        output = self.engine.ingest_inbox()
        self.assertEqual(output[0]["rejected"], "ValueError")
        self.assertEqual(self.engine.rows("problems"), [])
        self.assertFalse(bad.exists())
        self.assertEqual(len(list((self.engine.root / "rejected").glob("*.json"))), 1)

    def test_separate_workers_refuse_to_take_the_same_lock(self):
        with self.engine.lock():
            with self.assertRaisesRegex(RuntimeError, "ANOTHER_FRONTIER_WORKER"):
                self.engine.watch(interval=0.05, cycles=1)

    def test_symlink_input_refused(self):
        data = load_file(SEED)["problems"][0]
        real = self.engine.root / "input.json"
        real.write_text(json.dumps(data))
        link = self.engine.root / "alias.json"
        link.symlink_to(real)
        with self.assertRaisesRegex(ValueError, "SYMLINK_PATH"):
            load_file(link)


if __name__ == "__main__":
    unittest.main()
