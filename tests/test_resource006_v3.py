"""Independent process-level regressions for the qualified resource-wrapper revision."""
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'experiments/resource006_v3.py'
V2_SHA = '8a59559fd1d02af280719dabf6499295afd82f23a36a812d0d7c757dee82f6d5'


def live(pid):
    try:
        descriptor = os.pidfd_open(pid)
    except ProcessLookupError:
        return False
    try:
        poller = select.poll()
        poller.register(descriptor, select.POLLIN)
        return not poller.poll(0)
    finally:
        os.close(descriptor)


def cleanup(process, worker=None):
    if worker and live(worker):
        try:
            os.killpg(worker, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=5)


class ResourceV3Tests(unittest.TestCase):
    def command(self, base, worker, *, wall=2, output_bytes=131072, storage_bytes=131072):
        return [sys.executable, str(WRAPPER), '--ledger', str(base / 'ledger.json'),
                '--run-id', 'independent-regression', '--output', str(base / 'output'),
                '--wall', str(wall), '--cpu', '2', '--memory-bytes', str(128 * 1024**2),
                '--output-bytes', str(output_bytes), '--storage-bytes', str(storage_bytes),
                '--', sys.executable, '-c', worker]

    def test_frozen_v2_evidence_is_not_rewritten(self):
        self.assertEqual(hashlib.sha256((ROOT / 'experiments/resource006.py').read_bytes()).hexdigest(), V2_SHA)

    def test_actual_sigterm_supervisor_reaps_live_worker_and_records_interruption(self):
        with tempfile.TemporaryDirectory(prefix='resource-v3-signal-') as temporary:
            base = Path(temporary)
            marker = base / 'output' / 'worker.pid'
            worker = 'import os,time,pathlib;pathlib.Path(%r).write_text(str(os.getpid()));time.sleep(30)' % str(marker)
            process = subprocess.Popen(self.command(base, worker, wall=1), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            pid = None
            try:
                deadline = time.monotonic() + 4
                while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertTrue(marker.exists(), 'actual worker must have launched before supervisor termination')
                pid = int(marker.read_text())
                self.assertTrue(live(pid))
                process.send_signal(signal.SIGTERM)
                stdout, stderr = process.communicate(timeout=5)
                self.assertNotEqual(process.returncode, 0, (stdout, stderr))
                self.assertFalse(live(pid), 'supervisor termination must not leave its new-session worker alive')
                receipt = json.loads((base / 'output' / 'RECEIPT.json').read_text())
                self.assertEqual(receipt['state'], 'interrupted')
                self.assertFalse(receipt['descendant_survivors'])
            finally:
                cleanup(process, pid)

    def test_actual_pending_sigterm_after_mkdir_produces_initialization_receipt(self):
        with tempfile.TemporaryDirectory(prefix='resource-v3-initialization-') as temporary:
            base = Path(temporary)
            driver = '''
import os,signal,sys
from pathlib import Path
sys.path.insert(0, %r)
from experiments import resource006_v3 as module
output = Path(%r)
original = Path.mkdir
fired = False
def injected(self, *args, **kwargs):
    global fired
    result = original(self, *args, **kwargs)
    if self == output and not fired:
        fired = True
        os.kill(os.getpid(), signal.SIGTERM)
    return result
Path.mkdir = injected
result = module.run([sys.executable, '-c', 'raise SystemExit(0)'], output,
    Path(%r), 'initialization-signal',
    dict(wall_seconds=2,cpu_seconds=2,memory_bytes=134217728,output_bytes=131072,storage_bytes=131072))
assert fired
assert result['receipt']['state'] == 'interrupted', result
''' % (str(ROOT), str(base / 'output'), str(base / 'ledger.json'))
            result = subprocess.run([sys.executable, '-c', driver], capture_output=True, timeout=6)
            self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
            self.assertTrue((base / 'output' / 'PENDING.json').is_file())
            receipt = json.loads((base / 'output' / 'RECEIPT.json').read_text())
            self.assertEqual(receipt['state'], 'interrupted')
            self.assertFalse(receipt['descendant_survivors'])

    def test_fast_exit_storage_overrun_is_not_a_successful_cli_completion(self):
        with tempfile.TemporaryDirectory(prefix='resource-v3-fast-exit-') as temporary:
            base = Path(temporary)
            destination = base / 'output'
            worker = 'from pathlib import Path;p=Path(%r);[(p/str(i)).write_bytes(b"x"*4000) for i in range(3)]' % str(destination)
            result = subprocess.run(self.command(base, worker, output_bytes=5000, storage_bytes=10000), capture_output=True, timeout=6)
            self.assertNotEqual(result.returncode, 0, (result.stdout, result.stderr))
            receipt = json.loads((destination / 'RECEIPT.json').read_text())
            self.assertEqual(receipt['state'], 'overrun')
            self.assertGreater(receipt['output_bytes'], 10000)
            self.assertFalse(receipt['descendant_survivors'])
            ledger = json.loads((base / 'ledger.json').read_text())
            self.assertEqual(ledger['state'], 'blocked-overrun')
            self.assertNotEqual(ledger['runs']['independent-regression']['outcome'], 'complete')

    def test_terminal_storage_check_when_first_observation_already_reports_exit(self):
        with tempfile.TemporaryDirectory(prefix='resource-v3-poll-boundary-') as temporary:
            base = Path(temporary)
            driver = '''
import json,os,sys
from pathlib import Path
sys.path.insert(0, %r)
from experiments import resource006_v3 as module
original_wait4 = os.wait4
def observe_after_exit(pid, options):
    # Deterministically select the valid schedule where the first observation
    # sees the completed child. Filesystem measurements remain unmodified.
    return original_wait4(pid, 0 if options == os.WNOHANG else options)
module.os.wait4 = observe_after_exit
output = Path(%r)
worker = 'from pathlib import Path;p=Path(%%r);[(p/str(i)).write_bytes(b"x"*4000) for i in range(3)]' %% str(output)
result = module.run([sys.executable, '-c', worker], output,
    Path(%r), 'terminal-boundary',
    dict(wall_seconds=2,cpu_seconds=2,memory_bytes=134217728,output_bytes=5000,storage_bytes=10000))
assert result['receipt']['state'] == 'overrun', result
assert result['receipt']['output_bytes'] > 10000, result
assert json.loads(Path(%r).read_text())['state'] == 'blocked-overrun'
''' % (str(ROOT), str(base / 'output'), str(base / 'ledger.json'), str(base / 'ledger.json'))
            result = subprocess.run([sys.executable, '-c', driver], capture_output=True, timeout=6)
            self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))


if __name__ == '__main__':
    unittest.main()
