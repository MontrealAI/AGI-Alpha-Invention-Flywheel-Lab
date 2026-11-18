"""Root supervisor. All private state and backup copying runs as the application user."""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys

UNIT = "ignition-studio.service"
MARKER = Path("/run/ignition-backup/restart-required")
LOCK = Path("/srv/ignition/.deploy.lock")


def systemctl(action):
    cp = subprocess.run(["/usr/bin/systemctl", action, UNIT], capture_output=True, text=True,
                        timeout=360, check=action != "is-active")
    return cp.stdout.strip() if action == "is-active" else None


def job(action):
    fields = ("IGNITION_STATE", "IGNITION_ENVIRONMENT", "IGNITION_BACKUP_MOUNT",
              "IGNITION_BACKUP_ROOT", "IGNITION_BACKUP_DEVICE_ID")
    child_env = {key: os.environ[key] for key in fields}
    child_env.update(PATH="/usr/bin:/bin", LANG="C.UTF-8")
    subprocess.run(["/usr/sbin/runuser", "--preserve-environment", "-u", "ignition", "--",
                    "/usr/bin/python3", "-B", "-m", "ignition.backup_job", action], check=True, env=child_env)


def recover(marker, control):
    if marker.exists():
        control("start")
        if control("is-active") != "active":
            raise RuntimeError("Studio restart has not reached active; inspect the service immediately")
        marker.unlink()


def backup(marker, control, execute):
    recover(marker, control)
    # An inactive studio may have been deliberately stopped; never start it here.
    if control("is-active") != "active":
        raise RuntimeError("Studio is not active; no stop or backup attempted")
    execute("preflight")
    marker.touch(exist_ok=False)
    try:
        control("stop")
        execute("save")
    finally:
        recover(marker, control)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("backup", "recover"))
    args = parser.parse_args()
    if args.action == "recover" and not MARKER.exists():
        return
    # Provision this root-owned lock next to the deployment symlink. Both
    # release switching and backups hold the same exclusive lock.
    with LOCK.open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "recover":
            recover(MARKER, systemctl)
        else:
            backup(MARKER, systemctl, job)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
