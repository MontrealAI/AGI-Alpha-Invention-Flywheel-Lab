"""Offline, verified snapshots and restores into new private directories."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time

from .hosted_auth import Access, private_dir
from .store import StateError


@contextlib.contextmanager
def exclusive(root, *, shared=False, lockfile=".maintenance.lock"):
    with (root / lockfile).open("a+b") as file:
        try:
            fcntl.flock(file.fileno(), (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise StateError("Stop the service or other maintenance before continuing") from None
        yield


def inventory(root):
    files = {}
    for item in sorted(root.rglob("*")):
        if item.is_symlink():
            raise StateError("Private state cannot include symbolic links")
        if item.name.endswith(".lock") or item == root / "SNAPSHOT.json" or item.is_dir():
            continue
        if not item.is_file():
            raise StateError("Snapshot contains a special file")
        digest = hashlib.sha256()
        with item.open("rb") as infile:
            for block in iter(lambda: infile.read(1024 * 1024), b""):
                digest.update(block)
        files[item.relative_to(root).as_posix()] = digest.hexdigest()
        if item.suffix == ".sqlite3":
            with contextlib.closing(sqlite3.connect(item.as_uri() + "?mode=ro", uri=True)) as db:
                if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise StateError("SQLite integrity check failed")
    if "access.sqlite3" not in files:
        raise StateError("Expected a hosted state directory")
    return files


def snapshot(source, destination, environment, *, restore=False):
    source, destination = Path(source).resolve(), Path(destination).absolute()
    if not source.is_dir() or destination.exists() or destination.is_symlink():
        raise StateError("Source must exist and destination must be new")
    parent = private_dir(destination.parent)
    if parent == source or parent.is_relative_to(source):
        raise StateError("Use a separate private parent for the destination")
    with exclusive(private_dir(source)):
        entries = inventory(source)
        if restore:
            manifest = json.loads((source / "SNAPSHOT.json").read_text())
            if manifest != {"format": 1, "environment": environment, "files": entries}:
                raise StateError("Snapshot environment, content or digest failed verification")
        elif (source / "SNAPSHOT.json").exists():
            raise StateError("Use the service state as backup source")
        with contextlib.closing(sqlite3.connect((source / "access.sqlite3").as_uri()+"?mode=ro", uri=True)) as db:
            if db.execute("SELECT env FROM setting WHERE id=1").fetchone() != (environment,):
                raise StateError("Source environment differs")
        with tempfile.TemporaryDirectory(dir=parent) as stage_dir:
            stage = Path(stage_dir) / "state"
            stage.mkdir(mode=0o700)
            for key in entries:
                target = stage / key
                directory = stage
                for component in Path(key).parts[:-1]:
                    directory /= component
                    directory.mkdir(mode=0o700, exist_ok=True)
                shutil.copy2(source / key, target)
            if inventory(stage) != entries:
                raise StateError("Snapshot copy differs")
            if restore:
                access = Access(stage, environment)
                with access.connection() as db:
                    db.execute("DELETE FROM sessions")
                    db.execute("DELETE FROM invitations")
                    access.record(db, int(time.time()), "restore-credentials-invalidated", None)
            else:
                (stage / "SNAPSHOT.json").write_text(json.dumps(
                    {"format": 1, "environment": environment, "files": entries}, sort_keys=True))
            os.rename(stage, destination)
    return len(entries)
