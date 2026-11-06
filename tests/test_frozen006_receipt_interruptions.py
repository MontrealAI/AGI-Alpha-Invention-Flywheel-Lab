"""Execute the workflow's exact inline wrapper with a tiny authenticated fixture.

Uses the real, unchanged v4 monitor and OS signals. The synthetic 6363-entry
closure only exercises wrapper decisions; this is not a historical replay.
No production test hooks, external mutation, or changes to registered limits.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = Path(os.environ.get("FROZEN006_WORKFLOW", ROOT / ".github/workflows/campaign.yml"))
MARKER = 'python - "$RUNNER_TEMP/frozen-cycle-006" "$RUNNER_TEMP/consequential-cycle-006" <<\'PY\'\n'
WRAPPER = textwrap.dedent(WORKFLOW.read_text().split(MARKER, 1)[1].split("          PY\n", 1)[0])

FIXTURE_RUNNER = r'''
import argparse, hashlib, json, os, time
from pathlib import Path
def source_identity(root, freeze_path, expected):
    count = 6362 if (root / "mode.txt").read_text() == "bad-closure" else 6363
    return {"sources": {str(n): "fixture" for n in range(count)}}, expected
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--worker", action="store_true")
    p.add_argument("--output")
    p.add_argument("--freeze")
    p.add_argument("--freeze-sha256")
    a = p.parse_args()
    out = Path(a.output)
    out.mkdir(parents=True)
    (out / "worker-pid.txt").write_text(str(os.getpid()))
    mode = (Path(__file__).parent / "mode.txt").read_text()
    if mode == "sleep":
        time.sleep(60)
    if mode == "fail":
        raise SystemExit(7)
    report = b'{"fixture": "not a historical worker"}\n'
    (out / "REPORT.json").write_bytes(report)
    sha = "incorrect" if mode == "mismatch" else hashlib.sha256(report).hexdigest()
    (out / "COMPLETE.json").write_text(json.dumps({"state": "COMPLETE", "report_sha256": sha}))
'''

HARNESS = r'''
import hashlib, importlib.util, json, os, signal, sys, types
from pathlib import Path
wrapper_path, root_arg, output_arg, monitor_path, injection = sys.argv[1:]
root, output = Path(root_arg), Path(output_arg)
freeze = root / "FREEZE.json"
expected = (root / "expected-freeze.txt").read_text()
events = []
triggered = False
second_signal = False
def event(point):
    global triggered
    events.append(point)
    if triggered or injection.removeprefix("double-") != point:
        return
    triggered = True
    if point.endswith("-io"):
        raise OSError("injected I/O failure: " + point)
    if point.endswith("-kill"):
        os.kill(os.getpid(), signal.SIGKILL)
    else:
        os.kill(os.getpid(), signal.SIGTERM)

# Fixture only: no production source-authentication shortcut is modified.
spec = importlib.util.spec_from_file_location("experiments.resource006_v4", monitor_path)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)
run = monitor.run
def traced_run(*args, **kwargs):
    events.append({"monitor_arguments": [str(x) if isinstance(x, Path) else x for x in args],
                   "cwd": str(kwargs["cwd"])})
    result = run(*args, **kwargs)
    event("after-monitor")
    return result
monitor.run = traced_run
experiments = types.ModuleType("experiments")
experiments.resource006_v4 = monitor
sys.modules["experiments"] = experiments
reproduction = types.ModuleType("flywheel.reproduction006")
reproduction.FREEZE, reproduction.FREEZE_SHA256 = "FREEZE.json", expected
sys.modules["flywheel"] = types.ModuleType("flywheel")
sys.modules["flywheel.reproduction006"] = reproduction

read_bytes, mkdir, replace, fdopen, write_text, fsync = Path.read_bytes, Path.mkdir, os.replace, os.fdopen, Path.write_text, os.fsync
last_replaced = None
def patched_read_bytes(path):
    if path == freeze:
        event("read-freeze")
        event("read-freeze-io")
        event("read-freeze-kill")
    return read_bytes(path)
def patched_mkdir(path, *args, **kwargs):
    result = mkdir(path, *args, **kwargs)
    if path == output:
        event("after-mkdir")
    return result
def patched_replace(src, dst, *args, **kwargs):
    global last_replaced
    path = Path(dst)
    if path.parent == output:
        event("before-replace-" + path.name)
        event("before-replace-" + path.name + "-io")
    result = replace(src, dst, *args, **kwargs)
    if path.parent == output:
        last_replaced = path.name
        event("after-replace-" + path.name)
        event("after-replace-" + path.name + "-io")
    return result
def patched_fsync(fd):
    path = Path(os.readlink("/proc/self/fd/" + str(fd)))
    if path == output:
        event("directory-fsync-" + str(last_replaced))
        event("directory-fsync-" + str(last_replaced) + "-io")
    elif path.parent == output:
        for name in ("PENDING.json", "SOURCE_IDENTITY.json", "REPORT.json", "COMPLETE.json", "INTERRUPTED.json"):
            if path.name.startswith("." + name + "."):
                event("file-fsync-" + name + "-io")
    return fsync(fd)
class PartialWriter:
    def __init__(self, stream, point):
        self.stream, self.point = stream, point
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return self.stream.__exit__(*args)
    def write(self, data):
        self.stream.write(data[:7])
        self.stream.flush()
        event(self.point)
        return self.stream.write(data[7:])
    def __getattr__(self, name):
        return getattr(self.stream, name)
def patched_fdopen(fd, *args, **kwargs):
    path = Path(os.readlink("/proc/self/fd/" + str(fd)))
    stream = fdopen(fd, *args, **kwargs)
    if path.parent == output:
        for name in ("PENDING.json", "SOURCE_IDENTITY.json", "REPORT.json", "COMPLETE.json", "INTERRUPTED.json"):
            if path.name.startswith("." + name + "."):
                return PartialWriter(stream, "partial-" + name + "-io")
    return stream
def patched_write_text(path, data, *args, **kwargs):
    # Baseline reproduction only: detect direct, potentially torn writes.
    if path.parent == output and injection == "direct-partial-" + path.name:
        write_text(path, data[:7], *args, **kwargs)
        event(injection)
    return write_text(path, data, *args, **kwargs)
Path.read_bytes, Path.mkdir, os.replace, os.fdopen, Path.write_text, os.fsync = patched_read_bytes, patched_mkdir, patched_replace, patched_fdopen, patched_write_text, patched_fsync
previous = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
set_handler = signal.signal
def patched_signal(signum, handler):
    if signum == signal.SIGINT and handler == previous[signum]:
        event("restore-handler")
    return set_handler(signum, handler)
signal.signal = patched_signal
sys.argv = ["-", str(root), str(output)]
source = read_bytes(Path(wrapper_path)).decode()
cleanup_line = next((i for i, line in enumerate(source.splitlines(), 1) if line == "    if owned:"), None)
def trace_cleanup(frame, event_name, arg):
    global second_signal
    if (injection.startswith("double-") and triggered and not second_signal
            and event_name == "line" and frame.f_code.co_filename == str(wrapper_path)
            and frame.f_lineno == cleanup_line):
        second_signal = True
        events.append("second-signal-before-cleanup-mask")
        os.kill(os.getpid(), signal.SIGINT)
    return trace_cleanup
if injection.startswith("double-"):
    sys.settrace(trace_cleanup)
try:
    exec(compile(read_bytes(Path(wrapper_path)), str(wrapper_path), "exec"), {"__name__": "__main__"})
finally:
    # Store test instrumentation separately from production output/evidence.
    sys.settrace(None)
    Path.write_text = write_text
    (root.parent / "trace.json").write_text(json.dumps({"events": events, "triggered": triggered,
        "handlers_restored": all(signal.getsignal(s) == h for s, h in previous.items())}))
'''


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux signal-mask and /proc tests")
class Frozen006ReceiptInterruptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="frozen006-receipt-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.root = self.folder / "source"
        self.root.mkdir()
        self.output = self.folder / "output"
        self.wrapper = self.folder / "workflow-inline.py"
        self.wrapper.write_text(WRAPPER)
        runner = self.root / "run_cycle006.py"
        runner.write_text(textwrap.dedent(FIXTURE_RUNNER))
        freeze = json.dumps({"sources": {"run_cycle006.py": hashlib.sha256(runner.read_bytes()).hexdigest()}}).encode()
        (self.root / "FREEZE.json").write_bytes(freeze)
        (self.root / "expected-freeze.txt").write_text(hashlib.sha256(freeze).hexdigest())
        (self.root / "mode.txt").write_text("complete")

    def launch(self, injection="", mode="complete"):
        (self.root / "mode.txt").write_text(mode)
        return subprocess.Popen([sys.executable, "-B", "-c", HARNESS, str(self.wrapper),
            str(self.root), str(self.output), str(ROOT / "experiments/resource006_v4.py"), injection],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def run_wrapper(self, injection="", mode="complete"):
        process = self.launch(injection, mode)
        stdout, stderr = process.communicate(timeout=15)
        self.trace = json.loads((self.folder / "trace.json").read_text()) if (self.folder / "trace.json").exists() else {}
        self.assertTrue(self.trace.get("handlers_restored", True), stderr)
        return process.returncode, stdout, stderr

    def assert_incomplete(self, result, phase=None):
        code, _, stderr = result
        self.assertNotEqual(code, 0, stderr)
        self.assertFalse((self.output / "COMPLETE.json").exists(), stderr)
        pending = json.loads((self.output / "PENDING.json").read_text())
        receipt = json.loads((self.output / "INTERRUPTED.json").read_text())
        self.assertEqual(pending["state"], "PENDING")
        self.assertEqual(receipt["state"], "INCOMPLETE")
        self.assertEqual(receipt["prior_v3_run"], "42083204982")
        if phase:
            self.assertEqual(receipt["phase"], phase)
        self.assertFalse(list(self.output.glob(".*.tmp")))

    def test_happy_path_verified_report_and_original_limits(self):
        result = self.run_wrapper()
        self.assertEqual(result[0], 0, result[2])
        report = (self.output / "REPORT.json").read_bytes()
        complete = json.loads((self.output / "COMPLETE.json").read_text())
        self.assertEqual(complete["report_sha256"], hashlib.sha256(report).hexdigest())
        self.assertFalse(complete["historical_v3_failure_repaired_retroactively"])
        self.assertFalse((self.output / "INTERRUPTED.json").exists())
        calls = [e for e in self.trace["events"] if isinstance(e, dict)]
        self.assertEqual(len(calls), 1)
        args = calls[0]["monitor_arguments"]
        self.assertEqual(args[4], {"wall_seconds": 360, "cpu_seconds": 240, "memory_bytes": 4 * 1024 ** 3,
            "output_bytes": 64 * 1024 ** 2, "storage_bytes": 512 * 1024 ** 2})
        self.assertEqual(args[0][1:4], ["-I", str(self.root / "run_cycle006.py"), "--worker"])
        self.assertEqual(calls[0]["cwd"], str(self.root))
        receipt = json.loads((self.output / "bounded/RECEIPT.json").read_text())
        self.assertEqual(receipt["state"], "complete")
        self.assertFalse(receipt["descendant_survivors"])
        events = self.trace["events"]
        self.assertLess(events.index("after-replace-REPORT.json"), events.index("before-replace-COMPLETE.json"))
        self.assertFalse(list(self.output.glob(".*.tmp")))

    def test_sigterm_immediately_after_mkdir_is_owned_and_receipted(self):
        self.assert_incomplete(self.run_wrapper("after-mkdir"), "claim-output")
        self.assertTrue(self.trace["triggered"])

    def test_sigterm_during_source_authentication(self):
        self.assert_incomplete(self.run_wrapper("read-freeze"), "source-authentication")
        self.assertTrue(self.trace["triggered"])

    def test_second_signal_before_cleanup_mask_cannot_abandon_source_failure(self):
        self.assert_incomplete(self.run_wrapper("double-read-freeze"), "source-authentication")
        self.assertIn("second-signal-before-cleanup-mask", self.trace["events"])

    def test_source_read_failure_is_receipted(self):
        self.assert_incomplete(self.run_wrapper("read-freeze-io"), "source-authentication")

    def test_mismatched_freeze_stops_before_worker(self):
        (self.root / "FREEZE.json").write_text("{}"); self.assert_incomplete(self.run_wrapper())
        self.assertFalse((self.output / "bounded").exists())

    def test_mismatched_runner_stops_before_worker(self):
        (self.root / "run_cycle006.py").write_text("raise RuntimeError('never execute')")
        self.assert_incomplete(self.run_wrapper()); self.assertFalse((self.output / "bounded").exists())

    def test_closure_count_still_binding(self):
        self.assert_incomplete(self.run_wrapper(mode="bad-closure")); self.assertFalse((self.output / "bounded").exists())

    def test_existing_output_and_evidence_are_untouched(self):
        self.output.mkdir()
        sentinel = self.output / "COMPLETE.json"
        sentinel.write_bytes(b"old evidence must not be changed")
        self.assertNotEqual(self.run_wrapper()[0], 0)
        self.assertEqual(sentinel.read_bytes(), b"old evidence must not be changed")
        self.assertEqual(sorted(p.name for p in self.output.iterdir()), ["COMPLETE.json"])

    def test_symlink_output_is_untouched(self):
        target = self.folder / "other-owner"
        target.mkdir()
        self.output.symlink_to(target, target_is_directory=True)
        self.assertNotEqual(self.run_wrapper()[0], 0)
        self.assertTrue(self.output.is_symlink()); self.assertEqual(list(target.iterdir()), [])

    def test_symlink_parent_is_untouched(self):
        target = self.folder / "other-owner"
        target.mkdir()
        link = self.folder / "linked-parent"
        link.symlink_to(target, target_is_directory=True)
        self.output = link / "new-output"
        self.assertNotEqual(self.run_wrapper()[0], 0)
        self.assertEqual(list(target.iterdir()), [])

    def test_partial_source_identity_write_is_never_visible(self):
        self.assert_incomplete(self.run_wrapper("partial-SOURCE_IDENTITY.json-io"))
        self.assertFalse((self.output / "SOURCE_IDENTITY.json").exists())

    def test_source_identity_promotion_sigterm(self):
        self.assert_incomplete(self.run_wrapper("after-replace-SOURCE_IDENTITY.json"))
        json.loads((self.output / "SOURCE_IDENTITY.json").read_text())

    def test_failed_worker_stays_failed_and_keeps_v4_receipt(self):
        self.assert_incomplete(self.run_wrapper(mode="fail"), "bounded-worker")
        receipt = json.loads((self.output / "bounded/RECEIPT.json").read_text())
        self.assertEqual(receipt["state"], "failed"); self.assertEqual(receipt["exit_code"], 7)

    def test_worker_report_mismatch_cannot_complete(self):
        self.assert_incomplete(self.run_wrapper(mode="mismatch"), "worker-verification")
        self.assertFalse((self.output / "REPORT.json").exists())

    def test_sigterm_after_monitor_before_verification(self):
        self.assert_incomplete(self.run_wrapper("after-monitor"), "bounded-worker")
        self.assertEqual(json.loads((self.output / "bounded/RECEIPT.json").read_text())["state"], "complete")

    def test_report_promotion_interruption(self):
        self.assert_incomplete(self.run_wrapper("after-replace-REPORT.json"), "completion-promotion")
        json.loads((self.output / "REPORT.json").read_text())

    def test_partial_complete_write_is_never_visible(self):
        self.assert_incomplete(self.run_wrapper("partial-COMPLETE.json-io"), "completion-promotion")

    def test_sigterm_before_complete_promotion(self):
        self.assert_incomplete(self.run_wrapper("before-replace-COMPLETE.json"), "completion-promotion")

    def test_sigterm_after_complete_promotion_revokes_marker(self):
        self.assert_incomplete(self.run_wrapper("after-replace-COMPLETE.json"), "completion-promotion")

    def test_second_signal_before_cleanup_mask_cannot_strand_completion(self):
        self.assert_incomplete(self.run_wrapper("double-after-replace-COMPLETE.json"), "completion-promotion")
        self.assertIn("second-signal-before-cleanup-mask", self.trace["events"])

    def test_error_after_complete_promotion_revokes_marker(self):
        self.assert_incomplete(self.run_wrapper("after-replace-COMPLETE.json-io"), "completion-promotion")

    def test_complete_file_fsync_failure_never_promotes(self):
        self.assert_incomplete(self.run_wrapper("file-fsync-COMPLETE.json-io"), "completion-promotion")

    def test_complete_directory_fsync_failure_revokes_marker(self):
        self.assert_incomplete(self.run_wrapper("directory-fsync-COMPLETE.json-io"), "completion-promotion")

    def test_complete_directory_fsync_sigterm_revokes_marker(self):
        self.assert_incomplete(self.run_wrapper("directory-fsync-COMPLETE.json"), "completion-promotion")

    def test_report_file_fsync_failure_never_promotes(self):
        self.assert_incomplete(self.run_wrapper("file-fsync-REPORT.json-io"), "completion-promotion")
        self.assertFalse((self.output / "REPORT.json").exists())

    def test_sigterm_during_failure_receipt_does_not_tear_json(self):
        self.assert_incomplete(self.run_wrapper("after-replace-INTERRUPTED.json", mode="mismatch"))

    def test_receipt_io_failure_is_reported_not_called_success(self):
        result = self.run_wrapper("partial-INTERRUPTED.json-io", mode="mismatch")
        self.assertNotEqual(result[0], 0)
        self.assertIn("CONNECTED_FAILURE_RECEIPT_ERROR", result[2])
        self.assertFalse((self.output / "COMPLETE.json").exists())
        self.assertFalse((self.output / "INTERRUPTED.json").exists())
        self.assertEqual(json.loads((self.output / "PENDING.json").read_text())["state"], "PENDING")

    def test_pending_write_failure_still_attempts_terminal_receipt(self):
        result = self.run_wrapper("partial-PENDING.json-io")
        self.assertNotEqual(result[0], 0)
        self.assertFalse((self.output / "COMPLETE.json").exists())
        self.assertFalse((self.output / "PENDING.json").exists())
        self.assertEqual(json.loads((self.output / "INTERRUPTED.json").read_text())["state"], "INCOMPLETE")

    def test_sigkill_is_explicitly_only_pending_not_terminal_guarantee(self):
        result = self.run_wrapper("read-freeze-kill")
        self.assertEqual(result[0], -signal.SIGKILL)
        self.assertFalse((self.output / "COMPLETE.json").exists())
        self.assertFalse((self.output / "INTERRUPTED.json").exists())
        self.assertEqual(json.loads((self.output / "PENDING.json").read_text())["state"], "PENDING")

    def test_cancellation_after_durable_completion_does_not_imply_ci_success(self):
        result = self.run_wrapper("restore-handler")
        self.assertNotEqual(result[0], 0)
        complete = json.loads((self.output / "COMPLETE.json").read_text())
        self.assertEqual(complete["report_sha256"], hashlib.sha256((self.output / "REPORT.json").read_bytes()).hexdigest())
        self.assertFalse((self.output / "INTERRUPTED.json").exists())

    def test_real_monitor_cancels_and_reaps_running_worker(self):
        for signum in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=signum):
                self.output = self.folder / ("signal-" + str(signum))
                process = self.launch(mode="sleep")
                try:
                    pid_file = self.output / "bounded/artifacts/worker-pid.txt"
                    deadline = time.monotonic() + 5
                    while not pid_file.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertTrue(pid_file.exists(), "fixture worker never started")
                    pid = int(pid_file.read_text())
                    process.send_signal(signum)
                    stdout, stderr = process.communicate(timeout=10)
                    self.assert_incomplete((process.returncode, stdout, stderr), "bounded-worker")
                    receipt = json.loads((self.output / "bounded/RECEIPT.json").read_text())
                    self.assertEqual(receipt["state"], "interrupted")
                    self.assertFalse(receipt["descendant_survivors"])
                    with self.assertRaises(ProcessLookupError):
                        os.kill(pid, 0)
                finally:
                    if process.poll() is None:
                        process.kill(); process.communicate()


if __name__ == "__main__":
    unittest.main(verbosity=2)
