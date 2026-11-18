"""Independent adverse cases against the real source packet population."""

import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

if __package__:
    from . import adapter, capture, desk, direct
else:
    import adapter
    import capture
    import desk
    import direct


class NoticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = adapter.example_scope()
        cls.event = cls.scope["event"]
        reg = capture.manifest()
        cls.meta = reg["originals"][cls.event + ".xml_fmt"]
        cls.raw = capture.original(cls.event + ".xml_fmt", cls.meta)
        cls.parts = adapter.packets(cls.raw)
        cls.index = capture.roster(reg)

    def invalid_history(self, body, state, rows=None, meta=None):
        with self.assertRaises(adapter.EvidenceError) as cm:
            adapter.history(self.event, body, meta or self.meta, self.index if rows is None else rows)
        self.assertEqual(cm.exception.state, state)

    def test_issued_boundary_and_source_clocks(self):
        earlier = dict(self.scope, as_of="2024-04-20T05:06:22.999999Z")
        a = adapter.inspect_source(earlier, "status_history")
        b = adapter.inspect_source(self.scope, "status_history")
        self.assertEqual((a["finding"], b["finding"]), ("active", "retracted"))
        self.assertEqual([p["serial"] for p in a["evidence"]], [1, 2, 3])
        self.assertEqual(b["evidence"][-1]["record_id"], "ivo://gwnet/LVC#S240420aw-4-Retraction")
        t = capture.instant(self.scope["as_of"])
        self.assertEqual(direct.query(direct.schedule(self.event, "mail_notice"), t), "active")
        self.assertEqual(direct.query(direct.schedule(self.event, "issued"), t), "retracted")
        self.assertTrue(all(p["publication_utc"] is None for p in b["evidence"]))

    def test_pending_incomplete_outside_scope(self):
        pending = adapter.inspect_source(dict(self.scope, as_of="2024-04-20T04:22:45.509470Z"), "status_history")
        self.assertEqual((pending["state"], pending["evidence"]), ("pending", []))
        for scope, route in ((self.scope, "first_notice"), (dict(self.scope, clock="received"), "status_history"),
                             (dict(self.scope, as_of="2024-04-27T04:30:11.000001Z"), "status_history")):
            result = adapter.inspect_source(scope, route)
            self.assertEqual((result["state"], result["finding"]), ("incomplete", None))
        missing = adapter.inspect_source(dict(self.scope, event="S240411a"), "status_history")
        self.assertEqual((missing["state"], missing["finding"]), ("unavailable", None))

    def test_missing_middle_and_last_packet_reject(self):
        for i in (1, len(self.parts) - 1):
            self.invalid_history(b"\n".join(self.parts[:i] + self.parts[i+1:]), "incomplete")

    def test_wrong_identity_and_roles(self):
        self.invalid_history(self.raw.replace(b'name="GraceID" value="S240420aw"',
                                             b'name="GraceID" value="S240410ax"', 1), "contradictory")
        self.invalid_history(self.raw.replace(b'role="observation"', b'role="test"', 1), "incomplete")
        changed = self.raw.replace(b'name="internal" value="0"', b'name="internal" value="1"', 1)
        self.invalid_history(changed, "incomplete")
        self.invalid_history(self.raw, "contradictory", meta=dict(self.meta, url=self.meta["url"] + "?alias=1"))

    def test_conflicting_revision_and_reference(self):
        self.invalid_history(self.raw + b"\n" + self.parts[2], "contradictory")
        self.invalid_history(self.raw.replace(b"aw-4-Retraction", b"aw-4-Initial"), "contradictory")
        altered = [dict(r, kind="Ini") if (r["event"], r["serial"]) == (self.event, "4")
                   else r for r in self.index]
        self.invalid_history(self.raw, "contradictory", rows=altered)
        self.invalid_history(self.raw.replace(b"05:06:23Z", b"04:30:00Z"), "contradictory")

    def test_non_retraction_cannot_undo_withdrawal(self):
        records = adapter.history(self.event, self.raw, self.meta, self.index)
        # Counterfactual fifth revision. The archived science population still has four.
        successor = dict(records[-1], serial=5, notice_type="Update", issued_utc="2024-04-20T05:08:02Z")
        result = adapter.at_cutoff([*records, successor], capture.instant(successor["issued_utc"]),
                                   "issued", "status_history")
        self.assertEqual((result["state"], result["finding"]), ("contradictory", None))

    def test_different_bytes_cannot_inherit_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "sources").mkdir()
            (root / "sources.json").write_bytes((capture.HERE / "sources.json").read_bytes())
            (root / "sources" / (self.event + ".xml_fmt.gz")).write_bytes(gzip.compress(self.raw + b" "))
            with patch.object(capture, "HERE", root):
                result = adapter.inspect_source(self.scope, "status_history")
                self.assertEqual((result["state"], result["finding"]), ("incomplete", None))
                (root / "sources.json").write_text("{}")
                self.assertEqual(adapter.inspect_source(self.scope, "status_history")["state"], "incomplete")

    def test_recipient_matches_all_registered_cutoffs(self):
        result = desk.registered()
        frozen = json.loads((capture.HERE / "result.json").read_text())
        self.assertEqual(result, frozen)
        self.assertEqual((result["total_sql_matches"], result["total_registered_cutoffs"]), (34, 34))
        self.assertEqual(result["outcomes"]["S240410ax"]["group"], "consecutive_fifth_receiver_transfer")


if __name__ == "__main__":
    unittest.main()
