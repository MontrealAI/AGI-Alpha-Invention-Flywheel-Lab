"""Strong ordinary offsite-event-log control vs synthetic three-role custody.

Research ONLY. No financial authority, real order, supplier reservation, payment,
production delivery or customer acceptance. The common independent replay oracle
judges both arms; only the challenger requires the synthetic signature bundle.

This *does not* implement or replace the CONTINUITY Omega owner constructor.
"""
from __future__ import annotations

from reference_oracle import reconcile
from witness_chain import verify

SCHEMA = "continuity-omega/strong-incumbent-parity-research-v1"


def compare(
    events, recovered_v2, witness_bundle, *,
    role_public_keys, latest_witness_anchor, min_witness_sequence,
    externally_expected_case_id, offsite_source_available,
    offsite_source_pin, offsite_restored_pin,
):
    """Return the registered conditional engineering comparison; never a sale.

    offsite_source_available=False is an explicit unverified counterfactual
    capacity/availability assumption, not evidence the best ordinary provider
    cannot maintain independently protected archives. All trusted references
    are supplied out-of-band; none is extracted from the challenger package.
    """
    result = {
        "schema": SCHEMA,
        "scope": "AUTHORED_SYNTHETIC_ONLY",
        "incumbent": None,
        "challenger": None,
        "technical_verdict": "NO_QUALIFIED_DIFFERENTIAL",
        "current_obligations_verified": False,
        "as_of_external_pin_only": True,
        "competent_alternative_excluded": False,
        "observed_buyer_consent": False,
        "observed_customer_acceptance": False,
        "real_fulfillment": False,
        "real_supplier_reservation": False,
        "real_collections_usd": 0,
        "native_trailing_365_profit_usd": None,
        "complete_cost_comparison": "UNQUALIFIED_UNKNOWN_ACTUAL_COSTS",
        "commercial_decision": "NO_DEPLOY",
    }
    if type(offsite_source_available) is not bool:
        result["incumbent"] = {"verdict": "INVALID_ARCHIVE_AVAILABILITY_DECLARATION"}
        return result
    # The challenger gets no alternate evaluator or authority. Its verifier
    # already invokes the exact same independently authored reconciliation.
    witness = verify(
        events, recovered_v2, witness_bundle,
        pinned_public_keys=role_public_keys,
        expected_latest_anchor_sha256=latest_witness_anchor,
        expected_min_sequence=min_witness_sequence,
        expected_case_id=externally_expected_case_id,
    )
    result["challenger"] = witness
    if offsite_source_available:
        conventional = reconcile(
            events, recovered_v2,
            expected_source_sha256=offsite_source_pin,
            expected_restored_sha256=offsite_restored_pin,
        )
        result["incumbent"] = conventional
    else:
        result["incumbent"] = {
            "verdict": "ARCHIVE_UNAVAILABLE_BY_DECLARED_ASSUMPTION",
            "complete": False,
            "actual_competent_availability_established": False,
        }
    witness_ok = witness["verdict"] == "VERIFIED_SYNTHETIC_CUSTODY_ONLY"
    ordinary_ok = result["incumbent"]["verdict"] == "RECONCILED_SYNTHETIC"
    if ordinary_ok and witness_ok:
        result["technical_verdict"] = "FUNCTIONAL_PARITY_AS_OF_PINNED_SOURCE"
    elif witness_ok and not offsite_source_available:
        # This is a stipulated difference in which arm possesses the source.
        # It cannot demonstrate a competitive advantage under equal access.
        result["technical_verdict"] = "CONDITIONAL_EVIDENCE_AVAILABILITY_ONLY"
    elif ordinary_ok and not witness_ok:
        result["technical_verdict"] = "INCUMBENT_RECONCILES_CHALLENGER_REFUSES"
    elif witness_ok:
        result["technical_verdict"] = "INCOMPARABLE_EXTERNAL_INCUMBENT_PINS"
    else:
        result["technical_verdict"] = "NO_QUALIFIED_DIFFERENTIAL"
    return result
