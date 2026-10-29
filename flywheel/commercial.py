"""Evidence-gated adapter to Alpha's existing protected simulated exchange."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import resource
import time

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "vendor/__init__.py": "be8bdfe2c1e80537aa8346db6e39112224381b56a853f94d460c00d29692db54",
    "vendor/alpha_claim/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "vendor/alpha_claim/contracts.py": "3536b96c4b7ee46f9af7d807e02685aa55e42daae7f7c56b7e9029ca2cde0964",
    "vendor/alpha_claim/protected_exchange.py": "7b72c911d99a9aa12dc1f412d3b66f69ba58f3d4f2f50291310a7fd849df5272",
}
CONTRACT = "lab/invention-delivery-boundary/v1"
PRICE, OPENING, WORKING = 200_000, 10_000_000, 1_000_000


def _engine():
    for path, expected in PINS.items():
        source = ROOT / path
        if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError("PINNED_EXCHANGE_SOURCE_MISMATCH " + path)
    from vendor.alpha_claim.contracts import canonical, digest, read, write_new
    from vendor.alpha_claim.protected_exchange import ProtectedExchange
    return canonical, digest, read, write_new, ProtectedExchange


def run(artifact_path: Path, output: Path, *, technical_acceptance=None, commercial_evidence=None):
    canonical, digest, read, write_new, ProtectedExchange = _engine()
    artifact = read(Path(artifact_path))
    if not isinstance(artifact, dict):
        raise ValueError("TECHNICAL_ARTIFACT_OBJECT_REQUIRED")
    evidence = commercial_evidence or {}
    if not isinstance(evidence, dict):
        raise ValueError("COMMERCIAL_EVIDENCE_OBJECT_REQUIRED")
    acceptance = technical_acceptance or {}
    if not isinstance(acceptance, dict):
        raise ValueError("TECHNICAL_ACCEPTANCE_OBJECT_REQUIRED")
    raw = Path(artifact_path).read_bytes()
    raw_hash = hashlib.sha256(raw).hexdigest()
    technical_bound = acceptance.get("accepted") is True and acceptance.get("artifact_sha256") == raw_hash
    required = ("buyer_specification", "participation_evidence", "price_evidence", "complete_cost", "independent_service_acceptance")
    missing = [field for field in required if evidence.get(field) is None]
    task = {"schema": CONTRACT, "artifactHash": digest(artifact), "technicalEvidence": acceptance,
            "commercialEvidence": evidence}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    wall, cpu = time.monotonic(), time.process_time()
    checks, semantic = [], []
    db = output / "exchange.sqlite"

    def validate(value):
        if value != task:
            raise ValueError("FROZEN_DELIVERY_TASK_MISMATCH")

    def check(service, value):
        validate(service)
        result = {"accepted": False, "decisive": False,
                  "artifactBound": digest(value) == task["artifactHash"],
                  "technicalEvidenceBound": technical_bound,
                  "reason": "MISSING_COMMERCIAL_EVIDENCE" if missing else "BUYER_ACCEPTANCE_AUTHORITY_NOT_QUALIFIED",
                  "missing": missing}
        semantic.append(result)
        return result

    def open_exchange():
        return ProtectedExchange(db, key=b"c" * 32, contract=CONTRACT + "/" + digest(task),
                                 validate=validate, check=check, opening=OPENING, working=WORKING)

    ex = open_exchange()

    def refused(name, kinds, call):
        try:
            call()
        except kinds as error:
            checks.append({"name": name, "passed": True, "error": type(error).__name__, "detail": str(error)})
        else:
            raise AssertionError("UNEXPECTED_SUCCESS " + name)

    def offer(ident, buyer="funded-fixture"):
        ex.offer(ident, buyer, PRICE, "nonrecourse-simulated", task, 20)
        row = ex.order(ident)
        terms = {key: row[key] for key in ("id", "buyer", "price", "rail", "task_hash", "contract", "deadline")}
        ex.event(ident, "consent-" + ident, "consent", {"buyer": buyer, "termsHash": digest(terms)}, 0)

    def fund(ident):
        return ex.event(ident, "fund-" + ident, "fund", ex.provider.issue(ex.order(ident), "funded"), 1)

    def dispute(ident):
        refused("acceptance-dispute-" + ident, ValueError,
                lambda: ex.event(ident, "prepare-" + ident, "prepare", artifact, 2))
        if ex.order(ident)["state"] != "funded":
            raise AssertionError("DISPUTE_CHANGED_FUNDED_STATE")
        refused("release-blocked-" + ident, PermissionError, lambda: ex.download(ident, "funded-fixture"))

    try:
        ex.wallet("unfunded-fixture", 0)
        ex.wallet("funded-fixture", 5_000_000)
        offer("nonpayment", "unfunded-fixture")
        refused("nonpayment", ValueError, lambda: fund("nonpayment"))
        offer("disputed-delivery")
        fund("disputed-delivery")
        dispute("disputed-delivery")
        cleared = ex.provider.issue(ex.order("disputed-delivery"), "cleared")
        for name in ("unaccepted-settlement", "duplicate-unaccepted-settlement"):
            refused(name, ValueError, lambda: ex.event("disputed-delivery", "release-disputed", "release", cleared, 3))
        ex.event("disputed-delivery", "refund-disputed", "refund", {}, 3)
        before = ex.snapshot()
        ex.event("disputed-delivery", "refund-disputed", "refund", {}, 3)
        if before != ex.snapshot():
            raise AssertionError("DUPLICATE_REFUND_CHANGED_LEDGER")
        checks.append({"name": "duplicate-refund-idempotent", "passed": True})
        refused("refund-twice", ValueError, lambda: ex.event("disputed-delivery", "refund-again", "refund", {}, 4))
        offer("interrupted")
        receipt = ex.provider.issue(ex.order("interrupted"), "funded")
        refused("interrupted-transaction", InterruptedError,
                lambda: ex.event("interrupted", "interrupted-funding", "fund", receipt, 1, crash=True))
        if ex.order("interrupted")["state"] != "offered":
            raise AssertionError("INTERRUPTION_NOT_ROLLED_BACK")
        ex.close()
        ex = open_exchange()
        ex.event("interrupted", "interrupted-funding", "fund", receipt, 1)
        dispute("interrupted")
        ex.event("interrupted", "refund-interrupted", "refund", {}, 3)
        checks.append({"name": "durable-interruption-recovery", "passed": True})
        for i in range(3):
            ident = "correlated-" + str(i)
            offer(ident)
            fund(ident)
            dispute(ident)
        if ex.snapshot()["custodyRestricted"] != 3 * PRICE:
            raise AssertionError("CORRELATED_RESTRICTED_CUSTODY")
        for i in range(3):
            ident = "correlated-" + str(i)
            ex.event(ident, "refund-" + ident, "refund", {}, 3)
        snapshot = ex.snapshot()
        if any(snapshot[key] != 0 for key in ("revenue", "collections", "custodyRestricted", "unrestrictedEarned")):
            raise AssertionError("UNEARNED_REVENUE_OR_RESTRICTED_FUNDS")
        if snapshot["cash"] != OPENING:
            raise AssertionError("REFUNDS_CHANGED_PRINCIPAL")
        checks.append({"name": "correlated-failures-refunded", "passed": True})
        refused("opening-capital-cannot-fund-successor", ValueError,
                lambda: ex.reserve_investment("successor", 1, 1, intent_hash=digest(artifact)))
        states = [dict(row) for row in ex.db.execute("SELECT id,state,custody,refund_due,compensation_due FROM trades ORDER BY id")]
        journal = [dict(row) for row in ex.db.execute("SELECT seq,order_id,kind,amount FROM journal ORDER BY seq")]
    finally:
        ex.close()
    result = {"schema": "lab/invention-commercial-boundary/v1", "mode": "SIMULATED_BOUNDARY_PROBE",
              "source": {"repository": "MontrealAI/AGI-Alpha-Agent-v0",
                         "commit": "a6b2d869a7736e7c414d7d615d86c616c2f82615", "sha256": PINS},
              "artifact_sha256": raw_hash, "task": task, "technicalEvidenceBound": technical_bound,
              "missingCommercialEvidence": missing, "semanticChecks": semantic, "mechanismChecks": checks,
              "states": states, "journal": journal, "snapshot": snapshot,
              "economics": {"complete_cost": None, "submitted_cost_evidence": evidence.get("complete_cost"), "complete_profit": None,
                            "ledger_profit_is_complete_profit": False, "same_cohort_boundary_crossing": "NOT_ESTABLISHED",
                            "unit_rates": None, "available_earned_funds": snapshot["unrestrictedEarned"],
                            "actual_receipts": 0, "funded_successor": "DEFERRED_NO_AVAILABLE_EARNED_FUNDS"},
              "resources": {"wall_seconds": time.monotonic() - wall, "cpu_seconds": time.process_time() - cpu,
                            "database_bytes": db.stat().st_size, "complete_monetary_cost": None},
              "verdicts": {"settlement_failure_controls": "EXECUTED", "commercial_success": "NOT_ESTABLISHED",
                           "buyer_acceptance": "NOT_QUALIFIED", "full_flywheel": "NOT_DEMONSTRATED"},
              "limits": ["Fixture accounts and consent are engineering inputs, not observed buyer participation or prices",
                         "Technical acceptance does not authorize commercial acceptance",
                         "No independently authenticated buyer acceptance adapter is installed",
                         "No positive settlement or positive duplicate-settlement qualification claimed",
                         "Ledger expense zero is unpriced, not complete-cost zero",
                         "No real receipts, spending, outreach or transfers"]}
    write_new(output / "COMMERCIAL.json", result)
    return result
