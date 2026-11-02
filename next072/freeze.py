"""Bind execution to an immutable public source-map document."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FREEZE_RELATIVE = "experiments/next_series_20261102/FREEZE.json"
PREREG_RELATIVE = "experiments/next_series_20261102/PREREG_K1.md"
PREFLIGHT_RELATIVE = "experiments/next_series_20261102/DEVELOPMENT_RECEIPT.json"
REQUIRED_PATHS = {
    ".github/workflows/next072.yml", "requirements-next072.txt",
    "next072/__init__.py", "next072/data.py", "next072/evaluate.py",
    "next072/freeze.py", "next072/policy.py", "next072/protocol.py", "next072/plot_results.py",
    "next072/run.py", "next072/test_experiment.py", "next072/independent_verify.py",
    "next072/test_independent_verify.py",
    "next072/economic_check.py",
    PREREG_RELATIVE, PREFLIGHT_RELATIVE, "experiments/next_series_20261102/INDEPENDENT_PREREG.md",
    "experiments/next_series_20261102/ECONOMIC_ADVERSARY.md",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_freeze(repository: Path, manifest: Path | None = None) -> dict:
    repository = repository.resolve()
    manifest = manifest or repository / FREEZE_RELATIVE
    data = json.loads(manifest.read_text())
    if data.get("schema") != 1 or data.get("experiment_id") != "NEXT072-20261102":
        raise ValueError("Unrecognized public source freeze")
    files = data.get("files", {})
    if not isinstance(files, dict) or not REQUIRED_PATHS.issubset(files):
        raise ValueError("Source freeze omits a required constructor/verifier/contract file")
    actual = {}
    for relative, expected in files.items():
        if not isinstance(relative, str) or not (relative.startswith(("next072/", "experiments/next_series_20261102/")) or relative in {".github/workflows/next072.yml", "requirements-next072.txt"}):
            raise ValueError("Source freeze contains an unowned path")
        path = (repository / relative).resolve()
        if not path.is_relative_to(repository) or relative == FREEZE_RELATIVE:
            raise ValueError("Invalid source-map path or circular freeze identity")
        actual[relative] = digest(path)
        if actual[relative] != expected:
            raise ValueError(f"Frozen source mismatch: {relative}")
    if data.get("prereg_sha256") != actual[PREREG_RELATIVE]:
        raise ValueError("Preregistration digest does not match the source map")
    return {"freeze_document_sha256": digest(manifest), "actual_code_and_contract_hashes": actual}


def write_prospective_freeze(repository: Path):
    """Coordinator uses this once all independent prospective files are ready."""
    paths = set(REQUIRED_PATHS)
    for relative in (
        "next072/README.md", "next072/.gitignore", "next072/THIRD_PARTY_NOTICES.md",
        "experiments/next_series_20261102/SELECTION.md",
        "experiments/next_series_20261102/DEPENDENCY_DECISIONS.md",
        "experiments/next_series_20261102/SOURCES.json",
    ):
        if (repository / relative).exists():
            paths.add(relative)
    files = {relative: digest(repository / relative) for relative in sorted(paths)}
    data = {
        "schema": 1, "experiment_id": "NEXT072-20261102",
        "status": "prospective_before_measurement_retrieval",
        "public_commit_supplied_separately": True,
        "prereg_sha256": files[PREREG_RELATIVE], "files": files,
        "registered_primary_recipe": {
            "command_template": "python -m next072.run --execution-kind registered_confirmation --freeze PUBLIC_FREEZE_COMMIT --download --workbook next072/downloads/suppl-qqplot.xlsx --output experiments/next_series_20261102/attempts/confirmation_001",
            "public_commit_placeholder": "The coordinator supplies the immutable published commit before retrieval; actual argv is retained by the run receipt",
            "execution_count": "one registered primary attempt; any transport/contract failure remains retained",
            "ci_repeats": "engineering_reproduction; do not add fresh scientific denominators",
        },
        "preflight_receipt": PREFLIGHT_RELATIVE,
        "preflight_summary": json.loads((repository / PREFLIGHT_RELATIVE).read_text()),
    }
    target = repository / FREEZE_RELATIVE
    target.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
    return validate_freeze(repository, target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-prospective", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = write_prospective_freeze(root) if args.write_prospective else validate_freeze(root)
    print(json.dumps(result, indent=2, sort_keys=True))
