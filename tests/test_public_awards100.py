"""Fixed synthetic M0–M7 cases; no external GET, accounts or private data."""
import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import public_awards100 as a

COLUMNS = [
    "title-titre-eng", "title-titre-fra",
    "awardDescription-descriptionAppelOffres-eng",
    "awardDescription-descriptionAppelOffres-fra",
    "contractAmount", "totalContractValue", "contractCurrency",
    "procurementCategory-categorieApprovisionnement",
]


def fixture(rows, columns=COLUMNS):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(columns)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


class RegisteredAwardTests(unittest.TestCase):
    def rows(self):
        return [
            ["AI governance", "", "Artificial intelligence regulatory support", "", "100", "100", "CAD", "*SRV"],
            ["Maintenance painting", "", "Electrical installation", "", "0", "", "CAD", "*GD"],
            ["Regulatory audit", "", "Document review", "", "", "0", "CAD", "*SRVTGD"],
            ["Machine learning", "", "Model engineering", "", "40", "40", "USD", "*GD\n*SRV"],
            ["", "Intelligence artificielle", "", "audit et conformité", "0", "0", "", "*SRV"],
        ]

    def test_m0_bilingual_empty_english_falls_back_without_leaking_text(self):
        v = a.aggregate(fixture(self.rows()))
        self.assertEqual(v["rows_observed"], 5)
        self.assertNotIn("Intelligence artificielle", json.dumps(v))
        self.assertEqual(v["schema"]["column_count"], len(COLUMNS))

    def test_m1_ai_token_boundaries_do_not_match_maintenance_painting(self):
        self.assertFalse(a.AI.search("maintenance painting chain"))
        self.assertFalse(a.AI.search("fair train daily"))
        self.assertTrue(a.AI.search("AI enabled"))
        self.assertTrue(a.AI.search("artificial intelligence"))

    def test_m2_partition_sum_is_exact(self):
        v = a.aggregate(fixture(self.rows()))
        self.assertEqual(v["lexical_classes"], {
            "joint_signal": 1, "ai_only": 1, "governance_only": 2, "neither": 1})
        self.assertEqual(sum(v["lexical_classes"].values()), v["rows_observed"])
        self.assertEqual(v["category_occurrences_among_joint_notices"]["SRV"], 1)

    def test_m3_missing_zero_and_currency_not_booked(self):
        v = a.aggregate(fixture(self.rows()))
        self.assertEqual(v["award_value_disclosure"]["at_least_one_positive_disclosed_field"], 2)
        self.assertEqual(v["award_value_disclosure"]["unknown_or_zero_not_free"], 3)
        self.assertEqual(v["currency_labels_for_positive_disclosed_fields"], {"CAD": 1, "USD": 1})
        with self.assertRaises(ValueError):
            a.aggregate(fixture([["AI", "", "Audit", "", "-1", "", "CAD", "*SRV"]]))

    def test_m4_malformed_row_and_duplicate_header_fail(self):
        with self.assertRaisesRegex(ValueError, "MALFORMED"):
            a.aggregate(fixture([["Only", "two"]]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            a.aggregate(fixture(self.rows(), COLUMNS[:-1] + [COLUMNS[-2]]))

    def test_m5_missing_currency_description_or_amount_fails(self):
        for prefixes in (("contractAmount", "totalContractValue"),
                         ("contractCurrency",), ("awardDescription",)):
            names = [n for n in COLUMNS if not any(n.startswith(p) for p in prefixes)]
            with self.subTest(prefixes=prefixes), self.assertRaises(ValueError):
                a.aggregate(fixture([[""] * len(names)], names))

    def test_m6_source_hash_changes_on_one_byte(self):
        data = fixture(self.rows())
        self.assertNotEqual(hashlib.sha256(data).hexdigest(),
                            hashlib.sha256(data + b"\n").hexdigest())

    def test_m7_create_only_failure_is_aggregate_and_has_no_private_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "aggregate.json"
            with patch.object(a, "observe", side_effect=ValueError("INVALID_OFFICIAL_CSV")):
                result = a.run(out)
            self.assertEqual(result["status"], "FAILED")
            self.assertEqual(result["commercial_decision"], "NO_BID_NO_DEPLOY")
            self.assertIsNone(result["native_profit"])
            self.assertEqual(result["error_code"], "INVALID_OFFICIAL_CSV")
            self.assertEqual(json.loads(out.read_text())["schema"], "agi-alpha/public-award-evidence100/v1")
            with self.assertRaises(FileExistsError):
                a.run(out)
            self.assertNotIn("supplierLegalName", out.read_text())
            self.assertNotIn("contactInfoEmail", out.read_text())

    def test_m8_award_description_is_required_tender_only_is_not_accepted(self):
        columns = [n.replace("awardDescription", "tenderDescription") for n in COLUMNS]
        with self.assertRaisesRegex(ValueError, "ENGLISH_OFFICIAL_TITLE_OR_DESCRIPTION_MISSING"):
            a.aggregate(fixture([[""] * len(columns)], columns))
        self.assertEqual(a.aggregate(fixture(self.rows()))["rows_observed"], 5)

    def test_m9_failed_schema_preserves_actual_source_hash_and_byte_count(self):
        raw = fixture([["title", "", "description", "", "1", "1", "CAD", "*SRV"]],
                      [x.replace("awardDescription", "tenderDescription") for x in COLUMNS])
        class Response:
            status = 200
            headers = {"Last-Modified": "Sun, 08 Nov 2026 00:00:00 GMT"}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def geturl(self): return a.URL
            def read(self, length): return raw
        with patch.object(a, "urlopen", return_value=Response()):
            observed = a.observe()
        self.assertEqual(observed["source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(observed["source_bytes"], len(raw))
        self.assertEqual(observed["parse_error_code"],
                         "ENGLISH_OFFICIAL_TITLE_OR_DESCRIPTION_MISSING")
        self.assertNotIn("title", json.dumps(observed))


if __name__ == "__main__":
    unittest.main()
