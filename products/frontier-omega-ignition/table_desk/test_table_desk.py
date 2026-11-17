"""TD01 failure controls are independent of the published table's contents."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from table_desk import compare, execute, reference


class TableDeskTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.author = self.base / "authorized.html"
        self.author.write_text('<table><tr><th>Unit</th><th>Change</th></tr>'
                               '<tr><td>mg / L</td><td>−1.25</td></tr></table>', encoding="utf-8")
        self.spec = {"author_sha256": hashlib.sha256(self.author.read_bytes()).hexdigest(), "table_ordinal": 1}

    def test_exact_cells_and_adverse_controls(self):
        gold = reference(self.author, self.spec)
        self.assertTrue(compare([["Unit", "Change"], ["mg  / L", "−1.25"]], gold)["accepted"])
        proposals = [[["Unit", "Change"], ["mg / L", "−1.26"]],
                     [["Unit", "Change"], ["mg / L", "1.25"]],
                     [["Unit", "Change"], ["mg / L", "-1.25"]],
                     [["Unit", "Change"], ["mg / L"]],
                     [["Unit", "Change"], ["mg / L", "−1.25"], []],
                     [["Unit", "Change"], ["mg / L", "−1.25", ""]],
                     [["Unit", "Change"], ["mg / L", None]],
                     ["Unit", "Change"]]
        for candidate in proposals:
            with self.subTest(candidate=candidate):
                self.assertFalse(compare(candidate, gold)["accepted"])
        with self.assertRaises(ValueError):
            reference(None, self.spec)
        with self.assertRaises(ValueError):
            reference(self.author, {**self.spec, "author_sha256": "0" * 64})
        with self.assertRaises(ValueError):
            reference(self.author, {**self.spec, "table_ordinal": 2})

    def test_unaccepted_proposal_cannot_emit_csv(self):
        spec_path = self.base / "spec.json"
        spec_path.write_text(json.dumps(dict(self.spec, schema="frontier-table-registration/1", dpi=72,
                                   pdf_sha256="0"*64, column_edges_pt=[0, 10, 20],
                                   pages=[{"page":1, "box_pt":[0, 0, 20, 20], "row_edges_pt":[[0,10],[10,20]]}])))
        gold = reference(self.author, self.spec)
        from table_desk import digest
        for index, proposal in enumerate((
            [gold[0], ["mg / L", "−1.26"]], [gold[0], ["mg / L", "1.25"]],
            [gold[0], ["mg / L"]], gold
        )):
            out = self.base / f"run-{index}"
            out.mkdir()
            candidate = out / "transcript.json"
            candidate.write_text(json.dumps(proposal))
            witness = out / "witness.json"
            witness.write_text(json.dumps({"registration_sha256":digest(spec_path),
                                          "proposal_sha256":digest(candidate),"crop_sha256":["fixture"]}))
            args = SimpleNamespace(registration=spec_path, action="check", author=self.author,
                                   candidate=candidate, witness=witness, pdf=None)
            # These controls isolate receipt/CSV decisions from rasterization.
            with patch("table_desk.crops", return_value={"images":[{"png_sha256":"fixture"}]}):
                verdict = execute(args, out)
            self.assertEqual(verdict == "accepted", proposal == gold)
            self.assertEqual((out / "table.csv").exists(), proposal == gold)

    def test_absent_author_withholds_csv(self):
        path = self.base / "spec.json"
        path.write_text(json.dumps(dict(self.spec, schema="frontier-table-registration/1", dpi=72,
                                  pdf_sha256="0" * 64, column_edges_pt=[0, 10],
                                  pages=[{"page": 1, "box_pt": [0, 0, 10, 10], "row_edges_pt": [[0, 10]]}])))
        result = execute(SimpleNamespace(registration=path, action="direct", author=None), self.base)
        self.assertEqual(result, "withheld")
        self.assertFalse((self.base / "table.csv").exists())


if __name__ == "__main__":
    unittest.main()
