# Native risk152 — prospective protocol (frozen before code)

**Base:** `de4e9c2425c3879ad1b2e52bbe44cff79dcf973d` (qualified main, 2026-11-13 UTC). **Owner:** isolated, additive research-only component. Financial P0, original Account/JournalAccount, operating queues, signer, and all other owners remain untouched. No new credentials, spending, procurement response, outreach, private data or deployment.

## Material new source and binding scope

The [official CanadaBuys Amendment 001, posted 2026-11-10](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-189-51083224), PDF Q1/A1, Q6/A6, Q20/A20 (pp. 1, 2, 5–6) states that **Essential Outcome 6 requires native data/model/output-risk and quality evaluation**; integration of third-party/open-source evaluation tools or receipt of externally computed scores is insufficient. It also requires updated governance requirements to reprocess completed assessments. Q3/A3 anticipates bidder-hosted demonstration with access for Canada. Q7/A7 confirms the governance application need not itself use AI. CanadaBuys controls over divergent challenge summaries. The independent [ISC challenge](https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance) requires all essential outcomes, documented TRL 5–9 and competitive advantage. All those whole-product conditions remain **unqualified**.

The merged `products/governance_impact140` currently maps evolving requirements and untrusted evidence but documents **no native risk/quality evaluation**. A narrow new source-contained evaluator is a consequential product dependency, **not** an eligible government product or transformative invention alone. Human specialist with conventional scripts, established GRC/evaluation platform plus qualified integrator, native first-party instrument with authorized review, third-party-only adapter (now inadmissible for EO6), and no-deploy are the alternatives. Their full costs, access, risk and superiority remain unknown; **no-deploy remains the commercial choice**.

## Fixed native construction and adversarial acceptance

Develop only `products/governance_impact140/native_risk152.py` with a no-network, no-third-party, standard-library binary-classification evidence evaluator, and `tests/test_governance_native_risk152.py`. Input: an exact schema, one synthetic registered system, declared decimal thresholds and distinct case rows containing observed binary predictions, optional verified-in-future ground-truth labels, disclosed group, repeated prediction, and output violation *claims*. Compute **from rows** rather than accepting outside scores: data missing-label rate, accuracy, group true-positive-rate gap where supported, repeated-output disagreement, and declared policy-violation rate. Derive exact rational comparisons; provide counts, denominators, and explicit unable-to-determine where missing truth/repeat/group support defeats a metric. No validated fairness, privacy, or safety claims from group labels or asserted flags.

Frozen cases:
- T1: a fully populated synthetic case produces deterministic exact computed numerators/denominators and threshold signals, with *no* compliance approval;
- T2: shuffled row order changes neither computed result nor content digest, but altered inputs do;
- T3: duplicate case IDs, unexpected keys, invalid scalar types and duplicate JSON fields fail closed;
- T4: thresholds outside 0..1, non-finite, scientific notation if unsupported, mixed numeric types and implicit float conversion fail closed;
- T5: missing truth prevents accuracy and TPR clearance instead of excluding hard examples; unknown repeated prediction blocks consistency clearance;
- T6: absent or too-small positive groups block group TPR clearance; do not interpret a gap as proof of fair treatment;
- T7: adverse accuracy, violation, consistency, missingness or group-gap values produce negative threshold signals without overriding other unqualified dimensions;
- T8: input flags like `claimed_review: approved` cannot authenticate observations; no report is an official result, authenticated review or certification;
- T9: mutation of row evidence changes digest, and report identity uses an external anchor rather than self-certifying SHA;
- T10: independently check a clean CLI input/output roundtrip and reject overwrite, raw duplicate JSON keys, malformed UTF-8 and nonobject JSON.
All examples are authored synthetic cases, not government data or paying customer tasks. If a fixed test fails, preserve the failure, repair implementation and repeat without changing these gates or cherry-picking. Never call source-level success a TRL 5 result or a completed EO6.

## Stop, qualification, retention and commercial decision

Stop this finite scope after source tests, independent key-free review, exact-head CI and a public PR. If any source gate fails, do not merge; preserve failure and repair. Do not request a release or merge before source-matched all-applicable checks, independent review and one owner-led integration decision. Even with passing tests, **no-bid/no-deploy** persists until the complete first-party risk stack, safe real inputs, authorized RBAC review, data residency, API integration, official machine-readable policy derivation, buyer acceptance, credible TRL and full costed alternative comparison pass. This module neither uses nor creates the canonical native finance account. Actual buyer demand, cash collections, hosting/inference cost and USD 3B trailing-365 profit remain unknown/unqualified.
