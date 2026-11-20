# P197 — AI governance change-impact research on a public buyer problem

**Research-only, not a qualified procurement product, commercial offering, regulatory opinion, valid access-control system or native enterprise.** This branch is an additive construction on the published main at `f0987aa48d5c9136b28540f54eabf5367e63bbe6`. The [frozen protocol](PREREGISTRATION.md) predates the implementation.

## Why this exists

The [official Shared Services Canada challenge](https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance), published 30 October 2026, documents a real government need: reduce manual burden in continuously determining how evolving AI governance requirements affect registered AI systems. It is open until **22 December 2026 at 14:00 Eastern**. The program estimates **one or two** Phase 2 contracts capped at **CAD 2 million each**, but explicitly guarantees no award. An eligible bidder must already demonstrate TRL **5–9**, substantive innovation, *all* essential outcomes and other criteria. None of those has been established for this research. No bid or communication is authorized.

## Actual executable means

`impact.py` computes exact impacts of **already-curated** requirement-version changes against synthetic per-tenant system registries. It keeps out-of-date and missing evidence **UNABLE_TO_DETERMINE**, demands a separate v2 evidence reference for an updated requirement, records retirement as requiring reassessment rather than declaring compliance, and appends a hash-linked reviewer decision without changing the evidence verdict. The same affected set is independently matched by a competent ordinary list-join. This is **ordinary deterministic software**, not AI invention or a demonstrated advantage over standard governance offerings.

The audit hash chain is **not signed, anchored, concurrency-safe, durable or remotely authenticated**. Reviewer objects and `verified` evidence booleans are caller-supplied fixture assertions, not deployed RBAC, attestation or government evidence. There are no policy-text interpretation models, actual connectors, persistent registries, security/privacy compliance, regulatory guarantee, buyer data or commercial processes.

### Offline reproduction

```sh
python3 -m unittest discover -s campaign/governance-impact197 -p 'test_impact.py' -v
python3 campaign/governance-impact197/impact.py
```

Exactly eight frozen test groups cover affected tenant scope, missing evidence, version specificity, retirement, reviewer gating, chain tamper/reorder, equal-information ordinary parity and NO BID under unknown eligibility/commercial facts. The `impact.py` command emits one synthetic JSON example to standard output, not a deployable service.

## Acceptance matrix

| Stage | Current verdict |
| --- | --- |
| Official government buyer problem and published funding ceiling | Public primary evidence; **not** contract demand for us |
| Three different opportunity arrangements + no-bid | Preregistered; only AI governance selected for isolated construction |
| Technical prototype / eight fixed tests | Local PASS on source authored 20 Nov; hosted exact-head source CI separately required |
| Ordinary comparator | TIE by design; no superiority claim |
| Regulatory interpretation, full essential functionality, TRL 5–9, legal eligibility | **UNQUALIFIED** |
| Actual buyer consent, provider comparison, complete costs, government award, revenue | **UNKNOWN / ZERO OBSERVED** |
| Original native financial account, transition/queues and source integration | **UNTOUCHED / BLOCKED** |
| US$3 billion trailing-365-day complete-cost profit | **NOT ACHIEVED** |

**Decision: NO BID / NO DEPLOY.** Advance only upon independent proof of a true, competitively underprovided accepted outcome, full requirement coverage and authorized source-bound funding. Keep the single original native-financial owner, current released enterprise and historical failures unchanged.
