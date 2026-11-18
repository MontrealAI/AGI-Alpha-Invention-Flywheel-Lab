import unittest

from discovery_field import protocol
from discovery_field.decision_study import private_sources as private
from ignition import research


def decide(number, source_index, *, edit_source=None, bind=True):
    doc = private.export(number)
    inputs = doc["sources"]
    if edit_source:
        inputs[source_index] = edit_source(inputs[source_index])
    def respond(stage, payload):
        if stage == "discover":
            signal = payload["signals"][source_index]
            premise = signal.get("observed_premise")
            row = {key: "Finite source comparison" for key in research.CANDIDATE_FIELDS}
            row.update(kind="existing", sources=[signal["id"]], evidence=[premise] if bind and premise else [],
                       change=protocol.statement(premise) if premise else "Comparison unavailable")
            return {"candidates": [row], "favourite": "C1"}
        return {"challenger": None, "objections": [], "decision": "incumbent", "selected": "C1",
                "fit": [], "reason": "Check a conventional alternative on the declared scope."}
    return research.investigate(doc["mission"], inputs, respond, as_of=private.OBSERVED_BY)


class PrivateResearchTest(unittest.TestCase):
    def test_exact_decision_affirms_correct_source_only(self):
        for case, selected, verdict in [(1, 1, "incumbent"), (3, 0, "incumbent"), (1, 0, "defer"),
                                        (3, 1, "defer"), (2, 0, "defer"), (4, 0, "defer")]:
            with self.subTest(case=case, selected=selected):
                receipt = decide(case, selected)
                self.assertEqual(receipt["decision"], verdict)
                if verdict == "incumbent":
                    self.assertEqual(receipt["selected"]["evidence_level"], "checked material premise")

    def test_changed_or_withdrawn_source_decorations_do_not_pass(self):
        mutations = [
            lambda row: dict(row, status="withdrawn"),
            lambda row: dict(row, source_response_sha256="a" * 64),
            lambda row: dict(row, text="The article reports something quite unrelated.",
                             sha256=protocol.digest(b"The article reports something quite unrelated.")),
        ]
        for mutate in mutations:
            for bind in (True, False):
                self.assertEqual(decide(1, 1, edit_source=mutate, bind=bind)["decision"], "defer")
        self.assertEqual(decide(1, 1, bind=False)["decision"], "defer")

    def test_arbitrary_sources_and_other_missions_keep_ordinary_behavior(self):
        row = private.export(1)["sources"][1]
        self.assertIsNone(protocol.observe(dict(row, role="ordinary import")))
        self.assertIsNone(protocol.record_key(row["url"]))
        self.assertFalse(private.supports_decision(row, "Explore another outcome"))


if __name__ == "__main__":
    unittest.main()
