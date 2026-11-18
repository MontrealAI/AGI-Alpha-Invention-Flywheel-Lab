"""Private, precommitted shadow-review packets and arm-blind adjudication."""
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ARMS = ("A", "B", "C", "D", "E")
CATEGORIES = ("acquisition", "compute_and_tools", "operator_delivery", "failed_work_and_corrections",
              "independent_verification", "allocated_construction", "maintenance_support", "other_obligations")
MEASURES = ("operator_seconds", "correction_seconds", "verification_seconds", "interventions",
            "search_requests", "repeated_search_requests")
SHA = re.compile(r"[0-9a-f]{64}\Z")
MEASUREMENT = ("witness", "reference", "baseline", "trigger", "unit", "packet_sha256", "direction", "delta_mag", "sigma_mag")
ID = re.compile(r"[a-zA-Z0-9_-]{1,100}\Z")


def check(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        check(key not in result, "Duplicate JSON member")
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique, parse_constant=bad_constant)


def bad_constant(value):
    raise ValueError("Nonfinite JSON value: " + value)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")


def utc(value):
    check(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value),
          "Full UTC timestamp required")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def safe_member(name):
    return (isinstance(name, str) and bool(name) and not Path(name).is_absolute()
            and all(part not in ("", ".", "..") for part in name.split("/")) and "\\" not in name)


def bind_sources(root, names):
    root = Path(root).resolve(strict=True)
    names = list(names)
    check(names and len(set(names)) == len(names), "Name distinct authorized source files")
    out = {}
    for name in names:
        check(safe_member(name), "Use a relative source member inside the authorized folder")
        path = (root / name).resolve(strict=True)
        check(path.is_relative_to(root) and path.is_file(), "Source member is outside the authorized folder")
        h = hashlib.sha256()
        with path.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        out[name] = h.hexdigest()
    return out


def initialize(directory, plan, cases):
    check(plan.get("mode") in {"field", "historical_rehearsal"}, "Unknown study mode")
    required = ("objective", "roster_rule", "end_rule", "allowed_sources", "clock_basis", "grading_rule",
                "cost_horizon", "incumbent", "operator_budget", "source_access", "assignment_rule")
    check(all(isinstance(plan.get(k), str) and plan[k].strip() for k in required), "Incomplete beneficiary protocol")
    check(re.fullmatch(r"[A-Z]{3}", plan["currency"]), "Currency required")
    if plan["mode"] == "field":
        check(all(isinstance(plan.get(k), str) and plan[k].strip()
                  for k in ("authority_receipt", "consent_receipt")), "Actual field authority and consent references required")
        assignments = plan.get("operator_assignments")
        check(isinstance(assignments, dict) and set(assignments) == set(ARMS),
              "Declare each arm's private assigned operator or an unstaffed null")
        staffed = [v for v in assignments.values() if v is not None]
        check(all(isinstance(v, str) and ID.fullmatch(v) for v in staffed) and len(set(staffed)) == len(staffed),
              "The same operator cannot handle multiple arms on a shared cluster")
        reviewers = plan.get("reviewers")
        check(isinstance(reviewers, list) and len(reviewers) >= 2 and len(set(reviewers)) == len(reviewers)
              and all(isinstance(v, str) and ID.fullmatch(v) for v in reviewers)
              and not set(reviewers).intersection(staffed), "Register independent pseudonymous graders")
    roster = {}
    for case in cases:
        key = case["case_id"]
        check(ID.fullmatch(key) and key not in roster and ID.fullmatch(case["cluster"]), "Invalid or repeated roster case")
        utc(case["cutoff_utc"])
        check(isinstance(case.get("question"), str) and case["question"].strip() and SHA.fullmatch(case["source_set_sha256"]),
              "Missing question or source snapshot identity")
        if plan["mode"] == "field":
            check(utc(case["decision_due_utc"]) >= utc(case["cutoff_utc"]), "Due time predates the evidence cutoff")
            manifest = case.get("source_manifest")
            check(isinstance(manifest, dict) and bool(manifest) and all(safe_member(k) and isinstance(v, str)
                  and SHA.fullmatch(v) for k, v in manifest.items()) and digest(manifest) == case["source_set_sha256"],
                  "Field case must bind the exact authorized source manifest")
        arrival = case.get("available_utc")
        if arrival is not None:
            check(plan["mode"] == "field" and utc(arrival) <= utc(case["cutoff_utc"])
                  and SHA.fullmatch(case["availability_proof_sha256"]), "Unqualified availability clock")
        roster[key] = case
    check(roster, "An empty roster cannot be scored")
    directory = Path(directory)
    directory.mkdir(mode=0o700)
    (directory / "tasks").mkdir(mode=0o700)
    seed = secrets.token_bytes(32)
    commitment = digest({"plan": plan, "cases": cases})
    def token(kind, *parts):
        return hmac.digest(seed, encoded([kind, *parts]).encode(), "sha256").hex()[:32]
    dbpath = directory / "private.sqlite"
    with sqlite3.connect(dbpath) as db:
        os.chmod(dbpath, 0o600)
        db.executescript("""
            CREATE TABLE study(plan TEXT, commitment TEXT, truth TEXT, blinded INTEGER DEFAULT 0, review_closure TEXT);
            CREATE TABLE tasks(arm TEXT, case_id TEXT, cluster_id TEXT, task TEXT UNIQUE, blind TEXT UNIQUE,
                               body TEXT, answer TEXT, received TEXT, PRIMARY KEY(arm,case_id));
            CREATE TABLE reviews(reviewer TEXT PRIMARY KEY, scores TEXT);
        """)
        db.execute("INSERT INTO study(plan,commitment) VALUES (?,?)", (encoded(plan), commitment))
        for arm in ARMS:
            tasks = []
            for key, case in roster.items():
                task, blind = token("ticket", arm, key), token("grading", arm, key)
                tasks.append({"ticket": task, "question": case["question"], "case_id": key,
                              "cluster": case["cluster"], "cutoff_utc": case["cutoff_utc"],
                              "source_set_sha256": case["source_set_sha256"]})
                if "source_manifest" in case:
                    tasks[-1]["source_manifest"] = case["source_manifest"]
                    tasks[-1]["decision_due_utc"] = case["decision_due_utc"]
                db.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,NULL,NULL)",
                           (arm, key, case["cluster"], task, blind, encoded(case)))
            # Keep each event's cutoffs chronological. Rotate event order independently.
            tasks.sort(key=lambda t: (token("order", arm, t["cluster"]), t["cutoff_utc"], t["case_id"]))
            write(directory / "tasks" / (arm + ".json"), {"protocol_sha256": commitment, "tasks": tasks,
                  "brief": {k: plan[k] for k in ("objective", "clock_basis", "allowed_sources", "source_access",
                                                  "operator_budget", "grading_rule", "end_rule")}})
    write(directory / "commitment.json", {"protocol_sha256": commitment, "cases": len(cases),
                                           "clusters": len({case["cluster"] for case in cases}), "arms": list(ARMS)})
    return commitment


def connect(directory):
    path = Path(directory) / "private.sqlite"
    check(path.is_file(), "Private study has not been prepared")
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db


def save_key(db, answers):
    with db:
        db.execute("BEGIN IMMEDIATE")
        state = db.execute("SELECT * FROM study").fetchone()
        check(not state["blinded"], "Key must be sealed before grading")
        cases = {row[0] for row in db.execute("SELECT DISTINCT case_id FROM tasks")}
        check(set(answers) == cases, "The key must cover the entire frozen roster")
        for answer in answers.values():
            check(answer["action"] in {"deliver", "keep_open", "review", "unsettled"}
                  and SHA.fullmatch(answer["reference_sha256"]), "Incomplete independent key")
            if answer["action"] == "deliver":
                check(valid_measurement(answer.get("measurement")), "Unqualified reference measurement")
        value = encoded(answers)
        check(state["truth"] in (None, value), "The committed decision key changed")
        db.execute("UPDATE study SET truth=?", (value,))
    return digest(answers)


def valid_measurement(m):
    if not isinstance(m, dict):
        return False
    numbers = [m.get("delta_mag"), m.get("sigma_mag")]
    return (m.get("unit") == "mag" and m.get("direction") in {"persisted", "reversed", "not_reproduced"}
            and all(isinstance(m.get(k), str) and m[k].isdigit() for k in ("witness", "reference", "baseline", "trigger"))
            and isinstance(m.get("packet_sha256"), str) and bool(SHA.fullmatch(m["packet_sha256"]))
            and all(type(v) in (float, int) and math.isfinite(v) for v in numbers) and numbers[1] > 0)


def submit(db, packet):
    with db:
        db.execute("BEGIN IMMEDIATE")
        state = db.execute("SELECT * FROM study").fetchone()
        check(not state["blinded"] and packet.get("protocol_sha256") == state["commitment"],
              "Closed study or changed protocol")
        check(state["truth"] is not None, "Lock the independent key before accepting route submissions")
        plan = json.loads(state["plan"])
        seen = set()
        for entry in packet["responses"]:
            ticket = entry["ticket"]
            row = db.execute("SELECT * FROM tasks WHERE task=?", (ticket,)).fetchone()
            check(row and ticket not in seen, "Duplicate or unknown assignment")
            seen.add(ticket)
            if plan["mode"] == "field":
                check(plan["operator_assignments"][row["arm"]] is not None and
                      packet.get("operator") == plan["operator_assignments"][row["arm"]], "Different or unstaffed field operator")
            body = json.loads(row["body"])
            check(entry["source_set_sha256"] == body["source_set_sha256"], "Source snapshot changed")
            ans = encoded(entry["answer"])
            check(isinstance(entry["answer"], dict) and row["answer"] in (None, ans), "Conflicting or malformed answer")
            if row["answer"] is None:
                received = datetime.now(timezone.utc)
                if plan["mode"] == "field":
                    check(received >= utc(body["cutoff_utc"]), "Cannot submit this prospective evidence prefix before its cutoff")
                db.execute("UPDATE tasks SET answer=?, received=? WHERE task=?", (ans, received.isoformat(), ticket))


def blind(db):
    with db:
        db.execute("BEGIN IMMEDIATE")
        state = db.execute("SELECT * FROM study").fetchone()
        check(state["truth"] is not None, "An independently committed reference is required")
        db.execute("UPDATE study SET blinded=1")
        output = []
        for r in db.execute("SELECT * FROM tasks WHERE answer IS NOT NULL ORDER BY blind"):
            body = json.loads(r["body"])
            answer = json.loads(r["answer"])
            public = {"action": answer.get("action") if answer.get("action") in {"deliver", "keep_open", "review"} else "invalid"}
            if isinstance(answer.get("measurement"), dict):
                m = answer["measurement"]
                if valid_measurement(m):
                    public["measurement"] = {k: (round(m[k], 5) if k in ("delta_mag", "sigma_mag") else m[k]) for k in MEASUREMENT}
                else:
                    public["measurement"] = {"invalid": True}
            output.append({"code": r["blind"], "question": body["question"], "cutoff_utc": body["cutoff_utc"],
                           "source_set_sha256": body["source_set_sha256"],
                           "decision": public})
    return {"protocol_sha256": state["commitment"], "key_sha256": digest(json.loads(state["truth"])),
            "records": output}


def review(db, record):
    with db:
        db.execute("BEGIN IMMEDIATE")
        state = db.execute("SELECT * FROM study").fetchone()
        check(state["blinded"] and state["review_closure"] is None and record["protocol_sha256"] == state["commitment"]
              and record["key_sha256"] == digest(json.loads(state["truth"])), "Closed or different grading batch")
        who = record["reviewer"]
        check(ID.fullmatch(who), "Use a private pseudonym for the reviewer")
        check(record.get("reviewer_independent") is True, "Independent reviewing role required")
        codes = {r[0] for r in db.execute("SELECT blind FROM tasks WHERE answer IS NOT NULL")}
        plan = json.loads(state["plan"])
        if plan["mode"] == "field":
            check(who in plan["reviewers"], "Use an independently registered reviewer")
        scores = record["scores"]
        check(set(scores) == codes, "Grade each returned response, retaining unknowns")
        for code, item in scores.items():
            if item.get("accepted_decision_utc") is not None:
                received = db.execute("SELECT received FROM tasks WHERE blind=?", (code,)).fetchone()[0]
                check(utc(received) <= utc(item["accepted_decision_utc"]) <= datetime.now(timezone.utc),
                      "A witnessed acceptance must follow submission and precede grading")
                check(isinstance(item.get("acceptance_receipt_sha256"), str)
                      and SHA.fullmatch(item["acceptance_receipt_sha256"]), "A dated accepted decision needs a receipt")
            check(item.get("use") in {"observed_use", "no_observed_use", "unknown"}, "Invalid beneficiary use adjudication")
            if item["use"] != "unknown":
                check(isinstance(item.get("beneficiary_receipt_sha256"), str)
                      and SHA.fullmatch(item["beneficiary_receipt_sha256"]), "Beneficiary observation receipt is required")
        old = db.execute("SELECT scores FROM reviews WHERE reviewer=?", (who,)).fetchone()
        check(not old or old[0] == encoded(scores), "Reviewer submission already locked")
        db.execute("INSERT OR IGNORE INTO reviews VALUES (?,?)", (who, encoded(scores)))


def close_reviews(db, reason):
    check(isinstance(reason, str) and bool(reason.strip()), "Record the actual reason for closing the panel")
    with db:
        db.execute("BEGIN IMMEDIATE")
        state = db.execute("SELECT * FROM study").fetchone()
        check(state["blinded"] and state["review_closure"] in (None, reason), "Different or premature review closure")
        db.execute("UPDATE study SET review_closure=?", (reason,))


def correct(expected, answer):
    if expected["action"] == "unsettled":
        return None
    if expected["action"] != answer.get("action"):
        return False
    if expected["action"] != "deliver":
        return answer.get("measurement") is None
    got, ref = answer.get("measurement"), expected["measurement"]
    if not valid_measurement(got):
        return False
    fields = ("witness", "reference", "baseline", "trigger", "unit", "packet_sha256", "direction")
    return all(got[k] == ref[k] for k in fields) and all(
        abs(got[k] - ref[k]) <= 0.00001 for k in ("delta_mag", "sigma_mag"))


def arm_cost(plan, supplied, useful):
    if supplied is None:
        supplied = {}
    if supplied:
        check(supplied.get("currency") == plan["currency"] and supplied.get("horizon") == plan["cost_horizon"],
              "Cost currency or allocation horizon differs")
        check(set(supplied.get("costs", {})) == set(CATEGORIES), "Enter every cost category, including unknowns")
    amounts = {}
    for name in CATEGORIES:
        raw = supplied.get("costs", {}).get(name)
        if raw is None:
            amounts[name] = None
        else:
            check(isinstance(raw, str), "Use decimal strings for money")
            n = Decimal(raw)
            check(n.is_finite() and n >= 0, "Invalid cost")
            amounts[name] = n
    provenance = supplied.get("basis", {})
    for name, amount in amounts.items():
        if amount is not None:
            basis = provenance.get(name, {})
            check(basis.get("kind") in {"measured", "estimate"} and isinstance(basis.get("source"), str)
                  and bool(basis["source"].strip()), "Each priced cost needs evidence or an identified estimate")
    counts = {}
    for k in MEASURES:
        v = supplied.get("measures", {}).get(k)
        check(v is None or (type(v) in (float, int) and math.isfinite(v) and v >= 0), "Invalid work measure")
        counts[k] = v
    complete = sum(amounts.values(), Decimal(0)) if all(v is not None for v in amounts.values()) else None
    return {"currency": plan["currency"], "cost_horizon": plan["cost_horizon"], "work_measures": counts,
            "allocated_amounts": {k: str(v) if v is not None else None for k, v in amounts.items()},
            "basis": provenance, "complete_cost": str(complete) if complete is not None else None,
            "complete_cost_kind": (("includes_estimates" if any(provenance[n]["kind"] == "estimate" for n in CATEGORIES)
                                    else "all_measured") if complete is not None else None),
            "accepted_useful_decisions_per_operator_hour": (useful * 3600 / counts["operator_seconds"]
                                                            if useful is not None and counts["operator_seconds"] else None),
            "cost_per_accepted_useful_decision": str(complete / useful) if complete is not None and useful else None}


def summarize(db, costs=None):
    state = db.execute("SELECT * FROM study").fetchone()
    check(state["blinded"], "Close submissions before unmasking")
    plan, truth = json.loads(state["plan"]), json.loads(state["truth"])
    panels = [json.loads(r[0]) for r in db.execute("SELECT scores FROM reviews")]
    if plan["mode"] == "field":
        check(state["review_closure"] is not None, "Lock reviews before revealing field arm labels")
    costs = costs or {}
    check(set(costs) <= set(ARMS), "Unknown cost arm")
    arms, delivered = {}, {}
    for arm in ARMS:
        rows = list(db.execute("SELECT * FROM tasks WHERE arm=? ORDER BY case_id", (arm,)))
        counts = dict.fromkeys(("submitted","accepted","scientifically_correct","late_submissions","correct_deliveries","false_priorities","missed_priorities",
                                "invalid_decisions","missing_actions_on_deliverable","unsettled_reference"), 0)
        delivered[arm] = set()
        useful = 0
        fully_reviewed = True
        available_lags = []
        accepted_lags = []
        for row in rows:
            ref = truth[row["case_id"]]
            if ref["action"] == "unsettled":
                counts["unsettled_reference"] += 1
            if row["answer"] is None:
                counts["missing_actions_on_deliverable"] += ref["action"] == "deliver"
                continue
            counts["submitted"] += 1
            answer = json.loads(row["answer"])
            scientific = correct(ref, answer)
            case = json.loads(row["body"])
            late = bool(case.get("decision_due_utc") and utc(row["received"]) > utc(case["decision_due_utc"]))
            counts["late_submissions"] += late
            counts["scientifically_correct"] += scientific is True
            accepted = False if late and scientific is not None else scientific
            counts["accepted"] += accepted is True
            counts["invalid_decisions"] += scientific is False
            counts["false_priorities"] += ref["action"] not in {"deliver", "unsettled"} and answer.get("action") == "deliver"
            counts["missed_priorities"] += ref["action"] == "deliver" and accepted is False
            if accepted and ref["action"] == "deliver":
                counts["correct_deliveries"] += 1
                delivered[arm].add(row["case_id"])
            if accepted and case.get("available_utc"):
                lag = (utc(row["received"]) - utc(case["available_utc"])).total_seconds()
                check(lag >= 0, "Receipt predates verified availability")
                available_lags.append(lag)
            ratings = [p[row["blind"]] for p in panels]
            if accepted and case.get("available_utc"):
                attestations = [(v["accepted_decision_utc"], v["acceptance_receipt_sha256"])
                                for v in ratings if v.get("accepted_decision_utc")]
                for stamp in set(attestations):
                    if attestations.count(stamp) >= 2 and attestations.count(stamp) > len(ratings) / 2:
                        accepted_at = utc(stamp[0])
                        check(utc(row["received"]) <= accepted_at, "Observed acceptance predates route submission")
                        accepted_lags.append((accepted_at - utc(case["available_utc"])).total_seconds())
            choices = [(v["use"], v.get("beneficiary_receipt_sha256")) for v in ratings]
            majority = [v[0] for v in set(choices) if v[0] != "unknown" and choices.count(v) >= 2
                        and choices.count(v) > len(choices) / 2]
            if not majority:
                fully_reviewed = False
            elif accepted and majority[0] == "observed_use":
                useful += 1
        observed_use = useful if (plan["mode"] == "field" and counts["submitted"] and fully_reviewed) else None
        arms[arm] = {"slots": len(rows), "clusters": len({r["cluster_id"] for r in rows}), **counts,
                     "missing_submissions": len(rows)-counts["submitted"], "accepted_with_observed_beneficiary_use": observed_use,
                     "availability_to_accepted_submission_seconds": available_lags or None,
                     "availability_to_accepted_decision_seconds": accepted_lags or None,
                     "costs": arm_cost(plan, costs.get(arm), observed_use)}
    for arm in ARMS:
        measured = arms["A"]["submitted"] == arms["A"]["slots"] and arms[arm]["submitted"] == arms[arm]["slots"]
        arms[arm]["accepted_cases_unresolved_by_actual_incumbent"] = sorted(delivered[arm] - delivered["A"]) if measured else None
    return {"protocol_sha256": state["commitment"], "key_sha256": digest(truth), "mode": plan["mode"],
            "independent_use_reviewers": len(panels), "closure": state["review_closure"], "arms": arms}
