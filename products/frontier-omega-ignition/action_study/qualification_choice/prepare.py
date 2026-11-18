"""Bind the independent roster and stable projections of original resolution records."""
import argparse
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path
import shutil

if __package__:
    from .acquire import A, B, BUCKET, LEADERBOARD, LOGS, STATUS, digest
    from .roster import URL, decode_prefix
else:
    from acquire import A, B, BUCKET, LEADERBOARD, LOGS, STATUS, digest
    from roster import URL, decode_prefix


def load(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def materialize(capture, roster_dir, output):
    output.mkdir(exist_ok=False, parents=True)
    raw = roster_dir / "roster.parquet-prefix"
    roster = decode_prefix(raw.read_bytes())
    roster_receipt = load(roster_dir / "roster-receipt.json")
    if digest(raw.read_bytes()) != roster_receipt["sha256"]:
        raise ValueError("Princeton roster fingerprint changed")
    shutil.copyfile(raw, output / raw.name)
    write(output / "roster-receipt.json", roster_receipt)
    catalog = load(capture / "sources.json")
    attachments = {}
    for filename in (raw.name, "roster-receipt.json"):
        attachments[filename] = digest((output / filename).read_bytes())
    for method in (A, B):
        filename = method + ".yaml"
        shutil.copyfile(capture / filename, output / filename)
        attachments[filename] = digest((output / filename).read_bytes())
    schedule = sorted(Counter(roster.values()).items(), key=lambda pair: (pair[1], pair[0]))
    if [repo for repo, size in schedule] != catalog["schedule"]:
        raise ValueError("Repository acquisition order disagrees with independent roster")
    groups = {}
    totals = Counter()
    for repo, size in schedule:
        name = repo.replace("/", "__") + ".json"
        rows = load(capture / name)
        if len(rows) != size or {r["id"] for r in rows} != {key for key, value in roster.items() if value == repo}:
            raise ValueError("Submission rows disagree with official partition")
        first = min(r["retrieved_utc"] for r in rows if "b_prefix" in r)
        last = max(r["retrieved_utc"] for r in rows if "b_prefix" in r)
        patterns = sorted({r["b_prefix"] for r in rows if "b_prefix" in r})
        observed = []
        for row in rows:
            key = row["id"]
            if key not in roster or roster[key] != repo or type(row["a"]) is not bool or "b_prefix" not in row:
                raise ValueError(f"Missing or ambiguous checked result: {key}")
            # Each returned prefix is a physical slice of the named case's report.
            # The catalogued A boolean is a projection of a single pinned JSON file.
            match = STATUS.match(row["b_prefix"].encode("ascii"))
            if not match:
                raise ValueError(f"Invalid evaluator prefix for {key}")
            totals["A"] += row["a"]
            totals["B"] += match.group(4) == b"true"
            observed.append([key, row["a"], patterns.index(row["b_prefix"]), row["etag"], row["last_modified"],
                             row["content_range"], row["retrieved_utc"]])
        projected = {"repository": repo, "A_source": LEADERBOARD, "B_source_base": BUCKET + "/" + LOGS,
                     "prefixes": patterns, "row_fields": ["id", "A_resolved", "B_prefix_index", "B_etag",
                     "B_last_modified", "B_content_range", "B_retrieved_utc"], "rows": observed}
        # One row per physical report. Original bytes for identical prefixes are deduplicated.
        header = json.dumps({key: value for key, value in projected.items() if key != "rows"}, ensure_ascii=False)
        body = ",\n".join(json.dumps(row, ensure_ascii=False) for row in observed)
        (output / name).write_text(header[:-1] + ',\n"rows":[\n' + body + '\n]}\n')
        groups[repo] = {"file": name, "sha256": digest((output / name).read_bytes()),
                        "size": size, "first_retrieved_utc": first, "retrieved_utc": last}
    published = {method: int(5 * Fraction(str(catalog["pool"][method]["resolved"]))) for method in ("A", "B")}
    if totals != published:
        raise ValueError(f"Complete issue-level resolution totals differ from source: {totals} vs {published}")
    pool = {"publisher": "SWE-bench maintainers; Princeton NLP / SWE-bench roster",
            "cases": len(roster), "candidates": catalog["pool"], "pooled": published,
            "catalogue_receipts": catalog["catalogue"], "roster_url": URL, "attachments": attachments,
            "groups": groups, "publication_utc": None, "retrieved_utc": catalog["catalogue"][2]["retrieved_utc"]}
    write(output / "pool.json", pool)
    return digest((output / "pool.json").read_bytes())


def compare_capture(capture, source_dir):
    """Recheck original statuses after a full or decision-stopped physical replay."""
    captured, frozen = load(capture / "sources.json"), load(source_dir / "pool.json")
    for old, new in zip(frozen["catalogue_receipts"], captured["catalogue"], strict=True):
        if any(old[key] != new[key] for key in ("url", "bytes", "sha256")):
            raise ValueError("Publisher catalogue bytes changed")
    original_roster = decode_prefix((source_dir / "roster.parquet-prefix").read_bytes())
    count = 0
    for repo, g in frozen["groups"].items():
        if not (capture / g["file"]).exists():
            continue
        projected = load(source_dir / g["file"])
        rows = {row[0]: row for row in projected["rows"]}
        live = load(capture / g["file"])
        expected = {k for k, assigned in original_roster.items() if assigned == repo}
        if expected != {row["id"] for row in live} or len(live) != len(expected):
            raise ValueError("Reacquired identifiers differ")
        for item in live:
            row = rows[item["id"]]
            if not (row[1] == item["a"] and projected["prefixes"][row[2]] == item["b_prefix"]
                    and row[3:6] == [item["etag"], item["last_modified"], item["content_range"]]):
                raise ValueError("Original evaluator byte prefix or object identity changed")
            count += 1
    decision_path = capture / "decision.json"
    expected_count = load(decision_path)["source_reports"] if decision_path.exists() else len(original_roster)
    if count != expected_count or count == 0:
        raise ValueError("Physical capture coverage differs")
    return count


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("capture", type=Path)
    p.add_argument("roster", nargs="?", type=Path)
    p.add_argument("output", nargs="?", type=Path)
    p.add_argument("--compare", type=Path, metavar="FROZEN_SOURCES",
                   help="Compare the source bytes and object identities of a fresh full or stopped capture")
    args = p.parse_args()
    if args.compare:
        print(compare_capture(args.capture, args.compare), "original report identities agree")
    elif args.roster and args.output:
        print(materialize(args.capture, args.roster, args.output))
    else:
        p.error("Supply roster and output directories or --compare")
