"""Switch the service symlink, validate the running revision and restore the prior one on failure."""
import argparse
import contextlib
import fcntl
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import urlsplit


def checked_checkout(root, revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Use a full lowercase release commit")
    target = root / revision
    if target.is_symlink() or not target.is_dir():
        raise ValueError("Expected a preinstalled immutable release directory")
    def git(*args):
        return subprocess.check_output(["git", "-c", f"safe.directory={target}", "-C", str(target), *args],
                                       text=True, timeout=15).strip()
    if (git("rev-parse", "HEAD") != revision
            or git("status", "--porcelain", "--untracked-files=all")
            or not (target / "products/frontier-omega-ignition/ignition/hosted.py").is_file()):
        raise ValueError("Release checkout differs from its reviewed revision or lacks the hosted runtime")
    return target


def probe(port, host, revision, *, deadline=45):
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        try:
            with contextlib.closing(http.client.HTTPConnection("127.0.0.1", port, timeout=3)) as conn:
                conn.request("GET", "/readyz", headers={"Host": host})
                response = conn.getresponse()
                obj = json.loads(response.read(4096))
                if response.status == 200 and obj.get("status") == "ok" and obj.get("revision") == revision:
                    return
        except (OSError, ValueError, http.client.HTTPException):
            pass
        time.sleep(0.5)
    raise RuntimeError("The expected release did not become ready")


def switch(current, root, revision, restart, check):
    root, current = root.resolve(), current.absolute()
    target = checked_checkout(root, revision)
    if not current.is_symlink():
        raise ValueError("Install the first release separately; rollback requires an existing release")
    old = current.resolve(strict=True)
    if old.parent != root or checked_checkout(root, old.name) != old:
        raise ValueError("Previous target is not a verified release")
    with (current.parent / ".deploy.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if current.resolve() != old:
            raise RuntimeError("Deployment changed while acquiring the lock")
        with tempfile.TemporaryDirectory(dir=current.parent) as tmp:
            link = Path(tmp) / "next"
            def aim(to):
                link.symlink_to(to, target_is_directory=True)
                os.replace(link, current)
            check(old.name)
            aim(target)
            try:
                restart()
                check(revision)
            except BaseException:
                aim(old)
                restart()
                check(old.name)
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision")
    parser.add_argument("--releases", type=Path, default=Path("/srv/ignition/releases"))
    parser.add_argument("--current", type=Path, default=Path("/srv/ignition/current"))
    parser.add_argument("--origin", required=True)
    parser.add_argument("--port", type=int, default=8784)
    args = parser.parse_args()
    url = urlsplit(args.origin)
    if url.scheme != "https" or not url.netloc or url.path or url.username:
        parser.error("Use the approved HTTPS origin")
    switch(args.current, args.releases, args.revision,
           lambda: subprocess.run(["systemctl", "restart", "ignition-studio"], check=True, timeout=350),
           lambda rev: probe(args.port, url.netloc, rev))
    print(json.dumps({"verified_revision": args.revision}))


if __name__ == "__main__":
    main()
