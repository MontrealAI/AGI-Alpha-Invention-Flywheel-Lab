import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from verification.cycle006_active_interrupt import proc_state, termination_observation, verify_sources, worker_identity


class KernelInterruptionTests(unittest.TestCase):
    def test_stopped_live_worker_cannot_be_mistaken_for_exited_worker(self):
        with tempfile.TemporaryDirectory(prefix='cycle006-kernel-negative-') as temporary:
            marker = Path(temporary) / 'unique-output'
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)',
                'run_cycle.py', '--worker', '--output', str(marker)],
                env={'PATH': os.defpath, 'LANG': 'C.UTF-8'})
            pidfd = None
            try:
                identity, deadline = None, time.monotonic() + 3
                while time.monotonic() < deadline and identity is None:
                    identity = worker_identity(marker)
                    time.sleep(.002)
                self.assertIsNotNone(identity)
                self.assertEqual(identity['namespace_pid'], child.pid)
                pidfd = os.pidfd_open(child.pid)
                signal.pidfd_send_signal(pidfd, signal.SIGSTOP)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    if proc_state(identity['host_pid'])['state'] in ('T', 't'):
                        break
                    time.sleep(.002)
                alive = termination_observation(pidfd, identity, 0)
                self.assertFalse(alive['exit_ready'])
                self.assertFalse(alive['not_live'])
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                child.wait(timeout=3)
                exited = termination_observation(pidfd, identity, 1000)
                self.assertTrue(exited['exit_ready'])
                self.assertTrue(exited['not_live'])
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=3)
                if pidfd is not None:
                    os.close(pidfd)

    def test_corrupted_old_freeze_refuses_before_worker_effect(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            freeze = root / 'campaign/cycle-004/FREEZE.json'
            freeze.parent.mkdir(parents=True)
            freeze.write_text('{"sources": {}}')
            with self.assertRaisesRegex(ValueError, 'HISTORICAL_FREEZE_IDENTITY_MISMATCH'):
                verify_sources(root)


if __name__ == '__main__':
    unittest.main()
