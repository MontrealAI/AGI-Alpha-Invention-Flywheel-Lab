import hashlib
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from flywheel.sandbox import qualify, run


class SandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qualification = qualify()

    def interpreter(self, source, payload=None, **kwargs):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "interpreter.py"
            path.write_text(source)
            return run(path, "execute", payload, hashlib.sha256(path.read_bytes()).hexdigest(), **kwargs)

    def test_real_effect_and_resource_qualification(self):
        self.assertTrue(self.qualification["qualified"], json.dumps(self.qualification))
        self.assertEqual(len(self.qualification["probes"]), 10)

    def test_json_strategy_executes_inside_filter(self):
        receipt = self.interpreter("def execute(p):\n return {'value': sum(p['values'])}\n", {"values": [3, 7]})
        self.assertEqual(receipt["state"], "COMPLETE", receipt)
        self.assertEqual(receipt["worker"]["result"], {"value": 10})
        self.assertEqual(receipt["worker"]["confinement"], "linux-seccomp-default-deny")

    def test_module_initialization_is_also_confined(self):
        receipt = self.interpreter("open('/etc/passwd').read()\ndef execute(p):\n return True\n")
        self.assertEqual(receipt["state"], "FAILED", receipt)
        self.assertIn("PermissionError", receipt["stderr"])

    def test_corrupt_source_refuses_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "interpreter.py"
            path.write_text("raise Exception('MUST_NOT_RUN')\n")
            with self.assertRaisesRegex(ValueError, "SOURCE_IDENTITY_MISMATCH"):
                run(path, "execute", {}, "0" * 64)

    def test_symlink_refuses(self):
        with tempfile.TemporaryDirectory() as folder:
            source, link = Path(folder) / "source.py", Path(folder) / "link.py"
            source.write_text("def execute(p): return p\n")
            link.symlink_to(source)
            with self.assertRaisesRegex(ValueError, "SOURCE_SYMLINK"):
                run(link, "execute", {}, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_program_output_and_time_are_bounded(self):
        output = self.interpreter("def execute(p):\n while True: print('x'*8192, flush=True)\n", limits={"output_bytes": 4096})
        self.assertEqual(output["state"], "OUTPUT_LIMIT", output)
        self.assertLessEqual(output["stdout_bytes"] + output["stderr_bytes"], 4096)
        timed = self.interpreter("def execute(p):\n while True: pass\n", limits={"wall_seconds": 0.2})
        self.assertEqual(timed["state"], "WALL_LIMIT", timed)

    def test_no_credentials_in_worker_environment(self):
        receipt = self.interpreter("import os\ndef execute(p):\n return dict(os.environ)\n")
        self.assertEqual(receipt["worker"]["result"], {})

    def test_new_unknown_or_excessive_limits_refuse(self):
        source = "def execute(p): return p\n"
        for limits in ({"network": True}, {"cpu_seconds": 31}, {"memory_bytes": 2**31}, {"cpu_seconds": 0.2}):
            with self.assertRaises(ValueError):
                self.interpreter(source, limits=limits)

    def test_supervisor_death_terminates_worker(self):
        libc = ctypes.CDLL(None)
        old_subreaper = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(old_subreaper), 0, 0, 0), 0)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "interpreter.py"
            source.write_text("def execute(p):\n while True: pass\n")
            program = ("import flywheel.sandbox as s\noriginal=s.subprocess.Popen\n"
                       "def launch(*a,**kw):\n p=original(*a,**kw)\n print(p.pid,flush=True)\n return p\n"
                       "s.subprocess.Popen=launch\ns.run(%r, 'execute', {}, %r, {'cpu_seconds': 10, 'wall_seconds': 20})\n") % (str(source), hashlib.sha256(source.read_bytes()).hexdigest())
            supervisor = subprocess.Popen([sys.executable, "-c", program], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            child = None
            terminated = False
            try:
                child = int(supervisor.stdout.readline())
                time.sleep(0.2)
                supervisor.kill()
                supervisor.wait(timeout=2)
                for _ in range(100):
                    reaped, status = os.waitpid(child, os.WNOHANG)
                    if reaped == child:
                        terminated = True
                        break
                    time.sleep(0.01)
                self.assertTrue(terminated, 'Worker survived its killed supervisor')
            finally:
                if supervisor.poll() is None:
                    supervisor.kill()
                    supervisor.wait(timeout=2)
                if child is not None and not terminated:
                    try:
                        os.kill(child, signal.SIGKILL)
                        os.waitpid(child, 0)
                    except ProcessLookupError:
                        pass
                supervisor.stdout.close()
                libc.prctl(36, old_subreaper.value, 0, 0, 0)


if __name__ == "__main__":
    unittest.main()
