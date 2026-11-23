# P0-253 — owner-pinned historical signer source substitution protocol

Frozen 23 November 2026. Research-only selectable patch against historical PR #40 commit `ced6c1cb004887dcdafaea59a2976020be649f8e`, exact Git blob `9866d004c412fc05c9f6292cf898307f177359df` (`connected_enterprise/upgrades.py`). Historical trusted codec: Git blob `2397091ef8e1960ad13950693d5b3cd04e2ff7c5` (`connected_enterprise/transition_evidence.py`). Do not alter either historical commit, the active owner branch, account/keys/queues, or protected main. This is an *owner-reviewed proposed patch*, not a financial integration.

## Concrete change

Remove the `codec_source` field supplied from `target_root` to the historical key-bearing signer and remove `exec(p['codec_source'], codec)`. In that historical signer subprocess, use *only* the already imported, historical-root `connected_enterprise.transition_evidence` module's `externalize`, `preflight_storage` and `persist_evidence` functions. Keep the original code's HMAC, Account/JournalAccount, signed state guards, limits, source inventory checks, operating queue handling, preflight ordering, timeouts, authorization semantics and error paths unchanged. No target-root callback, plugin or Python execution is allowed in the signer. Reject source inputs other than the exact pinned old-owner Git blob; never apply fuzzily.

## Frozen finite independent regression gates

1. Pinned historical upgrades.py and transition_evidence.py Git blob identities match exactly before running owner source in a key-free isolated fixture.
2. The source-matched patch replaces exactly the known insecure payload and three codec call sites, and is reversible with no other edits.
3. The patched source parses and contains no `codec_source`, target-root `transition_evidence.py` read, or `exec(p['codec_source'],codec)`.
4. The replacement imports all three fixed historical codec functions inside the signer; no permissions, native financial history or resource guards are removed.
5. Applying the patch twice, or applying it to a mismatched historical source, rejects rather than silently modifying another owner version.
6. Two-field v2-CAS representation retains exact historical source-matched wire/hash parity on synthetic input.
7. Three-field v2-CAS with nonempty queued settlement and permanent claims retains exact historical source-matched wire/hash parity on synthetic input.
8. Historical trusted preflight/storage functions are callable and the proposal contains no credential access or account writes in this research test.
9. The test does not require reading or executing any successor codec and cannot claim authenticated original-account migration.

Run a separate exact-head no-credential GitHub Actions gate with explicit job-start marker and a compact nonsecret receipt. Preserve all failed tests and earlier workflow failures. P0 exit still requires the actual owner's verified checkpoint, source composition with current main, approved owner-side patch application, signed nonempty native operating migration, writer/race and crash testing through the public canonical CLI, normal protected release, clean independently downloaded release run and audit. No release, real commerce, external outreach, spending or credential creation in this research phase.
