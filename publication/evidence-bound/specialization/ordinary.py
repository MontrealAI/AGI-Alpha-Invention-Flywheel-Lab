# SPDX-License-Identifier: Apache-2.0
"""Conventional SQL comparison using exact rational-text sort and group operations."""

from fractions import Fraction
import sqlite3


QUERY = """
WITH latest AS (
    SELECT event, MAX(revision) AS revision FROM records GROUP BY event
),
distinct_versions AS (
    SELECT DISTINCT r.event, r.lon, r.lat, r.mag, r.event_time
    FROM records AS r JOIN latest AS v USING (event, revision)
),
variants AS (
    SELECT event, COUNT(*) AS versions FROM distinct_versions GROUP BY event
)
SELECT d.event,
       CASE WHEN v.versions > 1 THEN 'conflicting' ELSE 'included' END
FROM distinct_versions AS d JOIN variants AS v USING (event)
WHERE v.versions > 1 OR (
    d.event_time >= :start AND d.event_time < :end
    AND d.lat COLLATE rational BETWEEN :south AND :north
    AND d.mag COLLATE rational >= :minimum
    AND (
        (:wrap = 0 AND d.lon COLLATE rational BETWEEN :west AND :east)
        OR (:wrap = 1 AND (d.lon COLLATE rational >= :west OR d.lon COLLATE rational <= :east))
        OR (d.lon = '-180' AND (:wrap = 1 OR :east = '180'))
    )
)
GROUP BY d.event
ORDER BY d.event
"""


def rational_text(value):
    return str(Fraction(str(value)))


def compare(left, right):
    x, y = Fraction(left), Fraction(right)
    return (x > y) - (x < y)


def audit(case):
    bounds = case["bounds"]
    west, east = Fraction(str(bounds["west"])), Fraction(str(bounds["east"]))
    parameters = {"start": bounds["start_ms"], "end": bounds["end_ms"],
                  "south": rational_text(bounds["south"]), "north": rational_text(bounds["north"]),
                  "minimum": rational_text(bounds["min_magnitude"]), "west": str(west), "east": str(east),
                  "wrap": west > east}
    rows = []
    for raw in case["records"]:
        longitude = rational_text(raw["lon"])
        rows.append((raw["id"], raw["updated_ms"], "-180" if longitude == "180" else longitude,
                     rational_text(raw["lat"]), None if raw["mag"] is None else rational_text(raw["mag"]), raw["time_ms"]))
    db = sqlite3.connect(":memory:")
    try:
        db.create_collation("rational", compare)
        db.execute("CREATE TABLE records(event TEXT, revision INTEGER, lon TEXT, lat TEXT, mag TEXT, event_time INTEGER)")
        db.executemany("INSERT INTO records VALUES (?, ?, ?, ?, ?, ?)", rows)
        result = {"included": [], "conflicting": []}
        for event, decision in db.execute(QUERY, parameters):
            result[decision].append(event)
        return result
    finally:
        db.close()
