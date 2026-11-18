"""Conventional SQLite analysis of the official case roster and public resolution fields."""
import argparse
from fractions import Fraction
from hashlib import sha256
import json
from math import lcm
from pathlib import Path
import sqlite3

if __package__:
    from .roster import decode_prefix
else:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from roster import decode_prefix

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources"


def read(path):
    return json.loads(path.read_bytes())


def row_status(prefix):
    # Only four complete JSON properties fit inside the registered HTTP prefix.
    # Recover the complete object up to the delimiter. Decode using the JSON grammar.
    end = prefix.find(',', prefix.index('"resolved"') + len('"resolved"'))
    if end < 0:
        raise ValueError("Truncated resolved field")
    status = json.loads(prefix[:end] + "}")
    if set(status) != {"patch_is_None", "patch_exists", "patch_successfully_applied", "resolved"} or any(
            type(value) is not bool for value in status.values()):
        raise ValueError("Unrecognized publisher status schema")
    if status["resolved"] and (status["patch_is_None"] or not status["patch_exists"] or not status["patch_successfully_applied"]):
        raise ValueError("Inconsistent publisher resolution")
    return status


def initialize(source_dir=SOURCES):
    source = (source_dir / "pool.json").read_bytes()
    if sha256(source).hexdigest() != "c75dec4fdeb27b4c38f678c61836348e5e4eba7326fa849fb89fd72acff3eb1d":
        raise ValueError("Published source manifest differs")
    pool = json.loads(source)
    for method, candidate in pool["candidates"].items():
        filename = candidate["folder"] + ".yaml"
        orig = (source_dir / filename).read_bytes()
        if sha256(orig).hexdigest() != pool["attachments"][filename]:
            raise ValueError("Original submission record differs")
        scores = [line.split(": ")[1] for line in orig.decode().splitlines() if line.startswith("  resolved: ")]
        if len(scores) != 1 or Fraction(scores[0]) * 5 != pool["pooled"][method]:
            raise ValueError("Published pooled score differs")
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE roster(issue TEXT PRIMARY KEY, repo TEXT NOT NULL);
        CREATE TABLE outcomes(issue TEXT PRIMARY KEY REFERENCES roster, repo TEXT NOT NULL,
                    a INTEGER CHECK(a IN (0,1)), b INTEGER CHECK(b IN (0,1)),
                    b_missing INTEGER, b_unapplied INTEGER);
    """)
    db.execute("PRAGMA foreign_keys=ON")
    raw = (source_dir / "roster.parquet-prefix").read_bytes()
    if sha256(raw).hexdigest() != pool["attachments"]["roster.parquet-prefix"]:
        raise ValueError("Roster bytes changed")
    db.executemany("INSERT INTO roster VALUES(?, ?)", decode_prefix(raw).items())
    sizes = dict(db.execute("SELECT repo, count(*) FROM roster GROUP BY repo ORDER BY count(*),repo"))
    return db, pool, sizes


def ingest(db, source_dir, repo, meta):
    raw = (source_dir / meta["file"]).read_bytes()
    if sha256(raw).hexdigest() != meta["sha256"]:
        raise ValueError("Changed status evidence")
    projected = json.loads(raw)
    rows = []
    for issue, a, index, *_ in projected["rows"]:
        if type(a) is not bool:
            raise ValueError("Unknown A status")
        status = row_status(projected["prefixes"][index])
        rows.append((issue, repo, a, status["resolved"],
                     status["patch_is_None"] or not status["patch_exists"], not status["patch_successfully_applied"]))
    db.executemany("INSERT INTO outcomes VALUES(?,?,?,?,?,?)", rows)
    (missing,) = db.execute("""SELECT count(*) FROM roster r LEFT JOIN outcomes o ON r.issue=o.issue
        WHERE r.repo=? AND (o.issue IS NULL OR r.repo != o.repo)""", (repo,)).fetchone()
    if missing or len(rows) != meta["size"]:
        raise ValueError("Incomplete group coverage")


def sharp(db, pooled, scale, nrepos):
    # Each remaining success can occupy one open instance at its repository's
    # integer weight. SQLite orders *individual slots*, independently of the
    # inherited routine that fills whole groups. Ties do not change extrema.
    row = db.execute("""
        WITH group_sizes AS (SELECT repo,count(*) AS n FROM roster GROUP BY repo),
        slots AS (
          SELECT r.issue, :scale / s.n AS w, o.a, o.b FROM roster r
          JOIN group_sizes s USING(repo) LEFT JOIN outcomes o USING(issue)
        ), known AS (
          SELECT coalesce(sum(a*w-b*w),0) AS delta, :a-coalesce(sum(a),0) AS a_left,
                 :b-coalesce(sum(b),0) AS b_left FROM slots
        ), open_slots AS (
          SELECT w, row_number() OVER(ORDER BY w,issue) AS low,
                    row_number() OVER(ORDER BY w DESC,issue) AS high FROM slots WHERE a IS NULL
        )
        SELECT delta + coalesce(sum(w*(low<=a_left)-w*(high<=b_left)),0),
               delta + coalesce(sum(w*(high<=a_left)-w*(low<=b_left)),0),
               a_left,b_left,count(w)
        FROM known LEFT JOIN open_slots ON 1=1
        """, {"scale": scale, "a": pooled["A"], "b": pooled["B"]}).fetchone()
    if not (0 <= row[2] <= row[4] and 0 <= row[3] <= row[4]):
        raise ValueError("Contradictory published margins")
    return tuple(Fraction(value, scale * nrepos) for value in row[:2])


def conventional(source_dir=SOURCES, *, stop=False, check_prefixes=True):
    db, pool, sizes = initialize(source_dir)
    try:
        scale = lcm(*sizes.values())
        ranges = [sharp(db, pool["pooled"], scale, len(sizes))] if stop or check_prefixes else []
        for repo in sizes:
            ingest(db, source_dir, repo, pool["groups"][repo])
            if stop or check_prefixes:
                ranges.append(sharp(db, pool["pooled"], scale, len(sizes)))
            if stop and (ranges[-1][0] > 0 or ranges[-1][1] < 0):
                break
        columns = ("cases", "A", "B", "A_only", "B_only", "both", "neither", "B_missing_patch_status", "B_unapplied_status")
        groups = {repo: dict(zip(columns, counts)) for repo, *counts in db.execute("""
            SELECT repo,count(*),sum(a),sum(b),sum(a=1 AND b=0),sum(b=1 AND a=0),
                sum(a=1 AND b=1),sum(a=0 AND b=0),sum(b_missing),sum(b_unapplied)
            FROM outcomes GROUP BY repo ORDER BY count(*),repo""")}
        totals = {c: sum(cells[c] for cells in groups.values()) for c in columns}
        rates = {}
        if len(groups) == len(sizes):
            rates = {name: str(Fraction(sum((scale // sizes[repo]) * group[name] for repo, group in groups.items()),
                                        scale * len(sizes))) for name in ("A", "B")}
        return {"ranges": [[str(x) for x in pair] for pair in ranges], "repositories": groups, "paired": totals,
                "equal_repository_rates": rates}
    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--all-prefixes", action="store_true", help="Also check the exact bounds after each group")
    p.add_argument("--stop", action="store_true", help="Stop when the equal-repository ordering is determined")
    args = p.parse_args()
    print(json.dumps(conventional(stop=args.stop, check_prefixes=args.all_prefixes), indent=2))
