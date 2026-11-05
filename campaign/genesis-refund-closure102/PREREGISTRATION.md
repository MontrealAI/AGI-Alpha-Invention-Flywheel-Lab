# GENESIS102 — unrefunded selected-order closure: frozen protocol

Protocol freeze: committed **before** corrective implementation and executable regressions.
Parent: existing GENESIS integration source `d2a367a9fe35fd97cc85b5a2aa841174b090b3f0` (PR #229). Research-only stacked branch, **not main**, not an operating-account migration.

## Falsifiable defect

An authenticated native account can retain an outstanding selected order, while a producer marks that selected row finished with no resource receipt, no production, no acceptance and **no buyer refund**. Existing GENESIS audit's no-receipt branch checks only absence of spend/acceptance and misses the required registered refund. An independent source review at [PR #229 thread 4476541319](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/229#discussion_r4476541319) supplied a genuine disposable-account counterexample. This protocol does **not** retroactively change that observed failure.

## Registered adversarial cases

- **C0, positive:** unchanged public canonical GENESIS pilot runs through settlement, pause/resume, audit and idempotent completed resume.
- **C1, positive selected no-resource:** one real selected native order receives zero production spend; actual native refund occurs at registered hour `H+2`, the completed row has `resource_receipt=None`, `accepted=False`; GENESIS audit must accept.
- **C2, negative custody:** otherwise identical real native order and completed row, but no refund. Native audit must **accept** its authentic unresolved liabilities, while GENESIS independent audit must reject `REGISTERED_UNREFUNDED_SELECTED_ORDER`. Do not modify or sign tape manually.
- **C3, negative timing:** otherwise identical native order refunded at `H+3` instead of `H+2`; native audit must accept its actual event and GENESIS must reject `REGISTERED_UNREFUNDED_SELECTED_ORDER`.
- **C4, positive pending:** uncompleted, genuinely active `phase='refund'` checkpoint with no refund yet remains admissible as **incomplete**; do not require settlement before the scheduled refund phase has executed. The account is never misrepresented as complete.

All cases use disposable original `flexibility063.native.BusinessAccount`/JournalAccount, the existing frozen `campaign/genesis-enterprise-002/PROTOCOL.json`, genuine event authoring and `connected_enterprise.finance.audit_journal`. Public execution rows are event-derived, not financial authority. Never alter ledger actions, balances, signed state or externally held accounts.

## Candidate minimal rule

For each **completed** selected-but-unaccepted row without a resource receipt, require exactly one replay-verified native refund for its registered order at hour `H+2`; prohibit preparation/release. Retain the already-qualified funded-row chronology guard, taxes, overhead, contract, capital registration, existing replay and source binding. No new ledger, service provider, key, price or buyer demand.

## Acceptance / stop

Preregistered C0/C1/C4 must pass; C2/C3 must reject for the registered cause after a native-valid journal. Existing GENESIS and original source CI must pass exact head. Preserve failures without selectively changing frozen outcomes or seeds; report any mismatch as failure, repair with explicit source commits and rerun as **new correction**. Independent review and integration into #229 must be protected and source-matched; no main merge/release claim without actual normal GitHub release and downloaded-byte operation. This is an engineering funding/obligation guard, **not** real commerce, prospective legacy migration, discovery advantage or $3B profit.

Cost scope: only existing simulated costs plus measured CI telemetry where available; actual whole-run host/model billing unknown. No spending, outreach, private data or external transactions.
