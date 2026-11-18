"""Offline regression tests for a supplied single-band notice and incomplete evidence."""

import base64
import gzip
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import broker_control as broker


class ExternalNoticeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.index = self.data / "index.vot"
        self.notice = self.data / "notice.json"
        original = broker.notice_from_file()
        anchors = {role: original.bands["r"][role]["candid"] for role in broker.ROLES}
        # This artificial object name exercises target binding. Its fluxes come from the frozen r fixture.
        target = "ZTF25zzzzzzz"
        self.notice.write_text(json.dumps({"target": target, "issue_utc": original.issued,
                                          "deadline_utc": original.deadline, "bands": {"r": anchors}}))
        case = broker.notice_from_file(self.notice)
        raw_index = (broker.SOURCES / "alerce-window.vot").read_bytes()
        index, _ = broker.index_rows(raw_index, original)
        xml = ET.fromstring(raw_index)
        query = xml.find(".//{*}INFO[@name='query']")
        query.set("value", broker.selection_query(case))
        binary = bytearray()
        for cid, (mjd, fid, rfid, pid) in index.items():
            if fid != 2:
                continue
            text = target.encode()
            binary.extend(struct.pack(">I", len(text)) + text + struct.pack(">qdiqq", cid, mjd, fid, rfid, pid))
            source = broker.SOURCES / f"{cid}.avro.gz"
            if not source.is_file():
                source = broker.EARLY / "exposures" / "sources" / "r.avro.gz"
            body = gzip.decompress(source.read_bytes())
            self.assertEqual(body.count(original.target.encode()), 1)
            (self.data / f"{cid}.avro").write_bytes(body.replace(original.target.encode(), text))
        xml.find(".//{*}STREAM").text = base64.b64encode(binary).decode()
        self.index.write_bytes(ET.tostring(xml))

    def replay(self):
        return subprocess.run([sys.executable, str(broker.HERE / "broker_control.py"), "--notice", str(self.notice),
                               "--index", str(self.index), "--packets", str(self.data)], capture_output=True, text=True)

    def test_external_target_single_filter(self):
        run = self.replay()
        self.assertEqual(run.returncode, 0, run.stderr)
        outcome = json.loads(run.stdout)["result"]
        self.assertEqual(outcome["target"], "ZTF25zzzzzzz")
        self.assertEqual(list(outcome["bands"]), ["r"])
        self.assertEqual(outcome["bands"]["r"]["witness"]["candid"], "3587389715815015003")
        self.assertEqual(outcome["bands"]["r"]["status"], "persisted")

    def test_missing_packet_stays_unresolved(self):
        (self.data / "3587389715815015003.avro").unlink()
        run = self.replay()
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("Missing or ambiguous packet", run.stderr)
        self.assertFalse(run.stdout)

    def test_overflow_stays_unresolved(self):
        xml = ET.parse(self.index)
        xml.find(".//{*}INFO[@name='QUERY_STATUS']").set("value", "OVERFLOW")
        xml.write(self.index)
        run = self.replay()
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("overflowed", run.stderr)
        self.assertFalse(run.stdout)


if __name__ == "__main__":
    unittest.main()
