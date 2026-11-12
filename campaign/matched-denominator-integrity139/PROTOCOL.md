# Matched denominator integrity 139 — preregistered observer correction

**Frozen source:** released/main `3b55e0eec99cdc8a57af7e196fd6962bce6d69ee` after Integrity138, `connected_enterprise/scale.py::compare`. **Owner:** independent analysis-only workstream; financial PR #40 and its signer/ledger/queues remain untouched. **Status:** frozen before code changes. The existing public-release artifact and its failed adversarial examples are immutable.

## Decisive defect observed on the exact released bytes

`compare` silently drops any key having only the selected baseline or candidate arm; it returns `pairs=[]` for a seed or case mismatch, or a favorable subset when a second adversarial key is unmatched. One can thus lose an adverse world without a nonzero comparison failure. Exact observed released-source examples: mismatched seeds (one baseline and one candidate) -> zero pairs/no rejection; mismatched case labels -> zero pairs/no rejection; one valid pair plus two unmatched extra results -> one pair/no rejection. The prior Integrity138 tests reject exogenous mismatches only **after** a key is successfully paired.

## Prospective acceptance

1. With identical baseline/candidate keys and exogenous inputs, original per-pair deltas, identity and source metadata stay unchanged.
2. A baseline and candidate with different seed, case or customer-pool key must fail closed, never report an empty matched result as eligible.
3. One legitimate matched pair *plus* unmatched candidate or baseline observations must fail closed. This prevents selective omission of disclosed losing worlds.
4. Declared named policy treatments may differ while exogenous/source conditions remain equal; arbitrary third-party arms are irrelevant to the selected pair but cannot conceal an unmatched requested arm.
5. Empty input or absence of either required arm must fail closed. Duplicate requested-arm identity remains rejected. Preserve original 138 cost/market/source mismatch failures.
6. The observer must explicitly report its matched denominator and counts (both selected arms) so a caller can check against the **separately registered protocol**. It cannot infer unsubmitted registered tasks. Upstream registered task-count audit remains mandatory.
7. Existing tests `tests.test_connected_matched_market138` and `tests.test_connected_scale`, full source-bound connected CI, protected merge, release publication, separately downloaded release, resume and audit are required before declaring this change qualified.

**Permitted implementation:** only `connected_enterprise/scale.py::compare` and a new adversarial regression test file. No native account/financial engine changes; no altered old tests, accounting, positive-demand assumptions, seeds, archive guard, private authority or evaluator. Preserve the existing released result and the demonstrated failure as failure. This is a measurement guard, not a new customer, revenue, profitable invention, true game equilibrium, native migration or US$3B progress.

**Decision rule:** reject a new claim when an eligible pair is missing; otherwise preserve all original audited-source financial protections and explicit `scope` limitations. If CI fails, investigate code/test assumptions without changing this frozen protocol or cherry-picking observations.