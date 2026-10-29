# SPDX-License-Identifier: Apache-2.0
"""Fail-closed campaign adapter to the pinned Alpha protected simulated exchange."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import resource
import time
from typing import Any

PINNED = {"protected_exchange.py": "378bf67ae24c18ad58b684ce8b13492fd06f8556",
          "contracts.py": "a26129ff4ee72ed8b4f8467f6c9de07b8d67508c"}
for _filename, _expected in PINNED.items():
    _raw = (Path(__file__).parent / "vendor" / "alpha_claim" / _filename).read_bytes()
    if hashlib.sha1(b"blob " + str(len(_raw)).encode() + b"\0" + _raw).hexdigest() != _expected:
        raise ValueError("pinned Alpha source mismatch: " + _filename)
from vendor.alpha_claim.contracts import canonical, digest, read, write_new
from vendor.alpha_claim.protected_exchange import ProtectedExchange

CONTRACT = "lab/dc-operational-service-boundary/v1"
KEY = b"d" * 32
OPENING, WORKING, PRICE = 10_000_000, 1_000_000, 200_000

def validate(task: Any) -> None:
    if not isinstance(task, dict) or set(task) != {"schema", "reportHash", "requiredService", "buyerSpecification"}:
        raise ValueError("boundary task schema")
    if task["schema"] != CONTRACT or task["requiredService"] != "buyer-defined-completed-service":
        raise ValueError("service contract")
    if task["buyerSpecification"] is not None:
        raise ValueError("this boundary probe has no buyer-issued acceptance specification")
    value = task["reportHash"]
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("report identity")

def run(report_path: Path, output: Path) -> dict[str, Any]:
    report = read(report_path)
    if not isinstance(report, dict):
        raise ValueError("actual campaign report object required")
    raw = report_path.read_bytes()
    task = {"schema": CONTRACT, "reportHash": digest(report),
            "requiredService": "buyer-defined-completed-service", "buyerSpecification": None}
    validate(task)
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_SELF)
    semantic_calls: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    def check(service: Any, artifact: Any) -> dict[str, Any]:
        validate(service)
        same = isinstance(artifact, dict) and digest(artifact) == service["reportHash"]
        verdict = {"accepted": False, "decisive": False,
                   "reason": "NO_INDEPENDENT_BUYER_SERVICE_SPEC" if same else "REPORT_IDENTITY_MISMATCH",
                   "artifactBound": same,
                   "scope": "DC engineering evidence is not buyer acceptance or an operational interconnection study"}
        semantic_calls.append({"taskHash": digest(service), "artifactHash": digest(artifact), "verdict": verdict})
        return verdict

    db = output / "exchange.sqlite"
    adapter_source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    def open_exchange() -> ProtectedExchange:
        return ProtectedExchange(db, key=KEY, contract=CONTRACT + "/" + adapter_source, validate=validate, check=check,
                                 opening=OPENING, working=WORKING)
    ex = open_exchange()

    def expect_error(name: str, types: Any, call: Any) -> None:
        try:
            call()
        except types as exc:
            checks.append({"name": name, "passed": True, "error": type(exc).__name__, "detail": str(exc)})
        else:
            raise AssertionError(name + " unexpectedly succeeded")

    def offer(ident: str, buyer: str) -> None:
        ex.offer(ident, buyer, PRICE, "nonrecourse-simulated", task, 20)
        row = ex.order(ident)
        terms = {k: row[k] for k in ["id", "buyer", "price", "rail", "task_hash", "contract", "deadline"]}
        ex.event(ident, "consent-" + ident, "consent", {"buyer": buyer, "termsHash": digest(terms)}, 0)

    def fund(ident: str) -> None:
        ex.event(ident, "fund-" + ident, "fund", ex.provider.issue(ex.order(ident), "funded"), 1)

    def reject(ident: str) -> None:
        expect_error("semantic-acceptance-refused-" + ident, ValueError,
                     lambda: ex.event(ident, "prepare-" + ident, "prepare", report, 2))
        assert ex.order(ident)["state"] == "funded"
        expect_error("no-output-release-" + ident, PermissionError, lambda: ex.download(ident, "fixture-funded"))

    try:
        ex.wallet("fixture-unfunded", 0)
        ex.wallet("fixture-funded", 5_000_000)
        offer("nonpayment", "fixture-unfunded")
        expect_error("nonpayment-refused", ValueError, lambda: fund("nonpayment"))
        assert ex.order("nonpayment")["state"] == "offered"

        offer("refused-delivery", "fixture-funded")
        fund("refused-delivery")
        reject("refused-delivery")
        release = ex.provider.issue(ex.order("refused-delivery"), "cleared")
        expect_error("unaccepted-settlement-refused", ValueError,
                     lambda: ex.event("refused-delivery", "release-refused", "release", release, 3))
        expect_error("repeated-unaccepted-settlement-refused", ValueError,
                     lambda: ex.event("refused-delivery", "release-refused", "release", release, 3))
        ex.event("refused-delivery", "refund-refused", "refund", {}, 3)
        snap = ex.snapshot()
        ex.event("refused-delivery", "refund-refused", "refund", {}, 3)
        assert ex.snapshot() == snap
        checks.append({"name": "duplicate-refund-idempotent", "passed": True})
        expect_error("fresh-event-cannot-refund-twice", ValueError,
                     lambda: ex.event("refused-delivery", "refund-again", "refund", {}, 4))

        offer("interruption", "fixture-funded")
        receipt = ex.provider.issue(ex.order("interruption"), "funded")
        expect_error("interruption-before-commit", InterruptedError,
                     lambda: ex.event("interruption", "fund-interrupted", "fund", receipt, 1, crash=True))
        assert ex.order("interruption")["state"] == "offered"
        ex.close()
        ex = open_exchange()
        ex.event("interruption", "fund-interrupted", "fund", receipt, 1)
        assert ex.order("interruption")["state"] == "funded"
        checks.append({"name": "durable-reopen-and-recovery", "passed": True})
        reject("interruption")
        ex.event("interruption", "refund-interruption", "refund", {}, 3)

        for i in range(3):
            ident = "correlated-" + str(i)
            offer(ident, "fixture-funded")
            fund(ident)
            reject(ident)
        assert ex.snapshot()["custodyRestricted"] == 3 * PRICE
        for i in range(3):
            ident = "correlated-" + str(i)
            ex.event(ident, "refund-" + ident, "refund", {}, 3)
        snapshot = ex.snapshot()
        assert snapshot["revenue"] == snapshot["collections"] == snapshot["custodyRestricted"] == 0
        assert snapshot["unrestrictedEarned"] == 0 and snapshot["cash"] == OPENING
        assert int(ex.db.execute("SELECT balance FROM wallets WHERE buyer='fixture-funded'").fetchone()[0]) == 5_000_000
        checks.append({"name": "correlated-refunds-preserve-cash-and-zero-revenue", "passed": True})
        expect_error("startup-equity-cannot-fund-earned-investment", ValueError,
                     lambda: ex.reserve_investment("successor", 1, 1, intent_hash=digest(report)))
        expect_error("persistent-contract-mismatch", ValueError,
                     lambda: ProtectedExchange(db, key=KEY, contract=CONTRACT + "-changed", validate=validate,
                                               check=check, opening=OPENING, working=WORKING))
        states = [dict(row) for row in ex.db.execute("SELECT id,state,custody,refund_due,compensation_due FROM trades ORDER BY id")]
        journal = [dict(row) for row in ex.db.execute("SELECT seq,order_id,kind,amount FROM journal ORDER BY seq")]
        event_count = ex.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    finally:
        ex.close()
    after = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": "lab/dc-exchange-boundary-evidence/v1",
        "mode": "PROTECTED_SIMULATED_EXCHANGE_BOUNDARY_PROBE",
        "source": {"repository": "MontrealAI/AGI-Alpha-Agent-v0",
                   "commit": "a6b2d869a7736e7c414d7d615d86c616c2f82615",
                   "module": "alpha_factory_v1/core/runtime/claim_probe/protected_exchange.py",
                   "gitBlob": "378bf67ae24c18ad58b684ce8b13492fd06f8556",
                   "adapterSha256": adapter_source,
                   "acceptanceContract": CONTRACT + "/" + adapter_source},
        "actualReport": {"fileSha256": hashlib.sha256(raw).hexdigest(), "canonicalSha256": digest(report),
                         "bytes": len(raw)},
        "task": task, "semanticChecks": semantic_calls, "mechanismChecks": checks,
        "states": states, "journal": journal, "durableEventCount": event_count,
        "snapshot": snapshot,
        "costMeter": {"wallSeconds": time.monotonic() - start,
                      "userCPUSeconds": after.ru_utime - before.ru_utime,
                      "systemCPUSeconds": after.ru_stime - before.ru_stime,
                      "peakProcessRSSKiB": after.ru_maxrss,
                      "databaseBytes": db.stat().st_size,
                      "unitRates": None, "completeMonetaryCost": None},
        "verdicts": {"protectedFailureMechanisms": "DEMONSTRATED_IN_BOUNDARY_PROBE",
                     "buyerAcceptance": "BLOCKED_NO_INDEPENDENT_SERVICE_SPEC",
                     "commercialViability": "UNKNOWN",
                     "actualReceipts": "NONE",
                     "unrestrictedEarnedFunding": "NOT_DEMONSTRATED",
                     "earnedFundedSuccessor": "BLOCKED"},
        "limits": ["Fixture accounts, consent and amounts exercise mechanisms only; no demand or pricing evidence",
                   "No positive settlement qualified for this report",
                   "No real provider, money movement, customer contact or native Jobs/Manager settlement",
                   "SQLite transaction interruption tested; arbitrary host crash/power-loss testing not performed",
                   "Snapshot zero expense is unpriced mechanism ledger only, not zero campaign cost",
                   "No positive duplicate-settlement claim; repeated unaccepted settlement is refused"]
    }
    write_new(output / "EXCHANGE.json", result)
    with (output / "INPUT_REPORT.json").open("xb") as stream:
        stream.write(raw)
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    outcome = run(args.report, args.output)
    print(json.dumps({"verdicts": outcome["verdicts"], "checks": len(outcome["mechanismChecks"]),
                      "output": str(args.output)}, indent=2))

