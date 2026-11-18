import copy
import json
from pathlib import Path
import tempfile
import unittest

from discovery_field.decision_study import evaluate as study


class SourceDecisions(unittest.TestCase):
    def test_both_held_relations_and_both_withdrawals(self):
        for case in range(1, 5):
            with self.subTest(case=case):
                lookup = study.conventional(case)
                self.assertTrue(study.assess(case, lookup)["evidence_decision_accepted"])
                self.assertFalse(study.assess(case, lookup)["design_fields_present"])

    def test_real_and_topical_citation_to_wrong_comparison_is_rejected(self):
        for case, other in [(1, "A"), (3, "D")]:
            wrong = dict(study.conventional(case), source=other, quote=study.sources()[other]["excerpt"])
            report = study.assess(case, wrong)
            self.assertEqual(report["passage"], "verbatim")
            self.assertEqual(report["relation"], "different_comparison")
            self.assertFalse(report["evidence_decision_accepted"])

    def test_source_withdrawal_invalidates_existing_research_brief(self):
        for case in [1, 3]:
            answer = dict(study.conventional(case), claim="under review", uncertainty="still unknown",
                          action="an independent public experiment", test="compare both methods")
            original = study.assess(case, answer)
            changed = study.assess(case, answer, withdraw={answer["source"]})
            self.assertTrue(original["evidence_decision_accepted"])
            self.assertFalse(changed["evidence_decision_accepted"])
            self.assertTrue(changed["design_fields_present"])

    def test_forged_truncated_and_missing_support(self):
        source = study.conventional(1)
        for quote in ["outperforms all physics solvers", "a sufficiently parallelized CPU solver",
                      "", None]:
            self.assertFalse(study.assess(1, dict(source, quote=quote))["evidence_decision_accepted"])
        self.assertFalse(study.assess(4, {"decision": "unresolved"})["evidence_decision_accepted"])
        self.assertFalse(study.assess(1, study.conventional(4))["evidence_decision_accepted"])

    def test_design_prose_is_not_automatically_certified(self):
        bad = dict(study.conventional(3), claim="All future facilities will save money",
                   uncertainty="none", action="adopt immediately", test="a field exists")
        result = study.assess(3, bad)
        self.assertTrue(result["evidence_decision_accepted"])
        self.assertEqual(result["open_design_verdict"], "requires independent scientific review")
        self.assertTrue(result["design_fields_present"])

    def test_preparation_preserves_excerpts_without_withdrawn_sources(self):
        for n in range(1, 5):
            direct, prepared = study.packet(n), study.packet(n, True)
            self.assertEqual(direct["question"], prepared["question"])
            self.assertEqual(direct["sources"], [{k: v for k, v in x.items() if k != "curated_scope"}
                                                for x in prepared["sources"]])
        self.assertEqual([s["id"] for s in study.packet(4, True)["sources"]], ["A"])
        self.assertEqual([s["id"] for s in study.packet(2, True)["sources"]], ["D"])

    def test_recorded_answer_is_bound_to_original_prompt(self):
        answer = study.conventional(1)
        trial = dict(route="direct", context=1, packet_sha256=study.fingerprint(study.packet(1)),
                     answer=answer, answer_sha256=study.fingerprint(answer))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "result.json")
            path.write_text(json.dumps({"cases": [trial]}))
            self.assertTrue(study.replay(path)[0]["verdict"]["evidence_decision_accepted"])
            for key in ["answer_sha256", "packet_sha256"]:
                corrupted = copy.deepcopy(trial)
                corrupted[key] = "0" * 64
                path.write_text(json.dumps({"cases": [corrupted]}))
                with self.assertRaises(ValueError):
                    study.replay(path)

    def test_possibility_links_and_bilingual_coverage(self):
        entries = json.loads((study.HERE / "possibilities.json").read_text())["opportunities"]
        self.assertEqual(len({e["id"] for e in entries}), 5)
        records = study.sources()
        for item in entries:
            self.assertEqual(records[item["source_ids"][0]]["url"], item["url"])
            self.assertTrue(all(ref in records for ref in item["source_ids"]))
            for language in ["en", "fr"]:
                self.assertEqual(set(item[language]), {"title", "finding", "limit", "test"})
                self.assertTrue(all(item[language].values()))


if __name__ == "__main__":
    unittest.main()
