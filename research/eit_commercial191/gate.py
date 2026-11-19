"""EIT191 finite public-source procurement admissibility check, not a sales engine.

The two official notices were manually reviewed before protocol freeze.  This
offline program does NOT establish new demand, medical rights, price, or revenue.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path

AS_OF = date(2026, 11, 19)
SCHEMA = "agi-alpha/eit191-commercial-admissibility/v1"
POLAND = {
    "notice": "2026/BZP 00530780/01",
    "primary_url": "https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/2026%2FBZP%2000530780%2F01",
    "buyer": "Instytut Pomnik-Centrum Zdrowia Dziecka",
    "country": "Poland",
    "published": "2026-11-09",
    "subject": "supply of EIT medical device",
    "official_deadline": None,
    "secondary_deadline_unverified": "2026-11-17",
    "full_bundle_estimate_eur": None,
    "eit_only_estimate_eur": None,
    "part_bids_allowed": False,
    "requires_regulated_medical_device": True,
    "is_award": False,
}
SPAIN = {
    "notice": "A/SUM-037956/2026",
    "primary_url": "https://op.europa.eu/en/web/public-procurement/procurement-details/-/procurement/3db0e6fd-f382-4395-ae83-579604916457",
    "buyer": "Hospital Universitario Puerta de Hierro Majadahonda",
    "country": "Spain",
    "published": "2026-09-16",
    "subject": "joint invasive ventilators and EIT supply, installation and operation",
    "official_deadline": "2026-10-01",
    "secondary_deadline_unverified": None,
    "full_bundle_estimate_eur": 228000,
    "eit_only_estimate_eur": None,
    "part_bids_allowed": None,
    "requires_regulated_medical_device": True,
    "is_award": False,
}
# Independent claims on our particular offer are not observed in either notice.
# These are proof requirements, not buyer-choice probabilities or modeled revenue.
REQUIREMENTS = {
    "direct_medical_device": (
        "accepted_complete_device", "medical_device_authorization",
        "eligible_live_procurement", "delivery_capacity",
        "complete_verified_costs", "authoritative_native_funding",
    ),
    "authorized_oem_companion": (
        "accepted_incremental_outcome", "written_oem_partner_consent",
        "rights_and_distribution_cleared", "verified_payable_buyer_demand",
        "complete_verified_costs", "authoritative_native_funding",
    ),
    "industrial_research_validation": (
        "accepted_nonmedical_industrial_outcome", "verified_industrial_buyer_demand",
        "commercial_rights_cleared", "complete_verified_costs",
        "authoritative_native_funding",
    ),
}


class GateError(ValueError):
    pass


def validate_notices(notices: tuple[dict, ...]) -> None:
    ids = [x.get("notice") for x in notices]
    if len(ids) != 2 or len(set(ids)) != 2:
        raise GateError("EIT191_NOTICE_SET_MISMATCH")
    if set(ids) != {POLAND["notice"], SPAIN["notice"]}:
        raise GateError("EIT191_NOTICE_ID_MISMATCH")
    for n in notices:
        if not str(n.get("primary_url", "")).startswith("https://"):
            raise GateError("EIT191_PRIMARY_URL_MISSING")
        deadline = n.get("official_deadline")
        if deadline is not None:
            try:
                date.fromisoformat(deadline)
            except (ValueError, TypeError):
                raise GateError("EIT191_INVALID_OFFICIAL_DEADLINE") from None
        if n.get("is_award") is not False:
            raise GateError("EIT191_TENDER_IS_NOT_AN_AWARD")
        if n.get("eit_only_estimate_eur") is not None:
            raise GateError("EIT191_UNSUPPORTED_EIT_ONLY_VALUATION")
    for n in notices:
        reference = POLAND if n["notice"] == POLAND["notice"] else SPAIN
        if n != reference:
            raise GateError("EIT191_REGISTERED_NOTICE_FACTS_CHANGED")
    spanish = next(n for n in notices if n["notice"] == SPAIN["notice"])
    if (spanish.get("full_bundle_estimate_eur") != 228000 or
            spanish.get("subject") != SPAIN["subject"]):
        raise GateError("EIT191_BUNDLED_VALUE_OR_SCOPE_CHANGED")


def deadline_gate(notice: dict, as_of: date) -> str:
    closing = notice.get("official_deadline")
    if closing is None:
        return "UNKNOWN_NOT_PROVEN_OPEN"
    if date.fromisoformat(closing) < as_of:
        return "CLOSED_BY_DECLARED_OFFICIAL_DEADLINE"
    return "DATE_NOT_ELAPSED_ELIGIBILITY_UNVERIFIED"


def evaluate(*, notices: tuple[dict, ...] = (POLAND, SPAIN),
             claimed_proofs: dict | None = None,
             as_of: date = AS_OF) -> dict:
    """Only independently sourced, identifiable actual proof can unlock a path.

    The current evaluation cannot accept newly asserted true flags: no verifier
    or native account authority is attached. Any attempt to claim one fails
    closed, instead of simulating authorization.
    """
    validate_notices(notices)
    claimed_proofs = claimed_proofs or {}
    if any(value is True for value in claimed_proofs.values()):
        raise GateError("EIT191_NO_PROOF_AUTHENTICATOR_OR_NATIVE_ACCOUNT")
    if any(value not in (None, False) for value in claimed_proofs.values()):
        raise GateError("EIT191_UNSUPPORTED_PROOF_CLAIM")
    routes = []
    for name, requirements in REQUIREMENTS.items():
        missing = list(requirements)
        routes.append({
            "route": name, "qualified": False,
            "missing_independently_authenticated": missing,
            "collected_payments": None,
            "complete_costs_usd": None,
            "native_profit_usd": None,
        })
    routes.append({
        "route": "no_deploy_no_bid", "qualified": True,
        "missing_independently_authenticated": [],
        "collected_payments": 0,
        "complete_costs_usd": None,
        "native_profit_usd": None,
    })
    return {
        "schema": SCHEMA, "as_of": as_of.isoformat(),
        "scope": "EXPOSED_PRIMARY_NOTICES_OFFLINE_MANUAL_TRANSCRIPTION_NO_NEW_BUYER",
        "notices": [{**n, "procurement_window": deadline_gate(n, as_of)}
                    for n in notices],
        "comparisons": routes,
        "selected": "no_deploy_no_bid",
        "reason": "No offer-specific buyer acceptance, rights, complete costs or native funding authenticated",
        "observed_paid_contracts_from_this_work": 0,
        "new_earned_cash_from_this_work_usd": 0,
        "actual_native_trailing_365_profit_usd": None,
        "three_billion_target_achieved": False,
        "economic_claim": "NOT_COMMERCIALLY_QUALIFIED",
        "clinical_or_physical_acceptance": False,
        "release_or_deploy": False,
    }


def write_create_only(path: Path, report: dict) -> None:
    if path.exists() or path.is_symlink():
        raise GateError("EIT191_RECEIPT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags, 0o600), "w", encoding="utf-8") as out:
        json.dump(report, out, indent=2, sort_keys=True, allow_nan=False)
        out.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    path = Path(args.out)
    if path.exists() or path.is_symlink():
        raise GateError("EIT191_RECEIPT_ALREADY_EXISTS")
    report = evaluate()
    protocol = Path(__file__).resolve().parents[2] / "campaign/eit-commercial191/PREREGISTRATION.md"
    report["protocol_sha256"] = hashlib.sha256(protocol.read_bytes()).hexdigest()
    report["executing_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    write_create_only(path, report)
    print(json.dumps({"selected": report["selected"], "qualified_paid_routes": 0,
                      "observed_paid_contracts": 0, "three_billion_target": False},
                     sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (GateError, OSError, ValueError) as error:
        print(json.dumps({"status": "FAILED_PRESERVE", "error": str(error)}, sort_keys=True))
        raise SystemExit(2)
