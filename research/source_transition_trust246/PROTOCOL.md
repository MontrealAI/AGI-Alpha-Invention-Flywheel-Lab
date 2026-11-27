# P0-246 — pre-registered signer-boundary negative witness

**Frozen before implementation: 23 November 2026 UTC.** This is a read-only independent security review of the historical finance-owner draft, **not** a source migration, custody handoff, or commercial flagship.

## Fixed subject
- Current protected-runtime integration baseline: main commit `f0987aa48d5c9136b28540f54eabf5367e63bbe6`.
- Historical owner-only PR #40 head: `ced6c1cb004887dcdafaea59a2976020be649f8e`; path `connected_enterprise/upgrades.py`, Git blob `9866d004c412fc05c9f6292cf898307f177359df`.
- Owner's source-only `authorize_upgrade` deliberately invokes a historical `JournalAccount` signer in a subprocess. The question is whether bytes obtained from the *new target* tree are interpreted as Python inside that already authenticated historical signing context.

## Fixed tests; not authorization or exploitation
1. Fetch the **exact pinned public Git blob** as untrusted text over HTTPS and verify its Git object SHA-1. Abort on fetch failure or changed bytes; do not execute any downloaded owner-source code.
2. Parse the inspected owner function and identify the target-root source acquisition, subprocess transport, literal injected `exec` and active `JournalAccount` context. Report a **negative trust-boundary witness** if all hold.
3. Run only a locally authored, zero-secret *synthetic interpreter* proof that interpreted Python can inspect its immediate caller's synthetic account-like local state via a stack frame. Read only the constant marker `SYNTHETIC_NO_KEY`, never actual signing keys or user accounts.
4. Keep a non-injected synthetic control. No real migration, account/queue, HMAC, paid service, external outreach, release or deployment.
5. Output evidence fields separately: exact source identity, proven code structure, synthetic Python mechanism, *unproven actual compromise*, *unverified real owner custody*, and owner-safe remediation boundary.

## Acceptance and disposition
- The test suite passes only as a **reproduction of a negative security witness**, not as a safe-release pass. A changed pinned blob is a hard fail, never reinterpretation as fixed.
- No claim of observed malicious target, leaked secret, exploited account, or upstream repair. Owner must eliminate evaluation of target-supplied executable bytes inside the key-bearing historical signer. Choose a manifest-selected source identity, keep old verifier/ledger/queues/HMAC and single-writer locks, separate any untrusted codec transformation from signing authority, and independently qualify resumed native receipts.
- Full protected release, actual download and external commercial value are **not** qualified by this work. Historical failed suites remain failed.
