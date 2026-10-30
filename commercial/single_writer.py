"""Opt-in owned execution; historical commercial010 source remains unchanged.

All cooperating live owners of one account must use this entrypoint. Legacy
unguarded processes and hostile filesystem writers are outside this boundary.
"""
from pathlib import Path
import os

from .persistence import DurableTape
from .tape_lease import WriterLease


def _acquire(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('OWNED_ACCOUNT_SYMLINK_REFUSED')
    path.parent.mkdir(parents=True, exist_ok=True)
    return WriterLease(path.with_name(path.name + '.writer.lock'))


class OwnedTape(DurableTape):
    """Lease the existing tape before the unchanged constructor reads history."""
    def __init__(self, path, config, encode, decode):
        self.writer_lease = _acquire(path)
        self._closed = False
        try:
            super().__init__(path, config, encode, decode)
        except BaseException:
            self.close()
            raise

    @property
    def lease(self):
        return self.writer_lease

    def append(self, event):
        self.writer_lease.assert_owner()
        return super().append(event)

    def checkpoint(self, connection, actions):
        self.writer_lease.assert_owner()
        return super().checkpoint(connection, actions)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if hasattr(self, 'stream'):
                self.stream.close()
        finally:
            self.writer_lease.close()


class SingleWriterExchange:
    """Hold exclusive account ownership through native replay, actions and close.

    Use this facade, not OwnedTape, around commercial.ledger.TapeExchange. It retains
    all native service, finance, audit and checkpoint behavior without replacing its
    frozen persistence implementation. Work across distinct accounts may proceed in
    parallel. Sharing one account requires serialized ownership and current replay.
    """
    def __init__(self, path, **kwargs):
        self.lease = _acquire(path)
        self._closed = False
        self._exchange = None
        try:
            from .ledger import TapeExchange
            self._exchange = TapeExchange(path, **kwargs)
        except BaseException:
            self.close()
            raise

    def execute(self, op, args, day):
        self.lease.assert_owner()
        return self._exchange.execute(op, args, day)

    def export(self):
        self.lease.assert_owner()
        return self._exchange.export()

    def snapshot(self):
        self.lease.assert_owner()
        return self._exchange.ex.snapshot()

    def task(self, job_id):
        self.lease.assert_owner()
        return self._exchange.task(job_id)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self._exchange is not None and self.lease.pid == os.getpid():
                self.lease.assert_owner()
                self._exchange.close()
        finally:
            self.lease.close()

    def __enter__(self):
        self.lease.assert_owner()
        return self

    def __exit__(self, *exc):
        self.close()
