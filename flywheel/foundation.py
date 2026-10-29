"""Small source-pinned adapter to Alpha's unchanged structural evidence contracts."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_COMMIT = "a6b2d869a7736e7c414d7d615d86c616c2f82615"
PINS = {
    "vendor/alpha_structure/contracts.py": "26caa51dad283d55023ce6605528ef1366153a8cfe3e9657e2b6ac9f012370ee",
    "vendor/alpha_structure/LICENSE": "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
}


def _engine():
    captured = {}
    for relative, expected in PINS.items():
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("PINNED_STRUCTURE_SOURCE_MISMATCH " + relative)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("PINNED_STRUCTURE_SOURCE_MISMATCH " + relative)
        captured[relative] = raw
    module = ModuleType("_lab_pinned_alpha_structure")
    source = "vendor/alpha_structure/contracts.py"
    exec(compile(captured[source], str(ROOT / source), "exec"), module.__dict__)
    return module


def canonical(value):
    return _engine().canonical(value)


def digest(value):
    return _engine().digest(value)


def write_new(path, value):
    return _engine().write_new(Path(path), value)


def strict_acceptance(verdict, task_id, artifact_hash):
    return _engine().strict_acceptance(verdict, task_id, artifact_hash)


def qualify():
    engine = _engine()
    artifact = {"schema": "lab/foundation-boundary/v1", "quantity": "3/2"}
    identity = engine.digest(artifact)
    verdict = {"accepted": True, "task_id": "foundation-boundary", "artifact_hash": identity}
    engine.strict_acceptance(verdict, "foundation-boundary", identity)
    return {"upstream_commit": UPSTREAM_COMMIT, "source_sha256": dict(PINS),
            "executed": ["canonical", "digest", "strict_acceptance"],
            "artifact_hash": identity, "accepted": True,
            "scope": "Exact evidence identity and inert records; no discovery or scientific truth claim."}
