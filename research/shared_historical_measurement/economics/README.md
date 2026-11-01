# Conditional complete-transaction funding boundary

**No buyer demand, willingness to pay, price, revenue, profit, or financial admission has been observed in this experiment.** Road, promenade, and canopy are output scopes, not three customers. Their recorded native observations are not fresh inference. Code here neither executes payments nor adds a ledger.

## Explicit assumptions and exact condition

Fix a finite set of real identities, a bounded service horizon, and a full allocation of specified source-bound deliverables. For requester i let:

- `v_i`: value of this delivered allocation, in a consistent declared unit;
- `b_i`: available payment budget;
- `o_i`: utility from the best voluntary alternative, including doing nothing, a rival, independent production, a leaked copy, or waiting;
- `c_i = min(b_i, v_i - o_i)`: maximum individually rational nonnegative transfer, provided `v_i >= o_i`.

For this fixed full allocation, known nonstrategic values, quasilinear utility, enforceable commitments/exclusion, and complete bounded-horizon cost `C`, a cost-covering, budget-respecting, weakly voluntary transfer vector exists **iff every `v_i >= o_i` and `sum(c_i) >= C`**. Necessity follows by summing each payment bound. Sufficiency follows by allocating payments up to these caps until C is covered. Equality is zero surplus at the aggregate cost boundary—not positive profit. Strict participation requires slack for the participating requesters. If any requester prefers its alternative even to free delivery, that full allocation is infeasible; considering an optional subset requires recomputing both source sharing costs and the relevant outside utilities.

This is an existence bound, **not** a strategy-proof, coalition-proof, Sybil-resistant, or dominant-strategy mechanism. The code never labels an implementable transaction as established. Mutable identities, unenforceable exclusion, post-commitment copying, and strategic waiting invalidate a naive interpretation. A complete equivalent leaked free copy gives `o_i=v_i`, hence zero cap. An equivalent rival priced at r gives `o_i=max(0,v_i-r)` (ignoring switching differences), so the cap is at most r. No demand gives no positive funding cap. Nothing about public source availability alone establishes free availability of the finished verified deliverable, but it must be tested as an outside option.

## Full costs, not image-read savings as profit

The required components are acquisition, setup, calibration, feature execution, model work, verification, delivery, coordination, and maintenance. Unknown or omitted components remain unknown. Included semantic replay incurs zero fresh inference **in this run**; original inference billing and production-service remeasurement costs remain unpriced unless independently established. Already incurred costs may be separately classified as sunk for an incremental decision but cannot disappear from a full lifecycle profit claim. Human labor, capital, insurance, storage, and deployment costs belong in the relevant components when applicable; no amounts are invented here.

Let `C_sep`, `C_shared`, and `C_comm` be complete costs, and `F=sum(c_i)`. The region `C_shared <= F < C_sep` is where ordinary sharing makes the fixed batch fundable while separate execution does not. If commissioning performs exactly the same image/feature work plus nonnegative coordination/verification overhead h, `C_comm=C_shared+h`. Then **there is no region `C_comm <= F < C_shared`**: this commissioning path cannot establish a transaction newly feasible relative to competent ordinary sharing on cost alone. Shared reads can still matter versus separate execution, but that does not demonstrate a new industry or a commissioning-specific advantage.

A genuine commissioning advantage would need independently evidenced changes elsewhere: stronger commitments that actually aggregate previously unavailable demand, lower acquisition/verification burden, improved quality, access rights, or another relevant difference. The ordinary competitor must be permitted the same batching and conventional contracting capabilities. An asserted increase in F from invented principals is not evidence.

## Current conclusion and next binding evidence

All demand and monetary cost inputs are currently unknown; feasibility is **unknown**, not universally forbidden for conditional SIM. This module supports future conditional scenarios without substituting for actual evidence. No infinite demand, short-cohort annualization, or trailing-365 extrapolation is permitted. The USD 100,000 seed → USD 3 billion native trailing-365 full modeled profit objective is not established by this work.

Next evidence required: an independently documented buyer problem tied to a usable acceptance test and bounded service horizon; that buyer's budget and credible best alternative (including cheap rival/leakage); complete incremental and lifecycle costs with unknown billing resolved; and enforceable production/delivery commitments. Native admission additionally requires the genuine historical-measurement schema, source binding and mandatory audit in the canonical system—not renamed CO2 output or a parallel account.

## Run

`cd economics && python -m unittest -v`

The eleven tests use authored dimensionless arithmetic fixtures only, never empirical sensor-service prices. They cover unknown demand/cost, budgets, leakage, cheap rivals, no demand, zero-surplus boundary, dominating alternatives, invalid identities/nonfinite inputs, and the impossibility of a commissioning cost advantage when its competent shared baseline has the same work plus no extra overhead.
