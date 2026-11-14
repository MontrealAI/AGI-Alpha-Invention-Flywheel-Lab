# Governance temporal-risk 159 — frozen pre-implementation contract

**Registered 2026-11-14 against released main `b25c15fdcdaf235ed8f5188ef6ba72b02f52c36e`; protocol is committed before code, tests, workflow or test execution.** No source/account financial writes, signer access, original-user data, bids or deployment. This is a first-party *synthetic* research dependency on existing native-risk152, not a new Blue Sky flagship or independently validated buyer advantage.

## Consequential product dependency and alternatives

Shared Services Canada's public 2026-10-30 AI governance challenge specifically asks for ongoing reassessment of model/data/output risks. Existing Governance158 recomputes before/after **policy** against the **same** authored observations; it does **not** evidence performance shifts across two separate observation periods with a fixed policy. The missing means is a verifiable two-period observation comparison, not a new regulator or an invented compliance approval. The potential productive outcome is timely identification of a newly adverse risk signal while preserving historical evidence and a required human decision.

Compare four complete arrangements: (A) original single-snapshot Governance158 (strong frozen incumbent for this narrow dependency), (B) paired independent native observations with the existing risk152 evaluator, (C) capable existing human-plus-conventional monitoring or established enterprise GRC/AI-risk vendor, and (D) no bid/no deploy. B may establish **engineering change detection only**; no claim that it beats C, establishes TRL 5–9 or can win or serve SSC. Its actual buyer value, acquisition, enterprise integration, personnel, billing, tax, support and complete costs remain **unknown**. Government's CAD 2M per-contract ceiling is not income. The US$3B trailing-365-day full-cost profit target remains unachieved.

## Fixed input and decision rule

Input has exactly `schema`, `system_id`, `prior_date`, `current_date`, `thresholds`, `prior_rows`, `current_rows`. Dates are strict ISO dates and **prior < current**. Both periods are actual row inputs to the unchanged `native_risk152.evaluate`, with identical exact policy. The two case-ID sets must be disjoint to prevent reused cases posing as new samples; each is nonempty and individually validated by the original native evaluator. Duplicate or nonfinite JSON input and injected untrusted reviewer claims fail closed. Source-observation digests bind sorted actual rows, not just threshold-dependent reports. Every native signal is reproduced, with a change classification:
- previous WITHIN, current ADVERSE => `NEW_ADVERSE_SYNTHETIC_SIGNAL`
- previous ADVERSE, current WITHIN => `RESOLVED_SYNTHETIC_SIGNAL`
- both ADVERSE => `PERSISTENT_ADVERSE_SYNTHETIC_SIGNAL`
- both WITHIN => `BOTH_WITHIN_SYNTHETIC_THRESHOLDS`
- either UNABLE => `UNQUALIFIED_OBSERVATION`

All reported changes retain the **synthetic** qualifier and must not be described as statistical significance, causal drift, legal compliance or actual field performance. The system is **always** `requires_authorized_review=true` when new observations are supplied; no authorization mechanism is implemented. Output is create-only; verify requires external anchors for report and BOTH original input digests, not self-approval. Unmeasured metrics retain `UNQUALIFIED_OBSERVATION`.

## Fixed tests — no cherry-picking

T1: 3-row prior accuracy 3/3 vs disjoint 3-row current 2/3, min_accuracy 0.75: exactly one NEW_ADVERSE accuracy signal, originally WITHIN, remaining outcomes reported, no compliance approval.
T2: both periods 3/3 (distinct IDs): BOTH_WITHIN, still requires review.
T3: prior 2/3 and current 3/3: RESOLVED, still no approval.
T4: prior and current 2/3: PERSISTENT_ADVERSE.
T5: missing current true labels => accuracy UNQUALIFIED even with original complete.
T6: bad/identical/reversed dates, overlapping case IDs, duplicate rows, and bad policy all fail closed.
T7: original inputs/thresholds not mutated; row order invariant; altered current prediction changes bound digest and output.
T8: source/receipt external anchoring: changed report or wrong prior/current source hashes rejected.
T9: strict CLI fails on duplicate JSON keys, nonfinite values, output overwrite and identical input/output.
T10: first-party native evaluator outputs exactly match both independent period rows; source scopes are explicit.
T11: irrelevant claimed reviewer approvals cannot enter the strict row schema.
T12: full regression on original risk152, reassessment153 and governance158 after this additive source; original engines unchanged.

## Acceptance and decision

First run is fixed, not tuned to pass. Run focused tests and exact-head hosted workflows with standard `ubuntu-latest`, `timeout-minutes:360`, initial `AGI_JOB_START_EPOCH`, no paid services, APIs or external accounts. A passing isolated research artifact is not the original-account financial migration, native commerce, a public released executable or a buyer. Preserve all failures, host test logs and exact source SHA. **No bid/no deploy until authorized reviewers, enterprise integration and externally accepted utility are independently qualified.**
