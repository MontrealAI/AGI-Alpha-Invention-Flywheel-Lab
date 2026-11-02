"""Stage an exact, private Python import snapshot for historical verification.

This narrows writable-source import races. It is not a security sandbox, a
historical-source trust anchor, or authority to access an existing account.
"""
import hashlib
from pathlib import Path
import stat


def stage_verified_python_closure(root, snapshot, inventory, inventory_reader):
    root, snapshot = Path(root).absolute(), Path(snapshot).absolute()
    if not isinstance(inventory, dict) or not inventory or len(inventory) > 4000:
        raise ValueError('PINNED_HISTORICAL_FILE_INVENTORY_REQUIRED')
    if inventory_reader(root) != inventory:
        raise ValueError('PINNED_HISTORICAL_SOURCE_CHANGED_BEFORE_STAGE')
    snapshot.mkdir(mode=0o700, parents=True, exist_ok=False)
    for relative, expected in sorted(inventory.items()):
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise ValueError('PINNED_HISTORICAL_SOURCE_PATH_INVALID')
        path = Path(relative)
        if (path.is_absolute() or '..' in path.parts or path.suffix != '.py'
                or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected)):
            raise ValueError('PINNED_HISTORICAL_SOURCE_PATH_INVALID')
        original = root / path
        if original.is_symlink():
            raise ValueError('HISTORICAL_SOURCE_SYMLINK_REFUSED')
        info = original.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('PINNED_HISTORICAL_REGULAR_SOURCE_REQUIRED')
        raw = original.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('PINNED_HISTORICAL_SOURCE_CHANGED_DURING_STAGE')
        staged = snapshot / path
        staged.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with staged.open('xb') as output:
            output.write(raw)
        if hashlib.sha256(staged.read_bytes()).hexdigest() != expected:
            raise ValueError('PINNED_HISTORICAL_SNAPSHOT_WRITE_CHANGED')
        staged.chmod(0o400)
    if inventory_reader(root) != inventory or inventory_reader(snapshot) != inventory:
        raise ValueError('PINNED_HISTORICAL_SOURCE_CHANGED_AFTER_STAGE')
    return snapshot
