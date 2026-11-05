# Governance-change086: prospective review-integrity adversarial addendum

Frozen before repair. Source parent: `da92c36ebcebff46cee49ee8549dfb528e5d7fcf`; issue: #259; candidate PR: #260.

The original eight exposed synthetic cases C0–C7 and their results remain unchanged. The 5 November 2026 independent code review found two P2 problems: (1) an altered non-tail review entry can pass the tail-only compare-and-append check; (2) tuple-keyed assessment maps cannot be hashed through the existing generic JSON helper, so C6 incorrectly uses the registration hash instead of binding the report.

Register these independent **prospective** engineering cases; no cherry-picking or post-outcome amendments:

* **C8:** a revised report's canonical digest binds all result and metadata fields; a trusted-role stub may reference that digest, not merely the registration hash. A result alteration must change the digest.
* **C9:** a valid two-review sequence extends with correct sequence/predecessor linkage. Changing an earlier decision while leaving its successor unmodified must fail before append.
* **C10:** wrong prior digest, skipped sequence and duplicate decision must fail; legitimate stale-tail expected_head still fails.
* **C11:** report hashes must be deterministic across assessment dictionary insertion order and distinct across modified results, affected set and registry data.

Stop at these four authored adversarial tests and the unchanged C0–C7 suite. No private/government source ingestion, outside payments, actual approval or bidder representation; role claims remain a synthetic demonstration, **not authentication**. No observed buyer or compliance validation is inferred. If checks fail, retain original failure and repair prospectively. Reverify exact new commit in GitHub-hosted CI and independently review before merge consideration.
