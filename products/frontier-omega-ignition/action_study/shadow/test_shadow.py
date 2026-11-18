"""Field accounting and the registered archival comparison, including adverse decisions."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from action_study.shadow import archive, fieldkit as kit


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "study"
        self.plan, self.cases = archive.plan_and_cases()
        self.truth = archive.sql_reference(self.cases)

    def start(self):
        kit.initialize(self.path, self.plan, self.cases)
        db = kit.connect(self.path)
        self.addCleanup(db.close)
        return db

    def packet(self, arm, case_index=0, answer=None):
        ticket = kit.load(self.path / "tasks" / (arm + ".json"))["tasks"][case_index]
        return {"protocol_sha256": kit.load(self.path / "commitment.json")["protocol_sha256"],
                "responses": [{"ticket": ticket["ticket"], "source_set_sha256": ticket["source_set_sha256"],
                               "answer": {"action": "keep_open"} if answer is None else answer}]}

    def test_conventional_integrated_and_independent_original_packets(self):
        actions = []
        for case in self.cases:
            reference = self.truth[case["case_id"]]
            for route in (archive.engine, archive.conventional):
                self.assertTrue(kit.correct(reference, route(case["band"], case["cutoff_utc"])))
            actions.append(reference["action"])
        self.assertEqual(actions, ["keep_open", "keep_open", "deliver", "keep_open", "deliver", "deliver"])
        g, r = (self.truth[t]["measurement"] for t in ("1029-g", "1029-r"))
        self.assertEqual((g["witness"], r["witness"]), ("3587249065815015015", "3587389715815015003"))

    def test_wrong_source_reference_baseline_sign_unit_and_interest(self):
        reference = self.truth["1028-g"]
        for key, value in (("witness", "3587389715815015003"), ("reference", "504120158"),
                           ("baseline", reference["measurement"]["trigger"]), ("packet_sha256", "1"*64),
                           ("delta_mag", 1.0697), ("sigma_mag", -0.1), ("unit", "flux"), ("direction", "reversed")):
            answer = copy.deepcopy(reference)
            answer["measurement"][key] = value
            self.assertFalse(kit.correct(reference, answer), key)
        self.assertFalse(kit.correct(self.truth["1027-g"], reference))
        self.assertIsNone(kit.correct({"action": "unsettled"}, reference))
        self.assertFalse(kit.correct(reference, {"action": "deliver"}))

    def test_key_precedes_answers_changed_sources_tickets_and_retries(self):
        db = self.start()
        batch = self.packet("B")
        with self.assertRaisesRegex(ValueError, "Lock the independent key"):
            kit.submit(db, batch)
        kit.save_key(db, self.truth)
        for key, value in (("source_set_sha256", "2" * 64), ("ticket", "absent")):
            bad = copy.deepcopy(batch)
            bad["responses"][0][key] = value
            with self.assertRaises(ValueError):
                kit.submit(db, bad)
        bad = copy.deepcopy(batch)
        bad["responses"] *= 2
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            kit.submit(db, bad)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM tasks WHERE answer IS NOT NULL").fetchone()[0], 0)
        kit.submit(db, batch)
        kit.submit(db, batch)
        bad = copy.deepcopy(batch)
        bad["responses"][0]["answer"] = {"action": "deliver"}
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            kit.submit(db, bad)
        with self.assertRaisesRegex(ValueError, "changed"):
            kit.save_key(db, {**self.truth, "1027-g": self.truth["1029-g"]})
        with self.assertRaisesRegex(ValueError, "Closed"):
            kit.submit(db, dict(batch, protocol_sha256="0"*64))

    def test_blinding_strips_identity_and_unused_fields(self):
        db = self.start()
        kit.save_key(db, self.truth)
        measure = dict(self.truth["1029-r"]["measurement"], operator="LEAK", annotation="LEAK")
        answer = {"action": "deliver", "private": "LEAK", "measurement": measure}
        packet = self.packet("D", 5, answer)
        kit.submit(db, packet)
        hidden = kit.blind(db)
        self.assertNotIn("LEAK", json.dumps(hidden))
        self.assertNotIn(packet["responses"][0]["ticket"], json.dumps(hidden))
        self.assertEqual([r["decision"]["measurement"]["witness"] for r in hidden["records"]], [measure["witness"]])
        with self.assertRaisesRegex(ValueError, "Closed"):
            kit.submit(db, self.packet("B"))
        report = kit.summarize(db)
        self.assertEqual(report["arms"]["D"]["submitted"], 1)
        self.assertEqual(report["arms"]["D"]["accepted"], 1)
        self.assertEqual(report["arms"]["D"]["missing_submissions"], 5)
        self.assertIsNone(report["arms"]["D"]["accepted_cases_unresolved_by_actual_incumbent"])
        self.assertIsNone(report["arms"]["D"]["accepted_with_observed_beneficiary_use"])

    def test_field_requires_authority_assignment_and_source_identity(self):
        self.plan["mode"] = "field"
        with self.assertRaisesRegex(ValueError, "authority"):
            self.start()
        self.field_setup()
        self.plan["operator_assignments"]["D"] = "operatorA"
        with self.assertRaisesRegex(ValueError, "multiple arms"):
            self.start()
        self.plan["operator_assignments"]["D"] = None
        self.cases[0]["source_manifest"] = {"other": "f"*64}
        with self.assertRaisesRegex(ValueError, "exact authorized source"):
            self.start()

    def field_setup(self):
        self.plan.update(mode="field", authority_receipt="UNIT-TEST-AUTHORITY", consent_receipt="UNIT-TEST-CONSENT",
                         operator_assignments={"A": "operatorA", "B": None, "C": None, "D": None, "E": None},
                         reviewers=["reviewer1", "reviewer2", "reviewer3"])
        now = datetime.now(timezone.utc)
        self.cases = [dict(self.cases[0], cutoff_utc=now.isoformat(), decision_due_utc=(now+timedelta(hours=1)).isoformat(),
                           source_manifest={"original": "e"*64}, source_set_sha256=kit.digest({"original": "e"*64}),
                           available_utc=(now-timedelta(hours=1)).isoformat(), availability_proof_sha256="b"*64)]
        self.truth = {self.cases[0]["case_id"]: {"action": "keep_open", "reference_sha256": "c"*64}}

    def test_real_observed_use_requires_independent_agreement_and_cost_basis(self):
        self.field_setup()
        db = self.start()
        kit.save_key(db, self.truth)
        response = self.packet("A")
        with self.assertRaisesRegex(ValueError, "field operator"):
            kit.submit(db, dict(response, operator="wrong"))
        kit.submit(db, dict(response, operator="operatorA"))
        b = kit.blind(db)
        with self.assertRaisesRegex(ValueError, "Lock reviews"):
            kit.summarize(db)
        code = b["records"][0]["code"]
        now = datetime.now(timezone.utc).isoformat()
        score = {"use": "observed_use", "beneficiary_receipt_sha256": "a"*64, "accepted_decision_utc": now,
                 "acceptance_receipt_sha256": "d"*64}
        grade = {"protocol_sha256": b["protocol_sha256"], "key_sha256": b["key_sha256"], "reviewer_independent": True,
                 "scores": {code: score}}
        with self.assertRaisesRegex(ValueError, "registered reviewer"):
            kit.review(db, dict(grade, reviewer="operatorA"))
        for label in ("reviewer1", "reviewer2"):
            kit.review(db, dict(grade, reviewer=label))
        kit.close_reviews(db, "unit test complete")
        with self.assertRaisesRegex(ValueError, "Closed"):
            kit.review(db, dict(grade, reviewer="reviewer3"))
        price = {"currency": self.plan["currency"], "horizon": self.plan["cost_horizon"],
                 "costs": {k: "1.00" for k in kit.CATEGORIES}, "measures": {"operator_seconds": 90}}
        with self.assertRaisesRegex(ValueError, "evidence"):
            kit.summarize(db, {"A": price})
        price["basis"] = {k: {"kind": "estimate", "source": "unit-test example"} for k in kit.CATEGORIES}
        a = kit.summarize(db, {"A": price})["arms"]["A"]
        self.assertEqual(a["accepted_with_observed_beneficiary_use"], 1)
        self.assertGreaterEqual(a["availability_to_accepted_decision_seconds"][0], 3600)
        self.assertEqual(a["costs"]["complete_cost_kind"], "includes_estimates")
        self.assertEqual(a["costs"]["cost_per_accepted_useful_decision"], "8.00")
        self.assertEqual(a["costs"]["accepted_useful_decisions_per_operator_hour"], 40)
        self.assertIsNone(kit.summarize(db)["arms"]["E"]["costs"]["complete_cost"])

    def test_late_qualified_delivery_and_unresolved_receipt(self):
        self.field_setup()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        self.cases[0].update(cutoff_utc=cutoff, decision_due_utc=cutoff, available_utc=None)
        db = self.start()
        kit.save_key(db, self.truth)
        kit.submit(db, dict(self.packet("A"), operator="operatorA"))
        kit.blind(db)
        kit.close_reviews(db, "closed with two missing field reviews")
        a = kit.summarize(db)["arms"]["A"]
        self.assertEqual((a["late_submissions"], a["scientifically_correct"], a["accepted"]), (1, 1, 0))
        self.assertIsNone(a["accepted_with_observed_beneficiary_use"])
        self.assertIsNone(a["availability_to_accepted_decision_seconds"])

    def test_source_hash_confines_the_scope_and_detects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as ext:
            (self.root / "data").write_bytes(b"first")
            prior = kit.bind_sources(self.root, ["data"])
            (self.root / "data").write_bytes(b"changed")
            self.assertNotEqual(prior, kit.bind_sources(self.root, ["data"]))
            (Path(ext) / "foreign").write_bytes(b"outside")
            (self.root / "linked").symlink_to(Path(ext) / "foreign")
            for name in ("../private", "/absolute", "linked"):
                with self.assertRaises(ValueError):
                    kit.bind_sources(self.root, [name])


if __name__ == "__main__":
    unittest.main()
