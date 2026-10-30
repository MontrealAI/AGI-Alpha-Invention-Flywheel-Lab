# AGI ALPHA — Open-ended autonomous service universe and $10B–$100B stress design

**Research-only additive child of the existing 25-job portfolio in [PR #17](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/17).** It does not edit `portfolio25/`, interfere with the autonomous-delivery owner [PR #16](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/16), change any production account, or claim actual service delivery.

## Decision

Optimize the **autonomous business's expected sustainable collected contribution and unrestricted cash growth**, not the number of listings, apparent savings versus human wages, discount percentage, win percentage, or an arbitrary revenue cap. Offer complete *outcomes*, including recurring service bundles and permitted digital workflows. Existing frontier AI may suffice: a fixed-capability commercial flywheel is distinct from an invention-improvement flywheel.

A giant job list is not itself a market. The catalogue includes **160 distinct, explicitly described candidate work products across 20 families**. The same work may be sold to a different authorized buyer class with a different SLA: the default planning grid is 4 business-buyer segments × 2 delivery tiers = **1,280 hypothetical offer configurations**. These are not 1,280 observed demand pools. The input model has no 25-job or $1B cap; every finite execution has ordinary computational, file and resource bounds. Future job definitions should be added based on actual scope/evidence, not fabricated by crossing arbitrary dimensions.

### Twenty exploration families (8 work products in each)

Software engineering; data engineering; business intelligence; revenue operations; enterprise proposals; customer operations; marketing research; writing and publication; finance back office; procurement operations; legal-document administration; people operations; product operations; localization/media; IT/cloud administration; insurance administration; healthcare administration; property administration; logistics/supply chain; scientific/research operations.

The input file contains each exact service unit, acceptance contract, proposed source-access boundary, human occupation proxy, assumed human task-hours, assumed autonomous inference/tool/compute budget, and presumed risk level. **None has passed real buyer qualification or equivalent-quality production tests in this experiment.** `APPROVAL_REQUIRED` offerings are barred from first-wave launch; clinical advice, legal counsel, privileged production changes, eligibility determination, financial signoff and unsanctioned customer outreach are outside the proposed autonomous deliverables.

### Proposed first experimental lanes — not a claim of optimality

* **Software reliability packages:** reproducible bug fixes, regression tests, API migration and technical documentation. Strong machine-checkable acceptance, but copyright, repository permissions, environment reproducibility and cheap rival coding agents are serious constraints.
* **Source-grounded enterprise response and assurance:** RFPs, questionnaires, compliance evidence maps and cited proposal packets. Recurring, potentially costly human work, but enterprise trust, source access and cheap subscription competitors must be faced.
* **Finance and data reconciliation:** audited data workflows, KPI variance, invoices and evidence packets, with deterministic acceptance and no assumption of payment/ledger authority.
* **Customer operations + knowledge-base maintenance:** recurring work and cross-sell, but Intercom Fin at **$0.99 per outcome** shows real AI price competition. Do not sell an equivalent commodity at a human-wage price without independently demonstrated value.

The selected first lane depends on actual accepted quality, accessible sources, buyer participation and measured complete expenses. The highest *modeled* pricing score is **not** automatically the most promising real-world business.

## Mechanism: buyer/competitor strategic pricing

For a specified job, buyer segment and SLA, the model computes a hypothetical human-labor proxy `H = assumed human hours × sourced hourly wage × aggregate compensation loading`. The fully autonomous agent's complete *attempt budget* is an explicit author assumption, and agent onboarding/qualification is separately charged with **no default human QA**.

For each candidate price, a profit-seeking, price-setting autonomous rival chooses a best response from a finite grid. A hypothetical buyer chooses among our completed service, that rival, human provision, self-service and not purchasing, based on risk-adjusted generalized costs. We evaluate a weighted set of four adverse futures: competitive market, AI price war, verified quality differentiation, and simultaneous trust/demand/cost shock.

The leader chooses the price maximizing **weighted expected collected contribution minus a penalty for negative-scenario exposure**, with a `NO_BID` alternative worth zero. The formula does not maximize conversion or automatically grant a small discount, and a model-dependent deviation from the owner's preferred human-cost price anchor needs explicit real evidence before any live quote. Per-job launch remains **HOLD** because quality, demand, credentials and costs are not calibrated.

Important distinction: this is **a finite conditional Stackelberg-style calculation with logit-response assumptions, not an established equilibrium or calibrated optimal price**. There are no actual buyer choices, actual competitor cost disclosures, customer quotes, provider tokens or paid sales in this run. Source transparency is more important than a dramatic numerical margin.

## Portfolio-level opportunity is not revenue

A customer can buy a combination of accepted work products. `bundles.py` proposes 12 outcome-oriented bundles. Each bundle selects two example jobs from four relevant families and assumes three completed units per selected job each month. This is illustrative full utilization, not empirically determined demand. Reusing onboarding context can save work **only** when the customer permits the needed access and data-use conditions; the first-customer resource budget is shown rather than buried.

**Avoid double-counting:** a sold bundle *replaces* sales of its constituent individual jobs; totals cannot be summed. If customers buy multiple bundles, overlapping job activity must be deduplicated or contracted distinctly. Bundle listed value is not paid ACV, and the simple bundle calculation does not independently optimize enterprise procurement/willingness to pay.

### No artificial $1B limit: scale arithmetic

At an illustrative **$100,000 actually collected ACV**, the number of simultaneously paying customers needed to sustain annual revenue is:

| Annual revenue target | Paying customers at $100k ACV |
| ---: | ---: |
| $1 billion | 10,000 |
| $10 billion | 100,000 |
| $100 billion | 1,000,000 |

These are arithmetic identities. Revenue is **not profit**, and customer lifetime value and retained bookings are not collected cash. Time to target is **UNIDENTIFIABLE** absent empirically calibrated qualified-lead volume, willingness to pay, CAC, conversion, churn, capacity, reliability, capital needs, competitive reactions and reinvestment. The model intentionally does **not** print a year or a speculative win rate as a forecast.

## Measurement needed before a real business claim

1. **A complete matched work sample:** choose one accessible, rights-cleared task family; collect a fixed representative mix of simple, hard, failed, revised and rejected jobs. Independently evaluate acceptance, customer time/approval, actual frontier-model and tool traces, capacity and cost for all attempts.
2. **A human comparator:** measure human work speed and loaded compensation at the same required outcome and SLA. Use specific occupational sources rather than assume every human task costs $200.
3. **A real market calibration:** with authorized customer contact, capture actual quotes, bids, losses, complaints, rival alternatives, paid demand and retention. Register prospective pricing experiments including no-bid controls. No invented buyers or outcome-selected holdouts.
4. **A simulated strategic operating cycle, independently qualified:** integrate with the existing owner's actual production and protected settlement engine; preserve the source-bound events and show repeated delivery funded from simulated unrestricted **earned** funds. The exploratory model here never fabricates acceptance or settlement.
5. **An observed commercial claim, separately:** accepted real output, collected real cash, complete measured operating costs and repeated reinvestment. Capability improvement is not a prerequisite. Regulatory, confidentiality, credentials, safety and property rights still apply.
6. **A scalable portfolio:** only expand from one successfully qualified lane when measured cross-sell, service reliability, onboarding and incremental net returns justify investment. Use withheld scenarios and strong AI competitor controls. Preserve failures and reject unprofitable offers.

## Run

Requires Python 3.11+ standard library only, no network, payments or provider access.

```sh
python3 -m unittest discover -s portfolio_scale -p 'test_*.py' -v
python3 portfolio_scale/engine.py --output /tmp/alpha-universe-plan-NEW.json
python3 -m portfolio_scale.bundles --output /tmp/alpha-enterprise-bundles-NEW.json
```

The output directories/files must not exist. `reference_summary.json` and `reference_bundles.json` are deterministic author-prior scenario snapshots. The full 1,280-offer output is generated by the CLI; its digest is preserved in `reference_summary.json` rather than committing a large generated listing. Neither summary is confirmation evidence, company financial records, or proof of earned funding.

## Source grounding and limitations

**Public source parameters (2026-10-30):** U.S. BLS *Occupational Employment and Wages, May 2025* https://www.bls.gov/news.release/ocwage.t01.htm ; BLS *Employer Costs for Employee Compensation, June 2026* https://www.bls.gov/news.release/ecec.nr0.htm (private-industry $32.82 wages, $46.89 total, aggregate ratio 1.4287); McKinsey *State of AI 2026* https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai (surveyed 40% of large organizations scaling agents, 32% reporting product non-purchase because agents could build in-house); Intercom Fin https://www.intercom.com/pricing (AI support from $0.99/outcome); OpenAI official API https://developers.openai.com/api/docs/pricing (current model/tariff schedule).

**Not sourced or proven:** task hours, true task incidence, lead counts, conversion rates, price elasticity, agent cost by work product, rival provider margins, onboarding consent friction, multi-product willingness to pay, service quality, enterprise buyer value, and actual earned revenue. All these are `AUTHOR_PRIORS_NOT_MARKET_CALIBRATION` and cannot be promoted into facts by generating more examples or executing deterministic replays.

The employment groups and the approximate $62T global labor-income context are **broad-scale indicators, not a measured AI-addressable market**. Do not count every employee as replaceable or attribute all wages to autonomous profit. Market demand and pricing are endogenous, and increasingly competent rival AI can remove much of the presumed wage-to-price spread. All estimates require geographic, currency and occupational checking before use.
