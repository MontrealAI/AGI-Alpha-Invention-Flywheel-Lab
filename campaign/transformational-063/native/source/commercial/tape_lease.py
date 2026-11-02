"""Exclusive local POSIX ownership for one native-exchange recovery tape.

A cooperative local-filesystem lock, not a distributed lease or an authority
credential. Keep the lock inode permanently: unlinking it can split ownership.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path
import stat


class WriterLease:
    def __init__(self, path):
        self.path = Path(path).absolute()
        self.pid = os.getpid()
        self.fd = None
        try:
            import fcntl
        except ImportError as exc:
            raise ValueError('LOCAL_POSIX_WRITER_LEASE_REQUIRED') from exc
        flags = os.O_RDWR | os.O_CREAT | os.O_NONBLOCK | getattr(os, 'O_CLOEXEC', 0)
        if not hasattr(os, 'O_NOFOLLOW'):
            raise ValueError('NOFOLLOW_WRITER_LEASE_REQUIRED')
        descriptor = os.open(self.path, flags | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('SINGLE_REGULAR_LEASE_FILE_REQUIRED')
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno in (errno.EACCES, errno.EAGAIN):
                    raise ValueError('TAPE_ALREADY_OWNED') from exc
                raise
            self.fd = descriptor
            self.assert_owner()
        except BaseException:
            self.fd = None
            os.close(descriptor)
            raise

    def assert_owner(self):
        if self.fd is None or os.getpid() != self.pid:
            raise ValueError('TAPE_WRITER_LEASE_NOT_OWNED')
        opened, named = os.fstat(self.fd), self.path.lstat()
        if (not stat.S_ISREG(named.st_mode) or opened.st_nlink != 1 or named.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)):
            raise ValueError('TAPE_WRITER_LEASE_IDENTITY_CHANGED')

    def close(self):
        if self.fd is not None:
            descriptor, self.fd = self.fd, None
            # Close, never LOCK_UN: a forked child's close must not unlock its parent.
            os.close(descriptor)
