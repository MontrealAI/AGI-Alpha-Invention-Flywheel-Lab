"""Offline, source-bound allocation of a place in the next engineering qualification."""
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
if str(HERE.parents[1]) not in sys.path:
    sys.path.insert(0, str(HERE.parents[1]))
from discovery_field.decision_study.calibration_bounds import bounds
from action_study.qualification_choice.acquire import STATUS, A, B, BUCKET, LEADERBOARD, LOGS
from action_study.qualification_choice.roster import decode_prefix

SOURCES = HERE / "sources"
POOL_SHA256 = "c75dec4fdeb27b4c38f678c61836348e5e4eba7326fa849fb89fd72acff3eb1d"


def example_scope():
    return {"max_repositories": 12}


def verified_bytes(path, identity):
    data = path.read_bytes()
    if sha256(data).hexdigest() != identity:
        raise ValueError(f"Changed evidence file: {path.name}")
    return data


def load_pool(source_dir=SOURCES, identity=None):
    pool = json.loads(verified_bytes(source_dir / "pool.json", identity or POOL_SHA256))
    roster_bytes = verified_bytes(source_dir / "roster.parquet-prefix", pool["attachments"]["roster.parquet-prefix"])
    roster = decode_prefix(roster_bytes)
    receipt = json.loads(verified_bytes(source_dir / "roster-receipt.json", pool["attachments"]["roster-receipt.json"]))
    if receipt["url"] != pool["roster_url"] or receipt["sha256"] != pool["attachments"]["roster.parquet-prefix"]:
        raise ValueError("Princeton roster provenance differs")
    pool["roster_last_retrieved_utc"] = max(row["retrieved_utc"] for row in receipt["ranges"])
    if len(roster) != pool["cases"] or set(roster.values()) != set(pool["groups"]):
        raise ValueError("Independent roster and named repositories differ")
    for name, group in pool["groups"].items():
        if group["size"] != sum(value == name for value in roster.values()):
            raise ValueError("Independent roster and denominator differ")
    for label, submission in (("A", A), ("B", B)):
        filename = submission + ".yaml"
        raw = verified_bytes(source_dir / filename, pool["attachments"][filename]).decode()
        score = re.findall(r"^  resolved: (\d+(?:\.\d+)?)$", raw, re.MULTILINE)
        if (len(score) != 1 or Fraction(score[0]) * len(roster) / 100 != pool["pooled"][label]
                or pool["candidates"][label]["folder"] != submission or "  mini-swe-agent_version: 2.0.0\n" not in raw):
            raise ValueError("Submission identity, harness or registered margins differ")
    return pool, roster


def witnessed_counts(source_dir, repo, group, roster):
    payload = json.loads(verified_bytes(source_dir / group["file"], group["sha256"]))
    if (payload["repository"] != repo or payload["A_source"] != LEADERBOARD
            or payload["B_source_base"] != BUCKET + "/" + LOGS):
        raise ValueError("Evidence origin differs")
    expected = {key for key, assigned in roster.items() if assigned == repo}
    rows = payload["rows"]
    if len(rows) != len(expected) or {row[0] for row in rows} != expected:
        raise ValueError("Missing, duplicate or unregistered evaluator record")
    counts = {"A": 0, "B": 0, "both": 0, "A_only": 0, "B_only": 0, "neither": 0}
    for key, passed_a, index, etag, modified, byte_range, retrieval in rows:
        if type(passed_a) is not bool or type(index) is not int or not 0 <= index < len(payload["prefixes"]):
            raise ValueError("Invalid resolution label")
        data = payload["prefixes"][index].encode("ascii")
        match = STATUS.match(data)
        if not match or not etag or not modified or not retrieval or not byte_range.startswith(f"bytes 0-{len(data)-1}/"):
            raise ValueError("Invalid original evaluator status or source identity")
        passed_b = match.group(4) == b"true"
        if passed_b and not (match.group(1) == b"false" and match.group(2) == match.group(3) == b"true"):
            raise ValueError("B resolved status conflicts with original evaluator flags")
        counts["A"] += passed_a
        counts["B"] += passed_b
        section = ("both" if passed_b else "A_only") if passed_a else ("B_only" if passed_b else "neither")
        counts[section] += 1
    return counts


def interval(sizes, pooled, known):
    if not sizes or set(known) - set(sizes):
        raise ValueError("Invalid stratum")
    remaining = [n for repo, n in sizes.items() if repo not in known]
    fixed = sum((Fraction(count["A"] - count["B"], sizes[repo]) for repo, count in known.items()), Fraction())
    left = {m: pooled[m] - sum(count[m] for count in known.values()) for m in ("A", "B")}
    if any(not 0 <= n <= sum(remaining) for n in left.values()):
        raise ValueError("Reported statuses contradict published margins")
    if not remaining:
        return fixed / len(sizes), fixed / len(sizes)
    result = bounds({method: {"passes": value, "trials": remaining} for method, value in left.items()})
    return tuple((fixed + len(remaining) * Fraction(result[side]["difference"])) / len(sizes)
                 for side in ("minimum", "maximum"))


def sign(lower, upper, complete=False):
    if lower > 0:
        return "A"
    if upper < 0:
        return "B"
    if complete and lower == upper == 0:
        return "tie"
    return None


def decide(scope, route, source_dir=SOURCES):
    if route not in ("pooled", "repository_outcomes"):
        raise ValueError("Unknown acquisition route")
    if (not isinstance(scope, dict) or set(scope) != {"max_repositories"}
            or type(scope["max_repositories"]) is not int or scope["max_repositories"] < 0):
        raise ValueError("Acquisition scope needs a nonnegative integer max_repositories")
    pool, roster = load_pool(source_dir)
    sizes = {repo: item["size"] for repo, item in pool["groups"].items()}
    order = sorted(sizes, key=lambda repo: (sizes[repo], repo))
    known = {}
    lower, upper = interval(sizes, pool["pooled"], known)
    finding = sign(lower, upper)
    receipts = []
    if route == "repository_outcomes":
        for repo in order[:scope["max_repositories"]]:
            if finding is not None:
                break
            group = pool["groups"][repo]
            counts = witnessed_counts(source_dir, repo, group, roster)
            known[repo] = counts
            receipts.append({"id": repo, "cases": sizes[repo], "A": counts["A"], "B": counts["B"],
                             "source_path": "sources/" + group["file"], "sha256": group["sha256"], "retrieved_utc": group["retrieved_utc"]})
            lower, upper = interval(sizes, pool["pooled"], known)
            finding = sign(lower, upper, len(known) == len(order))
    evidence = {"id": "swe-bench-verified/500/equal-repository", "publisher": pool["publisher"],
                "url": LEADERBOARD, "sha256": pool["catalogue_receipts"][2]["sha256"],
                "decision_manifest_sha256": POOL_SHA256, "roster_sha256": pool["attachments"]["roster.parquet-prefix"],
                "B_report_base": BUCKET + "/" + LOGS, "lower": str(lower), "upper": str(upper),
                "revealed": list(known), "repository_count": len(sizes), "cases": pool["cases"], "pooled": pool["pooled"],
                "next_repository": order[len(known)] if len(known) < len(order) and finding is None else None,
                "publication_utc": None, "retrieved_utc": max([pool["retrieved_utc"], pool["roster_last_retrieved_utc"]] + [r["retrieved_utc"] for r in receipts]),
                "A": A, "B": B, "roster_url": pool["roster_url"]}
    reason = "fixed_population_order" if finding else "equal_repository_order_unresolved"
    return {"state": "observed" if finding else "incomplete", "finding": finding, "evidence": [evidence, *receipts], "reason": reason}


def inspect_source(scope, route):
    try:
        return decide(scope, route)
    except FileNotFoundError as error:
        return {"state": "unavailable", "finding": None, "evidence": [], "reason": str(error.filename and Path(error.filename).name)}
    except (KeyError, ValueError, TypeError, IndexError, UnicodeError) as error:
        return {"state": "contradictory", "finding": None, "evidence": [], "reason": str(error)}
