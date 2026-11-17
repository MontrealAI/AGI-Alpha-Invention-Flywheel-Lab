import hashlib
import json
import unittest
from pathlib import Path

import pilot

HERE = Path(__file__).resolve().parent


class FreshPilot(unittest.TestCase):
    def setUp(self):
        self.raw = (HERE / "runs.csv").read_bytes()
        self.grader = hashlib.sha256(b"illustrative independent checker").hexdigest()
        self.plan = pilot.register(self.raw, ["fresh-1", "fresh-2"], self.grader,
                                   budget=2000000, width=2, min_percent=45)
        self.payload = pilot.canonical(self.plan)
        self.commitment = hashlib.sha256(self.payload).hexdigest()
        header = ",".join(pilot.FIELDS)
        rows = []
        for idx, task in enumerate(self.plan["tasks"]):
            for j, stack in enumerate(self.plan["required_stacks"]):
                rows.append(",".join([task, *stack.split("/"), str(int(idx == 0)), "17",
                                      self.grader, f"trial-{idx}-{j}"]))
        self.lines = [header, *rows]

    def apply(self, lines):
        return pilot.audit(self.payload, self.commitment, "\n".join(lines).encode())

    def test_registered_and_missing_observations(self):
        result = self.apply(self.lines)
        self.assertEqual((result["verdict"], result["tasks_with_reported_success"],
                          result["reported_tokens"]), ("criteria_met", 1, 68))
        self.assertEqual(self.apply(self.lines[:-1])["verdict"], "incomplete")
        expensive = [line.replace(",17,", ",9000000,") for line in self.lines]
        self.assertEqual(self.apply(expensive)["verdict"], "criteria_failed")

    def test_mutation_duplicate_and_grader_mismatch(self):
        altered = json.loads(self.payload)
        altered["parameters"]["budget"] *= 2
        with self.assertRaises(ValueError):
            pilot.audit(pilot.canonical(altered), self.commitment, b"")
        for lines in (self.lines + [self.lines[1]],
                      [line.replace(self.grader, "f"*64) for line in self.lines],
                      [line.replace("trial-1-0", "trial-0-0") for line in self.lines]):
            with self.assertRaises(ValueError):
                self.apply(lines)

    def test_fresh_ids_and_failed_historical_spec(self):
        for fresh, budget, width in ((["django__django-11039"], 2000000, 2),
                                    (["fresh-1"], 0, 1), (["x","x"], 2000000, 2)):
            if fresh[0].startswith("django"):
                fresh = [self.raw.decode().splitlines()[1].split(",")[0]]
            with self.assertRaises(ValueError):
                pilot.register(self.raw,fresh,self.grader,budget=budget,width=width,min_percent=45)

    def test_externally_committed_malformed_plans_and_changed_evidence(self):
        changes = [
            ("tasks", []), ("tasks", ["fresh-1", "fresh-1"]), ("required_stacks", []),
            ("required_stacks", ["glm/acr", "glm/acr"]), ("required_stacks", ["new/model"]),
            ("selection_data_sha256", "0" * 64), ("selector_sha256", "0" * 64),
            ("parameters", dict(self.plan["parameters"], min_percent=-1)),
            ("parameters", dict(self.plan["parameters"], width=True)), ("unexpected", True),
        ]
        for field, value in changes:
            body = pilot.canonical(dict(self.plan, **{field: value}))
            with self.subTest(field=field), self.assertRaises(ValueError):
                pilot.audit(body, hashlib.sha256(body).hexdigest(), b"")
        with self.assertRaises(ValueError):
            pilot.audit(self.payload, self.commitment, b"", data=self.raw.replace(b"87975", b"87976", 1))
