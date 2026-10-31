"""Admission checks only. Never authenticates evidence or grants financial authority."""
from __future__ import annotations
import os
from pathlib import Path
from .readout import EvidenceError, canonical


def benefit_members(synergies, action_ids):
    """A bookkeeping provision is a cost dependency, never a productive benefit member."""
    if type(synergies) is not list or len(synergies) > 128:
        raise EvidenceError('BOUNDED_PRODUCTIVE_SYNERGIES_REQUIRED')
    for benefit in synergies:
        if type(benefit) is not dict:
            raise EvidenceError('PRODUCTIVE_BENEFIT_OBJECT_REQUIRED')
        members = benefit.get('members')
        if (type(members) is not list or not 2 <= len(members) <= 16
                or any(type(x) is not str for x in members)
                or len(set(members)) != len(members)
                or not set(members) <= action_ids):
            raise EvidenceError('BENEFITS_REQUIRE_ORIGINAL_PRODUCTIVE_ACTIONS')


def same_canonical(actual, expected):
    """JSON booleans, integers and floats are distinct, unlike Python dict equality."""
    try:
        return canonical(actual) == canonical(expected)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return False


def fresh_output(value, enterprise=None):
    """Reject unsafe/overlapping export destinations before executing trusted source."""
    target = Path(value).expanduser().absolute()
    if (target.exists() or target.is_symlink() or not target.parent.is_dir()
            or any(p.is_symlink() for p in target.parents)
            or '..' in target.parts):
        raise EvidenceError('FRESH_NORMAL_OUTPUT_DIRECTORY_REQUIRED')
    if enterprise is not None:
        source = Path(enterprise).expanduser().absolute()
        if (not source.is_dir() or any(p.is_symlink() for p in [source, *source.parents])
                or '..' in source.parts):
            raise EvidenceError('TRUSTED_NORMAL_ENTERPRISE_REQUIRED')
        source, target = source.resolve(), target.resolve()
        if source == target or source in target.parents or target in source.parents:
            raise EvidenceError('EXPORT_MUST_BE_OUTSIDE_NATIVE_ENTERPRISE')
    return target


def write_new(path, data):
    """Create-only public artifact; callers must first admit its enclosing directory."""
    with Path(path).open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
