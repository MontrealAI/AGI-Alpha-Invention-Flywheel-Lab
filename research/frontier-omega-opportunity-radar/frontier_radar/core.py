"""Explicit decision gates and as-of rendering. Source text has no authority."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json

DATA = Path(__file__).with_name("data")
TORONTO = ZoneInfo("America/Toronto")


def digest(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load_data():
    atlas = json.loads((DATA / "atlas.json").read_text(encoding="utf-8"))
    opportunities = json.loads((DATA / "opportunities.json").read_text(encoding="utf-8"))
    return atlas, opportunities


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Explicit timezone required")
    return parsed


def next_friday(as_of):
    local = as_of.astimezone(TORONTO)
    target = (local + timedelta(days=(4 - local.weekday()) % 7)).replace(hour=8, minute=0, second=0, microsecond=0)
    return target if target > local else target + timedelta(days=7)


def _known_at(day, stamp, cutoff):
    """Conservatively treat date-only claims as known after their UTC day.

    An optional observed timestamp can establish earlier eligibility; never
    invent an intraday publication hour from a calendar date.
    """
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("timezone-aware cutoff required")
    declared = date.fromisoformat(day)
    if stamp is not None:
        try:
            observed = instant(stamp).astimezone(timezone.utc)
        except (ValueError, TypeError, OverflowError, AttributeError):
            return False
        return observed.date() == declared and observed <= cutoff.astimezone(timezone.utc)
    return cutoff.astimezone(timezone.utc) >= datetime.combine(
        declared + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )


def evidence_available(record, as_of):
    """Require every source to be known at this exact UTC instant."""
    sources = record.get("sources", [])
    return bool(sources) and all(s.get("date") and _known_at(s["date"], s.get("available_at"), as_of)
                                 for s in sources)


def assess(record, as_of, *, history=False):
    def result(label, reason, alert=False):
        return {"id": record["id"], "decision": label, "reason": reason, "alert": alert}

    end = as_of.astimezone(timezone.utc).date()
    if not _known_at(record["as_of"], record.get("as_of_instant"), as_of) or not evidence_available(record, as_of):
        return result("UNAVAILABLE", "Record or source availability not proven by the cutoff.")
    if record["recommendation"] == "PASS":
        return result("PASS", "Recorded rejection.")
    if record["capability_verified"] is not True:
        return result("TEST", "Capability not verified. No immediate alert.")
    if record["ownership_supported"] is not True:
        return result("TEST", "Retained value not supported. No immediate alert.")
    label = record["recommendation"]
    if label == "SELL" and not (record["demand_observed"] is True and record["delivery_verified"] is True):
        label = "TEST"
    if history:
        return result(label, "Historical replay never emits immediate alerts.")
    if end - date.fromisoformat(record["as_of"]) > timedelta(days=7):
        return result(label, "Needs fresh review; historical backfill is silent.")
    urgency = record.get("urgency")
    if not urgency or not urgency.get("reason", "").strip():
        return result(label, "No specific cost of waiting.")
    if urgency.get("certainty") != "fixed_deadline":
        return result(label, "A lower bound, estimate, or unknown cutoff is not a verified deadline.")
    if not any(s.get("url") == urgency.get("source_url") and s.get("url")
               for s in record["sources"]):
        return result(label, "Urgency has no dated evidence reference.")
    deadline = instant(urgency["expires_at"])
    if not as_of < deadline <= next_friday(as_of):
        return result(label, "Opening already expired or next Friday comes first.")
    return result(label, urgency["reason"], True)


def atlas_at(atlas, as_of):
    return [r for r in atlas["milestones"]
            if _known_at(r["announced_at"], r.get("announced_at_instant"), as_of)
            and evidence_available(r, as_of)]


def briefing(atlas, records, as_of, health=None):
    cutoff = as_of.astimezone(TORONTO).strftime("%Y-%m-%d %H:%M %Z")
    lines = ["# FRONTIER Ω | Friday research briefing", f"As of {cutoff}. Historical claims are not live verification."]
    if health and any(x.get("status") not in ("ok", "not_modified") for x in health):
        lines.append("**Coverage degraded.** See source health; silence is not confirmation.")
    milestones = atlas_at(atlas, as_of)
    recent = [x for x in milestones if date.fromisoformat(x["announced_at"]) >= as_of.astimezone(timezone.utc).date() - timedelta(days=7)]
    ranked = sorted(recent, key=lambda x: (x["importance"], x["relevance"], x["announced_at"]), reverse=True)
    lines += ["", "## Read first"]
    if not ranked:
        lines.append("No material recent milestone in the reviewed atlas. This is not a claim about unreviewed sources.")
    for m in ranked[:4]:
        s = m["sources"][0]
        lines.append(f'- [{m["title"]}]({s["url"]}) ({m["announced_at"]}): {m["change"]} Evidence: {m["evidence"]}')
    lines += ["", "## Moves worth testing"]
    for r in sorted(records, key=lambda x: (-x["priority"], x["id"])):
        d = assess(r, as_of, history=True)
        if d["decision"] in ("UNAVAILABLE", "PASS"):
            continue
        lines += [f'- **{d["decision"]} · {r["title"]}**: {r["move"]}',
                  f'  Next: {r["experiment"]} Stop: {r["stop_threshold"]}']
    lines += ["", f"Atlas research cutoff: {atlas['cutoff']}. See atlas coverage and exclusions for gaps."]
    return "\n".join(lines) + "\n"


def alert_text(record, decision):
    refs = " ".join(f'[{s["title"]}]({s["url"]})' for s in record["sources"])
    return "\n".join([
        f'**{decision["decision"]} · {record["title"]}**',
        record["move"], f'**Evidence:** {record["change"]} {refs}',
        f'**Alternative:** {record["alternative"]}',
        f'**Retained value:** {record["ownership"]} {record["economics"]}',
        f'**Why now:** {decision["reason"]} Deadline: {record["urgency"]["expires_at"]}.',
        f'**Next:** {record["experiment"]} Pass: {record["pass_threshold"]} Stop: {record["stop_threshold"]}',
    ])
