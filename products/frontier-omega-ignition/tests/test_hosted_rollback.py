"""Execute the switcher against real subprocesses; explicitly inject readiness failure."""
import importlib.util
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

from ignition.store import PRODUCT

spec = importlib.util.spec_from_file_location("studio_switch_release", PRODUCT / "deploy/switch_release.py")
switcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(switcher)


class LocalRollback(unittest.TestCase):
    def test_failed_readiness_restarts_previous_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            releases = root / "releases"
            releases.mkdir()
            source = root / "source"
            source.mkdir()
            def git(*args):
                return subprocess.check_output(["git","-C",str(source),"-c","user.name=Local QA",
                                                "-c","user.email=qa@localhost",*args], text=True,
                                               stderr=subprocess.DEVNULL).strip()
            git("init")
            product = Path("products/frontier-omega-ignition")
            shutil.copytree(PRODUCT/"ignition", source/product/"ignition", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(PRODUCT/"discovery_field", source/product/"discovery_field", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(PRODUCT.parent/"alpha-genesis-harness/bridge",
                            source/"products/alpha-genesis-harness/bridge", ignore=shutil.ignore_patterns("__pycache__"))
            launcher = source/product/"qa_launch.py"
            launcher.write_text(
                "import sys\nfrom pathlib import Path\nfrom ignition.hosted import HostedService\n"
                "from ignition.hosted_auth import Access\n"
                "access=Access(Path(sys.argv[1]),'staging')\n"
                "ready=Path(__file__).with_name('ready').read_text() == 'yes'\n"
                "with HostedService(access,'https://qa.example.test',int(sys.argv[2]),ready_probe=lambda: ready) as s:\n"
                "    s.serve_forever()\n")
            mark = source/product/"ready"
            revisions = []
            for val in ("yes", "no"):
                mark.write_text(val)
                git("add",".")
                git("commit","-m","controlled "+val)
                revision = git("rev-parse","HEAD")
                revisions.append(revision)
                git("worktree","add","--detach",str(releases/revision),revision)
            before, unhealthy = revisions
            current = root/"current"
            current.symlink_to(releases/before, target_is_directory=True)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1",0))
                port = sock.getsockname()[1]
            process = None
            visits = []
            def stop():
                nonlocal process
                if process:
                    process.terminate()
                    process.wait(timeout=5)
                    process = None
            def restart():
                nonlocal process
                stop()
                visits.append(current.resolve().name)
                process = subprocess.Popen([sys.executable,"-B", "qa_launch.py",str(root/"private"),str(port)],
                                           cwd=current/product, env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"},
                                           stdout=subprocess.DEVNULL)
            def check(rev):
                switcher.probe(port,"qa.example.test",rev,deadline=1.5 if rev == unhealthy else 5)
            try:
                restart()
                with self.assertRaisesRegex(RuntimeError,"did not become ready"):
                    switcher.switch(current,releases,unhealthy,restart,check)
                self.assertEqual(visits,[before,unhealthy,before])
                self.assertEqual(current.resolve(),releases/before)
                check(before)
            finally:
                stop()
