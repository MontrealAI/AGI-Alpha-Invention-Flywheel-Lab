"""Small data and publication helpers. This module is not a financial ledger."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def strict_loads(data: bytes | str) -> Any:
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('DUPLICATE_JSON_KEY:' + key)
            out[key] = value
        return out
    def reject(value):
        raise ValueError('NONFINITE_JSON_NUMBER:' + value)
    return json.loads(data, object_pairs_hook=pairs, parse_constant=reject)


def read(path: Path) -> Any:
    p = regular(path)
    if p.stat().st_size > 32_000_000:
        raise ValueError('INPUT_EXCEEDS_DECLARED_32MB_FILE_LIMIT')
    return strict_loads(p.read_bytes())


def regular(path: Path) -> Path:
    p = Path(os.path.abspath(path))
    if any(q.is_symlink() for q in (p, *p.parents)):
        raise ValueError('SYMLINK_REFUSED')
    if p.exists() and not p.is_file():
        raise ValueError('REGULAR_FILE_REQUIRED')
    return p


def write(path: Path, value: Any, *, immutable: bool = False) -> None:
    p = regular(path)
    data = canonical(value) + b'\n'
    if p.exists() and immutable:
        if p.read_bytes() != data:
            raise ValueError('IMMUTABLE_RECORD_CHANGED:' + p.name)
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.genesis-', dir=p.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, p)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def integer(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError('INVALID_INTEGER:' + field)
    return value


def text(value: Any, field: str, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('INVALID_TEXT:' + field)
    return value


def package_identity() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.py'))}
