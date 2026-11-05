"""Produce a standalone, accepted SQL/CSV package from a live SQLite source.

Ordinary SQLite online backup is the comparator and implementation. Source is
opened read-only. Only the destination snapshot is projected. No account code.
"""
import fcntl
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from enterprise078.transactional_data.operator import project, export_csv
from .contract import accept, request


def deliver(source, destination, identity, events):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    contract = request(identity, events)
    if not source.is_file() or source.is_symlink():
        raise ValueError('REGULAR_SOURCE_DATABASE_REQUIRED')
    if not destination.parent.is_dir():
        raise ValueError('EXISTING_DELIVERY_PARENT_REQUIRED')
    lock = destination.with_name(destination.name+'.publisher.lock')
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if destination.exists() or destination.is_symlink():
            raise ValueError('NEW_DELIVERY_DESTINATION_REQUIRED')
        with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=destination.parent) as tmp:
            staging = Path(tmp)/'package'; staging.mkdir()
            database, csv = staging/'delivery.sqlite', staging/'derived.csv'
            src = sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)
            dst = sqlite3.connect(database)
            try:
                src.backup(dst)
            finally:
                dst.close(); src.close()
            project(database); export_csv(database, csv)
            receipt = accept(contract, events, database, csv)
            if not receipt['accepted']:
                raise ValueError('SNAPSHOT_DOES_NOT_MATCH_COMMISSIONED_INPUT')
            (staging/'request.json').write_text(json.dumps(contract, sort_keys=True)+'\n')
            (staging/'receipt.json').write_text(json.dumps(receipt, sort_keys=True)+'\n')
            # Flush complete files before publishing the directory. Same-parent
            # rename gives all-or-nothing visibility on the supported POSIX FS.
            for p in staging.iterdir():
                with p.open('rb') as f: os.fsync(f.fileno())
            dfd = os.open(staging, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(dfd)
            finally: os.close(dfd)
            os.rename(staging, destination)
            dfd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(dfd)
            finally: os.close(dfd)
            return receipt
    finally: os.close(fd)
