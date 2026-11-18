"""Unprivileged real snapshot and isolated supervisor failure drills. Uses no host services."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from ignition.backup_job import MARKER, destination, record
from ignition.hosted_auth import Access
from ignition.hosted_backup import snapshot
from ignition.hosted_monitor import check
from ignition.store import PRODUCT, StateError
from unittest.mock import MagicMock

spec = importlib.util.spec_from_file_location("backup_supervisor", PRODUCT/"deploy/backup_supervisor.py")
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


class ScheduledBackup(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.marker = self.root/"restart-required"
        self.state = self.root/"state"
        self.access = Access(self.state,"staging")
        self.folder = self.root/"external"
        self.folder.mkdir(mode=0o700)
        self.active = "active"
        self.actions = []

    def control(self, action):
        self.actions.append(action)
        if action == "is-active":
            return self.active
        self.active = {"stop":"inactive", "start":"active"}[action]

    def test_success_saves_to_held_directory_and_updates_age(self):
        def execute(action):
            if action == "save":
                self.assertEqual(self.active,"inactive")
                fd = os.open(self.folder,os.O_RDONLY|os.O_DIRECTORY)
                try:
                    files = snapshot(self.state,Path(f"/proc/self/fd/{fd}")/"example","staging",parent_fd=fd)
                finally:
                    os.close(fd)
                record(self.state,"staging","example",files)
        supervisor.backup(self.marker,self.control,execute)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.active,"active")
        self.assertTrue((self.folder/"example/SNAPSHOT.json").is_file())
        reply = MagicMock()
        reply.return_value.getresponse.return_value.status = 200
        reply.return_value.getresponse.return_value.read.return_value = b'{"status":"ok"}'
        result = check(self.state,"https://example.test",8784,client=reply,backup_required=True)
        self.assertLessEqual(result["measurements"]["last_verified_backup_age_seconds"],5)
        data = json.loads((self.state/MARKER).read_text())
        data["finished"] = int(time.time())-86401
        (self.state/MARKER).write_text(json.dumps(data))
        stale = check(self.state,"https://example.test",8784,client=reply,backup_required=True)
        self.assertTrue(any("24 hours" in a for a in stale["alarms"]))

    def test_copy_failure_starts_service_and_never_records_success(self):
        def execute(action):
            if action == "save":
                raise OSError("injected unavailable storage")
        with self.assertRaises(OSError):
            supervisor.backup(self.marker,self.control,execute)
        self.assertEqual(self.actions,["is-active","stop","start","is-active"])
        self.assertFalse((self.state/MARKER).exists())
        self.assertFalse(self.marker.exists())

    def test_preflight_and_inactive_unit_are_left_alone(self):
        def execute(action):
            raise StateError("preflight failed")
        with self.assertRaises(StateError):
            supervisor.backup(self.marker,self.control,execute)
        self.assertEqual(self.actions,["is-active"])
        self.active = "inactive"
        with self.assertRaises(RuntimeError):
            supervisor.backup(self.marker,self.control,execute)
        self.assertEqual(self.actions,["is-active","is-active"])
        with self.assertRaises(StateError):
            destination(self.state, self.folder,self.folder,"CRYPT-LUKS2-enrolled")

    def test_marker_recovers_interruption_and_failed_restart_retries(self):
        self.active = "inactive"
        self.marker.touch()
        def fail(action):
            if action == "start":
                raise OSError("injected restart failure")
        with self.assertRaises(OSError):
            supervisor.recover(self.marker,fail)
        self.assertTrue(self.marker.exists())
        supervisor.recover(self.marker,self.control)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.active,"active")
