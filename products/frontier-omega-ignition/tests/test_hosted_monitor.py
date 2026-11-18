"""Readiness and storage alarms expose an actionable status without mission contents."""
import json
from pathlib import Path
import tempfile
import unittest

from ignition.hosted_auth import Access
from ignition.hosted_monitor import check
from ignition.store import Store


class Reply:
    def __init__(self,*args,**kwargs): pass
    def request(self,*args,**kwargs): pass
    def close(self): pass
    def getresponse(self): return self
    def read(self,n): return b'{"status":"unavailable"}'
    status = 503


class Monitor(unittest.TestCase):
    def test_queue_age_readiness_and_unreadable_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/"private"
            access = Access(root, "staging")
            access.issue("private-tenant")
            store = Store(access.workspaces/"private-tenant")
            mission = {"purpose":"private never output"}
            rid,rev = store.create({"mission":mission,"request_id":"backlog-test"}, {}, "test")
            state = store.get(rid)
            state["events"][-1]["at"] = "2025-01-01T00:00:00+00:00"
            store.save(state)
            report = check(root, "https://example.test", 8784, client=Reply)
            self.assertEqual(report["measurements"]["queued"],1)
            self.assertTrue(any("five minutes" in a for a in report["alarms"]))
            self.assertTrue(any("model" in a for a in report["alarms"]))
            self.assertNotIn(mission["purpose"], json.dumps(report))
            self.assertNotIn("private-tenant", json.dumps(report))
            missing = check(root/"absent", "https://example.test", 8784, client=Reply)
            self.assertTrue(any("storage unreadable" in a for a in missing["alarms"]))
