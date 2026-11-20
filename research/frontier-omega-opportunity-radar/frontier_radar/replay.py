"""Offline comparison of dated reconstructions, not a deployment backtest."""
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from . import core

_START = date(2026, 7, 1)
_DIGEST_LIMIT = 4
_DIGEST_LOOKBACK_DAYS = 7
_ACTION_FIELDS = ("move", "alternative", "ownership", "experiment", "pass_threshold", "stop_threshold")


def _end_of_day(day):
    return datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc)


def _windows(start, cutoff):
    """One fixed seven-day sequence plus partial final window."""
    day = start + timedelta(days=_DIGEST_LOOKBACK_DAYS - 1)
    while day < cutoff.date():
        yield _end_of_day(day)
        day += timedelta(days=_DIGEST_LOOKBACK_DAYS)
    yield cutoff


def _known_instant(day, stamp, cutoff):
    """An undated-in-time announcement is known only at UTC day close."""
    day = date.fromisoformat(day)
    if stamp:
        published = core.instant(stamp)
        return published.astimezone(timezone.utc).date() == day and published <= cutoff
    return _end_of_day(day) <= cutoff


def _dated_available(row, key, cutoff):
    return _known_instant(row[key], row.get(key + "_instant"), cutoff) and all(
        _known_instant(source["date"], source.get("available_at"), cutoff)
        for source in row.get("sources", ())
    )


def _digest(atlas, cutoff):
    earliest = cutoff.date() - timedelta(days=_DIGEST_LOOKBACK_DAYS - 1)
    headlines = [
        row for row in core.atlas_at(atlas, cutoff)
        if date.fromisoformat(row["announced_at"]) >= earliest
        and _dated_available(row, "announced_at", cutoff)
    ]
    # No importance weights, downstream information or injected decisions.
    headlines.sort(key=lambda r: (-date.fromisoformat(r["announced_at"]).toordinal(), r["id"]))
    return headlines[:_DIGEST_LIMIT]


def _release_match(rec, headline):
    return (headline["id"] in (rec.get("enabled_by") or ()) or
            not {s["url"] for s in rec.get("sources", [])}.isdisjoint(
                s["url"] for s in headline.get("sources", [])))


def _comparison(atlas, records, cutoff):
    published = _digest(atlas, cutoff)
    dig = [{"id": r["id"], "title": r.get("title"), "announced_at": r["announced_at"]}
           for r in published]
    records_seen = []
    for rec in sorted(records, key=lambda r: r["id"]):
        policy = core.assess(rec, cutoff, history=True)
        if policy["decision"] == "UNAVAILABLE" or not _dated_available(rec, "as_of", cutoff):
            continue
        represented = any(_release_match(rec, headline) for headline in published)
        missing = [key for key in _ACTION_FIELDS
                   if not isinstance(rec.get(key), str) or not rec[key].strip()]
        records_seen.append({
            "id": rec["id"], "title": rec.get("title"),
            "radar_decision": policy["decision"], "radar_reason": policy["reason"],
            "digest_decision": None, "digest_mentions_related_release": represented,
            "radar_decision_fields_present": len(_ACTION_FIELDS) - len(missing),
            "radar_missing_decision_fields": missing,
            "radar_proposed_test": rec.get("experiment"),
            "radar_proposed_stop_threshold": rec.get("stop_threshold"),
            "alert_emitted": False,
            "verification": "current_curation_reconstructed_as_of_date",
        })
    return {"as_of": cutoff.isoformat(), "digest": dig, "radar": records_seen}


def run(atlas, records, as_of):
    """Return a JSON-serializable audit; no persistence, dispatch or network.

    Both arms read the same surviving milestone corpus. The radar arm also
    uses dated analyst-authored records: this is explicitly an intervention,
    not a controlled equal-effort test.
    """
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("Replay as_of must be a timezone-aware datetime")
    cutoff = as_of.astimezone(timezone.utc)
    if cutoff.date() < _START:
        raise ValueError("Replay cutoff precedes the coverage start")
    records = tuple(records)
    windows = [_comparison(atlas, records, t) for t in _windows(_START, cutoff)]
    reviewed = windows[-1]["radar"]
    # Count a record once, not every week it was retained.
    same_window_cases = {
        case["id"]
        for window in windows for case in window["radar"]
        if case["digest_mentions_related_release"] and not case["radar_missing_decision_fields"]
    }
    available_milestones = [
        r for r in core.atlas_at(atlas, cutoff)
        if _dated_available(r, "announced_at", cutoff)
    ]
    records_by_id = {r["id"]: r for r in records}
    retrospective = []
    historical_headlines = {h["id"] for window in windows for h in window["digest"]}
    for case in reviewed:
        record = records_by_id[case["id"]]
        linked = [m for m in available_milestones if _release_match(record, m)]
        retrospective.append({
            "id": case["id"],
            "disposition": case["radar_decision"],
            "related_public_milestones": sorted(m["id"] for m in linked),
            "related_milestones_seen_in_digest": sorted(
                m["id"] for m in linked if m["id"] in historical_headlines),
            "same_window_comparison": case["id"] in same_window_cases,
            "interpretation": "Analyst-authored record reviewed after headline curation; not a measured earlier or better decision.",
        })
    return {
        "mode": "retrospective_dated_reconstruction",
        "as_of": cutoff.isoformat(),
        "coverage_start": _START.isoformat(),
        "atlas_cutoff_precedes_run_date": (
            not atlas.get("cutoff") or date.fromisoformat(atlas["cutoff"]) < cutoff.date()
        ),
        "comparison_protocol": {
            "digest": "Up to four recent headlines ordered by date then ID; same curated milestone corpus, fixed seven UTC date lookback. No decision extraction.",
            "radar": "Dated milestone corpus plus human-authored opportunity records; historical evaluation is silent.",
            "rubric": list(_ACTION_FIELDS),
            "dates": "Exclude calendar-date-only evidence before UTC day close. Optional explicit timestamps must be timezone-aware and agree with the declared UTC date. Text/version availability is not proved by dates alone.",
            "gold_labels": "none independently timestamped and adjudicated",
            "scoring_registered_before_historical_period": False,
        },
        "metrics": {
            "cutoffs": len(windows),
            "milestones_available_at_final_cutoff": len(available_milestones),
            "decision_records_available_at_final_cutoff": len(reviewed),
            "decision_counts": dict(sorted(Counter(x["radar_decision"] for x in reviewed).items())),
            "complete_radar_decision_records": sum(not r["radar_missing_decision_fields"] for r in reviewed),
            "digest_headline_impressions_across_cutoffs": sum(len(w["digest"]) for w in windows),
            "distinct_digest_headlines": len(historical_headlines),
            "digest_produced_decisions": 0,
            "same_window_related_headline_and_complete_radar_record_count": len(same_window_cases),
            "alerts_emitted_by_replay": 0,
            "missed_material_events": None,
            "false_alerts": None,
            "duplicate_alerts_live": None,
            "decision_time_gained": None,
            "review_minutes": None,
            "operating_cost": None,
            "accuracy_or_economic_impact": None,
        },
        "cases": reviewed,
        "retrospective_review": retrospective,
        "windows": windows,
        "limitations": [
            "No frozen historical decision log or independent gold set. Earlier inputs, decision lead time, false positives, misses and actual economic improvements remain unmeasured.",
            "Source publication timestamps do not prove the exact facts, licenses or mutable text were available then.",
            "The comparator is a plain news digest, not a skilled analyst using it. Structured next actions are demonstrated; superiority over skilled analysts is not.",
            "Dated hand-curation is separate from live detection and cannot demonstrate autonomous discovery, real monitoring coverage or commercial demand.",
            "Use a prospective paired comparison with the rubric and stopping rule registered before opening captures, equal reviewer time, and independent adjudication before changing production delivery.",
        ],
    }
