"""Frozen 21 adversarial cases and independently written conventional CSV checks."""
import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import gc_ai_register231 as upstream
from tools import registry_interop233 as target


def fixture(specs):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(target.EXPECTED_COLUMNS)
    for spec in specs:
        fields = {name: "" for name in target.EXPECTED_COLUMNS}
        fields.update({
            "ai_register_id": spec.get("ai_register_id", "id0"),
            "government_organization": spec.get("government_organization", "Agency"),
            "name_ai_system_en": spec.get("name_ai_system_en", "Decision tool"),
            "name_ai_system_fr": spec.get("name_ai_system_fr", "Outil décisionnel"),
        })
        fields.update(spec)
        writer.writerow([fields[name] for name in target.EXPECTED_COLUMNS])
    return buffer.getvalue().encode("utf-8")


def independent_reader(raw):
    """No imports from the target's parsing, digest, or classification helpers."""
    source = io.StringIO(raw.decode("utf-8-sig"), newline="")
    reader = csv.DictReader(source, strict=True)
    records = {}
    for row in reader:
        ident = row["ai_register_id"]
        records[ident] = hashlib.sha256(
            json.dumps(row, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    return records


class FrozenCases(unittest.TestCase):
    def setUp(self):
        self.original = fixture([
            {"ai_register_id": "id1"},
            {"ai_register_id": "id2", "status_date": "2026-01-01"},
        ])

    def test_01_independent_ordinary_parity(self):
        report, _ = target.inspect(self.original)
        ordinary = independent_reader(self.original)
        self.assertEqual(report["row_count"], 2)
        self.assertEqual(
            {r["ai_register_id"]: r["record_sha256"] for r in report["records"]},
            ordinary,
        )

    def test_02_reversed_order_no_record_change(self):
        reordered = fixture([
            {"ai_register_id": "id2", "status_date": "2026-01-01"},
            {"ai_register_id": "id1"},
        ])
        result = target.compare(self.original, reordered)
        self.assertEqual((result["changed_count"], result["added_count"],
                          result["removed_count"]), (0, 0, 0))
        original, _ = target.inspect(self.original)
        new, _ = target.inspect(reordered)
        self.assertNotEqual(original["source_sha256"], new["source_sha256"])
        self.assertEqual(original["record_set_sha256"], new["record_set_sha256"])

    def test_03_added_id(self):
        new = fixture([
            {"ai_register_id": "id1"},
            {"ai_register_id": "id2", "status_date": "2026-01-01"},
            {"ai_register_id": "id3"},
        ])
        self.assertEqual(target.compare(self.original, new)["added_ids"], ["id3"])

    def test_04_removed_id(self):
        self.assertEqual(
            target.compare(self.original, fixture([{"ai_register_id": "id1"}]))[
                "removed_ids"], ["id2"]
        )

    def test_05_edited_system_description(self):
        updated = fixture([
            {"ai_register_id": "id1", "description_ai_system_en": "New scope"},
            {"ai_register_id": "id2", "status_date": "2026-01-01"},
        ])
        delta = target.compare(self.original, updated)
        self.assertEqual(delta["changed_count"], 1)
        self.assertEqual([x["name"] for x in delta["changed_records"][0][
            "changed_fields"]], ["description_ai_system_en"])

    def test_06_status_date_change(self):
        changed = fixture([
            {"ai_register_id": "id1"},
            {"ai_register_id": "id2", "status_date": "2026-02-01"},
        ])
        delta = target.compare(self.original, changed)
        self.assertEqual(delta["changed_records"][0]["changed_fields"][0][
            "name"], "status_date")

    def test_07_unrelated_vendor_change_not_risk(self):
        changed = fixture([
            {"ai_register_id": "id1", "vendor_information": "Vendor"},
            {"ai_register_id": "id2", "status_date": "2026-01-01"},
        ])
        delta = target.compare(self.original, changed)
        self.assertEqual(delta["changed_count"], 1)
        self.assertEqual(delta["governance_or_risk_assessment"], "NOT_PERFORMED")

    def test_08_bilingual_multiline(self):
        data = fixture([{
            "ai_register_id": "id-É",
            "name_ai_system_fr": "Outil \nquébécois",
            "description_ai_system_fr": "Évidence et vérification",
        }])
        report, _ = target.inspect(data)
        self.assertEqual(report["records"][0]["ai_register_id"], "id-É")

    def test_09_blank_id(self):
        with self.assertRaisesRegex(target.Rejected, "EMPTY_OR_NONCANONICAL_ID"):
            target.inspect(fixture([{"ai_register_id": ""}]))

    def test_10_duplicate_id(self):
        with self.assertRaisesRegex(target.Rejected, "DUPLICATE_REGISTER_ID"):
            target.inspect(fixture([{"ai_register_id": "same"},
                                    {"ai_register_id": "same"}]))

    def test_11_whitespace_id(self):
        with self.assertRaisesRegex(target.Rejected, "EMPTY_OR_NONCANONICAL_ID"):
            target.inspect(fixture([{"ai_register_id": " id1 "}]))

    def test_12_duplicate_header(self):
        header = list(target.EXPECTED_COLUMNS)
        header[1] = header[0]
        with self.assertRaisesRegex(target.Rejected, "DUPLICATE_HEADER"):
            target.inspect((",".join(header) + "\n" + "," * 23 + "\n").encode())

    def test_13_rearranged_header_rejected(self):
        rows = list(csv.reader(io.StringIO(self.original.decode())))
        rows[0][0], rows[0][1] = rows[0][1], rows[0][0]
        buffer = io.StringIO(newline="")
        csv.writer(buffer).writerows(rows)
        with self.assertRaisesRegex(target.Rejected, "EXACT_SCHEMA_NOT_RECOGNIZED"):
            target.inspect(buffer.getvalue().encode())

    def test_14_width_rejected(self):
        raw = (",".join(target.EXPECTED_COLUMNS) + "\nshort,row\n").encode()
        with self.assertRaisesRegex(target.Rejected, "ROW_WIDTH_MISMATCH"):
            target.inspect(raw)

    def test_15_bad_utf8(self):
        with self.assertRaisesRegex(target.Rejected, "UTF8_REQUIRED"):
            target.inspect(self.original + b"\xff")

    def test_16_source_sha_mismatch(self):
        with self.assertRaisesRegex(target.Rejected, "SOURCE_DIGEST_MISMATCH"):
            target.inspect(self.original, expected_sha256="0" * 64)

    def test_17_no_original_descriptions_or_compliance_in_receipt(self):
        report, _ = target.inspect(fixture([{
            "ai_register_id": "x", "description_ai_system_en": "secret-like public description"
        }]))
        self.assertNotIn("secret-like", json.dumps(report))
        self.assertEqual(report["real_governance_policy_or_compliance_claim"], "NONE")
        self.assertIsNone(report["complete_cost_and_economic_advantage"])

    def test_18_replay_determinism(self):
        self.assertEqual(target.inspect(self.original)[0],
                         target.inspect(self.original)[0])
        self.assertEqual(target.compare(self.original, self.original),
                         target.compare(self.original, self.original))

    def test_19_upstream_231_full_denominator_parity(self):
        baseline = upstream.scan(self.original, source_url=target.SOURCE_URL)
        report, _ = target.inspect(self.original)
        self.assertEqual((baseline["row_count"], baseline["source_sha256"]),
                         (report["row_count"], report["source_sha256"]))

    def test_20_create_only_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "registered.csv"
            out = Path(tmp) / "receipt.json"
            raw.write_bytes(self.original)
            command = [sys.executable, "-m", "tools.registry_interop233",
                       str(raw), "--output", str(out)]
            first = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                   capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            second = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(json.loads(out.read_text())["row_count"], 2)

    def test_21_simulated_comparison_never_proves_official_amendment(self):
        updated = fixture([{"ai_register_id": "id1", "notification_ai": "Yes"}])
        witness = target.compare(fixture([{"ai_register_id": "id1"}]), updated)
        self.assertFalse(witness["historical_official_amendment_proven"])
        self.assertEqual(witness["interpretation"],
                         "EXACT_PUBLIC_CSV_FIELD_CHANGES_ONLY")
        self.assertEqual(witness["changed_count"], 1)


if __name__ == "__main__":
    unittest.main()
