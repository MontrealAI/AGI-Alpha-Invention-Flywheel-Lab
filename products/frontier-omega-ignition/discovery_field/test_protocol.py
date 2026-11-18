import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ignition import model_schema, research
from discovery_field import open_trial, protocol, source_check, study


ROOT = Path(__file__).resolve().parent
PUBLIC = protocol.inputs()
WHEN = "2026-11-19T00:00:00+00:00"


def investigate(source, purpose, change=None, edit=None, issue_denial=False, additional=()):
    def respond(stage, payload):
        if stage == "discover":
            signal = payload["signals"][0]
            premise = dict(signal.get("observed_premise", {}))
            if edit:
                premise.update(edit)
            row = {k: "Controlled test field" for k in research.CANDIDATE_FIELDS}
            row.update(kind="existing", sources=["S1"], evidence=[premise] if premise else [], route="compare native alternatives",
                       change=signal.get("verified_statement", "reported source statement") if change is None else change)
            if issue_denial:
                row["obstruction"] = "Issue-level measurements are unavailable"
            return {"candidates": [row], "favourite": "C1"}
        return {"challenger": None, "objections": [], "decision": "incumbent",
                "selected": "C1", "fit": [], "reason": "Compare this direct route on its stated scope."}
    return research.investigate({"purpose": purpose, "requirements": []}, [source, *additional], respond, as_of=WHEN)


class SourceDiscoveryTests(unittest.TestCase):
    def test_public_responses_are_distinct_and_each_fragment_decodes(self):
        catalog = json.loads((ROOT / "catalog.json").read_text())
        self.assertEqual(len({s["source_response_sha256"] for s in catalog["sources"]}), 5)
        for row, card in zip(PUBLIC, catalog["opportunities"]):
            self.assertEqual(protocol.record_key(row["url"]), card["source"])
            with self.subTest(card=card["id"]):
                self.assertTrue(protocol.observe(row))
        with tempfile.TemporaryDirectory() as d:
            wrong = Path(d) / "page.html"
            wrong.write_text("Site unavailable")
            self.assertFalse(source_check.check("nomai", wrong)["registered_response_accepted"])

    def test_independently_observed_premise_survives_private_runtime_and_wire(self):
        result = investigate(PUBLIC[0], "Test a science team’s transient observing queue.")
        self.assertEqual(result["decision"], "incumbent")
        selected = result["selected"]
        self.assertEqual(selected["usable_sources"], ["S1"])
        self.assertEqual(selected["evidence_level"], "checked material premise")
        self.assertEqual(selected["evidence_review"]["checks"][0]["status"], "supported")
        observed = protocol.observe(dict(PUBLIC[0], id="S1"))
        schema = model_schema.candidate({"signals": [{"id": "S1", "observed_premise": observed}]})
        self.assertIn("evidence", schema["properties"])
        self.assertNotIn("evidence", schema["required"])

    def test_claims_refuse_unknown_values_citation_spoof_and_reversed_polarity(self):
        for mutation in ({"scope": "all_alerts"}, {"polarity": "denied"}, {"value": "24/24"},
                         {"source": "S9"}, {"metric": "mean_reward"}):
            with self.subTest(mutation=mutation):
                self.assertEqual(investigate(PUBLIC[0], "transient queue", edit=mutation)["decision"], "defer")
        for text in ("Operational yield is 22/24.", "recovered_fraction = 22/24 (active_labeled_upper_limit)\nField proof."):
            self.assertEqual(investigate(PUBLIC[0], "transient queue", change=text)["decision"], "defer")
        self.assertEqual(investigate(PUBLIC[0], "Compare editable CAD workflows")["decision"], "defer")

    def test_modified_bytes_with_old_identity_do_not_qualify(self):
        source = dict(PUBLIC[0], source_response_sha256="a"*64)
        self.assertEqual(investigate(source, "transient queue")["decision"], "defer")
        with self.assertRaises(ValueError):
            investigate(dict(PUBLIC[0], text=PUBLIC[0]["text"].replace("24", "25")), "transient queue")

    def test_issue_level_denial_is_adjudicated_against_actual_published_projection(self):
        raw = (ROOT.parent / "flagship/runs.csv").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), "c60d0b58ab109ba900e36465a0ffadaaeb4c8a2743abc744eb17f3f596842118")
        rows = list(csv.DictReader(raw.decode().splitlines()))
        self.assertEqual((len(rows), len({row["task"] for row in rows})), (1800, 100))
        self.assertTrue(all(row["solved"] in {"0", "1"} for row in rows))
        s = {"publisher": "Study authors", "title": "Pairing Matters", "url": protocol.PAIR_URL,
             "text": protocol.PAIR_TEXT, "retrieved_at": WHEN}
        self.assertEqual(investigate(s, "coding-agent issue outcomes")["decision"], "incumbent")
        denial = investigate(s, "coding-agent issue outcomes", issue_denial=True)
        self.assertEqual(denial["decision"], "defer")
        self.assertEqual(denial["selected"]["evidence_review"]["checks"][-1]["status"], "contradicted")

    def test_issue_denial_with_other_citation_is_also_detected(self):
        s = {"publisher": "Study authors", "title": "Pairing Matters", "url": protocol.PAIR_URL,
             "text": protocol.PAIR_TEXT, "retrieved_at": WHEN}
        outcome = investigate(PUBLIC[0], "Use coding agents to prepare a transient queue", issue_denial=True, additional=[s])
        self.assertEqual(outcome["decision"], "defer")
        self.assertIn("S2", outcome["selected"]["ineligible_sources"])

    def test_ids_from_a_live_feed_cannot_replace_a_checked_premise(self):
        source = {"publisher": "Public publisher", "title": "Release", "url": "https://example.org/release",
                  "text": "A product was released.", "retrieved_at": WHEN, "acquisition": "curated publisher feed"}
        outcome = investigate(source, "Select a specific operating route.")
        self.assertEqual(outcome["decision"], "defer")
        self.assertEqual(outcome["selected"]["evidence_level"], "reference identity only")

    def test_claim_withdrawal_and_unrelated_true_claim(self):
        original = json.loads((ROOT / "open-included.json").read_text())
        trial = open_trial.compare(original)
        self.assertTrue(all(row["binding"] == "supported" for row in trial["original"]["rows"]))
        self.assertTrue(all(st.count("no_eligible_source") == 1 for st in trial["withdrawal"].values()))
        swapped = trial["true_but_unrelated_first_case"]
        self.assertEqual((swapped["eligible_id"], swapped["binding"], swapped["is_material"]), (True, "supported", False))
        self.assertEqual(open_trial.score({"candidates": [None]*6})["format"], "failed")
        self.assertEqual(open_trial.score({"candidates": []})["returned"], 0)
        self.assertEqual(open_trial.score({"candidates": [{"source": None}]})["rows"][0]["binding"], "no_eligible_source")

    def test_scoped_exact_ratio_and_decimal_representations(self):
        data = study.available(study.read_packet())
        cad, sky = protocol.observe(data["B"]), protocol.observe(data["A"])
        for literal in ("0.6103", "61.03", "61.0300%", "6103/10000", "0.6103 fraction"):
            self.assertEqual(protocol.quantity(cad, {"value": literal}), "exact", literal)
        for literal in ("22/24", "11/12"):
            self.assertEqual(protocol.quantity(sky, {"value": literal}), "exact")
        for literal in ("0.9167", "0.917", "91.67%"):
            self.assertEqual(protocol.quantity(sky, {"value": literal}), "rounded", literal)
        for literal in ("0.9166", "0.87", "91.67", "0.9167%", "22/25", "1"):
            self.assertEqual(protocol.quantity(sky, {"value": literal}), "mismatch", literal)
        for claim in ({"value":"0.6103%"}, {"value":"61.03", "unit":"fraction"},
                      {"value":"0.6103","unit":"percent"}, {"value":"61.03%", "unit":"ratio"},
                      {"value":"0.6103","unit":"tokens/s"}, {"value":"0.6103","unit":"widgets"}):
            self.assertNotIn(protocol.quantity(cad, claim), ("exact", "rounded"), claim)
        self.assertEqual(protocol.quantity(cad, {"value":"0.6103", "unit":"fraction"}), "exact")
        self.assertEqual(protocol.quantity(cad, {"value":"61.03", "unit":"%"}), "exact")
        self.assertEqual(protocol.quantity(cad, {"value":"0.6103", "unit":"dimensionless"}), "exact")
        wrong_scope = dict(cad, value="0.6103", scope="field_acceptance")
        self.assertEqual(protocol.binding(wrong_scope, cad), "contradicted")

    def test_invalid_precision_bombs_and_repeated_evidence(self):
        signal = dict(PUBLIC[0], id="S1")
        fact = protocol.observe(signal)
        for literal in ("1"*100000, "1e10000000", "0/0", "NaN", {"unit":"fraction"}, 0.9167):
            self.assertEqual(protocol.quantity(fact, {"value":literal}), "invalid")
        candidate = {"sources":["S1"],"evidence":[fact, dict(fact)], "change":protocol.statement(fact)}
        reviewed = protocol.review(candidate, [signal], "transient queue", ["S1"])
        self.assertEqual((len(reviewed["checks"]), reviewed["supported_sources"]), (1, ["S1"]))
        candidate["evidence"].append(dict(fact, value="0.9166"))
        checked = protocol.review(candidate, [signal], "transient queue", ["S1"])["checks"]
        self.assertEqual([r["status"] for r in checked], ["supported","contradicted"])

    def test_rounding_never_launders_the_exact_decision_or_action(self):
        packet = study.read_packet()
        sky = study.bounded(packet, packet["tasks"][0])
        rounded = study.assess(packet, packet["tasks"][0], dict(sky, value="0.9167", test="22/24 twice: 22/24"))
        self.assertEqual((rounded["factual_status"], rounded["decision_eligible"]), ("rounded_consistent", False))
        cad = dict(study.bounded(packet, packet["tasks"][1]), value="0.6103")
        verdict = study.assess(packet, packet["tasks"][1], cad)
        self.assertTrue(verdict["decision_eligible"])
        self.assertIsNone(verdict["design_scientifically_accepted"])
        self.assertEqual(study.assess(packet, packet["tasks"][1], dict(cad, unit="percent"))["factual_status"], "contradicted")
        open_answer = {"candidates":[dict(cad, source="cadbench", unit="percent")]}
        self.assertEqual(open_trial.score(open_answer)["rows"][0]["binding"], "unsupported_value_or_scope")

    def test_retrieval_and_observational_claim_survive_but_do_not_approve_design(self):
        results = study.replay()["routes"]
        self.assertTrue(all(c["verdict"]["decision_eligible"] for c in results["included_direct"]["cases"]))
        self.assertTrue(all(c["verdict"]["decision_eligible"] for c in results["bounded_lookup"]["cases"]))
        self.assertFalse(any(c["verdict"]["design_fields_present"] for c in results["bounded_lookup"]["cases"]))
        self.assertFalse(any(c["verdict"]["decision_eligible"] for c in results["targeted_retrieval"]["cases"]))
        packet = study.read_packet()
        changed_task = {"question": "Unregistered assay"}
        self.assertIsNone(study.bounded(packet, changed_task))
        for task in packet["tasks"]:
            targeted = study.payload(packet, task, True)
            self.assertEqual(len(targeted["source_fragments"]), 1)
            self.assertNotIn("answer", targeted)
            self.assertNotIn("verified_statement", str(targeted))


if __name__ == "__main__":
    unittest.main()
