"""Exhaustive relational baseline. This module has no dependency on the selector."""
import csv
import hashlib
import io
import sqlite3


def enumerate_sql(raw, budget, width, model=None, repository=None):
    db = sqlite3.connect(":memory:")
    try:
        db.create_function("split_key", 1, lambda x: hashlib.sha256(("pairing-lab-v1/" + x).encode()).hexdigest())
        db.create_function("repo_of", 1, lambda x: x.rsplit("-", 1)[0])
        db.execute("create table r(id text, stack text, solved integer, tokens integer, primary key (id, stack))")
        db.executemany("insert into r values (?,?,?,?)", (
            (r["task"], r["model"] + "/" + r["harness"], int(r["solved"]), int(r["tokens"]))
            for r in csv.DictReader(io.StringIO(raw.decode()))
        ))
        score = db.execute("""
            WITH ids AS (SELECT DISTINCT id FROM r),
            ranked AS (SELECT id, ROW_NUMBER() OVER (ORDER BY split_key(id), id) AS n FROM ids),
            attempts AS (
                SELECT r.*, ranked.n <= (SELECT COUNT(*) * 3 / 5 FROM ids) AS cal
                FROM ranked JOIN r USING (id)
                WHERE (:model IS NULL OR substr(stack,1,instr(stack,'/')-1) = :model)
                AND (:repo IS NULL OR repo_of(id) = :repo)
            ),
            plans AS (
                SELECT cal, stack AS first, '' AS second, solved, tokens FROM attempts
                UNION ALL
                SELECT a.cal, a.stack, b.stack, MAX(a.solved,b.solved), a.tokens+b.tokens
                FROM attempts AS a JOIN attempts AS b ON a.id=b.id AND a.stack<b.stack
                WHERE :width=2
            )
            SELECT cal, first, second, COUNT(*), SUM(solved), SUM(tokens)
            FROM plans GROUP BY cal, first, second
            ORDER BY cal DESC, SUM(solved) DESC, SUM(tokens), first, second
        """, {"model": model, "repo": repository, "width": width}).fetchall()
        by_split = {"calibration": {}, "audit": {}}
        for cal, first, second, n, solved, tokens in score:
            by_split["calibration" if cal else "audit"][(first, second) if second else (first,)] = {
                "tasks": n, "solved": solved, "tokens": tokens}
        selected = next((plan for plan, value in by_split["calibration"].items()
                         if value["tokens"] <= budget * value["tasks"]), None)
        return selected, by_split
    finally:
        db.close()
