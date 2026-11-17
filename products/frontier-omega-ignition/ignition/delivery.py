"""Build a self-contained, source-checked local delivery. No network or generated code."""

import hashlib
import io
import json
import zipfile
from pathlib import Path

from .construction import ConstructionError, canonical
from .evaluation import check_receipt_integrity, evaluate
from .portable import MEMBERS, semantic_receipt


def _json(data):
    return json.dumps(data, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False).encode() + b"\n"


def export_bundle(contract, artifact, receipt, context=None):
    """Only export current verified artifacts. Evidence belongs to the requesting mission."""
    check_receipt_integrity(receipt)
    fresh = evaluate(contract, artifact)
    if fresh["status"] != "pass" or canonical(semantic_receipt(receipt)) != canonical(semantic_receipt(fresh)):
        raise ConstructionError("stale_receipt", "delivery requires matching independently reproduced acceptance")
    here = Path(__file__).resolve().parent
    first_case = next(c for c in contract["spec"]["cases"] if "expected" in c)
    readme = """FRONTIER Ω IGNITION | MONTREAL.AI × QUEBEC.AI

This package contains a mission-specific, data-only program and the trusted Python
interpreter and independent comparator that ran it. Use Python 3.10 or newer.
Extract the ZIP into a fresh private directory. Run these commands there:

    python3 -I run.py verify
    python3 -I run.py run < example-input.json

For a new input, replace example-input.json with a file using the same JSON
envelope. A rejected input returns a nonzero exit code and a diagnostic on stderr.
The verifier re-executes positive cases, controls and the conventional comparator.
Review contract.json for exact input policies and acceptance. See artifact.json
for the executable program, receipt.json for observations, and context.json for
the provenance supplied by the parent mission. The interpreter supports no file
reads, network, package installation, subprocesses or tool calls from a program.
Only the fixed CLI reads this package and the input you explicitly select.

The issued receipt records local acceptance within this frozen scope. A test of
a digest against a manifest assumes an independently trusted manifest. SHA-256
identifies bytes; it does not establish publisher identity or the truth of claims.
Check the archive digest through a trusted channel before executing the package.
An operator could replace a manifest and contents together. Local verification
is not an external audit or evidence of an economic frontier crossing.

This private delivery can contain mission data and acceptance inputs. Use and
redistribute only under applicable rights; possession does not grant publishing
rights to customer material or any licence to the surrounding repository.
"""
    if artifact["kind"] == "manifest_audit":
        readme += """
AUDIT A RECEIVED DIRECTORY

    python3 -I run.py audit-directory /path/to/received-release

Run against a stable, unpacked directory you control. Output lists matched,
changed, missing and unexpected files in sorted order. Exit codes are 0 for
an exact match, 1 for differences, and 2 for an invalid or changing input.
The runner uses POSIX directory descriptors, refuses symlinks (including in
the selected path), special files, multiply linked files, different-device
entries and unsafe logical names. It streams expected regular files in 1 MiB
chunks. Unexpected file bytes are never opened. Empty directories carry no
manifest identity. The limit is 256 regular files and 512 directories. It
never creates, unpacks or changes any item in the selected directory.
"""
    else:
        readme += """
MIGRATE A JSON LINES STREAM

    python3 -I run.py migrate-jsonl < incoming.jsonl > transformed.jsonl

Supply one UTF-8 JSON row object per line. Output preserves input order and
writes one migrated row per line. The 2 MiB line limit includes its terminator,
and the normal 2 MiB wrapped input/output limits also apply. Empty streams
succeed. Blank lines, invalid or repeated JSON keys and invalid rows fail.
On the first rejected line the command stops with exit 2; stderr gives its
1-based line number and the number of rows already written. Prior output is
a valid partial prefix. When all-or-nothing file replacement is required,
write a new temporary result and move it into place only after exit 0. The
existing 'run' command validates one complete JSON batch before any output.
"""
    files = {"README.txt": readme.encode(), "artifact.json": _json(artifact), "context.json": _json(context or {}),
             "contract.json": _json(contract), "example-input.json": _json(first_case["input"]),
             "receipt.json": _json(receipt), "run.py": (here / "portable.py").read_bytes(),
             "ignition/__init__.py": b'"""Portable FRONTIER OMEGA execution and evaluation."""\n'}
    for name in ("construction", "evaluation"):
        files[f"ignition/{name}.py"] = (here / f"{name}.py").read_bytes()
    if set(files) != set(MEMBERS):
        raise RuntimeError("portable entrypoint and export member lists disagree")
    files["SHA256SUMS.json"] = _json({k: hashlib.sha256(v).hexdigest() for k, v in files.items()})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()
