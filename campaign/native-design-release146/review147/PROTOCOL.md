# Review147 — fail-closed released native-design146 provenance and public upload correction

**Source owner:** Release146 PR #352 retains sole integration ownership. This stacked review branch is based on immutable candidate `b3e924dd100d4165b1faff6d36e3232d7db0ee7f` and must be reviewed into that branch before its normal main merge; never merge this review independently to main. Native-finance original account, keys, queues, liabilities, P0 and all other branches are out of scope.

**Preimplementation registration:** frozen before source/test changes. Preserve five zero-job failed workflow-registration attempts and three subsequent exact-head privacy failures unchanged. Repair the documented cause rather than rerunning to select successful seeds. Use the original fixed 341014/341015 synthetic demo and unchanged 21 native tests.

**Target defects:**
1. Existing privacy regression correctly rejects 10 uploads; introduce *one explicitly audited* new key-free release-proof upload, guarded by success of the actual downloaded operation, native tests/demo/verify and receipt sealing. Require its exact three file paths, no private paths/globs or an unconditional upload. Keep all existing nine upload guards and acceptance requirements intact.
2. The standalone released-native seal presently labels an actual public download and test/audit completion without checking the actual `RELEASE_DOWNLOAD.json`. Bind its exact source/tag/asset hashes and require the genuine schema and boolean, reject malformed, missing, tampered, forked or synthetic receipts. Record SHA-256 of the verified download receipt; label separate test/audit results as workflow-step observations rather than independent verifications.
3. Add focused adversarial tests for positive valid receipts and all representative negative receipt/privacy mutations. Preserve source-account invariants; do not weaken the archive count/size guard, source guard, production release identity, independent financial audit, buyer assumptions or native economic gates.

**Acceptance:** Focused tests including existing privacy protections; exact stacked-head CI; PR #352 source owner reviews and composes before normal protected merge and subsequently publishes release. A stacked PR pass alone cannot qualify an actual public release. No simulated profit or new customer demand is inferred from the correction. No new spending, APIs, credentials, outreach or deployment.

**Stop / rollback:** Fail closed on any test or owner-head conflict. Maintain all failed-run evidence. No force push or key disclosure.