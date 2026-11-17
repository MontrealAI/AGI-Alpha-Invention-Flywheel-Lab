"""Build a compact source kit from a fixed allowlist; never package runtime data."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "frontier_omega/__init__.py", "frontier_omega/core.py",
    "frontier_omega/releases.py", "frontier_omega/workbench.py",
    "frontier_omega/workbench.html", "start_frontier.py",
    "tests/test_frontier_workbench.py", "scripts/package_frontier_workbench.py",
    "examples/frontier-omega/public-opportunities-20261116.json",
    "examples/frontier-omega/expanded-opportunities-20261116.json",
    "examples/frontier-omega/workbench-release-sources.json",
    "docs/frontier-omega/WORKBENCH.md",
)
BASE = "277605490464431bc989752c08f6f39320871b12"


def build(output):
    output = Path(output)
    if output.exists():
        raise ValueError("NEW_OUTPUT_PATH_REQUIRED")
    files = {}
    for name in FILES:
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("MISSING_OR_LINKED_SOURCE: " + name)
        files[name] = path.read_bytes()
    files["START-HERE.md"] = (
        "# FRONTIER Ω — Capturing the Exponential\n\n"
        "Run: `python3 start_frontier.py`\n\n"
        "Optional approved source monitoring: `python3 start_frontier.py --monitor`\n\n"
        "Requires Python 3.10+ on POSIX. Tested Linux; no model API key or runtime "
        "package installation. Data remains in your private local state folder. "
        "Keep the process running to keep the workbench active.\n\n"
        "Read docs/frontier-omega/WORKBENCH.md. The 12 public dossiers are "
        "unqualified opportunity hypotheses, not confirmed buyers or profitable crossings.\n"
    ).encode("utf-8")
    manifest = {
        "schema": "frontier-omega/workbench-source-kit/v1",
        "upstream_base_commit": BASE,
        "scope": "Source identity, not independent certification or production qualification",
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())},
    }
    files["SOURCE-MANIFEST.json"] = json.dumps(manifest, indent=2, sort_keys=True).encode()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 16, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    return {"archive": str(output), "files": len(files), "bytes": output.stat().st_size,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    print(json.dumps(build(p.parse_args().output), indent=2))
