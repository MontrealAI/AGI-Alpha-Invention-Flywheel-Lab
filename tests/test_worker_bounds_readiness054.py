"""054 checker regressions; observer-interposed tests are not canonical receipts."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from flywheel.legacy import materialize
from verification import probe_worker_bounds_current054 as bounds

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = '''import importlib.util,pathlib,subprocess,sys,time
root,output,barrier,release,pidfile=map(pathlib.Path,sys.argv[1:])
s=importlib.util.spec_from_file_location('frozen',root/'reproduce.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
original_write,original_popen=m.write,subprocess.Popen
def write(path,data):
 original_write(path,data)
 if path.name=='STARTED.json':
  barrier.write_text('STARTED published before protected try')
  while not release.exists():time.sleep(.002)
def popen(*a,**kw):
 child=original_popen(*a,**kw)
 pidfile.write_text(str(child.pid))
 return child
m.write=write;m.subprocess.Popen=popen
sys.argv=[str(root/'reproduce.py'),'--output',str(output)]
raise SystemExit(m.main())
'''


def wait_file(path, process=None, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        if process is not None and process.poll() is not None:
            raise AssertionError("controlled process exited before event")
        time.sleep(.002)
    raise AssertionError("controlled event timeout")


class WorkerReadiness054(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "frozen"
        materialize(ROOT, self.root)
        self.pins = {name: bounds.sha(self.root / name) for name in bounds.PINS}

    def wrapper(self, output):
        wrapper = self.base / "observer.py"
        wrapper.write_text(WRAPPER)
        barrier, release, pidfile = (self.base / name for name in ("barrier", "release", "worker-pid"))
        command = [sys.executable, "-I", str(wrapper), str(self.root), str(output / "interrupted-run"), str(barrier), str(release), str(pidfile)]
        return command, barrier, release, pidfile

    def test_actual_early_started_counterexample_remains_a_failure(self):
        output = self.base / "legacy"
        output.mkdir()
        command, barrier, _, _ = self.wrapper(output)
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=bounds.ENV)
        try:
            wait_file(barrier, process)
            self.assertTrue((output / "interrupted-run/STARTED.json").exists())
            self.assertFalse((output / "interrupted-run/WORKER.log").exists())
            process.send_signal(signal.SIGINT)
            _, stderr = process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("KeyboardInterrupt", stderr)
            self.assertFalse((output / "interrupted-run/INTERRUPTED.json").exists())
            self.assertFalse((output / "interrupted-run/COMPLETE.json").exists())
        finally:
            if process.poll() is None:
                process.kill(); process.communicate(timeout=5)
        self.assertEqual(self.pins, {name: bounds.sha(self.root / name) for name in bounds.PINS})

    def test_real_frozen_main_waits_for_protected_worker_with_disclosed_observer(self):
        output = self.base / "observed"
        output.mkdir()
        command, barrier, release, pidfile = self.wrapper(output)
        result, errors = [], []
        observed_pretry, resume_checker = threading.Event(), threading.Event()

        def actual_children(parent_host):
            if not pidfile.exists():
                return []
            try:
                child_pid = int(pidfile.read_text())
            except ValueError:  # Observer publication may still be in progress.
                return []
            fd = os.pidfd_open(child_pid)
            try:
                host, _ = bounds.fd_identity(fd)
                return [host]
            finally:
                os.close(fd)

        def exercise():
            try:
                result.append(bounds.active_interrupt(self.root, output, command=command, child_observer=actual_children))
            except BaseException as exc:
                errors.append(exc)

        original_sleep = time.sleep
        def observed_sleep(seconds):
            if threading.current_thread() is thread and barrier.exists() and not release.exists():
                # Observe a real readiness-loop iteration with the parent
                # deterministically held outside try. Do not fabricate readiness.
                observed_pretry.set()
                if not resume_checker.wait(5):
                    raise AssertionError("checker pre-try observation was not released")
            original_sleep(seconds)

        thread = threading.Thread(target=exercise)
        with patch.object(bounds.time, "sleep", observed_sleep):
            thread.start()
            try:
                wait_file(barrier)
                self.assertTrue(observed_pretry.wait(5))
                # A complete STARTED record is still outside the protected block.
                self.assertFalse((output / "interrupted-run/WORKER.log").exists())
                self.assertFalse((output / "interrupted-run/INTERRUPTED.json").exists())
                self.assertEqual(result, [])
                self.assertEqual(errors, [])
            finally:
                release.write_text("allow actual frozen main to enter protected try")
                resume_checker.set()
                thread.join(20)
        self.assertFalse(thread.is_alive())
        if errors:
            raise errors[0]
        self.assertTrue(result[0]["passed"], result[0])
        self.assertTrue(result[0]["parent_sigint_sent"])
        self.assertIn(result[0]["handshake"]["stopped_state"]["state"], ("T", "t"))
        self.assertTrue(result[0]["identified_worker_not_live"])
        self.assertTrue(result[0]["parent_sigint_terminated_worker"])
        self.assertFalse(result[0]["forced_checker_cleanup"])
        self.assertEqual(result[0]["handshake"]["parent_protected_wait_wchan"], "hrtimer_nanosleep")
        self.assertTrue(result[0]["partial_evidence_preserved"])
        self.assertNotEqual(result[0]["restart_returncode"], 0)
        self.assertEqual(self.pins, {name: bounds.sha(self.root / name) for name in bounds.PINS})
        # Real resource attempts use unchanged limits even on masked-proc hosts.
        resources = bounds.resource_probe(self.root, output)
        self.assertEqual(resources["returncode"], 0)
        for check in ("memory_limit_enforced", "file_limit_enforced", "fd_limit_enforced"):
            self.assertIs(resources[check], True)
        self.assertEqual(resources["file_bytes_at_stop"], 10 * 1024**2)

    def test_canonical_frozen_worker_probe_on_supported_linux(self):
        try:
            bounds.direct_children(int(Path("/proc/self/stat").read_text().split()[0]))
        except RuntimeError:
            self.skipTest("canonical path UNAVAILABLE: task/children hidden; observer test is separate")
        report = bounds.probe(self.root, self.base / "canonical")
        self.assertTrue(report["passed"])
        self.assertEqual(report["legacy_failure"]["early_started_interruption"], "PRESERVED_NOT_REPAIRED")

    def test_missing_platform_support_refuses_before_process_creation(self):
        # The canonical path must not start an unobservable worker.
        with patch.object(bounds, "direct_children", side_effect=RuntimeError("DIRECT_CHILD_OBSERVATION_UNAVAILABLE")):
            with patch.object(bounds.subprocess, "Popen") as popen:
                with self.assertRaisesRegex(RuntimeError, "UNAVAILABLE"):
                    bounds.active_interrupt(self.root, self.base)
                popen.assert_not_called()

    def test_no_readiness_early_exit_and_late_complete_never_signal(self):
        class Process:
            def __init__(self, returncode=None):
                self.returncode = returncode
            def poll(self):
                return self.returncode
        actual = self.base / "negative"
        actual.mkdir()
        for name, process, marker, error in (
            ("no-readiness", Process(), None, "TIMEOUT"),
            ("early-exit", Process(1), None, "EXITED"),
            ("late-complete", Process(), "COMPLETE.json", "COMPLETED"),
        ):
            with self.subTest(name=name):
                if marker:
                    (actual / marker).write_text("{}")
                with patch.object(bounds.signal, "pidfd_send_signal") as send:
                    with self.assertRaisesRegex(RuntimeError, error):
                        bounds.wait_ready(process, 0, actual, self.root / "reproduce.py", timeout=.01, child_observer=lambda _: [])
                    send.assert_not_called()

    def test_tampered_frozen_runner_refused_before_output_or_execution(self):
        (self.root / "reproduce.py").write_text("raise RuntimeError('tampered')\n")
        output = self.base / "must-not-exist"
        with self.assertRaisesRegex(ValueError, "FROZEN_SOURCE_IDENTITY"):
            bounds.probe(self.root, output)
        self.assertFalse(output.exists())

    def test_added_python_refused_before_output_or_execution(self):
        (self.root / "unregistered.py").write_text("raise RuntimeError('extra')\n")
        output = self.base / "must-not-exist"
        with self.assertRaisesRegex(ValueError, "FROZEN_PYTHON_SOURCE_SET"):
            bounds.probe(self.root, output)
        self.assertFalse(output.exists())

    def test_forced_cleanup_is_explicit_failure_evidence(self):
        process = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(30)"])
        pidfd = os.pidfd_open(process.pid)
        try:
            host, _ = bounds.fd_identity(pidfd)
            identity = {"host_pid": host, "namespace_pid": process.pid, **bounds.proc_state(host)}
            termination = bounds.terminate_worker(pidfd, identity)
            self.assertTrue(termination["forced_checker_cleanup"])
            self.assertFalse(termination["parent_sigint_terminated_worker"])
            self.assertTrue(termination["identified_worker_not_live"])
            process.wait(timeout=5)
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=5)
            os.close(pidfd)


if __name__ == "__main__":
    unittest.main()
