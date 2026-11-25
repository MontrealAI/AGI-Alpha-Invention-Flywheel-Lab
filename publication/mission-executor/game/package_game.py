"""Build the portable, deterministic Game Theory release archive."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from retained_allocation import SOURCE_SHA256


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PREFIX = HERE.relative_to(REPO)
RETAINED = Path("publication/universal/game-theory")
FILES = (
    "CAPABILITY.json",
    "DEVELOPMENT.json",
    "EXAMPLE-CERTIFICATE.json",
    "EXAMPLE-VERIFICATION.json",
    "EXAMPLE.json",
    "QUALIFICATION-PLAN.json",
    "REPORT.md",
    "START.md",
    "compare_observation.py",
    "observation.py",
    "package_game.py",
    "retained_allocation.py",
    "run_development.py",
    "solve_observation.py",
    "evaluator/EXACT-STRATEGIC-FREEZE.json",
    "evaluator/INDEPENDENT-COMPETITORS.json",
    "evaluator/README.md",
    "evaluator/REGISTRATION.json",
    "evaluator/grade_strategic_competitors.py",
    "evaluator/grade_strategic_games.py",
    "evaluator/held_games.json",
    "evaluator/strategic-final-v1/INDEPENDENT-STRATEGIC-REPORT.json",
    "evaluator/strategic_reference.py",
)


def digest(data):
    return sha256(data).hexdigest()


def package(output):
    paths = [PREFIX / name for name in FILES]
    paths.extend(RETAINED / f"{name}.py" for name in SOURCE_SHA256)
    entries = {path.as_posix(): (REPO / path).read_bytes() for path in sorted(paths)}

    def own(name):
        return entries[(PREFIX / name).as_posix()]

    plan = json.loads(own("QUALIFICATION-PLAN.json"))
    capability = json.loads(own("CAPABILITY.json"))
    qualification = capability["qualification"]
    exact = {
        **{(PREFIX / name).as_posix(): sha for name, sha in plan["candidate_sha256"].items()},
        **{(RETAINED / f"{name}.py").as_posix(): sha for name, sha in SOURCE_SHA256.items()},
        (PREFIX / "QUALIFICATION-PLAN.json").as_posix(): qualification["source_plan_sha256"],
        (PREFIX / "evaluator/held_games.json").as_posix(): qualification["held_suite_sha256"],
        (PREFIX / "evaluator/INDEPENDENT-COMPETITORS.json").as_posix(): qualification[
            "independent_comparators_sha256"
        ],
        (PREFIX / "evaluator/strategic-final-v1/INDEPENDENT-STRATEGIC-REPORT.json").as_posix():
            qualification["independent_report_sha256"],
    }
    for path, checksum in exact.items():
        if digest(entries[path]) != checksum:
            raise ValueError(f"Qualified source changed: {path}")

    manifest = {
        "schema": "frontier/costly-observation-archive-v1",
        "members": [{"path": name, "bytes": len(data), "sha256": digest(data)}
                    for name, data in entries.items()],
    }
    entries["ARCHIVE-MANIFEST.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    with ZipFile(output, "x", compression=ZIP_STORED) as archive:
        for name, data in sorted(entries.items()):
            info = ZipInfo(name)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    options = parser.parse_args()
    package(options.output)


if __name__ == "__main__":
    main()
