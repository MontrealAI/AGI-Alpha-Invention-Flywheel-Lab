# Optional fixed-share current-invoice caps050

A fresh frozen configuration may set
`strategic_allocation_policy.category_budgets_bps` to exactly
`{"acquisition":5000,"capacity":5000}` or another declared nonnegative integer
basis-point pair summing to10000. The feature is optional; absent configuration
preserves the existing planner behavior and serialized result fields. A golden
regression compares uncapped allocator bytes with the prior source.

At each native planning prefix, eligible funds are
`max(0,unrestrictedEarned-operating_envelope)`. Each category's cap is the floor
of eligible funds multiplied by its declared share/10000. The existing allocator
checks the **sum** of selected upfront invoices in that category against the cap
before ordinary ranking or finite-game selection. Delivery, global cash, earned
funding, principal protection, liabilities, risk, exclusivity, work identity and
existing commitment checks remain unchanged. Forecast revenue supplies no funds.

These are per-decision invoice limits. They do not create persistent category
balances, reserve unused headroom, impose cumulative lifetime spend proportions,
force an investment or make unused budget an expense or income. Remaining cash
stays cash and cap headroom is recomputed at the next native prefix. The interface
supports a precisely labeled fixed-share comparator, not a new ledger, optimizer,
default policy, claimed best allocation or forced research share.

Caps apply to current acquisition/capacity invoices regardless of their funding
label. An earned-derived acquisition cap of zero can therefore also block a
separately qualified seed-funded startup acquisition; there is no silent seed
exemption. Declare that benchmark implication. Contingent future capacity costs
remain within existing global earned/liability reservations, but are not current
upfront invoices. A later actual invoice must reobserve funds and satisfy its
then-current cap. No full-horizon or guaranteed future-allocation claim follows.

Planning records include `category_upfront_caps` only when configured. The caps
enter the hashed native allocation plan and survive retain-cash/unresolved paths.
Public refusal and selective recourse retain the same caps, mandatory investments
and accepted delivery commitments. Independent operating audit reconstructs caps
from the frozen policy and authenticated native prefix; a self-consistent stored
record with a forged cap still fails that check. Cash-relaxation diagnostics with
caps are explicitly unavailable at both connected and low-level allocator APIs. Complete-run capital reports record these diagnostics as `UNAVAILABLE` with the explicit reason; they do not abort an otherwise valid native operation. Records are ordered by native time so JSON serialization and completed resume preserve derived reports.

Verification:

```sh
python3 -m unittest tests.test_connected_category_budgets050 -v
python3 -m unittest tests.test_adaptive_allocation tests.test_refusal_recourse -v
```

Tests exercise cap binding across multiple invoices, rounding and operating
costs, no available/earned cash, liabilities/risk, zero caps and hold, duplicates,
mandatory commitments, game selection, recourse, legacy bytes and forged records.
The native fixture opens a fresh exact-money account, buys actual capped
investments, independently audits every cap/receipt, rejects a coherently forged
cap, resumes the same account and checks unchanged financial history. This is
engineering qualification, not a tuned-policy economic result; the separate
five-policy driver must freeze tuning/evaluation inputs and count all costs.
