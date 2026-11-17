"""Recipient acceptance and mutation checks independent of published headline values."""
import csv
import hashlib
import io
import unittest
from pathlib import Path

from conventional import enumerate_sql
from pairing_lab import analyze, read_grid, split_tasks

HERE = Path(__file__).resolve().parent
HEADER = "task,model,harness,solved,tokens\n"


def rows_csv(rows):
    return (HEADER + "".join(",".join(map(str, r)) + "\n" for r in rows)).encode()


class PairingChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (HERE / "runs.csv").read_bytes()

    def test_counts_and_public_identities(self):
        grid, stacks = read_grid(self.raw)
        self.assertEqual((len(grid), len(stacks)), (100, 18))
        result = analyze(self.raw, witnesses=False)
        self.assertEqual(result["data_sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(result["program_sha256"], hashlib.sha256((HERE / "pairing_lab.py").read_bytes()).hexdigest())

    def test_malformed_and_unpaired_data(self):
        good = [["o__r-1","m","a",1,10],["o__r-2","m","a",1,11]]
        for rows in (good + [good[1]], good + [["o__r-2","m","b",1,11]],
                     [["x","m","a",2,10]], [["x","m","a",0,-1]], [["x","m","a",0,"3.1"]]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                read_grid(rows_csv(rows))
        for opts in ({"budget": -1}, {"width":3}, {"min_percent":101},
                     {"model":"nonexistent"}, {"repository":"foo__bar"}):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                analyze(self.raw, **opts)

    def test_leakage_and_invalidation(self):
        pre = analyze(self.raw, witnesses=False)
        grid, _ = read_grid(self.raw)
        _, audit = split_tasks(grid)
        rows = list(csv.reader(io.StringIO(self.raw.decode())))[1:]
        for r in rows:
            if r[0] in audit:
                r[3] = "0"
        replay = analyze(rows_csv(rows), witnesses=False)
        self.assertEqual(pre["selected"], replay["selected"])
        self.assertEqual(pre["calibration"], replay["calibration"])
        self.assertFalse(replay["qualifies"])
        self.assertEqual(replay["audit"]["solved"], 0)
        self.assertNotEqual(replay["data_sha256"], pre["data_sha256"])
        self.assertIsNone(replay["public_source"])

    def test_all_attempts_count_and_double_success_is_one(self):
        report = analyze(self.raw)
        witnesses = report["audit"]["witnesses"]
        for item in witnesses:
            attempts = item["attempts"]
            self.assertEqual(item["tokens"], sum(a["tokens"] for a in attempts))
            self.assertEqual(item["solved"], max(a["solved"] for a in attempts))
        self.assertEqual(sum(w["tokens"] for w in witnesses), report["audit"]["tokens"])
        self.assertEqual(sum(w["solved"] for w in witnesses), report["audit"]["solved"])
        self.assertTrue(any(all(a["solved"] for a in w["attempts"]) for w in witnesses))

    def test_defective_success_only_meter_reverses_decision(self):
        # Rank IDs using the registered split. Each half has a failed, expensive A attempt.
        ids = [f"o__r-{i}" for i in range(10)]
        train, audit = split_tasks(dict.fromkeys(ids))
        fails = {train[-1], audit[-1]}
        rows, bad = [], []
        for task in ids:
            succeeds = task not in fails
            a = [task, "m", "a", int(succeeds), 1 if succeeds else 1000]
            b = [task, "m", "b", int(task in fails), 1]
            rows.extend([a, b])
            bad.extend([a if succeeds else [*a[:-1], 0], b])
        self.assertEqual(analyze(rows_csv(bad), budget=10, width=1)["selected"], ["m/a"])
        correct = analyze(rows_csv(rows), budget=10, width=1)
        self.assertEqual(correct["selected"], ["m/b"])
        self.assertEqual(enumerate_sql(rows_csv(rows), 10, 1)[0], ("m/b",))
        self.assertFalse(correct["qualifies"])

    def test_zero_budget_defers_and_ties_are_stable(self):
        report = analyze(self.raw, budget=0)
        self.assertEqual(report["verdict"], "no_feasible_calibration_policy")
        self.assertFalse(report["qualifies"])
        self.assertIsNone(report["audit"])
        rows = [[f"task-{t}", "m", h, 1, 0] for t in range(4) for h in ("z", "a")]
        orig = analyze(rows_csv(rows), budget=0)
        rev = analyze(rows_csv(rows[::-1]), budget=0)
        self.assertEqual(orig["selected"], ["m/a"])
        self.assertEqual(orig["selected"], rev["selected"])


if __name__ == "__main__":
    unittest.main()
