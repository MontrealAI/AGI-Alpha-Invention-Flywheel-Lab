# Buyer-income 039 — native recurring purchasing capacity

## Why this is a substantive, bounded change

The canonical connected enterprise starts from a finite buyer list, each with a finite lifetime spending budget. Even when sellers have unrestricted earned cash, buyers without replenished resources cannot keep buying. An opt-in `buyer_income_policy` adds periodic **exogenous buyer income** to their *buyer-side* spending budgets, never to the enterprise account.

The intervention is not a customer-acquisition mechanism, new customer population, price increase, success assertion, debt contract, partner-funded enterprise or live buyer datum. It isolates one necessary condition of recurring demand, while preserving voluntary choices, competing human/rival options, expiring costed acquisition channels, source-frozen jobs, native financial authority and all existing cash protection.

The default configuration remains byte-for-byte the prior finite-budget model when no optional policy is supplied.

## Exact optional terms (simulated only)

```json
{"buyer_income_policy":{
 "schema":"agi-alpha/connected014-buyer-income/v1",
 "first_day":30,
 "period_days":30,
 "income_microUSD":100000000,
 "receipt_bps":6000
}}
```

This example *assumes*, without observing, a 60% chance that a buyer receives $100 in outside operating income each period. All five fields are source-frozen as part of the canonical registered configuration. A deterministic keyed draw uses the world seed, buyer identity and day; the seller cannot observe future draws. No enterprise funds, customer deposits, reserves or native account entries are created by these events.

Every realized receipt carries the role `AUTHORED_EXOGENOUS_BUYER_INCOME_NOT_ENTERPRISE_REVENUE`. The buyer balance identity becomes:
`initial_budget + realized_external_income = remaining_budget + outside_spend + settled_enterprise_spend + pending_commitments`.
The independent verifier rederives exact receipt identities, dates, amounts, counts and buyer totals from the frozen configuration, then recomputes voluntary buyer decisions using *only income available at decision time*. Manipulated receipts, missing records, inflated balances and fabricated buyer resources fail.

**Important limits:** The original finite job inventory, opening customer population, channel reach, capacity, pricing, acceptance and risk limitations remain. This cannot establish $1B annual profit, recurring willingness to pay, new market segments, a validated income model, or an ongoing acquisition pipeline. It deliberately leaves the need for genuinely new buyer cohorts and fresh unique accepted work visible. New business models and registered comparison experiments remain necessary; arbitrary large income numbers are not evidence of demand.

## Fixed test and source qualification

`python3 -m unittest -v tests.test_connected_buyer_income039`

The tests exercise the actual `run_world` and `verify.audit` paths on frozen source and service fixtures, negative-policy validation, deterministic event timing, tampering, and a no-demand region where outside income grows but enterprise collections remain zero.

This amendment does not replace the concurrent $100k/60-month challenge PR #68 or the separate offer/capacity owner branches #65–#69. It is an opt-in native mechanism to be compared prospectively and adopted only after compatible source-qualified tests, independent audits and normal integration/release checks.

## Necessary next productive step

Connect a costed, voluntary external distribution cohort to genuine new permissioned work instances, first against strong existing service and customer-choice alternatives. Keep simulated buyer income, acquired leads and deposits separate from enterprise earned cash. Confirm that independently accepted work, not buyer creation, drives profit; register a finite and adverse 60-month comparison, with no invented probability of attainment.
