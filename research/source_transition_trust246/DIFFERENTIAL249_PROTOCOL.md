# P0-249 — frozen source-matched v2-CAS differential qualification

Date: 2026-11-23 UTC. **Independent research-only continuation of P0-248.**
Parent PR #553 exact head before registration: `ce343ed130a5c6bd05fcc33c3c5e6a345fa918e3`.
Current main inspected: `f0987aa48d5c9136b28540f54eabf5367e63bbe6`.
Historical financial-owner PR #40 commit: `ced6c1cb004887dcdafaea59a2976020be649f8e`.
Pinned owner codec file `connected_enterprise/transition_evidence.py` Git blob:
`2397091ef8e1960ad13950693d5b3cd04e2ff7c5`.

## Source-matched decisive question
P0-248's pure data codec passes synthetic independent tests. Does its v2-CAS
wire body and blob map actually match the **immutable historical owner's**
`externalize` output, and does the owner's own `ticket_body` reconstruct the
same v1 record under explicit key-free evidence scope? If not, it must be
rejected as wire-compatible. This tests only data interoperability.

## Frozen qualification protocol, before new code
1. Retrieve precisely the public historical codec file from the pinned owner
   commit using `raw.githubusercontent.com` (public HTTP, no token). Before
   loading, verify the **Git blob SHA-1 including the Git blob header** against
   the pinned object ID above. A mismatch or unavailable source **fails** the
   run, not a skip or a permissive fallback. Do not load target-controlled code.
2. Execute that pinned source **only in a separate synthetic, key-free CI test
   process** with a minimal sanitized environment, no Git credential, private
   data, signing authority, original account, ledger, or real file operations.
   This is not the historical signer's security context.
3. Compare both codecs' complete canonical v2 bodies and content-addressed
   blobs byte-for-byte on fixed source-independent synthetic v1 bodies:
   (a) two evidence fields and (b) three fields with a nonempty settlement
   queue, outstanding claim and permanent tail, (c) Unicode and nested values,
   and (d) an operating JSON blob just above 16,000,000 bytes but below the
   historical 64,000,000-byte bound. In each case check that the pinned owner
   `ticket_body(key=None)` round-trips the proposed blobs to the exact
   original v1 canonical body.
4. Register negative tests: owner v2 rejects counter outside 1..4; P0-248
   pre-sign reference must also reject it rather than imply acceptance.
   Owner-scoped resolution must reject omitted, swapped and corrupted evidence
   while the reference remains fail-closed. Noncanonical or duplicate JSON is
   not permitted by the stricter pre-sign reference even if legacy parsing
   behavior differs; do not rewrite historical owner behavior to make a pass.
5. Preserve any failing source, return code and test record. Never cherry-pick
   cases, hide a mismatch, loosen owner guards, use a second account, read
   secrets, or move any evaluation/authority function.

## Strict verdict boundaries
A pass establishes **key-free exact pinned-code wire interoperability only**.
It does not establish that PR #40's key-bearing signer is repaired (its
target-code `exec` remains a separate security blocker), that actual old
HMAC history/nonempty operating queues or financial liabilities migrated,
safe staging or crash/race recovery, source-version downgrade/fork rejection,
actual owner/writer custody, an approved merge, a released runtime, downloaded
release operation, genuine buyers, commercial earnings or the US$3B milestone.
The active original financial task's checkpoint and exclusive writer boundary
remain unknown until independently obtained. This branch must not touch the
original signer/account or be merged wholesale into main.
