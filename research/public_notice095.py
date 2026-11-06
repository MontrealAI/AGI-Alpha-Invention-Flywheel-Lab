"""PublicNotice095: chronologically honest public-procurement evidence, never bid authority.

Only public Find a Tender OCDS records. Historical awards are not prospective leads.
A hash + local clock is NOT a trusted external timestamp; no native account is touched.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

IDS = ("ocds-h6vhtk-05575d", "ocds-h6vhtk-05167a", "ocds-h6vhtk-050420")
HOST = "https://www.find-tender.service.gov.uk"
BASE = HOST + "/api/1.0/ocdsRecordPackages/"
LIMIT = 3 * 1024 * 1024
UTC = timezone.utc


def now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def timeparse(s):
    if type(s) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", s):
        raise ValueError("AMBIGUOUS_TIME")
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if t.utcoffset() is None or abs(t.utcoffset().total_seconds()) > 14 * 3600:
            raise ValueError("BAD_OFFSET")
        return t.astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise ValueError("INVALID_TIME") from exc


def unique_pairs(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("DUPLICATE_JSON_KEY")
        d[k] = v
    return d


def read_package(raw, ocid, sha256):
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError("SOURCE_SIZE")
    if ocid not in IDS:
        raise ValueError("UNREGISTERED_PROCESS")
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("SOURCE_SHA_MISMATCH")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs,
                         parse_constant=lambda z: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_SOURCE_JSON") from exc
    if not isinstance(obj, dict) or not isinstance(obj.get("records"), list):
        raise ValueError("NOT_AN_OCDS_RECORD_PACKAGE")
    license_ = obj.get("license", "")
    if not isinstance(license_, str) or "nationalarchives.gov.uk/doc/open-government-licence" not in license_:
        raise ValueError("PUBLIC_LICENSE_UNVERIFIED")
    if "publishedDate" in obj:
        timeparse(obj["publishedDate"])
    records = obj["records"]
    if len(records) != 1 or not isinstance(records[0], dict) or records[0].get("ocid") != ocid:
        raise ValueError("WRONG_OR_AMBIGUOUS_PROCESS")
    releases = records[0].get("releases")
    if not isinstance(releases, list) or not releases:
        raise ValueError("NO_RELEASES")
    seen = set()
    normal = []
    for r in releases:
        if not isinstance(r, dict) or r.get("ocid") != ocid:
            raise ValueError("FOREIGN_RELEASE")
        id_ = r.get("id")
        if not isinstance(id_, str) or not id_ or id_ in seen:
            raise ValueError("DUPLICATE_OR_MISSING_RELEASE_ID")
        seen.add(id_)
        published = timeparse(r.get("date"))
        tag = r.get("tag")
        if not isinstance(tag, list) or not all(isinstance(x, str) for x in tag):
            raise ValueError("MISSING_RELEASE_STAGE")
        normal.append((published, id_, tag, r))
    return sorted(normal, key=lambda x: (x[0], x[1]))


def public_snapshot(raw, ocid, source_sha256, captured_at, decision_at):
    """Create a public research dossier, never a tender or spending instruction."""
    captured, decision = timeparse(captured_at), timeparse(decision_at)
    releases = read_package(raw, ocid, source_sha256)
    # All bytes were first observed at capture. A later download cannot recreate
    # an earlier prospective information set even if historical release dates predate it.
    valid_capture = captured <= decision
    pre = [(dt, rid, r) for dt, rid, tags, r in releases
           if valid_capture and dt <= decision and "tender" in tags
           and not any(t in tags for t in ("award", "contract", "implementation", "compiled"))]
    all_awards = [rid for _, rid, tags, _ in releases if "award" in tags]
    pre_awards = [rid for dt, rid, tags, _ in releases if dt <= decision and "award" in tags]
    chosen = pre[0][2] if pre else {}
    tender = chosen.get("tender", {}) if isinstance(chosen.get("tender", {}), dict) else {}
    buyer = chosen.get("buyer", {}) if isinstance(chosen.get("buyer", {}), dict) else {}
    title, buyer_name = tender.get("title"), buyer.get("name")
    cpv = tender.get("classification", {})
    cpv_id = cpv.get("id") if isinstance(cpv, dict) else None
    if not isinstance(cpv_id, str):
        cpv_id = None
    if not isinstance(title, str) or not title.strip():
        title = None
    if not isinstance(buyer_name, str) or not buyer_name.strip():
        buyer_name = None
    # Do not forward contracts/awards/award value/supplier or contact point to
    # predecision features. Tender estimated value is intentionally omitted.
    return {
        "schema": "agi-alpha/public-notice095-research/v1",
        "ocid": ocid,
        "official_process_url": HOST + "/procurement/" + ocid,
        "official_api_url": BASE + ocid,
        "retrieved_source_sha256": source_sha256,
        "retrieved_source_bytes": len(raw),
        "capture_utc": captured_at,
        "decision_cutoff_utc": decision_at,
        "capture_available_at_cutoff": valid_capture,
        "all_releases_count_RETROSPECTIVE": len(releases),
        "award_releases_count_RETROSPECTIVE_ONLY": len(all_awards),
        "awards_already_public_by_cutoff_count": len(pre_awards) if valid_capture else None,
        "tender_releases_observable_at_cutoff": len(pre),
        "public_tender_title": title,
        "public_buyer_organization": buyer_name,
        "public_cpv_code": cpv_id,
        "historically_awarded_not_open_lead": bool(pre_awards),
        "actual_signed_capture_or_first_seen_attestation": None,
        "prospective_buyer_willingness_to_pay_our_service": None,
        "our_company_eligibility": None,
        "complete_solution_delivery_costs": None,
        "complete_human_conventional_and_competing_AI_alternatives": None,
        "native_account_operations": 0,
        "authorized_bid_or_purchase": False,
        "decision": "RESEARCH_ONLY_NO_BID",
        "reason": ("NOT_CAPTURED_BY_CUTOFF" if not valid_capture else
                   "NO_PREDECISION_TENDER" if not pre else
                   "HISTORICAL_AWARD_NOT_ACTIVE_BUYER" if pre_awards else
                   "UNVERIFIED_ELIGIBILITY_VALUE_AND_COMPLETE_COSTS" if title and buyer_name else
                   "MISSING_BUYER_OR_OUTCOME"),
    }


def fetch_registered(ocid):
    if ocid not in IDS:
        raise ValueError("UNREGISTERED_PROCESS")
    req = Request(BASE + ocid, headers={"User-Agent": "AGI-Alpha-PublicNotice095/1.0 (public research)",
                                            "Accept": "application/json"})
    with urlopen(req, timeout=25) as response:
        if response.status != 200 or not response.geturl().startswith(BASE):
            raise ValueError("OFFICIAL_SOURCE_OR_RESPONSE_REJECTED")
        raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("SOURCE_SIZE")
    return raw


def run(output):
    rows = []
    for ocid in IDS:
        try:
            raw = fetch_registered(ocid)  # exactly one request for each registered ID
            captured = now()
            source_sha = hashlib.sha256(raw).hexdigest()
            # Decision cutoff occurs after capture; it is NOT a historical backtest.
            row = public_snapshot(raw, ocid, source_sha, captured, now())
            row["source_retrieval"] = "SUCCEEDED"
        except Exception as exc:
            row = {"ocid": ocid, "official_api_url": BASE + ocid,
                   "source_retrieval": "FAILED", "failure_class": type(exc).__name__,
                   "failure_message": str(exc)[:200], "decision": "RESEARCH_ONLY_NO_BID"}
        rows.append(row)
    result = {"schema": "agi-alpha/public-notice095-registered-3/v1",
              "registered_source_ids": list(IDS), "records": rows,
              "all_official_retrievals_succeeded": all(r["source_retrieval"] == "SUCCEEDED" for r in rows),
              "no_actual_contract_or_buyer_contact": True, "commercial_admission": False,
              "target_3b_achieved": False, "decision": "RESEARCH_ONLY_NO_BID"}
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise ValueError("OUTPUT_EXISTS_NO_HISTORY_OVERWRITE")
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    a = p.parse_args()
    result = run(a.out)
    if not result["all_official_retrievals_succeeded"]:
        raise SystemExit("REGISTERED_OFFICIAL_SOURCE_RETRIEVAL_FAILED")


if __name__ == "__main__":
    main()
