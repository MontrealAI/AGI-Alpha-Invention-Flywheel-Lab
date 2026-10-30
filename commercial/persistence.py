"""I/O repair: unchanged native SQL rules in memory, fsynced action authority.

The native source is hash-pinned elsewhere. Only its constructor's sqlite I/O
namespace is briefly routed to an in-memory connection; SQL, receipts, finance
and investment admission are unchanged. No live SQLite journal uses scratch.
"""
import hashlib
import importlib
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import types

_LOCK = threading.RLock()


def memory_engine(Engine, **kwargs):
    module = importlib.import_module(Engine.__module__)
    with tempfile.TemporaryDirectory(prefix='commercial010-memory-constructor-') as tmp:
        placeholder = Path(tmp) / 'native-placeholder.sqlite'
        placeholder.touch(mode=0o600, exist_ok=False)
        with _LOCK:
            original = module.sqlite3
            def connect(path, *args, **options):
                target = ':memory:' if os.fspath(path) == str(placeholder) else path
                return original.connect(target, *args, **options)
            module.sqlite3 = types.SimpleNamespace(connect=connect, Row=original.Row)
            try:
                instance = Engine(placeholder, **kwargs)
            finally:
                module.sqlite3 = original
    if any(row[2] for row in instance.db.execute('PRAGMA database_list')):
        instance.close()
        raise ValueError('NATIVE_DATABASE_MUST_BE_IN_MEMORY')
    return instance


def atomic_bytes(path, raw):
    path = Path(path).absolute()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('PERSISTENCE_SYMLINK_REFUSED')
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name + '-pending-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink()
            raise
    try:
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()
    if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(raw).digest():
        raise ValueError('PERSISTENCE_READBACK_IDENTITY_MISMATCH')


class DurableTape:
    def __init__(self, path, config, encode, decode):
        self.path = Path(path).absolute()
        self.tape = self.path.with_name(self.path.name + '.actions.jsonl')
        self.proof = self.path.with_name(self.path.name + '.persistence.json')
        self.encode, self.decode, self.config = encode, decode, config
        self.failed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if any(p.is_symlink() for p in [self.path, self.tape, self.proof, *self.path.parents]):
            raise ValueError('PERSISTENCE_SYMLINK_REFUSED')
        header = {'schema': 'agi-alpha/commercial010-durable-actions/v1', 'config': config}
        self.recovery_actions = []
        if self.tape.exists():
            raw = self.tape.read_bytes()
            if len(raw) > 64000000 or not raw.endswith(b'\n'):
                raise ValueError('INCOMPLETE_OR_OVERSIZED_DURABLE_TAPE; ORIGINAL_PRESERVED')
            rows = [decode(line) for line in raw.splitlines()]
            if not rows or rows[0] != header:
                raise ValueError('DURABLE_TAPE_CONFIGURATION_MISMATCH')
            self.recovery_actions = rows[1:]
        elif self.path.exists():
            raise ValueError('LEGACY_DATABASE_REQUIRES_EXTERNALLY_QUALIFIED_ACTION_TAPE')
        else:
            with self.tape.open('xb') as stream:
                stream.write(encode(header) + b'\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(self.tape, 0o600)
        self.stream = self.tape.open('ab')

    def append(self, event):
        if self.failed:
            raise ValueError('DURABILITY_FAILURE_REQUIRES_RECOVERY')
        try:
            self.stream.write(self.encode(event) + b'\n')
            self.stream.flush()
            os.fsync(self.stream.fileno())
        except BaseException:
            self.failed = True
            raise

    def checkpoint(self, connection, actions):
        if self.failed:
            raise ValueError('FAILED_ACTION_TAPE_CANNOT_QUALIFY_CHECKPOINT')
        raw = connection.serialize()
        verifier = sqlite3.connect(':memory:')
        try:
            verifier.deserialize(raw)
            if verifier.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('SERIALIZED_NATIVE_DATABASE_FAILED_INTEGRITY')
        finally:
            verifier.close()
        # Existing checkpoints are never used as recovery authority. If one is
        # corrupt, preserve its exact bytes before replacing from checked tape.
        preserved = None
        if self.path.exists():
            old = self.path.read_bytes()
            probe = sqlite3.connect(':memory:')
            corrupt = False
            try:
                probe.deserialize(old)
                corrupt = probe.execute('PRAGMA integrity_check').fetchall() != [('ok',)]
            except sqlite3.DatabaseError:
                corrupt = True
            finally:
                probe.close()
            if corrupt:
                preserved = self.path.with_name(self.path.name + '.corrupt-' + hashlib.sha256(old).hexdigest())
                if preserved.exists():
                    if preserved.read_bytes() != old:
                        raise ValueError('CORRUPT_EVIDENCE_IDENTITY_COLLISION')
                else:
                    with preserved.open('xb') as stream:
                        stream.write(old)
                        stream.flush()
                        os.fsync(stream.fileno())
        atomic_bytes(self.path, raw)
        proof = {'schema': 'agi-alpha/commercial010-memory-persistence/v1',
                 'scope': 'SIMULATED_ENGINEERING_IO_REPAIR', 'native_financial_algorithm_changed': False,
                 'live_database': ':memory:', 'action_count': len(actions),
                 'actions_sha256': hashlib.sha256(self.encode(actions)).hexdigest(),
                 'tape_sha256': hashlib.sha256(self.tape.read_bytes()).hexdigest(),
                 'checkpoint_sha256': hashlib.sha256(raw).hexdigest(), 'integrity_check': 'ok',
                 'corrupt_checkpoint_preserved': str(preserved) if preserved else None,
                 'durability': 'Each acknowledged canonical action is fsynced; final serialize/deserialization/integrity-check and atomic fsync/readback publication. The JSONL tape is recovery authority, not the checkpoint.'}
        atomic_bytes(self.proof, self.encode(proof) + b'\n')

    def close(self):
        self.stream.close()
