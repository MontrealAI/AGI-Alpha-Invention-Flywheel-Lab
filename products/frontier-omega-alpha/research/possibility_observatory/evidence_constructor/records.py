"""Project the registered public records into the unchanged evidence contract."""

from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from ..endpoint_study import mlcommons
from ..endpoint_study.__main__ import load_observations
from ..hardware_history import __main__ as hardware

HERE = Path(__file__).resolve().parent
CAPTURE = HERE / "source-records.json"
PAGES_IDS = (45177415936, 45218349737, 45215919077, 45213693652)
LEAN_TAGS = ("v4.34.0", "v4.35.0", "v4.36.0", "v4.37.0-rc1")
REPO = "MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
GITHUB = "https://api.github.com/repos/"


def capture(root):
    pages = []
    lean = []
    for run_id in PAGES_IDS:
        run_raw = (root / "dev-pages" / f"{run_id}.json").read_bytes()
        job_raw = (root / "dev-pages" / f"{run_id}-jobs.json").read_bytes()
        run = json.loads(run_raw)
        jobs = json.loads(job_raw)["jobs"]
        if run["id"] != run_id or run["path"] != ".github/workflows/research-pages.yml" or len(jobs) != 2:
            raise ValueError("Unexpected Pages workflow")
        entry = {"id": run_id, "source_digests": [sha256(raw).hexdigest() for raw in (run_raw, job_raw)]}
        entry.update({key: run[key] for key in ("head_sha", "head_branch", "event")})
        entry["jobs"] = [{key: job[key] for key in ("id", "name", "conclusion", "completed_at")}
                         for job in jobs]
        pages.append(entry)

    for tag in LEAN_TAGS:
        raw = (root / "confirm-lean" / f"{tag}.json").read_bytes()
        data = json.loads(raw)
        if data["tag_name"] != tag:
            raise ValueError("Unexpected Lean release")
        assets = [asset for asset in data["assets"] if asset["name"] == f"lean-{tag[1:]}-linux.tar.zst"]
        if len(assets) > 1:
            raise ValueError("Ambiguous Linux release asset")
        lean.append({"tag": tag, "published_at": data["published_at"],
                     "prerelease": data["prerelease"], "draft": data["draft"],
                     "linux_asset": {key: assets[0][key] for key in ("name", "digest", "state")} if assets else None,
                     "source_digest": sha256(raw).hexdigest()})
    return {"pages": pages, "lean": lean}


def case(ident, source, actual, required):
    fields = ("scope", "chronology", "role", "qualification")
    return {"id": ident, "source": source, "observed": dict(zip(fields, actual, strict=True)),
            "required": dict(zip(fields, required, strict=True))}


def hardware_groups():
    evidence = json.loads((hardware.HERE / "observations.json").read_bytes())["sources"]
    req = ("orderable", "documented-specification", "receipt-reported", "independent-application")
    return [
        [case(f"{required_role}/{day}/{row['id']}/{role}", row["url"],
              ("ht-hotend", row["published"], role, True), ("ht-hotend", day, required_role, True))
         for day in hardware.DAYS for row in evidence for role in row["roles"]]
        for required_role in req
    ]


def pages_groups(entries):
    deployed = next(row["head_sha"] for row in entries if row["event"] == "push" and row["head_branch"] == "main")
    requests = ((deployed, "build", "2026-11-23"), (deployed, "deploy", "2026-11-23"),
                (deployed, "deploy", "2026-11-22"), (entries[0]["head_sha"], "deploy", "2026-11-23"))
    return [
        [case(f"{target}/{day}/{role}/{job['id']}", f"https://github.com/{REPO}/actions/runs/{row['id']}",
              (row["head_sha"], job["completed_at"][:10] if job["completed_at"] else None,
               job["name"], job["conclusion"] == "success" if job["conclusion"] else None),
              (target, day, role, True))
         for row in entries for job in row["jobs"]]
        for target, role, day in requests
    ]


def endpoint_quality(row, floor, ceiling):
    cert = ("version", "division", "availability", "submission")
    if any(row["facts"][name] != mlcommons.MATCH[name] for name in cert):
        return False
    bounds = ((row["metric"], lambda n: n >= Decimal(floor)),
              (row["upper_metric"], lambda n: n <= Decimal(ceiling)))
    relevant = bounds if ceiling is not None else bounds[:1]
    known = [rule(Decimal(value)) if value is not None else None for value, rule in relevant]
    known.append(None if row["objective"] is None else True)
    if False in known:
        return False
    return None if None in known else True


def endpoint_groups():
    evidence = load_observations()
    requests = (("2026-11-04", "40", "500"), ("2026-11-17", "40", "500"),
                ("2026-11-23", "40", "500"), ("2026-11-23", "40", None))
    scope = lambda facts: facts["model"] + "/" + facts["dataset"]
    return [
        [case(f"{day}/{floor}/{cap}/{row['id']}", row["id"],
              (scope(row["facts"]), row["published"], row["facts"]["run"], endpoint_quality(row, floor, cap)),
              (scope(mlcommons.MATCH), day, "valid-online", True))
         for row in evidence["rows"]]
        for day, floor, cap in requests
    ]


def lean_groups(entries):
    requests = (("v4.35.0", "2026-10-12"), ("v4.36.0", "2026-11-15"),
                ("v4.36.0", "2026-11-16"), ("v4.37.0-rc1", "2026-11-23"))
    return [
        [case(f"{target}/{day}/{row['tag']}", GITHUB + f"leanprover/lean4/releases/tags/{row['tag']}",
              (row["tag"], row["published_at"][:10] if row["published_at"] else None,
               "linux-x86_64-release" if row["linux_asset"] and row["linux_asset"]["state"] == "uploaded" else None,
               row["draft"] is False and row["prerelease"] is False),
              (target, day, "linux-x86_64-release", True))
         for row in entries]
        for target, day in requests
    ]
