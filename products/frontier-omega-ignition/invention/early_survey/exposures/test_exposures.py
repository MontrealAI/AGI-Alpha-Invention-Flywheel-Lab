"""Time, provenance and rights boundaries for the independently recovered repeats."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

if __package__:
    from . import verify
else:
    import verify


class ArchiveTest(unittest.TestCase):
    def test_frozen_science_and_access(self):
        result = verify.calculate()
        self.assertEqual(verify.json_bytes(result), (verify.HERE/"RESULT.json").read_bytes())
        for row in result["witnesses"].values():
            self.assertEqual((row["status"], row["fink_status"]), ("persisted", "coverage_gap"))
            self.assertEqual(row["witness"]["programid"], 1)
            self.assertEqual(row["forced_photometry"]["status"], "persisted")
            self.assertEqual(row["baseline"]["rfid"], row["witness"]["rfid"])
        _, raw, _ = verify.inputs(verify.HERE/"sources")
        access = verify.archive_access(raw)
        self.assertEqual(verify.json_bytes(access), (verify.HERE/"ARCHIVE_ACCESS.json").read_bytes())
        self.assertEqual(access["historical_footprint_rows"], 42)
        self.assertEqual(access["trigger_control_rows"], 0)

    def test_issue_and_first_subsequent_packet(self):
        self.assertFalse(verify.calculate("2026-10-25T23:59:59Z")["witnesses"])
        at_issue = verify.calculate(verify.ISSUE)
        self.assertTrue(all(v["witness"] is None and v["fink_status"] == "awaiting_repeat"
                            for v in at_issue["witnesses"].values()))
        exact = verify.calculate("2026-10-28T05:58:39.000000Z")
        self.assertIsNone(exact["witnesses"]["g"]["witness"])
        next_tick = verify.calculate("2026-10-28T05:58:39.000001Z")
        self.assertEqual(next_tick["witnesses"]["g"]["witness"]["candid"], "3587249065815015015")
        self.assertIsNone(next_tick["witnesses"]["g"]["forced_photometry"])

    def test_prefix_reconstructs_without_future_packets_or_calibration_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/"sources"
            shutil.copytree(verify.HERE/"sources", folder)
            for name in ("r.avro.gz", "history.avro.gz", "forced.json.gz"):
                (folder / name).unlink()
            early = verify.calculate("2026-10-28T07:00:00Z", folder=folder)
            first, second = early["witnesses"]["g"], early["witnesses"]["r"]
            self.assertEqual(first["status"], "persisted")
            self.assertEqual(second["status"], "awaiting_repeat")
            self.assertIsNone(second["witness"])
            self.assertIsNone(first["forced_photometry"])
            for private_future in ("3587389715815015003", "3593289315815015006", "2026-11-03T06:56"):
                self.assertNotIn(private_future, json.dumps(early))
            data = (folder/"g.avro.gz").read_bytes()
            # Re-encoding a tampered public payload cannot pass the pinned input.
            import gzip
            (folder/"g.avro.gz").write_bytes(gzip.compress(gzip.decompress(data)[:-10]))
            with self.assertRaisesRegex(ValueError, "source differs"):
                verify.calculate("2026-10-28T07:00:00Z", folder=folder)

    def test_distinct_source_and_carrier_times(self):
        end = verify.calculate(verify.DEADLINE)["witnesses"]
        self.assertEqual(end["g"]["forced_photometry"]["carrier_candid"], "3587389715815015003")
        self.assertIsNone(end["r"]["forced_photometry"])
        self.assertEqual(end["r"]["fink_status"], "coverage_gap")
        at_last = verify.calculate("2026-11-03T07:00:00Z")["witnesses"]
        self.assertEqual(at_last["r"]["forced_photometry"]["carrier_candid"], "3593289315815015006")
        self.assertEqual(at_last["r"]["status"], "persisted")


    def _replay_with_earlier_broker_row(self, reference_id):
        """Add a synthetic alternative-stream row only to the in-memory projection."""
        original_inputs = verify.inputs

        def supplemented(folder, until=None):
            index, raw, packets = original_inputs(folder, until)
            rows = json.loads(raw["alerce-api"])
            witness = next(row for row in rows["detections"]
                           if row["candid"] == "3587249065815015015")
            rows["detections"].append({
                **witness,
                "candid": "3586500000015000001",
                "mjd": 61340.5,
                "rfid": reference_id,
            })
            return index, {**raw, "alerce-api": json.dumps(rows).encode()}, packets

        with patch.object(verify, "inputs", side_effect=supplemented):
            return verify.calculate()

    def test_unrelated_reference_does_not_preempt_first_witness(self):
        # Not an observed event: an otherwise earlier same-band row from a
        # different reference-processing stream must be outside this notice.
        receipt = self._replay_with_earlier_broker_row(504120158)
        self.assertEqual(verify.json_bytes(receipt), (verify.HERE/"RESULT.json").read_bytes())

    def test_earlier_same_reference_without_packet_fails_closed(self):
        # A truly earlier same-reference candidate cannot be waved away.
        # Without source-qualified packet evidence the receiver must refuse.
        with self.assertRaisesRegex(ValueError, "ambiguous or missing first alternative-broker witness"):
            self._replay_with_earlier_broker_row(505120158)



if __name__ == "__main__":
    unittest.main()
