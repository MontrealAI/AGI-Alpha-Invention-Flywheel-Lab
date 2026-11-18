import tempfile
import unittest
from pathlib import Path

from study import CONDITIONS, read_record, rate_evidence, score, source


class PeakContextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.record = read_record()

    def test_scientific_scope_and_typed_counts(self):
        self.assertEqual(rate_evidence(self.rows), {"reported_peaks": 5, "possible_same_object_pairs_upper_bound": 0})
        self.assertEqual(sum(value is None for row in self.rows for value in row), 6)
        self.assertEqual(self.record["results"]["semantic_dom"]["csv_sha256"],
                         self.record["results"]["pdf_geometry"]["csv_sha256"])
        self.assertEqual(self.record["results"]["table_desk"]["quantities"], 24)
        self.assertFalse(self.record["results"]["table_desk"]["accepted"])

    def test_loss_of_sign_precision_missingness_or_inequality_rejects_delivery(self):
        mutations = ((0, 1, "19.0±0.2"), (0, 6, "24.9±1.75"), (1, 3, "0"),
                     (0, 3, "≤0.020"), (1, 4, "+23:40:53.04"))
        for row_index, column, new in mutations:
            with self.subTest(row_index=row_index, column=column):
                rows = [row.copy() for row in self.rows]
                rows[row_index][column] = new
                result = score(rows, list(CONDITIONS), self.rows)
                self.assertFalse(result["accepted"])
                self.assertEqual(result["quantities"], 35)

    def test_a_missing_condition_rejects_perfect_numbers(self):
        for removed in CONDITIONS:
            notes = [note for note in CONDITIONS if note != removed]
            result = score(self.rows, notes, self.rows)
            self.assertEqual(result["quantities"], 36)
            self.assertFalse(result["accepted"])

    def test_source_substitution_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.html"
            path.write_bytes(b"<p>other edition</p>")
            with self.assertRaisesRegex(ValueError, "source differs"):
                source(path, self.record["html_sha256"])


if __name__ == "__main__":
    unittest.main()
