# Design041 provenance-time164 — frozen negative-control protocol

**Registered before constructing or executing the new regression.** Exact parent main: `a4ee0c9deb217f4e2480808785ea813171793205`. Original corrected design controller on main: `connected_enterprise/design_flywheel.py` Git blob `eb84bc0d62ad227be1df352717391598a0f71d34`; current test blob `fbf194e76eedf9296985f2bb2de64b5da1bca2c3`. Leave original PR77/115, PR40 source/keys/queues, owner task and historical red findings untouched.

## Specific source-bound question

The canonical `find_native_successor` attributes all acquisition/capacity invoices and linked refunds across a connected native plan component. Does its **standalone witness construction** also refuse to treat an order as enabled by an investment that had not yet activated, or whose capacity had expired before production? Test the strongest complete financial path separately; this is **not** an assertion of real account corruption. The authoritative account and independent verifier may already reject forged timing.

## Fixed one-shot cases and acceptance

The cases share the same explicitly authored two-order result: an earlier settled order at hour 40, an EARNED acquisition plan purchased 80 / active 96 / expires 300, one later distinct accepted settled order qualified at hour 120, produced 121, collected 160, plus an EARNED capacity plan (purchased 80 / active 100 / expires 300). Both plans are linked to the successor; cost and contribution are kept identical across arms. Strictness boundary: activation <= qualification, production < expiry. Compare:

1. **VALID**: all direct and supplemental plan links valid and positive net; return a true positive source-linked witness.
2. **FUTURE-CAPACITY**: change only capacity activation to 140 (after successor qualification); refuse any positive witness.
3. **EXPIRED-CAPACITY**: change only capacity expiry to 121 (equal to production); refuse any positive witness.
4. **FUTURE-ADDITIONAL-CAPACITY**: attach the second plan through `capacity_source_plan_ids` instead of scalar capacity ID, with activation 140; refuse.
5. **REFUNDED-EARLY-LINK**: add a refunded order attributed to the second plan before its activation; no positive witness without independent native proof of impossible link.

Pass means the positive case still succeeds while all four invalid cases are rejected or return no positive successor. **A failing initial test remains FAILED**, even if source later changes. Run unchanged existing design041 suite after any local repair, then all applicable source-matched hosted CI. No rerolling, seed searches, alternate signer, resets, archive guard changes or statistical/commerce claims.

## Owner and commercial boundaries

This investigation may add a small prospective nonfinancial witness-validation guard only after the fixed failure is observed. It cannot substitute for mandatory `run_world`, `JournalAccount`, HMAC/audit, protected legacy operating-state migration, physical deliveries or actual buyers. No financial accounts or releases are to be altered merely to obtain a pass. The stronger complete incumbent, customer refusal, specialist/human AI alternatives and NO BID/NO DEPLOY stay admissible; no $3B trailing-365-day profit is established by either outcome. Unknown whole-host/model/engineering bills remain UNKNOWN.

**Independent decision:** a negative result motivates an exact nonfinancial witness guard and a stronger native verifier check, not a claim that legacy financial state is exploitable. A positive result ends this narrow branch without a fictional bug or duplicative release.