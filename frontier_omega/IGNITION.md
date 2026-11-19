# 🌌♾️ FRONTIER Ω — Ignition timing, not just monitoring

**FRONTIER Ω must determine when to investigate, run an experiment, initiate a paid pilot, or retain cash. A model release alone never ignites a business.**

This is a READ-ONLY ignition decision prototype on top of 57 structured buyer problems, implemented in [ignition.py](ignition.py). It does not call a paid model, authorize outreach, deploy products, move funds, merge code or change native enterprise accounts.

## Operating sequence

1. **Sense:** require the cited AI capability to be operationally accessible, not merely announced.
2. **Measure:** run a frozen, identical outcome contract on an authentic pre-October-12-2026 baseline and current implementation. Without the historical baseline, claim only present feasibility.
3. **Verify:** independently check acceptance, latency, all-in cost, failure modes, the best complete alternative and the buyer's realistic outside option. A URL or true/false assertion is not independently inspected by this module.
4. **Contract:** require legitimate customer permission and a *signed* voluntary customer order. The hypothetical quote in the inventory is not evidence of willingness to pay.
5. **Time ignition:** compare that signed contract price with a pessimistic all-in cost envelope, including retries, human effort, acquisition, support, refunds, financing and tail liabilities. Confirm that actual **unrestricted cash** can prefund delivery. A promise of future revenue cannot.
6. **Compound:** scale only after accepted and collected results, complete costs, repeat demand, protected obligations and independent journal review. The decision module does not authenticate these reports or run their execution.

There is no universal optimality claim. If evidence is missing, the correct decision is usually to run the next informative experiment, not to forecast success.

## Current inventory

57 candidate buyer problems, 12 dated signals, **zero verified new five-week technical crossings and zero independently confirmed real paid outcomes**. The current result for every entry is PROBE_CANDIDATE. A source change alone does not alter the commercial stage.

## Run

Use Python 3.10+, with no paid API call or third-party package:

~~~sh
python3 -m frontier_omega.ignition --limit 20
python3 -m frontier_omega.ignition --limit 57 > /tmp/frontier-omega-ignition.json
python3 -m unittest discover -s tests -p 'test_frontier_omega*.py' -v
~~~

To evaluate separate evidence assertions:

~~~sh
python3 -m frontier_omega.ignition --evidence /path/to/evaluations.json --limit 56
~~~

The input is a JSON object keyed by opportunity ID. It is not authenticated. For example, an intentionally incomplete input requiring investigation:

~~~json
{
  "O002": {
    "synthetic": false,
    "source_access_confirmed": false,
    "test_authorized": false,
    "buyer_contact_authorized": false
  }
}
~~~

This produces VERIFY_SOURCE_ACCESS rather than a pilot or sale.

Advancing to a provisional paid-pilot decision additionally requires a matched historical/current test as specified in [README.md](README.md), reported independent review, complete-incumbent comparison, actual authorized buyer contact, signed order, processing rights, buyer outside-option advantage, and a complete 12-category pessimistic cost breakdown.

The pilot evidence object requires signed_order, contract_price_usd, liquid_unrestricted_cash_usd, remaining_obligations_reserved_usd, customer_rights_confirmed, outside_option_beaten, and upper_complete_costs_usd. The last object includes every category from COST_CATEGORIES in [__main__.py](__main__.py).

**Accounting note:** tail reserves are a cash restriction, not a second expense. The residual_obligations cost category must already include the reserved amount. Complete cost is counted once. Signed but uncollected buyer commitments are not available cash.

## Timing condition

Let P be the actual signed pilot amount, C_upper an independently defensible conservative full-cost estimate, and L existing unrestricted liquid cash.

~~~text
P - C_upper > 0
L >= C_upper
technical acceptance and complete comparator tested
actual customer choice, rights and execution authorization
~~~

These are *necessary*, not sufficient conditions. A reported candidate passing them yields IGNITE_PILOT_REVIEW_REQUIRED, **not** an automatic sale, verified profit, deployment or payment. Claimed repeat paid outcomes yield SCALE_CANDIDATE_AUDIT_REQUIRED, not certified revenue.

A negative margin yields WAIT_FOR_COST_OR_PRICE_CROSSING. Inadequate existing cash yields AWAIT_FUNDED_EXECUTION. An incumbent may beat the AI-generated method. The optimal choice can therefore be to buy, partner, defer or not enter.

## First two decisive experiments

**O057 (COMPUTE) as the selected first economic qualification; O002 (MIGRATE):** attempt complete behavior-preserving Python-to-Rust migration with exact semantics, measured latency and equal-resource competent human/agent alternatives. A vendor's dramatic startup-speed improvement is not general performance parity, 26x economic value, or observed buyer demand.

**O050 (DISCOVER):** attempt a reproducible numerical-method improvement on an open engineering solver, compare its accuracy and complete cost with mature expert alternatives, and independently check every claimed scientific improvement. No algorithmic novelty or physical result is inferred from model capability news.

The next autonomous step would connect verified evidence runners, permitted buyer-demand channels, native accounts with conservation, and agentic production under explicit authority. This module implements the **decision gate**, not those external actions. Current public build remains research support to the AGI ALPHA flagship.
