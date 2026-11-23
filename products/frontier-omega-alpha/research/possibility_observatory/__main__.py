"""Read-only, evidence-bounded Possibility Observatory for FRONTIER Ω ALPHA.

Consumes the existing public release checkpoint and explicitly reviewed public
finding records. No model, network, publication, wallet or GitHub write actions.
"""
from argparse import ArgumentParser
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from ..__main__ import private_path
from ..scheduled import SCHEMA as RELEASE_SCHEMA, SOURCES

SCHEMA = "frontier-omega-alpha/possibility-atlas-v1"
GOALS_SCHEMA = "frontier-omega-alpha/blocked-purposes-v1"
AUDIT_SCHEMA = "frontier-omega-alpha/independent-coverage-review-v1"
FINDING_SCHEMA = "frontier-omega-alpha/research-finding-v2"
MAX_SOURCE_BYTES = 1024 * 1024
MAX_RECORD_BYTES = 96 * 1024
MAX_GOALS = 40
MAX_REVIEW_EVENTS = 100
SHA = re.compile(r"[a-f0-9]{64}\Z")
ID = re.compile(r"[a-z][a-z0-9-]{2,79}\Z")
STATES = {"unchanged", "first_observation", "checkpoint_upgraded",
          "published_version_changed", "metadata_changed", "unavailable"}
FINDING_STATES = {"detected", "experiment-prepared", "technically-verified",
                  "falsified", "source-insufficient"}
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()

def digest(data):
    return sha256(data).hexdigest()

def load(path, limit=MAX_SOURCE_BYTES):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Missing, linked, or oversized research input")
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError("Oversized research input")
    value = json.loads(raw)
    if type(value) is not dict:
        raise ValueError("Research input must be an object")
    return value, digest(raw)

def text(value, max_chars=350):
    if (not isinstance(value, str) or not value or len(value) > max_chars
            or any(ord(c) < 32 for c in value if c not in "\n\t")):
        raise ValueError("Invalid bounded research description")
    return value.strip()

def utc(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("Invalid UTC timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset().total_seconds() != 0:
        raise ValueError("Research date must be UTC")
    return dt

def safe_url(value):
    if not isinstance(value, str) or len(value) > 700:
        raise ValueError("Invalid source URL")
    p = urlsplit(value)
    if (p.scheme != "https" or not p.hostname or p.username or p.password
            or p.fragment or p.port not in (None, 443)):
        raise ValueError("Only public HTTPS source URLs are allowed")
    return value

def goals_at(path):
    value, hash_ = load(path, 96 * 1024)
    if value.get("schema") != GOALS_SCHEMA or type(value.get("goals")) is not list:
        raise ValueError("Wrong blocked-purpose registry")
    goals = value["goals"]
    if not 1 <= len(goals) <= MAX_GOALS:
        raise ValueError("Invalid goal count")
    seen = set()
    for g in goals:
        if (type(g) is not dict or set(g) !=
                {"id", "outcome", "binding_constraint", "missing_move_question",
                 "beneficiary", "strong_alternative", "experiment",
                 "falsifier", "rights", "source_keys", "future_trigger"}):
            raise ValueError("Invalid registered blocked-purpose fields")
        ident = g["id"]
        if not isinstance(ident, str) or not ID.fullmatch(ident) or ident in seen:
            raise ValueError("Duplicate or invalid goal")
        seen.add(ident)
        for key in ("outcome", "binding_constraint", "missing_move_question",
                    "beneficiary", "strong_alternative", "experiment",
                    "falsifier", "rights", "future_trigger"):
            text(g[key], 420)
        keys = g["source_keys"]
        if (type(keys) is not list or not keys or len(keys) != len(set(keys))
                or any(k not in SOURCES for k in keys)):
            raise ValueError("Unknown or duplicate source reference")
    return goals, hash_

def observations_at(path):
    value, hash_ = load(path)
    if (value.get("schema") != RELEASE_SCHEMA or type(value.get("sources")) is not dict
            or set(value["sources"]) != set(SOURCES)):
        raise ValueError("Unexpected release checkpoint or sources")
    observed = value["sources"]
    for key, item in observed.items():
        if type(item) is not dict or item.get("state") not in STATES:
            raise ValueError("Invalid observation state")
        record = item.get("observed")
        if record is None:
            if item["state"] != "unavailable":
                raise ValueError("No observed release")
            continue
        if (type(record) is not dict or type(record.get("id")) is not int
                or not isinstance(record.get("tag"), str)
                or not record["tag"] or len(record["tag"]) > 100
                or not isinstance(record.get("sha256"), str)
                or not SHA.fullmatch(record["sha256"])):
            raise ValueError("Invalid source identity")
        utc(record["published_at"])
        utc(record["retrieved_at"])
        safe_url(record["url"])
        repo = SOURCES[key][0]
        if not record["url"].startswith("https://api.github.com/repos/" + repo + "/releases/"):
            raise ValueError("Source identity outside reviewed release registry")
        if item["state"] == "published_version_changed":
            previous = item.get("preceding")
            if (type(previous) is not dict or not isinstance(previous.get("tag"), str)
                    or previous["tag"] == record["tag"]):
                raise ValueError("Version change without predecessor")
    return observed, hash_

def findings_at(paths):
    selected = []
    digests = []
    seen = set()
    if len(paths) > 40:
        raise ValueError("Too many approved records")
    for path in paths:
        obj, hash_ = load(path, MAX_RECORD_BYTES)
        if (obj.get("schema") != FINDING_SCHEMA
                or obj.get("classification") != "public-evidence"
                or obj.get("status") not in FINDING_STATES
                or obj.get("production_authority") is not False
                or type(obj.get("source_evidence")) is not list
                or not (1 <= len(obj["source_evidence"]) <= 4)):
            raise ValueError("Unapproved, private, or malformed finding")
        ident = obj.get("finding_id")
        if not isinstance(ident, str) or not SHA.fullmatch(ident) or ident in seen:
            raise ValueError("Invalid or repeated finding")
        seen.add(ident)
        reception = obj.get("reception") or {}
        if (reception.get("authenticated_by") != "github-rest"
                or reception.get("task_origin") != "operator-declared, task authorship unverified"
                or "source_task_id" in obj):
            raise ValueError("Finding lacks reviewed GitHub provenance")
        sources = []
        for source in obj["source_evidence"]:
            sources.append({"url": safe_url(source["url"]),
                            "sha256": source["sha256"], "version": text(source["version"], 120)})
            if not isinstance(source["sha256"], str) or not SHA.fullmatch(source["sha256"]):
                raise ValueError("Invalid referenced source hash")
        change = obj.get("change") or {}
        opportunity = obj.get("opportunity") or {}
        comparison = text(opportunity.get("existing_alternative"), 420)
        purpose = text(opportunity.get("purpose"), 420)
        selected.append({
            "id": ident, "status": obj["status"], "profile": text(obj.get("profile"), 90),
            "purpose": purpose, "strong_alternative": comparison, "sources": sources,
            "provenance": "GitHub-authenticated submission; ChatGPT origin operator-declared",
            "economics": "not independently established by this atlas",
        })
        digests.append({"id": ident, "digest": hash_})
    return sorted(selected, key=lambda x: x["id"]), sorted(digests, key=lambda x: x["id"])

def reviewed_audit(path, entries):
    if path is None:
        return {"state": "not-assessed", "reviewed": 0, "found": None,
                "missed": None, "note": "No independent, labelled reference set. Do not infer recall from alert count."}
    value, _ = load(path, 96 * 1024)
    if value.get("schema") != AUDIT_SCHEMA or type(value.get("events")) is not list:
        raise ValueError("Invalid independent review file")
    if len(value["events"]) > MAX_REVIEW_EVENTS:
        raise ValueError("Too many review references")
    observed = set()
    for e in entries:
        for s in e.get("source_events", []):
            if s.get("state") == "published_version_changed":
                observed.add((s["source_key"], s["tag"]))
    found, missed = [], []
    seen = set()
    for event in value["events"]:
        if type(event) is not dict or set(event) != {
                "id", "source_key", "tag", "evidence_url", "reviewer", "reviewed_at"}:
            raise ValueError("Invalid review event")
        ident = event["id"]
        if not isinstance(ident, str) or not ID.fullmatch(ident) or ident in seen:
            raise ValueError("Invalid independent reference ID")
        seen.add(ident)
        if event["source_key"] not in SOURCES:
            raise ValueError("Reference source is not in monitored universe")
        text(event["tag"], 100)
        text(event["reviewer"], 100)
        safe_url(event["evidence_url"])
        utc(event["reviewed_at"])
        (found if (event["source_key"], event["tag"]) in observed else missed).append(ident)
    return {"state": "reviewed-controls" if seen else "reference-set-empty",
            "reviewed": len(seen), "found": len(found), "missed": len(missed),
            "missed_ids": sorted(missed),
            "note": "Coverage only for these independently labelled source-version controls; not general frontier recall."}

def build(observations, goals, findings=None, audit=None, as_of=None):
    findings = findings or []
    as_of = as_of or date.today().isoformat()
    date.fromisoformat(as_of)
    entries, queue = [], []
    for g in goals:
        events = []
        for key in g["source_keys"]:
            item = observations[key]
            release = item.get("observed")
            events.append({
                "source_key": key, "state": item["state"],
                "tag": release["tag"] if release else None,
                "published_at": release["published_at"] if release else None,
                "retrieved_at": release["retrieved_at"] if release else None,
                "url": release["url"] if release else None,
                "evidence_sha256": release["sha256"] if release else None,
            })
        states = {event["state"] for event in events}
        if "published_version_changed" in states:
            status = "reopen-for-review"
        elif "metadata_changed" in states or "checkpoint_upgraded" in states:
            status = "source-change-review"
        elif states == {"unavailable"}:
            status = "source-unavailable"
        elif "first_observation" in states:
            status = "baseline-only"
        else:
            status = "watch"
        entry = {"id": g["id"], "purpose": g["outcome"],
                 "binding_constraint": g["binding_constraint"],
                 "missing_move_question": g["missing_move_question"],
                 "missing_move_hypothesis": None,
                 "beneficiary": g["beneficiary"], "strong_alternative": g["strong_alternative"],
                 "rights": g["rights"], "future_trigger": g["future_trigger"],
                 "status": status, "source_events": events,
                 "technical_advantage": "unproven",
                 "economic_advantage": "unproven",
                 "causal_successor_improvement": "unproven"}
        entries.append(entry)
        if status == "reopen-for-review":
            queue.append({"goal_id": g["id"], "status": "requires-registered-review",
                          "experiment": g["experiment"], "strong_alternative": g["strong_alternative"],
                          "falsifier": g["falsifier"], "rights": g["rights"],
                          "automatic_execution": False, "production_authority": False})
    entries.sort(key=lambda e: (e["status"] != "reopen-for-review", e["id"]))
    queue.sort(key=lambda e: e["goal_id"])
    counter = {state: 0 for state in STATES}
    for item in observations.values():
        counter[item["state"]] += 1
    result = {"schema": SCHEMA, "as_of": as_of,
              "scope": "Only monitored GitHub release identities and explicitly approved public findings",
              "source_count": len(observations), "source_states": counter,
              "entries": entries, "reviewed_findings": findings,
              "experiment_queue": queue, "independent_coverage": None,
              "alerts": "Not generated: a publisher version alone never authorizes an alert or experiment.",
              "financial_advice": False, "production_authority": False,
              "chatgpt_content_imported_automatically": False}
    result["independent_coverage"] = reviewed_audit(audit, entries)
    return result

def render(report, language="en"):
    fr = language == "fr"
    title = "# 🌌♾️ FRONTIER Ω ALPHA — Atlas des possibles" if fr else "# 🌌♾️ FRONTIER Ω ALPHA — Possibility Atlas"
    out = [title, "", "Date : " + report["as_of"] if fr else "Date: " + report["as_of"], ""]
    if fr:
        out.append("**Portée :** publications publiques suivies et dossiers explicitement approuvés; aucune importation automatique des conversations ChatGPT.")
    else:
        out.append("**Scope:** monitored public releases and explicitly approved findings; no automatic ChatGPT conversation import.")
    out += ["", "## " + ("Possibilités surveillées" if fr else "Tracked possibilities"), ""]
    for e in report["entries"]:
        out.append("- **" + e["id"] + "** — " + e["status"] + ": " + e["purpose"])
        out.append("  - " + ("Alternative : " if fr else "Comparator: ") + e["strong_alternative"])
    out += ["", "## " + ("Essais à examiner" if fr else "Experiments for human review"), ""]
    if not report["experiment_queue"]:
        out.append("Aucun essai débloqué par un changement de version confirmé." if fr
                   else "No experiment reopened by a confirmed source-version change.")
    for q in report["experiment_queue"]:
        out.append("- **" + q["goal_id"] + "** — " + q["experiment"])
    coverage = report["independent_coverage"]
    out += ["", "## " + ("Audit indépendant" if fr else "Independent discovery audit"), "",
            coverage["note"], "",
            "**" + ("Aucun avantage économique ou causal n'est prouvé par cet atlas." if fr
                    else "This atlas does not establish economic or causal invention advantage.") + "**", ""]
    return "\n".join(out)

def main():
    os.umask(0o077)
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--registry", default=str(HERE / "blocked-purposes.json"))
    parser.add_argument("--approved-record", action="append", default=[])
    parser.add_argument("--audit")
    parser.add_argument("--as-of")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        output = private_path(args.output)
        if output.exists() or output.is_symlink():
            raise ValueError("Choose a new private output directory")
        observations, observed_hash = observations_at(args.observations)
        goals, goal_hash = goals_at(args.registry)
        findings, finding_hashes = findings_at(args.approved_record)
        audit = args.audit
        report = build(observations, goals, findings, audit, args.as_of)
        report["input_provenance"] = {
            "release_checkpoint_sha256": observed_hash, "registry_sha256": goal_hash,
            "approved_findings": finding_hashes}
        output.mkdir(mode=0o700, parents=True)
        for name, value in (("atlas.json", report), ("experiment-queue.json", report["experiment_queue"])):
            with (output / name).open("x", encoding="utf-8") as f:
                json.dump(value, f, indent=2, ensure_ascii=False, sort_keys=True)
                f.write("\n")
        for lang in ("en", "fr"):
            (output / ("atlas." + lang + ".md")).write_text(render(report, lang), encoding="utf-8")
        return 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("Observatory rejected invalid, unreviewed or unsafe evidence: " + type(exc).__name__, file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
