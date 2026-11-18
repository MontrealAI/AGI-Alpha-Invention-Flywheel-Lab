"""Controls beyond the frozen EP01 observation, including actual source drift and ties."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from reference import SOURCES, check_points, connect, selection


class SourceDecisionTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((HERE/"contracts.json").read_bytes())["interactive_gpt"]
        self.db = connect()
        self.addCleanup(self.db.close)

    def test_duplicate_optimal_points_must_both_be_delivered(self):
        optimum, = selection(self.contract,self.db)["selected"]
        row = dict(self.db.execute("SELECT * FROM evidence WHERE source=? AND run=?",
                                   (optimum["source"], optimum["run"])).fetchone())
        # Add an equivalent, named source witness to the in-memory control only.
        row["source"] = "synthetic-equivalent-point"
        names = tuple(row)
        self.db.execute(f"INSERT INTO evidence ({','.join(names)}) VALUES ({','.join('?' for _ in names)})",
                        tuple(row[n] for n in names))
        expected = selection(self.contract,self.db)
        self.assertEqual(len(expected["selected"]),2)
        check_points(expected, expected)
        missing = deepcopy(expected)
        missing["selected"].pop()
        with self.assertRaises(ValueError):
            check_points(expected,missing)

    def test_source_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "reports"
            shutil.copytree(SOURCES,source)
            csv_path = next(source.glob("*.csv"))
            csv_path.write_bytes(csv_path.read_bytes()+b"\n")
            with self.assertRaisesRegex(ValueError,"Published source changed"):
                connect(source)

    def test_decimal_boundary_and_unsupported_turn(self):
        d = {**self.contract,"min_concurrency":140,"max_ttft_p90_ms":"147.60"}
        self.assertEqual(selection(d,self.db)["decision"],"supported")
        d["max_ttft_p90_ms"]="147.59999999999999999999"
        self.assertEqual(selection(d,self.db)["decision"],"withheld")
        d = {**self.contract,"rate_metric":"agentic_e2e"}
        self.assertEqual(selection(d,self.db)["decision"],"withheld")


if __name__ == "__main__":
    unittest.main()
