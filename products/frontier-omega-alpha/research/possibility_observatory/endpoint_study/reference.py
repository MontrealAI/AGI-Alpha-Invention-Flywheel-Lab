"""Direct SQLite decision table, independent of the portable Python selector."""

from contextlib import closing
from decimal import Decimal
import json
import sqlite3

CLASSIFY = """
    SELECT id, objective, CASE
        WHEN EXISTS (
            SELECT 1 FROM json_each(:match) AS required
            WHERE NOT EXISTS (
                SELECT 1 FROM json_each(facts) AS actual
                WHERE actual.key = required.key AND actual.value = required.value
            )
        ) THEN 'outside-scope'
        WHEN published IS NULL THEN 'missing-publication-date'
        WHEN published > :as_of THEN 'not-yet-documented'
        WHEN metric IS NULL OR objective IS NULL THEN 'missing-measurement'
        WHEN metric COLLATE exact_decimal < :minimum THEN 'below-threshold'
        WHEN :maximum IS NOT NULL AND upper_metric IS NULL THEN 'missing-measurement'
        WHEN :maximum IS NOT NULL AND upper_metric COLLATE exact_decimal > :maximum THEN 'above-ceiling'
        ELSE 'qualified'
    END AS disposition
    FROM evidence
"""


def compare_decimal(left, right):
    left, right = Decimal(left), Decimal(right)
    return (left > right) - (left < right)


def evaluate_many(rows, match, as_of, minimums, maximum=None):
    """Use a conventional indexed in-memory database and text-exact decimal ordering."""
    with closing(sqlite3.connect(":memory:")) as db:
        db.create_collation("exact_decimal", compare_decimal)
        db.execute("""CREATE TABLE evidence(
            id TEXT PRIMARY KEY, published TEXT, facts TEXT NOT NULL,
            metric TEXT, objective TEXT COLLATE exact_decimal, upper_metric TEXT
        )""")
        db.executemany("INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?)", [
            (row["id"], row["published"], json.dumps(row["facts"]), row["metric"],
             row["objective"], row.get("upper_metric"))
            for row in rows
        ])
        db.execute("CREATE INDEX evidence_objective ON evidence(objective DESC, id)")
        return [evaluate(db, match, as_of, minimum, maximum) for minimum in minimums]


def evaluate(db, match, as_of, minimum, maximum):
    bindings = {"match": json.dumps(match), "as_of": as_of, "minimum": minimum, "maximum": maximum}
    dispositions = dict(db.execute(
        f"SELECT id, disposition FROM ({CLASSIFY}) ORDER BY id", bindings
    ))
    winners = [row[0] for row in db.execute(f"""
        WITH classified AS ({CLASSIFY}),
        ranked AS (
            SELECT id, DENSE_RANK() OVER (ORDER BY objective COLLATE exact_decimal DESC) AS place
            FROM classified WHERE disposition COLLATE BINARY = 'qualified'
        )
        SELECT id FROM ranked WHERE place = 1 ORDER BY id
    """, bindings)]
    return {"dispositions": dispositions, "winners": winners}
