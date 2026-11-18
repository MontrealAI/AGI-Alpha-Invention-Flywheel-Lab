"""Run a fixed recipient on one allowlisted source snapshot and package its public files."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .store import StateError


def receive(files, script, failure_message):
    with tempfile.TemporaryDirectory(prefix="ignition-recipient-") as directory:
        root = Path(directory)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        proc = subprocess.run([sys.executable, "-IB", str(root / script), "--construct"],
                              cwd=root, env={}, capture_output=True)
        if proc.returncode:
            lines = proc.stderr.decode("utf-8", errors="replace").splitlines()
            reason = (lines[-1].removeprefix("ValueError: ") if lines and lines[-1].startswith("ValueError: ")
                      else f"recipient exit {proc.returncode}")
            raise StateError(failure_message + " " + reason[:320])
        return json.loads(proc.stdout)


def archive(files):
    output = io.BytesIO()
    with ZipFile(output, "w") as package:
        for name, content in sorted(files.items()):
            info = ZipInfo(name, (2026, 11, 17, 0, 0, 0))
            package.writestr(info, content, compress_type=ZIP_DEFLATED)
    return output.getvalue()
