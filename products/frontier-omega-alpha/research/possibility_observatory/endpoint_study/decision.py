"""Portable witness for a ranked decision over a finite, dated evidence set."""

from datetime import date
from decimal import Decimal
import re

NUMBER = re.compile(r"[0-9]{1,30}(?:\.[0-9]{1,30})?\Z")
ROW_FIELDS = {"id", "published", "facts", "metric", "objective"}


def exact(value):
    if not isinstance(value, str) or not NUMBER.fullmatch(value):
        raise ValueError("Expected a bounded unsigned decimal")
    return Decimal(value)


def day(value):
    if not isinstance(value, str):
        raise ValueError("Expected an ISO calendar day")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Expected a canonical ISO calendar day")
    return parsed


def validate(rows, match, as_of, minimum, maximum=None):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10_000:
        raise ValueError("Expected a bounded, nonempty set of evidence rows")
    if not isinstance(match, dict) or not match or not all(
        isinstance(key, str) and isinstance(value, str) and value
        for key, value in match.items()
    ):
        raise ValueError("Expected exact scope predicates")
    day(as_of)
    exact(minimum)
    if maximum is not None:
        exact(maximum)
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not ROW_FIELDS <= row.keys():
            raise ValueError("Incomplete evidence row")
        ident = row["id"]
        if not isinstance(ident, str) or not ident or len(ident) > 160 or ident in ids:
            raise ValueError("Missing or duplicate evidence identity")
        ids.add(ident)
        if row["published"] is not None:
            day(row["published"])
        facts = row["facts"]
        if not isinstance(facts, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in facts.items()
        ):
            raise ValueError("Expected literal evidence facts")
        for field in ("metric", "objective", "upper_metric"):
            if row.get(field) is not None:
                exact(row[field])


def classify(row, match, as_of, minimum, maximum=None):
    if any(row["facts"].get(key) != value for key, value in match.items()):
        return "outside-scope"
    if row["published"] is None:
        return "missing-publication-date"
    if row["published"] > as_of:
        return "not-yet-documented"
    if row["metric"] is None or row["objective"] is None:
        return "missing-measurement"
    if exact(row["metric"]) < minimum:
        return "below-threshold"
    if maximum is not None:
        ceiling_metric = row.get("upper_metric")
        if ceiling_metric is None:
            return "missing-measurement"
        if exact(ceiling_metric) > maximum:
            return "above-ceiling"
    return "qualified"


def evaluate(rows, match, as_of, minimum, maximum=None):
    """Return every row's disposition and all equally best qualifying witnesses."""
    validate(rows, match, as_of, minimum, maximum)
    threshold = exact(minimum)
    ceiling = exact(maximum) if maximum is not None else None
    dispositions = {}
    best = None
    winners = []
    for row in sorted(rows, key=lambda evidence: evidence["id"]):
        disposition = classify(row, match, as_of, threshold, ceiling)
        dispositions[row["id"]] = disposition
        if disposition == "qualified":
            value = exact(row["objective"])
            if best is None or value > best:
                best, winners = value, [row["id"]]
            elif value == best:
                winners.append(row["id"])
    return {"dispositions": dispositions, "winners": winners}


def breakpoints(rows, match, as_of):
    """Return measured thresholds where the eligible set changes. Limits are inclusive."""
    return sorted({
        exact(row["metric"]) for row in rows
        if classify(row, match, as_of, Decimal(0)) == "qualified"
    })
