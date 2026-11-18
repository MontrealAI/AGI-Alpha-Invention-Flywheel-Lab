"""Unprivileged half of an optional scheduled snapshot to a pinned LUKS mount."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

from .hosted_auth import private_dir
from .hosted_backup import snapshot
from .store import StateError

MARKER = ".last-verified-backup.json"


def destination(state, mount, parent, expected_device, *, sys_devices=Path("/sys/dev/block")):
    state, mount, parent = Path(state), Path(mount), Path(parent)
    if (not mount.is_absolute() or not parent.is_absolute() or mount != mount.resolve()
            or parent != parent.resolve() or not mount.is_mount() or not parent.is_dir()
            or not parent.is_relative_to(mount) or not expected_device.startswith("CRYPT-LUKS")):
        raise StateError("Use an existing private directory on the configured mounted encrypted volume")
    dev = parent.stat().st_dev
    if dev != mount.stat().st_dev or dev == state.stat().st_dev:
        raise StateError("Backup destination must be on the separate pinned volume")
    device = sys_devices / f"{os.major(dev)}:{os.minor(dev)}" / "dm" / "uuid"
    if device.read_text().strip() != expected_device:
        raise StateError("Mounted encrypted volume differs from the enrolled device")
    return private_dir(parent)


def record(state, environment, name, files):
    with tempfile.NamedTemporaryFile(mode="w", dir=state, prefix=".backup-receipt-", delete=False) as handle:
        tmp = Path(handle.name)
        try:
            json.dump(dict(finished=int(time.time()), environment=environment,
                           snapshot=name, verified_files=files), handle, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, state / MARKER)
    finally:
        tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "save"))
    args = parser.parse_args()
    os.umask(0o077)
    state = Path(os.environ["IGNITION_STATE"])
    environment = os.environ["IGNITION_ENVIRONMENT"]
    if environment not in ("staging", "production") or not (state / "access.sqlite3").is_file():
        raise StateError("Select the existing hosted state")
    folder = destination(state, Path(os.environ["IGNITION_BACKUP_MOUNT"]),
                         Path(os.environ["IGNITION_BACKUP_ROOT"]), os.environ["IGNITION_BACKUP_DEVICE_ID"])
    if args.action == "save":
        # Pin the approved volume across the copy. A lazy unmount cannot
        # redirect descriptor-relative writes to an underlying plaintext disk.
        fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        with contextlib.ExitStack() as stack:
            stack.callback(os.close, fd)
            confirmed = destination(state, Path(os.environ["IGNITION_BACKUP_MOUNT"]), folder, os.environ["IGNITION_BACKUP_DEVICE_ID"])
            if not os.path.samestat(os.fstat(fd), confirmed.stat()):
                raise StateError("Backup directory changed during verification")
            name = f"{environment}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:8]}"
            files = snapshot(state, Path(f"/proc/self/fd/{fd}") / name, environment, parent_fd=fd)
            destination(state, Path(os.environ["IGNITION_BACKUP_MOUNT"]), folder, os.environ["IGNITION_BACKUP_DEVICE_ID"])
        record(state, environment, name, files)
        print(json.dumps({"verified_files":files}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as exc:
        sys.exit(str(exc))
