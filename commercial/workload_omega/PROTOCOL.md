# WORKLOAD Ω — precommitted acceptance (21 November 2026)

## Economic question

Can MONTREAL.AI produce a repeatable, auditable *AI workload cost-reduction* capability that a buyer might subsequently pay to use, without violating paired answer quality and latency requirements? This is a **supporting commercial experiment** under the Blue Sky flagship, not evidence of a new frontier invention or authorized deployment.

## Fixed experiment and negative controls (before implementation)

1. **Input:** owner-provided, non-sensitive, fixed, case-paired reference and candidate observations in two disjoint `train` and `holdout` cohorts. Cost is exact integer micro-USD per request; latency is measured integer milliseconds; acceptance is an external Boolean label, not inferred by the optimizer. Require unique (split, case, arm), exactly one row per arm and case, and positive request counts. Reject invalid/mismatched contracts, non-finite values, missing arms, and any case that overlaps train/holdout.
2. **Selection:** evaluate all candidate arms on training rows only. Preserve the reference as the safe fallback. To admit a candidate into shadow qualification, require no observed quality regression relative to reference, a user-declared per-request latency ceiling, and positive mean gross cost saving. Rank by greatest training reduction, stable deterministic tie breaking. No holdout-based re-selection.
3. **Qualification:** evaluate the frozen training winner on fresh holdout cases. Refuse if insufficient independently labelled pairs, a quality regression, a latency failure, or nonpositive holdout savings. Always disclose total cohorts, comparison, exact observed costs and the possibility of distribution shift. Do not claim a population confidence interval from finite samples.
4. **Commercial gate:** model a buyer's gross cost savings and a potential MONTREAL.AI fee, including declared workload volume, savings share, recurring platform costs and per-request validation/monitoring costs. Missing costs/volume must remain unknown, never silently zero; estimates are not invoices or receipts. Refuse commercially viable status when modeled contribution is not positive.
5. **Evidence gate:** synthetic fixtures stay `ENGINEERING_ONLY`; even self-described measured records stay `SHADOW_CANDIDATE` until independently authenticated, customer-accepted delivery, verified bills/settlement, rights, and a safe operational rollout exist. No bank, checkout, live model API, tokens, or model endpoints are contacted.
6. **Adverse tests:** paired-quality regression; latency regression; failed candidate; no candidate; duplicate observations; train/holdout case overlap; missing reference/candidate; malformed prices and costs; missing commercial costs; simulated positive economics mistaken for revenue; holdout that reverses the train winner.
7. **Second-asset test (not self-certified):** retain optimizer code/receipts and reuse it on a *different, prospective* workload with matched equal-content ordinary reuse and from-scratch alternatives; count acquisition, integration, inference, monitoring, support and maintenance. Repeated use of the same optimizer is not a new invention. Require buyer acceptance/revenue separately.

## Authority / boundary

No edits to native accounting, current sales pages, checkout, existing releases, owner branches, or protected production. No private customer data, credentials, spending, model API calls or live routing. Public code/test workflow only. Report accurate engineering tests and explicit blockers, no synthetic first-dollar claim. If strongest conventional optimizer ties or wins, retain it without a novelty claim.
