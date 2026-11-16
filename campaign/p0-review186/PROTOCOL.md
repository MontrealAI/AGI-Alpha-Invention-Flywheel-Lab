# P0-186 — Independent constructive historical-CAS cache verification proposal

**Registration:** 2026-11-16 UTC. Freeze this protocol in a separate commit **before any implementation**. The active financial integration owner remains PR #40 at `ced6c1cb004887dcdafaea59a2976020be649f8e`. This review branch derives from unchanged P0-184/185 adversarial tests at `39f9b9cf9ed11291aa0628b01861a89078594c13`; it must NOT merge wholesale into main or override the financial owner.

## Fixed hypothesis and required behavior
The original `verify_historical` successful-audit cache is keyed only by ticket/manifest/root/source inventory. An accepted cached receipt must **never** bypass a missing or corrupted recursively referenced historical CAS object. A safe prospective review implementation may retain reuse for an *unchanged fully verified* evidence closure, but must re-resolve every required nested predecessor v2 ticket in the active caller-selected evidence store **on every cache hit**. If any nested evidence is missing/tampered or the proof cannot be checked within a fixed bound, the cached receipt is ineligible: execute the existing exact-source independent historical verifier or reject fail-closed. Never silently accept from a different store or the same store after deletion.

## Tests and stopping rule
1. Keep both original P0-184/185 tests byte-for-byte unchanged: original first clean scope success then *one* identical reuse, cross-directory missing predecessor refusal, and same-directory reopen after nested deletion refusal. Both currently FAILED on owner source. Preserve those historical reds.
2. Add a new preregistered third-generation nested-v2 test in a separately named file: intact evidence permits one cached replay; deletion of a grandparent-only immutable blob forces an independent re-audit and refusal. No alternative samples or fixture replacement after exposure.
3. Add a non-CAS/v1 unchanged-context control if feasible to protect historical behavior.
4. Run the exact branch's deterministic tests in normal hosted GitHub Actions, including the relevant original unchanged tests; report terminal exit codes and all failures. One fixed finite round; if a test fails, retain RED and diagnose without weakening frozen acceptance.
5. Do not claim authenticated HMAC/account custody, original signed account replay, race-free intra-scope filesystem mutation, source-owner approval, release or commerce from mocked subprocess fixtures.

## Implementation boundary
One isolated *review candidate* `connected_enterprise/upgrades.py` change plus additive tests/workflow/documentation on this review branch. No changes to PR40, PR35, current main, keys, accounts, journals, queues, liabilities, writer lease, archive limits or historical failures. Keep the original auditor and source-inventory checks. Only the PR40 owner can assess semantic integration under a single authenticated native writer and then independently prove nonempty-queue legacy continuity. No paid APIs, new credentials, spending, outreach or real transactions.
