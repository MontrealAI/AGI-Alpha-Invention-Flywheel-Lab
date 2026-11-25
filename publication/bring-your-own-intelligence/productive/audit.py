# SPDX-License-Identifier: Apache-2.0
"""Operator assistive audit of exactly pinned public executor archives."""

from argparse import ArgumentParser
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
from stat import S_IFMT, S_IFREG
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from zipfile import BadZipFile, ZipFile


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RELEASE = REPO / "publication/outcome-driven/verification/LIVE-RELEASE.json"
SOURCE_CONTEXT = "1bdac817b471157092ea4aac881916824b66734e"
COMMITS = {
    "1.1.0": "297a51c25c48031e1e6f964835f4dfae3ddb8023",
    "1.2.0": "9a53a4b8bb7eb3d5f82f50effcf44e3ec1291d19",
    "1.5.0": "436bb1b142a0da1f2c272f77821b75c3efdd73fe",
}
PACKAGE_IDS = {version: "frontier-harness-executor" for version in ("1.1.0", "1.2.0")}
PACKAGE_IDS["1.5.0"] = "frontier-activation"
SOURCE_BASE = "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/"
SOURCE_PATHS = {
    "bridge/relational.py": "products/frontier-member-tools/inventor/relational.py",
    **{name: "products/alpha-genesis-harness/" + name for name in (
        "bridge/universal_missions.py", "bridge/instruments.py", "bridge/workflows.py", "bridge/mission_tools.py",
        "Launch-FRONTIER.sh", "Launch-FRONTIER.command", "Launch-FRONTIER.cmd",
        "docs/CHATGPT-PLAN.md", "docs/MODEL-CONNECTIONS.md",
    )},
}
STARTUP_GUIDES = {"1.1.0": "publication/evidence-bound/README.md", "1.2.0": "publication/outcome-driven/README.md"}
FACTORY_SOURCES = {
    "verify_factory.py": "products/frontier-member-tools/activation/verify_factory.py",
    "evidence_truth.py": "products/frontier-member-tools/activation/evidence_truth.py",
    "study/factory/FACTORY.json": "publication/factory/FACTORY.json",
    "study/factory/REGISTRATION.md": "publication/factory/REGISTRATION.md",
}
SCHEMA = {
    "publisher": {"version": "TEXT", "archive_sha256": "TEXT", "source_url": "TEXT"},
    "observed": {"case_id": "TEXT", "archive_sha256": "TEXT", "source_url": "TEXT", "package_version": "TEXT",
                 "inventory_verified": "INTEGER", "source_verified": "INTEGER", "inventory_count": "INTEGER"},
}
ARTIFACT = "archive-readiness.json"
FILE_LIMIT = 2_000_000
EXPANDED_LIMIT = 12_000_000


def hash_bytes(data):
    return sha256(data).hexdigest()


def git_bytes(revision, path):
    return subprocess.check_output(["git", "-C", str(REPO), "show", f"{revision}:{path}"])


def capture_publisher():
    data = RELEASE.read_bytes()
    if data != git_bytes(SOURCE_CONTEXT, RELEASE.relative_to(REPO).as_posix()):
        raise ValueError("Historical publisher observation differs from stated source.")
    release = json.loads(data)
    if release["source_commit"] != COMMITS["1.2.0"] or release["workflow_run"] != "45637319050":
        raise ValueError("The expected independent Pages receipt was not present.")
    return data, release


def source_hashes(version):
    files = FACTORY_SOURCES if version == "1.5.0" else {**SOURCE_PATHS, "START.md": STARTUP_GUIDES[version]}
    return {name: hash_bytes(git_bytes(COMMITS[version], path)) for name, path in files.items()}


def inspect_archive(path, version, expected_sources, case_id):
    facts = {"case_id": case_id, "archive_sha256": None, "source_url": None, "package_version": None,
             "inventory_verified": None, "source_verified": None, "inventory_count": None}
    if path is None:
        return facts, {"measurement": "MISSING"}
    with path.open("rb") as stream:
        data = stream.read(FILE_LIMIT + 1)
    if len(data) > FILE_LIMIT:
        raise ValueError("File outside this registered small archive study.")
    facts["archive_sha256"] = hash_bytes(data)
    if facts["archive_sha256"] != subprocess.check_output(["sha256sum", "--", str(path)]).split()[0].decode("ascii"):
        raise ValueError("Independent system archive digest differs from Python measurement.")
    detail = {"bytes": len(data), "measurement": "PYTHON_SHA256_AND_SHA256SUM_AGREE"}
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            names = [item.filename for item in entries]
            unique = set(names)
            if (not 0 < len(entries) <= 256 or len(unique) != len(names)
                    or sum(item.file_size for item in entries) > EXPANDED_LIMIT):
                raise ValueError("Unsafe package extent or ambiguous duplicate member.")
            for item in entries:
                name = item.filename
                binding = PurePosixPath(name)
                if (binding.is_absolute() or ".." in binding.parts or name != binding.as_posix() or "\\" in name
                        or ":" in name or item.is_dir() or S_IFMT(item.external_attr >> 16) not in (0, S_IFREG)):
                    raise ValueError("Unsafe package path or nonregular member.")
            manifest_bytes = archive.read("manifest.json")
            manifest = json.loads(manifest_bytes)
            files = manifest["file_sha256"]
            if not isinstance(files, dict) or unique != {"manifest.json", *files} or "manifest.json" in files:
                raise ValueError("Package roster is inconsistent with its manifest.")
            observed = {name: hash_bytes(archive.read(name)) for name in files}
            if observed != files:
                raise ValueError("Package member digests are inconsistent with its manifest.")
            facts.update(inventory_verified=1, inventory_count=len(files), package_version=manifest["version"],
                         source_url=manifest["source"], source_verified=int(
                             manifest["schema"] == "frontier/portable-capability-v1"
                             and manifest["id"] == PACKAGE_IDS[version]
                             and manifest["source"] == SOURCE_BASE + COMMITS[version]
                             and manifest["version"] == version
                             and all(observed.get(name) == pin for name, pin in expected_sources.items())))
            detail.update(manifest_sha256=hash_bytes(manifest_bytes), required_sources=len(expected_sources))
    except (BadZipFile, KeyError, TypeError, ValueError) as error:
        facts["inventory_verified"] = 0
        detail["inventory_refusal"] = str(error)
    return facts, detail


def ordinary_explicit_check(publisher, observed):
    """Strong equal-content ordinary decision with all the same prerequisites."""
    prerequisites = (
        (bool(publisher["archive_sha256"] and publisher["source_url"]), "HOLD_MISSING_PUBLISHER_BINDING"),
        (bool(observed["archive_sha256"]), "HOLD_MISSING_PACKAGE"),
        (observed["archive_sha256"] == publisher["archive_sha256"], "HOLD_ARCHIVE_MISMATCH"),
        (observed["inventory_verified"] == 1, "HOLD_INVENTORY"),
        (observed["source_verified"] == 1 and observed["package_version"] == publisher["version"]
         and observed["source_url"] == publisher["source_url"], "HOLD_SOURCE"),
    )
    return next((reason for passed, reason in prerequisites if not passed), "VERIFIED_ARCHIVE")


def independent_incumbent(path, publisher, expected_sources):
    """Execute the existing release installer check in a disposable directory."""
    sys.path.insert(0, str(REPO / "scripts"))
    from qualify_frontier_member import install

    if publisher["archive_sha256"] is None or publisher["source_url"] is None:
        return "HOLD_MISSING_PUBLISHER_BINDING"
    if path is None:
        return "HOLD_MISSING_PACKAGE"
    if subprocess.check_output(["sha256sum", "--", str(path)]).split()[0].decode("ascii") != publisher["archive_sha256"]:
        return "HOLD_ARCHIVE_MISMATCH"
    with TemporaryDirectory() as directory:
        root = Path(directory)
        try:
            manifest = install(path, root, {"sha256": publisher["archive_sha256"]})
        except (ValueError, KeyError, BadZipFile):
            return "HOLD_INVENTORY"
        valid = (manifest["schema"] == "frontier/portable-capability-v1"
                 and manifest["id"] == PACKAGE_IDS[publisher["version"]]
                 and manifest["version"] == publisher["version"] and manifest["source"] == publisher["source_url"]
                 and all((root / name).is_file() and hash_bytes((root / name).read_bytes()) == pin
                         for name, pin in expected_sources.items()))
        return "VERIFIED_ARCHIVE" if valid else "HOLD_SOURCE"


def harness_runner(harness):
    sys.path.insert(0, str(harness))
    from bridge.mission_tools import execute

    storage = {}

    def write(name, source, kind):
        storage[name] = (kind, source.encode("utf-8"))
        return {"name": name, "sha256": hash_bytes(storage[name][1]), "bytes": len(storage[name][1])}

    def dispatch(action, tables):
        return execute(action, read=lambda name: storage[name][1], write=write,
                       kind=lambda name: storage.get(name, (None, None))[0], approved_tables=tables)

    constructed = dispatch({"tool": "construct_table", "name": ARTIFACT, "schema": SCHEMA,
                            "sql": (HERE / "readiness.sql").read_text(encoding="utf-8")}, {})

    def run(publisher, observation):
        contract = {"publisher": [publisher], "observed": [observation]}
        return dispatch({"tool": "run_table", "name": ARTIFACT, "input": {"dataset": "release-check"}},
                        {"release-check": contract})

    return constructed, run


def measure(function):
    started = perf_counter()
    value = function()
    return value, perf_counter() - started


def audit(args):
    used_at = perf_counter()
    release_bytes, release = capture_publisher()
    sources = {version: source_hashes(version) for version in COMMITS}
    source_duration = perf_counter() - used_at
    (constructed, run), construction_time = measure(lambda: harness_runner(args.harness))
    cases = (
        ("released-1.1", args.released_11, "1.1.0", "VERIFIED_ARCHIVE"),
        ("released-1.2", args.released_12, "1.2.0", "VERIFIED_ARCHIVE"),
        ("staged-same-name-1.2", args.staged_12, "1.2.0", "HOLD_ARCHIVE_MISMATCH"),
        ("missing-file", None, "1.2.0", "HOLD_MISSING_PACKAGE"),
        ("withdrawn-publisher-binding", args.released_12, "1.2.0", "HOLD_MISSING_PUBLISHER_BINDING"),
        ("factory-successor", args.factory_15, "1.5.0", "VERIFIED_ARCHIVE"),
        ("factory-binding-withdrawn", args.factory_15, "1.5.0", "HOLD_MISSING_PUBLISHER_BINDING"),
    )
    outcomes = {}
    for case_id, path, version, expected in cases:
        expected_sources = sources[version]
        records = release["foundry_sha256"] if version == "1.5.0" else release["universal_mission_sha256"]
        publisher = {"version": version, "archive_sha256": records[f"{PACKAGE_IDS[version]}-{version}.zip"],
                     "source_url": SOURCE_BASE + COMMITS[version]}
        withdrawal = expected == "HOLD_MISSING_PUBLISHER_BINDING"
        if withdrawal:
            publisher.update(archive_sha256=None, source_url=None)
        (observation, detail), acquisition_time = measure(lambda: inspect_archive(path, version, expected_sources, case_id))
        if withdrawal or path is None:
            detail["control"] = "AUTHORITY_WITHDRAWAL" if path else "SIMULATED_MISSING_APPROVED_FILE"
        times = {"assisted_harness": [], "equal_content_ordinary": [], "incumbent_full_read": []}
        answers = {}
        loops = 9 if case_id == "factory-successor" else (7 if case_id.startswith("released-") else 1)
        for idx in range(loops):
            arms = {
                "assisted_harness": lambda: run(publisher, observation),
                "equal_content_ordinary": lambda: ordinary_explicit_check(publisher, observation),
                "incumbent_full_read": lambda: independent_incumbent(path, publisher, expected_sources),
            }
            order = list(arms)
            for name in order if idx % 2 == 0 else list(reversed(order)):
                answers[name], wall = measure(arms[name])
                times[name].append(wall)
        candidate = answers["assisted_harness"]
        decisions = {**answers, "assisted_harness": candidate["rows"][0][2]}
        passed = all(value == expected for value in decisions.values()) and len(candidate["rows"]) == 1
        outcomes[case_id] = {"publisher": publisher, "observation": observation, "detail": detail, "expected": expected,
                             "agree": passed, "decisions": decisions, "execution": candidate,
                             "acquisition_wall_seconds": acquisition_time, "timed_repetitions": loops,
                             "median_wall_seconds": {key: median(values) for key, values in times.items()}}
    return {
        "schema": "frontier/exact-operator-package-continuity-v1", "qualification": "EXACT_ARCHIVE_REVIEW_ONLY",
        "go": all(row["agree"] for row in outcomes.values()), "release_receipt_sha256": hash_bytes(release_bytes),
        "release_revision": release["source_commit"], "release_workflow_run": release["workflow_run"],
        "source_sha256": {name: hash_bytes((HERE / name).read_bytes()) for name in
                          ("audit.py", "readiness.sql", "REGISTRATION.json", "TRANSFER-REGISTRATION.json")},
        "provenance_checks": {name: digest for name, digest in sources.items()}, "constructed": constructed,
        "costs": {"source_pin_acquisition_wall_seconds": source_duration, "construction_wall_seconds": construction_time,
                  "new_public_network_requests": 0, "runtime_inference_requests": 0, "first_worked_example_purchases": 0,
                  "inference_authoring_tokens_or_cost": None, "human_attention_or_maintenance_cost": None},
        "scope": "Actual public MONTREAL.AI package preflight, using prior observed publisher receipt and archive bytes. Included-Codex assisted authoring and bounded SQLite interpretation. No code execution from inspected ZIPs, protected evaluator custody or measured economic return.",
        "cases": outcomes,
        "successor": {"retained_mechanism": "Declared source scope plus explicit unavailable observation",
                      "original_inventor_matched_run": False,
                      "scope_withdrawal_observed": outcomes["factory-binding-withdrawn"]["agree"],
                      "ordinary_equal_content_tied": outcomes["factory-successor"]["agree"],
                      "gate": "NO_GO_CAUSAL_IMPROVEMENT_OR_NEW_GENERATION"},
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--released-11", type=Path, required=True)
    parser.add_argument("--released-12", type=Path, required=True)
    parser.add_argument("--staged-12", type=Path, required=True)
    parser.add_argument("--factory-15", type=Path, required=True)
    parser.add_argument("--harness", type=Path, default=REPO / "products" / "alpha-genesis-harness")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    for case_id, row in result["cases"].items():
        print(case_id, row["decisions"]["assisted_harness"], row["agree"])
    if not result["go"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
