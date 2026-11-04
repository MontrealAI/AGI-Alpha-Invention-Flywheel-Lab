"""ActiveTender096: bounded *public research*, never a verified paying lead or a bid.

Exact search window/denominator are frozen in campaign/omega-active-tender096/PROTOCOL.md.
No account interaction, credentials, customer contact, deposits or commercial action.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

HOST = "https://www.find-tender.service.gov.uk"
PATH = "/api/1.0/ocdsReleasePackages"
SEARCH_URL = (HOST + PATH +
    "?updatedFrom=2026-11-02T00%3A00%3A00&updatedTo=2026-11-04T15%3A00%3A00&stages=tender&limit=20")
RECORD_PREFIX = HOST + "/api/1.0/ocdsRecordPackages/"
RECORD_PATH = "/api/1.0/ocdsRecordPackages/"
MAX_BYTES = 3 * 1024 * 1024
MAX_SOURCE_RELEASES = 20
MAX_PROCESSES = 5
ID_RE = re.compile(r"ocds-h6vhtk-[0-9a-f]{6}\Z")
LICENCE_RE = re.compile(r"https?://(?:www\.)?nationalarchives\.gov\.uk/doc/open-government-licence/version/3/?\Z")
TIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z")
END_STAGES = frozenset(("award", "contract", "implementation", "tenderCancellation",
                       "tenderTermination", "contractTermination", "tenderWithdrawn"))
UTC = timezone.utc


def timestamp():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_time(s):
    if type(s) is not str or not TIME_RE.fullmatch(s):
        raise ValueError("AMBIGUOUS_OR_INVALID_TIME")
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.utcoffset() is None or abs(dt.utcoffset().total_seconds()) > 14 * 3600:
            raise ValueError("BAD_TIME_OFFSET")
        return dt.astimezone(UTC)
    except (ValueError, OverflowError) as e:
        raise ValueError("INVALID_TIME") from e


def unique_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("DUPLICATE_JSON_KEY")
        out[k] = v
    return out


def decode(raw, sha256):
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise ValueError("SOURCE_SIZE")
    if type(sha256) is not str or hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("SOURCE_HASH_CHANGED")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError("MALFORMED_SOURCE_JSON") from e
    if not isinstance(obj, dict) or not LICENCE_RE.fullmatch(str(obj.get("license", ""))):
        raise ValueError("UNVERIFIED_OPEN_LICENCE")
    if "publishedDate" in obj:
        parse_time(obj["publishedDate"])
    return obj


def stages(release):
    if not isinstance(release, dict) or not isinstance(release.get("tag"), list):
        raise ValueError("MALFORMED_RELEASE")
    tags = release["tag"]
    if not tags or any(type(t) is not str or not t for t in tags):
        raise ValueError("MALFORMED_RELEASE_TAG")
    return tags


def verify_release(release, seen):
    if not isinstance(release, dict):
        raise ValueError("MALFORMED_RELEASE")
    ocid, rid = release.get("ocid"), release.get("id")
    if type(ocid) is not str or not ID_RE.fullmatch(ocid):
        raise ValueError("INVALID_PROCESS_ID")
    if type(rid) is not str or not rid or (ocid, rid) in seen:
        raise ValueError("DUPLICATE_OR_INVALID_RELEASE_ID")
    seen.add((ocid, rid))
    dt = parse_time(release.get("date"))
    return dt, ocid, rid, stages(release)


def select(raw, sha256):
    """Return frozen lexicographic first five among one observed <=20-release page."""
    obj = decode(raw, sha256)
    rs = obj.get("releases")
    if not isinstance(rs, list) or len(rs) > MAX_SOURCE_RELEASES:
        raise ValueError("NOT_A_BOUNDED_RELEASE_PACKAGE")
    seen = set()
    for release in rs:
        verify_release(release, seen)
    selected = sorted({ocid for ocid, _ in seen})[:MAX_PROCESSES]
    return {"selected_ocids": selected, "source_release_count": len(rs),
            "unique_source_process_count": len({k[0] for k in seen}),
            "search_sha256": sha256, "search_bytes": len(raw)}


def assess_record(raw, sha256, ocid, captured_at, decision_at):
    """Fail closed; a future public deadline is NOT a verified open solicitation."""
    capture, decision = parse_time(captured_at), parse_time(decision_at)
    if type(ocid) is not str or not ID_RE.fullmatch(ocid):
        raise ValueError("INVALID_PROCESS_ID")
    obj = decode(raw, sha256)
    recs = obj.get("records")
    if not isinstance(recs, list) or len(recs) != 1 or not isinstance(recs[0], dict):
        raise ValueError("WRONG_RECORD_PACKAGE")
    if recs[0].get("ocid") != ocid:
        raise ValueError("FOREIGN_RECORD_PACKAGE")
    rs = recs[0].get("releases")
    if not isinstance(rs, list) or not rs:
        raise ValueError("MISSING_RECORD_RELEASES")
    seen, eligible = set(), []
    for r in rs:
        dt, o, rid, tags = verify_release(r, seen)
        if o != ocid:
            raise ValueError("FOREIGN_RELEASE")
        if dt <= decision and capture <= decision:
            eligible.append((dt, rid, tags, r))
    eligible.sort(key=lambda x: (x[0], x[1]))
    end_stages = [rid for _, rid, tags, _ in eligible if END_STAGES.intersection(tags)]
    tender_releases = [(dt, rid, tags, r) for dt, rid, tags, r in eligible
                       if any(t == "tender" or t.startswith("tenderAmendment") or
                              t.startswith("tenderUpdate") for t in tags)
                       and not END_STAGES.intersection(tags)]
    final = tender_releases[-1] if tender_releases else None
    latest = final[3] if final else {}
    tender = latest.get("tender") if isinstance(latest.get("tender"), dict) else {}
    buyer = latest.get("buyer") if isinstance(latest.get("buyer"), dict) else {}
    title = tender.get("title") if isinstance(tender.get("title"), str) and tender["title"].strip() else None
    buyer_name = buyer.get("name") if isinstance(buyer.get("name"), str) and buyer["name"].strip() else None
    period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
    end_text = period.get("endDate")
    end_date = parse_time(end_text) if end_text is not None else None
    # If later tender modifications omit complete fields, do not silently inherit a
    # potentially superseded old title/deadline. OCDS releases may be deltas.
    incomplete_latest = bool(final and (title is None or buyer_name is None or end_date is None))
    status = tender.get("status")
    allowed_status = (status == "active")
    future_deadline = bool(end_date is not None and end_date > decision)
    potential = bool(final and not end_stages and not incomplete_latest and
                     allowed_status and future_deadline and capture <= decision)
    if capture > decision:
        reason = "SOURCE_NOT_CAPTURED_BY_DECISION"
    elif end_stages:
        reason = "PUBLIC_CLOSING_STAGE_PRESENT"
    elif final is None:
        reason = "NO_OBSERVABLE_TENDER"
    elif incomplete_latest:
        reason = "INCOMPLETE_LATEST_TENDER_OR_AMENDMENT"
    elif not allowed_status:
        reason = "UNKNOWN_OR_INACTIVE_TENDER_STATUS"
    elif not future_deadline:
        reason = "DEADLINE_MISSING_OR_EXPIRED"
    else:
        reason = "PUBLIC_DEADLINE_FUTURE_UNVERIFIED_BUYER_FIT"
    return {
        "schema": "agi-alpha/active-tender096-process/v1",
        "ocid": ocid, "official_process_url": HOST + "/procurement/" + ocid,
        "official_api_url": RECORD_PREFIX + ocid,
        "source_sha256": sha256, "source_bytes": len(raw),
        "capture_utc": captured_at, "decision_cutoff_utc": decision_at,
        "capture_available_by_cutoff": capture <= decision,
        "release_count_RETROSPECTIVE_METADATA": len(rs),
        "asof_end_stage_count": len(end_stages),
        "asof_tender_release_count": len(tender_releases),
        "latest_tender_release_id": final[1] if final else None,
        "public_tender_title": title if capture <= decision and not end_stages else None,
        "public_buyer_organization": buyer_name if capture <= decision and not end_stages else None,
        "public_deadline_utc": end_date.isoformat().replace("+00:00", "Z")
                              if capture <= decision and end_date and not end_stages else None,
        "public_tender_status": status if isinstance(status, str) and capture <= decision and not end_stages else None,
        "public_deadline_in_future_unverified_eligibility": potential,
        "open_reachable_willing_buyer_confirmed": False,
        "first_seen_external_attestation": None,
        "our_service_eligibility": None, "complete_delivery_and_acquisition_costs": None,
        "human_and_competing_AI_alternative_prices": None,
        "authorized_bid_or_purchase": False, "native_account_operations": 0,
        "decision": "RESEARCH_ONLY_NO_BID", "reason": reason,
    }


def get_official(url, expected_path):
    req = Request(url, headers={"User-Agent": "AGI-Alpha-ActiveTender096/1.0 (public research)",
                                "Accept": "application/json"})
    with urlopen(req, timeout=25) as response:
        actual = urlsplit(response.geturl())
        if response.status != 200 or actual.scheme != "https" or actual.netloc != "www.find-tender.service.gov.uk" or actual.path != expected_path:
            raise ValueError("NONOFFICIAL_OR_UNEXPECTED_RESPONSE")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("SOURCE_SIZE")
        return raw


def run(output):
    out = Path(output)
    if out.exists():
        raise ValueError("OUTPUT_EXISTS_NO_REPLACEMENT")
    out.parent.mkdir(parents=True, exist_ok=True)
    result = {"schema": "agi-alpha/active-tender096-fixed-one-page/v1",
              "protocol": "campaign/omega-active-tender096/PROTOCOL.md",
              "fixed_search_url": SEARCH_URL, "fixed_max_search_requests": 1,
              "fixed_max_process_requests": MAX_PROCESSES, "records": [],
              "genuine_buyer_commitments": 0, "native_account_operations": 0,
              "real_revenue": None, "trailing_365_profit": None,
              "target_3b_achieved": False, "decision": "RESEARCH_ONLY_NO_BID"}
    try:
        search_raw = get_official(SEARCH_URL, PATH)
        search_capture = timestamp()
        selection = select(search_raw, hashlib.sha256(search_raw).hexdigest())
        result["search"] = {**selection, "capture_utc": search_capture, "retrieval": "SUCCEEDED"}
    except Exception as exc:
        result["search"] = {"retrieval": "FAILED", "failure_class": type(exc).__name__,
                            "failure": str(exc)[:200]}
        result["all_registered_source_retrievals_succeeded"] = False
        out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result
    for ocid in selection["selected_ocids"]:
        try:
            raw = get_official(RECORD_PREFIX + ocid, RECORD_PATH + ocid)
            capture = timestamp()
            record = assess_record(raw, hashlib.sha256(raw).hexdigest(), ocid, capture, timestamp())
            record["retrieval"] = "SUCCEEDED"
        except Exception as exc:
            record = {"ocid": ocid, "retrieval": "FAILED", "failure_class": type(exc).__name__,
                      "failure": str(exc)[:200], "decision": "RESEARCH_ONLY_NO_BID"}
        result["records"].append(record)
    result["all_registered_source_retrievals_succeeded"] = (len(result["records"]) == len(selection["selected_ocids"])
                            and all(r["retrieval"] == "SUCCEEDED" for r in result["records"]))
    result["public_future_deadline_unverified_fit_count"] = sum(
        bool(r.get("public_deadline_in_future_unverified_eligibility")) for r in result["records"])
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    args = p.parse_args()
    r = run(args.out)
    if not r["all_registered_source_retrievals_succeeded"]:
        raise SystemExit("REGISTERED_OFFICIAL_SOURCE_RETRIEVAL_FAILED")


if __name__ == "__main__":
    main()
