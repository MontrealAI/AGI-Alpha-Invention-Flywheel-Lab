# ALPHA ignition: dependent independent integrity review (2026-11-16)

Source owner: PR #417, immutable observed source `76a4dbd4222743b56c34057567ea9e426490a6a3`. This reviewer branch is based on that commit; it is not a competing integration or a separate financial system. Original account and canonical source are untouched.

## Preregistered test-first protocol

All three failure hypotheses were reported in the exact-head PR #417 review, before this branch's code changes. Freeze this protocol before adding the tests or correction. The *same* tests must fail before correction and pass afterward, without changing the generated deterministic seed or loosening assertions.

1. **Freelist/storage:** Start from the fixed 6,000-row demonstration database (seed 41), allocate and drop a one-megabyte scratch BLOB to create free SQLite pages, require a newly built nonempty index to consume positive storage even if `page_count` does not rise. With `max_index_bytes=0`, the request must be DECLINED and must not retain a capability. The measured budget must include consumed freelist pages; do not just suppress the index size field. Independently check the index's physical allocated pages using `dbstat` when available.
2. **Already-applied index:** Create an exact deterministic index from the supported `apply_sql` on the same source before submitting a job. The engine must evaluate the existing equivalent index without a duplicate-index exception and, for the already optimized workload, DECLINE rather than mark FAILED. A conflicting same-name definition must never be silently accepted as equivalent.
3. **Event/state mismatch:** Complete one ordinary delivered job, then change only its mutable jobs-table status to QUEUED, leaving the event chain untouched. Both `audit()` and a restarted `run()` must refuse the inconsistent state before any extra ATTEMPT_STARTED or delivery event. Normal interrupted RUNNING recovery, VERIFIED delivery recovery and quiescent resumes must still pass.

No edits to the evaluator, frozen tests, original owner PR #417, financial accounts, signing keys or receipts. No real commerce, payments, paid calls or production deployment. Preserve all test-first failures and subsequent failures unchanged.

## Mandatory qualification

- Original 27 tests stay unchanged and pass on corrected source; three new adversarial tests pass (plus independent positive control for allocated bytes).
- Focused source-matched GitHub Actions run must show frozen RED before corrected GREEN. Host/repository checks not finished are PENDING, never called passed.
- Compare direct pre/post source and closed-world events; use independent read and existing audit paths. Record the exact source commit, workflow IDs, pass/fail results and remaining limits.
- This is a narrow ordinary-source safety review; it does not prove cryptographic history authenticity, actual customer payment, earned reinvestment, database-optimality, discovery improvement or US$3 billion T365 profit.

## Decision boundary

Reviewer may propose a dependent draft PR against owner branch `feature/alpha-economic-engine-ignition-20261116`; owner keeps integration, merge and release decisions. No protected native-account writes, queue resets, hidden retries, or retroactive qualification.
