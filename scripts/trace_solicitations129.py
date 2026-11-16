"""Source-bound award -> original tender record join. No commerce or contacts."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

AWARD_URL = "https://canadabuys.canada.ca/opendata/pub/2026-2027-awardNotice-avisAttribution.csv"
TENDER_URL = "https://canadabuys.canada.ca/opendata/pub/tenderNoticeComplete-avisAppelOffresComplet.csv"
PR333_SHA = "b6a46f9cb21335879d0a409c87296623b4a36351468e6f10976f823ecdfe0dc0"
TITLE = "title-titre-eng"
SOLICITATION = "solicitationNumber-numeroSollicitation"
REFERENCE = "referenceNumber-numeroReference"
FAMILIES = {
    "accessible_publication": ("accessibility", "accessible document", "pdf remediation", "wcag", "aoda", "document conversion"),
    "physical_measurement": ("non-destructive testing", "nondestructive testing", "tomography", "metrology", "industrial inspection", "material testing"),
    "material_recovery": ("material recovery", "recycling", "waste valorization", "electrolysis", "resource recovery", "waste processing"),
}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{2,79}$")


class SourceRejected(ValueError):
    pass


def normalize(s):
    return unicodedata.normalize("NFKC", s).casefold().strip()


def safe_id(s):
    value = s.strip()
    return value.upper() if SAFE_ID.fullmatch(value) and any(c.isdigit() for c in value) else None


def digest(path):
    h = hashlib.sha256()
    length = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
            length += len(chunk)
    if length == 0:
        raise SourceRejected("EMPTY_SOURCE")
    return {"sha256": h.hexdigest(), "bytes": length}


def rows(path, required):
    csv.field_size_limit(64 * 1024 * 1024)
    try:
        with path.open("r", encoding="utf-8-sig", errors="strict", newline="") as f:
            reader = csv.reader(f, strict=True)
            try:
                headers = next(reader)
            except StopIteration as e:
                raise SourceRejected("EMPTY_OR_HEADERLESS_SOURCE") from e
            if not headers or any(not normalize(x) for x in headers):
                raise SourceRejected("BLANK_HEADER")
            if len(set(map(normalize, headers))) != len(headers):
                raise SourceRejected("DUPLICATE_HEADER")
            if any(headers.count(key) != 1 for key in required):
                raise SourceRejected("MISSING_OR_AMBIGUOUS_REQUIRED_COLUMN")
            indices = {key: headers.index(key) for key in required}
            for i, row in enumerate(reader, 2):
                if len(row) != len(headers):
                    raise SourceRejected(f"ROW_WIDTH_MISMATCH_AT_{i}")
                yield i, {key: row[n] for key, n in indices.items()}
    except (csv.Error, UnicodeError) as e:
        raise SourceRejected("INVALID_CSV_OR_UTF8") from e
    except OSError as e:
        raise SourceRejected("SOURCE_IO_FAILURE") from e


def analyze(award_path: Path, tender_path: Path) -> dict:
    award_hash, tender_hash = digest(award_path), digest(tender_path)
    total_awards = total_tenders = blank = missing_ids = unsafe_refs = overlap = 0
    counts = {key: 0 for key in FAMILIES}
    leads = []
    for n, fields in rows(award_path, (TITLE, SOLICITATION)):
        total_awards += 1
        title = normalize(fields[TITLE])
        if not title:
            blank += 1
        families = [name for name, terms in FAMILIES.items() if any(term in title for term in terms)]
        for family in families:
            counts[family] += 1
        if len(families) > 1:
            overlap += 1
        if not families:
            continue
        ident = safe_id(fields[SOLICITATION])
        if ident is None:
            missing_ids += 1
        leads.append({"award_row": n, "families": families, "solicitation_id": ident})
    if not total_awards:
        raise SourceRejected("NO_AWARD_ROWS")
    refs = {lead["solicitation_id"]: [] for lead in leads if lead["solicitation_id"]}
    for n, fields in rows(tender_path, (SOLICITATION, REFERENCE)):
        total_tenders += 1
        ident = safe_id(fields[SOLICITATION])
        if ident not in refs:
            continue
        ref = safe_id(fields[REFERENCE])
        if ref is None:
            unsafe_refs += 1
        refs[ident].append({"tender_row": n, "reference_id": ref})
    if not total_tenders:
        raise SourceRejected("NO_TENDER_ROWS")
    dispositions = {"matched_one_tender_row": 0, "amendment_or_collision_set": 0,
                    "no_exact_tender_match": 0, "missing_or_unsafe_solicitation_id": 0}
    for lead in leads:
        ident = lead["solicitation_id"]
        candidates = refs.get(ident, []) if ident else []
        verdict = ("missing_or_unsafe_solicitation_id" if ident is None else
                   "no_exact_tender_match" if not candidates else
                   "matched_one_tender_row" if len(candidates) == 1 else
                   "amendment_or_collision_set")
        dispositions[verdict] += 1
        lead.update({"disposition": verdict, "tender_row_count": len(candidates),
                     "tender_references": candidates})
    return {
        "schema": "agi-alpha/source-trace129/v1",
        "sources": {"awards": {"url": AWARD_URL, **award_hash, "rows": total_awards},
                    "tenders": {"url": TENDER_URL, **tender_hash, "rows": total_tenders},
                    "PR333_award_sha256": PR333_SHA,
                    "same_award_bytes_as_PR333": award_hash["sha256"] == PR333_SHA},
        "method": {"matching": "Frozen Public Evidence128 NFKC casefold English title terms",
                   "join": "exact stripped uppercase safe solicitation IDs only; no fuzzy/title URL matching",
                   "families": {k: list(v) for k, v in FAMILIES.items()}},
        "counts": {"award_rows": total_awards, "blank_english_titles": blank,
                   "matching_award_rows_not_buyers": len(leads),
                   "family_rows_not_unique_buyers": counts,
                   "multi_family_award_rows": overlap,
                   "missing_or_unsafe_award_ids": missing_ids,
                   "linked_rows_with_unsafe_tender_references": unsafe_refs,
                   "dispositions": dispositions},
        "leads": leads,
        "decision": "NO_BID_NO_DEPLOY",
        "unknown": {"full_original_tender_specifications": None,
                    "buyer_eligibility_acceptance_and_rights": None,
                    "competent_human_AI_and_self_service_complete_costs": None,
                    "future_demand_and_willingness_to_pay": None,
                    "native_profits_or_reinvestments": None,
                    "US3B_trailing365_complete_cost_profit": None},
        "warning": "Exact ID linkage yields notice candidates only; no fabricated notice URLs, bids, buyers, accepted outcomes, supplier rights, prices, revenues or profit.",
        "license": "Contains information licensed under the Open Government Licence – Canada.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--awards", required=True, type=Path)
    parser.add_argument("--tenders", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise SourceRejected("NO_CLOBBER")
        result = analyze(args.awards, args.tenders)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"accepted": True, "decision": result["decision"],
                          "counts": result["counts"], "source_hashes":
                          [result["sources"][key]["sha256"] for key in ("awards", "tenders")]},
                         sort_keys=True))
        return 0
    except (SourceRejected, OSError) as e:
        print(f"SOURCE_TRACE129_REJECTED: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
