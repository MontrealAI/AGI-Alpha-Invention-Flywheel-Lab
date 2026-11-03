# Isolated Enterprise078 scale composition

This independent review composes the source-runtime separation in PR174 at
`2c112fb0b82a1188e84548694157938cbce97f1d` with the unchanged PR176 scale tree
`92a59b2f61c9758900e83d0ca1eac80ddb2ab82c` and PR177's public-export guard at
`c3a4b5ec1c2328905d758c848b2215917bf5b3e6`. It does not modify any owner branch,
open an original account, add native catalog authority, or qualify commerce.

## Failure and prospective repair

PR177's portfolio and frontier qualification jobs genuinely failed with
`RECOVERY_ORIGINAL_SOURCE_REQUIRED`. The inherited scale branch used historical
Enterprise078 extensions in the shared ledger and finance modules. That changed
the original portfolio recovery source identity. Those failures remain failures;
the recovery guard and its fixed expected hash are not changed.

The pinned PR174 base already restores current native modules and retains the
historical versions in `enterprise078/frozen_native/`. The new wrapper composes
its existing 306-file materializer with all 11 exact scale files, then promotes
the complete source directory atomically outside the checkout. It checks the
unchanged scientific digest `c13a7411587736a18f1adc6422a15e026b6c934524eba745b344da82befff570`
and scale digest `50748c34a6ee2b528b78745eb947e191798906b91f1f9abbe26647622cae9dbc`,
plus the three original scale support-file hashes.

Current native finance and recovery checks run in the checkout. Historical
science/scale tests and operation run in separate processes from the staged
source, with explicit PYTHONPATH and disabled user-site imports. Tests, public
source packaging and financial-world runs each get fresh independent stages.
The unchanged runner exports its active 304-file scientific closure plus 11
scale files; the two unused original scientific test/scale files remain in the
317-file materialized runtime but are not added to its frozen export algorithm.

The sanitizer stays in the checkout so its receipt identifies the checked-out
composition commit. Successful exports contain only the previously allowlisted
files; failed financial operations retain only a redacted receipt and restore
their original nonzero process exit status. Neither the six original financial
review failures nor the separate corrected read-only audits are reclassified.

## Executed checks and acceptance boundary

Local source-bound checks passed: 8 composition controls, 3 existing runtime
controls, 14 unchanged export controls, and the original 18 scale plus 14 science
tests. Every shell step parsed with `bash -n`; the workflow parsed as YAML.
The composition controls check all 306 historical hashes, all 11 scale bytes,
current-native preservation, module import locations and original export closure,
changed source, stale destination, symlink/traversal refusal and partial staging.

Local tests are not hosted qualification. Require exact new-head portfolio,
frontier and source/scale CI results and actual sanitized artifact inspection
before adoption. A financial world that fails its frozen reviewer must still fail.
No normal merge, formal approval, release, deployment, spending, paid API,
outreach, private-key upload or original-account continuation is performed.

Lesson: keep each historical source identity intact in its own executable
runtime; restore current shared dependencies rather than weakening old recovery
pins or silently executing a mixed runtime.
