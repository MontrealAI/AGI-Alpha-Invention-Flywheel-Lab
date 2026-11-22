# Renewable paid-office-work market: corrective opt-in sensitivity (068)

**Correction:** an initial finite simulation list of prospective buyers must not be equated with the total market or allowed to permanently exhaust future paid work. Existing organizations generate new period-specific work; new organizations can become reachable; a former customer can rejoin under valid permission; marketing contacts cost money. An annually fixed occupational headcount is *not* one finite order queue.

This addition does **not** change the default native business, `JournalAccount`, `Account`, existing signed accounts, or any active commercial owner's branch. It is an **aggregate and explicitly hypothetical** opt-in screening model for acquisition and renewal decisions, not a source of customer orders, customer spending authority, verified deliveries or revenue in a native account. That distinction prevents the economic projection from falsely becoming a production receipt. `renewed_work_identity(...)` now creates period- and source-specific IDs without asserting that work exists. Native integration requires independently validated, permitted per-buyer work identities, a currently funded channel purchase, buyer choice, source-linked production and authoritative settlement.

## Why the former forecast failed

The current native `channel_menu.py` forecasts incremental reach only among identities in a fixed `buyers` collection. `channels.py` ranks buyers passed to its `expose` method and its independent audit reconstructs a single fixed population from the original registration. This is appropriate for *that frozen experiment*, not an empirical estimate of all organizations or replenished work. `complete_offer_market.py` has finite buyer budget atoms that do not independently establish later operating income. An active PR #103 examines separately costed buyer income, and PR #138 owns a growth-066 campaign; neither is overwritten by this addition.

## What changed here

1. **Demand stock versus flow:** The BLS-based occupational activity proxy is held separate from the assumed number of serviceable work packets; those packets are offered anew per period for retained customers. A packet from a new period is not reusing an already-sold task.
2. **Prospective acquisition versus recurring purchase:** Existing retained customers can place new monthly work without another cold marketing contact. New prospects are contacted at declared costs, with new customers starting work the following period.
3. **Customer conservation:** Aggregate buyers are partitioned into active, never-contacted, one-follow-up eligible, voluntarily reactivatable dormant, dormant without new permission, and exhausted contact-right cohorts. Churn does not create a new cold identity; a failed follow-up is not endlessly re-approached for free.
4. **Market entry and capacity:** New externally eligible organizations can enter in future months. Every cohort and outreach flow is an **assumption**; a newly registered eligible organization is not automatically a lead, order or paying customer. There is no permanent 12-buyer cap. Real serviceable work and monthly production capacity still constrain accepted throughput.
5. **Budget is not magical:** Every modeled renewed customer budget is an **explicit hypothesized monthly employer appropriation**, external to company cash. Company revenue arises only from hypothetical accepted work, discounted for noncollection. That is not actual cash and cannot be spent through a real/native account.
6. **Capital integrity:** Outreach and worst-case production costs are reserved in the model from available opening equity or already accumulated conditional cash; marketing occurs before the leads' first month's work and is not financed by those future sales. $100k and larger initial equity are separate, unpooled scenarios. Refuse if fixed costs cannot be prepaid. Support tails remain protected for one modeled month; releasing protection is not revenue.
7. **No forced outcome:** Explicit quote ceilings, a monthly purchase-intent rate, acceptance, collection and consent all remain contingent assumptions. Retention, quality, outreach expense, price, serviceability and initial reachable population are stress-tested. The primary comparator is fully burdened human office delivery; rival AI pricing belongs in a separate downstream commercial competition test.

## Reproduce

From the repository root, using Python 3.12+ and **no API keys or model calls**:

```sh
python3 -m unittest -v tests.test_renewable_market068
python3 -m connected_enterprise.renewable_market068
```

`python3 -m connected_enterprise.renewable_market068` prints a compact summary of **13 separate authored scenarios**. `simulate(Scenario())` returns exact integer monthly flow and expense histories with source input hash. Source file and test file are independent additions and do not import or update native ledgers. Do not merge results from these scenarios into one company account.

## Observed results / interpreted limits

On the initial tested code (21 local tests passed):

| Scenario | Last trailing-twelve-month profit | First modeled $3B trailing-year crossing |
| --- | ---: | --- |
| 500,000 initially eligible organizations, +2,000/month, $20M initial equity | **$726,900,906.31** | None within 24 months |
| **2 million initially eligible organizations**, otherwise the same *authored assumptions* | **$3,067,282,921.92** | Month 19 |
| Same assumptions but initial **$100,000** | **Not funded**; no operating year claimed | None |
| Lower retention (85% monthly) | **$176,441,119.00** | None |
| Lower cold-conversion (1% rather than 5%) | **$127,698,883.58** | None |

These values are not customer evidence, native audited business profits or an achieved milestone. The 2-million-reachable scenario is especially uncertain; U.S. occupational headcount is neither a count of reachable employers nor a contract. There is no calibrated source for the assumed $95 price, 24 monthly work packets per retained customer, 5% cold conversion, 97% monthly retention, cost envelopes or growth financing. Real acceptance quality, lead generation, settlement delays and physical capacity at millions of jobs have not been demonstrated. The reduced labor-office cost is a *scenario*, not an employer invoice. The model's same-period collection and one-month unclaimed support tails are optimistic assumptions. A modeled cash refusal is not evidence that real financing cannot be raised.

## Next meaningful adoption boundary

The PR #138 growth owner can adopt the **distinctions**, not transplant this aggregate engine as a second ledger. The native enterprise would need unique renewed work identities, explicit buyer-side income/budgets, paid channel acquisition of newly registered buyer cohorts, independent decision-time buyer choice, no reuse of sold work, full-cost funded production, and separate native replay audit. The registered source/seed must remain unchanged for historical accounts; create fresh prospectively frozen accounts and comparisons. Only native source-matched release checks and independently accepted deliveries could qualify a commercial milestone.

**Lesson:** fixed-cohort exhaustion is a simulation artifact; market renewal must be modeled as recurring paid need and actual acquisition flows. Replacing that ceiling with fabricated monthly orders is not a correction.
