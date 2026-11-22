"""Strictly offline, source-pinned triage of the historical NEED227 official CSV.

Not a bid, purchase, eligibility verdict, customer, actual payment or revenue.
No HTTP, credentials, native financial account, or fresh government request.
"""
import argparse
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path

SCHEMA = "agi-alpha/canada-open-review228/v1"
SOURCE_SHA256 = "2f58308f5e312472599d80cb6d1ea835c7004b446c30371c79d1b7cbd6a899a9"
RECEIPT_SHA256 = "a7bf21169189636eea6dc7dca50d93f80e81118994e188a0be5805e969769349"
SOURCE_RUN = "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44961099150"
SOURCE_ARTIFACT = 14728724874
REFERENCE = "referenceNumber-numeroReference"
TITLE = "title-titre-eng"
CLOSING = "tenderClosingDate-appelOffresDateCloture"
BUYER = "contractingEntityName-nomEntitContractante-eng"
BUYER_FR = "contractingEntityName-nomEntitContractante-fra"
NOTICE = "noticeType-avisType-eng"
METHOD = "procurementMethod-methodeApprovisionnement-eng"
DESCRIPTION = "tenderDescription-descriptionAppelOffres-eng"
EXPECTED_ROWS = 937
EXPECTED_CANDIDATES = 6

class ReviewError(ValueError):
    pass

def digest(data):
    return hashlib.sha256(data).hexdigest()

def canonical(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")

def pairs_unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReviewError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result

def clean(value, limit=500):
    if not isinstance(value, str) or len(value) > limit:
        return None
    value = value.strip()
    if not value or value[0] in "=+@" or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    return value

def classify(row):
    """Interpret explicit source statements conservatively, without granting eligibility."""
    kind = clean(row.get(NOTICE), 100)
    buyer = clean(row.get(BUYER), 240)
    buyer_fr = clean(row.get(BUYER_FR), 240)
    method = clean(row.get(METHOD), 150)
    description = row.get(DESCRIPTION, "")
    if not isinstance(description, str):
        raise ReviewError("UNSAFE_DESCRIPTION")
    d = description.casefold()
    if kind == "Request for Information":
        status = "RFI_INFORMATION_GATHERING_NOT_A_PAID_CONTRACT"
    elif kind == "Invitation to Qualify":
        status = "QUALIFICATION_ONLY_NOT_AN_AWARDED_PURCHASE"
    elif kind == "Request for Proposal":
        status = "PROPOSAL_REQUIRES_SOURCE_DOCUMENT_AND_ELIGIBILITY_REVIEW"
    else:
        status = "UNKNOWN_NOTICE_TYPE_REQUIRES_MANUAL_REVIEW"
    itq_publication_only = (
        kind == "Invitation to Qualify"
        and "publication closing date only" in d
        and "does not represent the itq response submission deadline" in d
    )
    renewal = "subscription renewal" in d
    restricted_supplier = (
        "only suppliers who are pre-qualified" in d
        or "only suppliers who are prequalified" in d
    )
    no_new_tool = "does not involve developing a new ai tool" in d
    if itq_publication_only:
        deadline_type = "PUBLICATION_DATE_NOT_QUALIFICATION_RESPONSE_DEADLINE"
    elif kind == "Request for Information":
        deadline_type = "RFI_RESPONSE_WINDOW_NOT_PURCHASE_CLOSING_PROOF"
    else:
        deadline_type = "PUBLISHED_DATE_ONLY_VERIFY_AMENDMENTS_AND_SOLICITATION"
    if renewal and restricted_supplier:
        status = "RESTRICTED_INCUMBENT_SUBSCRIPTION_RENEWAL"
    return {
        "buyer_as_published_en": buyer,
        "buyer_as_published_fr": buyer_fr,
        "notice_type_as_published": kind,
        "procurement_method_as_published": method,
        "notice_interpretation": status,
        "closing_date_interpretation": deadline_type,
        "source_text_flags": {
            "itq_publication_date_not_response_deadline": itq_publication_only,
            "subscription_renewal_mentioned": renewal,
            "prequalified_supplier_only_mentioned": restricted_supplier,
            "explicitly_excludes_new_ai_tool_development": no_new_tool,
        },
        "supplier_eligibility_verified": False,
        "application_or_bid_authorized": False,
        "qualified_sale_or_paid_customer": False,
    }

def read_source(source_dir):
    root = Path(source_dir)
    if root.is_symlink() or not root.is_dir():
        raise ReviewError("UNSAFE_SOURCE_DIR")
    source, receipt_path = root / "SOURCE.csv", root / "RECEIPT.json"
    if any(p.is_symlink() or not p.is_file() for p in (source, receipt_path)):
        raise ReviewError("UNSAFE_SOURCE_FILES")
    if source.stat().st_size > 32 * 1024 * 1024 or receipt_path.stat().st_size > 100 * 1024:
        raise ReviewError("SOURCE_BOUND")
    raw, original = source.read_bytes(), receipt_path.read_bytes()
    if digest(raw) != SOURCE_SHA256 or digest(original) != RECEIPT_SHA256:
        raise ReviewError("REGISTERED_SOURCE_OR_RECEIPT_CHANGED")
    receipt = json.loads(original.decode("utf-8"), object_pairs_hook=pairs_unique)
    if canonical(receipt) != original or receipt.get("source_sha256") != SOURCE_SHA256:
        raise ReviewError("BAD_PRIOR_RECEIPT")
    return raw, receipt

def assess(source_dir):
    raw, prior = read_source(source_dir)
    rows = []
    try:
        reader = csv.DictReader(StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        headers = reader.fieldnames
        necessary = {REFERENCE, TITLE, CLOSING, BUYER, NOTICE, METHOD, DESCRIPTION}
        if not headers or len(headers) != len(set(headers)) or not necessary.issubset(headers):
            raise ReviewError("UNSUPPORTED_CSV_SCHEMA")
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ReviewError("RAGGED_CSV")
            rows.append(row)
    except (UnicodeError, csv.Error) as exc:
        raise ReviewError("BAD_SOURCE_CSV") from exc
    if len(rows) != EXPECTED_ROWS or prior["counts"]["rows_all"] != EXPECTED_ROWS:
        raise ReviewError("SOURCE_ROW_DENOMINATOR_CHANGED")
    candidates = prior["review_candidates"]
    if (prior["review_candidates_total"] != EXPECTED_CANDIDATES or
            len(candidates) != EXPECTED_CANDIDATES or prior["truncated"]):
        raise ReviewError("REGISTERED_CANDIDATES_CHANGED")
    by_ref = {}
    for row in rows:
        by_ref.setdefault(row.get(REFERENCE), []).append(row)
    reviewed = []
    for candidate in candidates:
        ref = candidate["reference"]
        matched = by_ref.get(ref, [])
        if (len(matched) != 1 or matched[0].get(TITLE) != candidate["title"] or
                matched[0].get(CLOSING, "")[:10] != candidate["closing_date_recorded"]):
            raise ReviewError("CANDIDATE_SOURCE_ROW_CHANGED")
        row = matched[0]
        reviewed.append({
            "reference": ref,
            "title": candidate["title"],
            "closing_date_recorded": candidate["closing_date_recorded"],
            "source_full_row_sha256": digest(canonical(row)),
            **classify(row),
        })
    return {
        "schema": SCHEMA,
        "original_official_csv_sha256": SOURCE_SHA256,
        "original_receipt_sha256": RECEIPT_SHA256,
        "original_workflow": SOURCE_RUN,
        "original_artifact_id": SOURCE_ARTIFACT,
        "first_observation_utc": prior["observation_utc"],
        "source_rows": EXPECTED_ROWS,
        "registered_matches": EXPECTED_CANDIDATES,
        "reviewed_rows": reviewed,
        "source_kind": "government_open_tender_not_a_customer_or_award",
        "decision": "RESEARCH_ONLY_NO_BID_NO_DEPLOY",
        "currency_or_price_assumed": False,
        "financial_ledger_touched": False,
        "collected_payment": None,
        "complete_cost_profit": None,
        "empirical_buyer_demand_for_montreal_ai": None,
        "workstream_next": (
            "Evaluate AI governance traceability challenge against existing complete "
            "platforms; separately evaluate DFO applied interpretation work versus "
            "competent consulting/AI and no entry, using full solicitation; neither "
            "is yet eligible or ordered."
        ),
        "actual_frontier_invention_or_successor_advantage_proven": False,
        "usd_3b_trailing365_complete_cost_profit_proven": False,
    }

def audit(input_dir, report_path):
    report = Path(report_path)
    if report.is_symlink() or not report.is_file() or report.stat().st_size > 100 * 1024:
        raise ReviewError("UNSAFE_REPORT")
    actual = report.read_bytes()
    parsed = json.loads(actual.decode("utf-8"), object_pairs_hook=pairs_unique)
    if canonical(parsed) != actual or actual != canonical(assess(input_dir)):
        raise ReviewError("REPORT_CHANGED")
    return parsed

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("review", "audit"))
    parser.add_argument("--input", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        if args.action == "review":
            p = Path(args.report)
            if p.exists() or p.is_symlink():
                raise ReviewError("REPORT_ALREADY_EXISTS")
            result = assess(args.input)
            p.write_bytes(canonical(result))
            audit(args.input, args.report)
        else:
            result = audit(args.input, args.report)
    except (ReviewError, OSError, KeyError, TypeError, UnicodeError, ValueError) as exc:
        parser.exit(2, "NEED228_REFUSED: " + str(exc) + "\n")
    print(canonical(result).decode(), end="")

if __name__ == "__main__":
    main()
