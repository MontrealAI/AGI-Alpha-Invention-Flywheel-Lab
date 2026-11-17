# FRONTIER Ω IGNITION — portable arithmetic review, registered 17 November 2026

## Ownership and purpose

Original demonstration integration owner: [PR #436](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/436), exact inspected source `1fff39458c222c44c223ddbad221fafc102a6acc` on `feature/frontier-omega-ignition-experience-20261117`. This is a *dependent draft review*, not a second demo, new deployment, real customer transaction, autonomous model, treasury, public-release qualification or financial-account migration. Do not modify or merge the original owner branch directly. No new paid APIs, external data, customer contact, credentials or spending.

This review is a **specific dependency of the external-facing FRONTIER Ω research demonstration**: the visitor's generated, downloadable, genuinely executable decision instrument must reproduce its own declared arithmetic at the displayed scenario values and detect dollar-level tampering consistently over the disclosed CAD input range. The original receipt remains a hypothetical user-authored scenario, not a proof of buyer surplus or a cryptographic signature.

## Hypotheses registered before code changes

1. **Fractional probability portable replay.** The generated instrument exposes `step="any"` for `probability`, yet its reference replay rounds `100 * probability` to an integer success count. A permissible `0.555` probability is computed by the formula at 55.5%, but reference enumeration treats it as 56% and reports `arithmetic_passed=false` for a mathematically correct instrument. Correct by a genuinely independently enumerated exact 100-bucket *fractional boundary* method or other independently correct method; do not silently quantize a user's authorized fractional input. Preserve usual whole-percent acceptance.
2. **Monetary tamper false negative at documented scale.** The main page's reference uses `nearly(a,b)` relative tolerance `1e-6 * max(1,abs(a),abs(b))`. For an allowed ~CAD 1,000,000,000 magnitude, an injected CAD $1 drift becomes smaller than that tolerance, so the original `allChecks` adversarial test can falsely declare a changed result undetected. Require a suitably small **absolute monetary tolerance** across the disclosed range without causing false failures from ordinary floating-point summation. Preserve the original 100-case test and large-value honest control.
3. **Original equivalence controls.** Existing 6 Node tests, honest default whole-percent scenario, both alternatives and no-investment cases must remain unchanged and pass. No changed prices, profits, customer expectations, source events or test acceptance after observing outcomes.

## Exact negative and correction protocol

First commit *tests only* on top of this frozen document and the untouched PR #436 source. Open a draft dependent PR against the original owner branch to trigger the existing standard-runner `AGI ALPHA website` GitHub workflow. The new two adversarial tests MUST fail before the implementation changes, while original tests pass. Preserve exact commit, run ID, logs and failures permanently; do not retry until favorable or change test acceptance. Then change only source math implementations in `docs/research/frontier-omega.html` and rerun the **unchanged** tests at an exact corrected head.

Retain stricter-than-dollar-level accuracy, the original independently recomputed replay, explicit no-commerce disclosures and output scope. Run source-matched website and repository Actions; normal original-owner review/merge, Pages publication and independent downloaded actual-public-byte qualification remain separate. Historical failing and interrupted runs never become passes.

## Decision and acceptance

If test-first red reproduces and corrected current-head green is exact, label **engineering review achieved**, not new economic frontier, real accepted customer demand, native earnings, deployment or US$3B T365 profit. If any source-matched gate fails, hold, inspect and correct on unchanged registered cases. No account keys, liabilities, native queues or archived failure results change.
