# Transformational intelligence: remove the capital-recycling constraint

## Executed result, not a larger revenue forecast

This contribution adds a read-only diagnostic to the canonical connected enterprise. It identifies the conditions under which profitable autonomous delivery can recycle its cash into further delivery. It does not create a new ledger, change existing contracts, waive obligations, select a pricing policy or execute transactions.

A complete public-source replay of the eight previously exposed price-matching businesses passed: native financial history, actual deterministic service artifacts, buyer decisions and operating costs. The new instrument then checked **1,770 native snapshots** with zero arithmetic mismatches. Twenty-three new tests passed, including **120 generated native accounting fixtures** and an independently formulated inverse-constraint calculation. These are engineering checks over known data, not new commercial observations or fresh confirmation.

## The decisive structural distinction

The current protected exchange reserves the full sale price plus 0.20 simulated USD for every released order. No automatic maturity is part of this contract. This is an explicit protection design, not a universal requirement of business.

Let S be initial capital, C net collections, R recovery income, X paid costs, I separately booked investment payments, P payables, U custody reserve, W working capital, T tail reserve and K outstanding investment reservations. The unchanged native available balance satisfies:

    available = max(0, S + C + R - X - I - P - U - W - T - K)

For a settled cohort with no reversals, recoveries, pending custody or investment reservations, the permanent full-principal rule gives T = C + 0.20 * paid_orders. Therefore:

    available = max(0, S - X - P - W - 0.20 * paid_orders)

**Collected sale prices cancel their retained principal reserves.** Profit can rise while available cash falls. Calling the revenue earned is correct; treating all of it as newly spendable expansion capital is not.

This does NOT invalidate the existing successful finite simulated commercial loops. Initial equity may support reserves while earned funds finance new work. The diagnostic reports that distinction and keeps `unrestrictedEarned` separate from `available`, cash and profit. Nor does it establish that liquidity is already the immediate bottleneck in every observed case.

### Exact historical accounts (SIM USD)

All begin with 5,000 seed capital and 100 working capital: initial available cash is 4,900.

| Exposed world | Paid jobs | Recorded profit | Available cash | Decline in available cash |
| --- | ---: | ---: | ---: | ---: |
| Central 99014101, retained | 13 | 210.548348 | 4,692.566848 | 207.433152 |
| Central 99014101, price candidate | 29 | 568.907398 | 4,537.891898 | 362.108102 |
| Central 99014102, retained | 9 | 133.845249 | 4,737.754249 | 162.245751 |
| Central 99014102, price candidate | 32 | 643.963158 | 4,498.221158 | 401.778842 |
| Price pressure, retained | 5 | -4.857682 | 4,795.386068 | 104.613932 |
| Price pressure, price candidate | 22 | 192.449253 | 4,681.961128 | 218.038872 |
| Failed channel, retained | 6 | 70.124660 | 4,772.780660 | 127.219340 |
| Failed channel, price candidate | 12 | 189.707244 | 4,720.077494 | 179.922506 |

These are alternative simulated businesses; they must not be pooled into one enterprise's earnings. The favorable pricing effect remains intact. Neither tail diagnosis nor this replay is observed commerce. Historical unknown billing, synthetic demand, shared setup-cost assumptions and scope restrictions are preserved.

## What was constructed

`connected_enterprise/capital_frontier.py` supplies three deliberately small functions:

- `diagnose`: independently reconstruct cash, profit, available funds and earned-funds identities from a native snapshot. A mismatched identity refuses. A self-consistent snapshot is NOT authenticated by this function; authoritative native replay remains required.
- `required_tail_release`: calculate the smallest hypothetical tail reduction sufficient for one earned-funded commitment, including an upfront arrangement cost. It preserves custody, working capital, prior reservations, payables and breach stops. It cannot create earnings, release a reserve, or approve a contract. An unaffordable arrangement refuses.
- `settled_cost_bound`: calculate a necessary terminal upper bound on paid deliveries under permanent full-principal protection and a supplied positive complete-cost lower bound. Unknown cost stays unknown. Admission collateral and timing can make actual feasible delivery smaller than the bound.

The inverse calculation is monotone and exact in integer microUSD for this snapshot model. It is not a global optimum, provider quotation, legal opinion or real-market forecast.

### Illustration, not an observed service

Using the earlier hypothetical article price of 95, cost of at least 5.03, initial capital 5,000, setup 80, working capital 100 and permanent 0.20 extra protection per sale:

    maximum paid jobs <= floor((5000 - 80 - 100) / (5.03 + 0.20)) = 921

This is an optimistic necessary **terminal financing bound**, not a prediction or proof that 921 jobs can be funded. Upfront sale-price collateral, settlement delay, fees not included in the stated cost, refunds, acquisition failure and capacity can stop the business earlier. No article sales occurred here. A higher selling price alone does not relax this bound while the full corresponding principal remains reserved forever.

The point is not to reduce ambition. It is to stop extrapolating a capital-consuming contract into unlimited self-financed growth.

## The next enabling construction

Use the existing event-time contract and Account machinery to test a **new, explicitly priced capital-recycling contract**, never retroactively rewrite a released trade. Distinguish:

1. Existing permanent principal protection as the retained baseline.
2. A contract with independently supported finite exposure, actual maturity, and all applicable arrangement/risk costs.
3. Alternative limited obligations or transferred risks, only when the counterparty, buyer acceptance and payment route support them.

This list is a research design, not a claim that such terms are obtainable. Every alternative must change buyer utility and expected payments where appropriate, preserve all genuine refund/support/tax obligations and charge provider/insurance/arrangement costs. A new contract is allowed to lose to the original.

Compare the same qualified work, capital, opportunities and capable service tools. Keep an equally capable simple business-policy control. Measure settled contribution, obligations, reserve age, capital turnover, repeat customers and actual earned-financed commitments. Preserve failed and unreached trajectories. A useful contract must deliver additional accepted, collected, fully costed work, not merely reduce a spreadsheet reserve.

A forward scale model must reproduce exact native state transitions on overlapping traces before its cash claims are promoted. The present instrument validates only snapshot identities and exposes a necessary constraint. It does **not** bridge future demand, every event transition, capacity scaling or long-horizon projections. Falsifiable distributions of growth times remain conditional until those other parts are qualified.

## Integration and reproduction

Target: the canonical connected enterprise integrated in PR #28, inspected head `9354d76a7033e8958968cde4469cdd71ea870a21`. This contribution leaves all existing files and active evaluation untouched. The snapshot semantics inspected there match the historical protected exchange blob `378bf67ae24c18ad58b684ce8b13492fd06f8556` used by the replay. Current financial repairs remain the owner's responsibility and are not undone or replaced.

```sh
python3 -m unittest discover -s tests -p test_capital_frontier.py -v
python3 -m connected_enterprise.capital_frontier \
  --input campaign/capital-frontier-016/EXPOSED_STATE.json \
  --commitment-microUSD 100000000 \
  --output /tmp/capital-diagnostic-NEW.json
```

No monetary input is fabricated by the CLI. `EXPOSED_STATE.json` is one historical simulated state, not current spend authority. The diagnostic outputs `execution_authorized: false` and `native_authentication_performed: false`. A new costed commitment requires the current Account audit, an unmodified verified source, a fresh-state reservation and actual permission.

The separate package reproducibility receipt is in `RESULT.json`; full raw worlds remain in the previous price-matching package (SHA256 `ce0e1025bf54c5a032641003dea825c882f6531d1363a8a026e71db790e60838`). The public evidence was reaudited locally on its exact source. Current full-repository CI, qualified integration, real providers, metered frontier calls, physical productive expansion and new observed revenue were NOT established.

## Open-ended objective

Continue useful autonomous commerce without requiring intelligence improvement. Transform the binding production or financing constraint when that is worth its complete cost. Retain tested mechanisms and failure conditions for fresh successors. Separately evaluate scientific and physical productive expansion. There is no imposed business/revenue ceiling; there is a requirement that the actual operating design supports the claimed growth.
