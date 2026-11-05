# GENESIS103 — active native production chronology (frozen protocol)

Source parent: `2247fab0d38a6c04df7ad38ba0db140e776508b4`, the existing GENESIS financial integration owner PR #229, after GENESIS101/102 protected merges. The original, independently qualified but unmerged predecessor PR #249 is preserved untouched. This is an additive *stacked qualification candidate*, not a main release, source transition, account migration or new operating authority.

## Falsifiable financial-integrity claim

The replay-verifying GENESIS auditor must not certify **active** production/settlement checkpoints when an original native production commitment is absent, was incurred at a nonregistered hour, or completed after preparation/collection. This closes the distinct active-row skip in the current canonical audit. Keep the already merged GENESIS101 **completed**-row payment checks and GENESIS102 refund-obligation check intact; do not alter the original JournalAccount, BusinessAccount, HMAC signing, historical obligations, or control labels merely to pass a test.

## Frozen cases (no changes to seeds/cases after freeze)

- C0: original four-order funded pilot and completed idempotent resume both audit unchanged, with the exact frozen-source source-closure.
- C1: genuine native replay-valid **active** row containing a prepare event but no completed production spend is rejected; original native `account.audit()` remains accepted. Reuse the case *design* from existing PR #249, not its source.
- C2: genuine native replay-valid **active** row with prepare/release and a production spend completed later **in the same hour** is rejected; registered-hour equality alone is insufficient.
- C3: genuine native replay-valid active **funded but not yet prepared** checkpoint passes and remains resumable in the phase semantics; a still pending order is not falsely classified as a finished delivery.
- C4: genuine native replay-valid active **order/fund stage** with no production spend and no prepare event passes as an incomplete financial commitment, without invented revenue.
- C5: active production spend made at the wrong registered hour (regardless of event absence) is rejected; no chronology bypass through phase pause.
- C6: the existing completed-row GENESIS101 cases and refund GENESIS102 cases retain their original acceptance/rejection outcomes and original error semantics.

## Implementation boundary and verification

Run genuine disposable **canonical** `flexibility063.native.BusinessAccount` / `JournalAccount` cases; call original `account.audit()` and `connected_enterprise.finance.audit_journal` before GENESIS audit. No manually edited/signed history, key export, alternate ledger or wiping of any obligation. The only planned runtime modification is a narrow active-row guard inside `genesis_enterprise/native.py::audit`, invoked after mandatory native replay and before the existing completed-row skip. Test files are independently added; do not mutate PR #249. Every executed case and failure remains reported (never cherry-pick).

Exit: six active/control cases plus all preexisting GENESIS101/102 regressions, exact-head hosted native and release workflows, complete source-matched workflow-family pass, independent review and protected owner-branch integration with a renewed exact-merge-head qualification; subsequent normal main release plus actual downloaded operation/resume/audit remain separate. A preregistered failed case stays failed pending explicit repair and a new clean confirmation.

Cost/stop: finite single-source candidate with one mechanical repair pass if needed; use current standard platform six-hour job boundaries and existing included compute only. Actual whole-campaign/model/host billing unknown; tests are simulated engineering and record no customers/real profit. No paid APIs, credentials, outreach, spending or production deployment. If a critical ownership/financial-integrity boundary is hit, stop mutation, preserve exact checkpoint and report the gate.

Verdicts to keep separate: registered-source engineering qualification; protected integration; actual released-byte operation; native legacy migration; customer revenue; complete-cost trailing-365 profit; causal self-improving discovery. The last five are not proven by these tests, and the US$3B milestone remains unachieved.
