# P0-252 — owner-head compare-and-set and fork resistance (frozen protocol)

**Preregistration:** 23 November 2026. Freeze this document in a separate public commit **before writing P0-252 execution code or evaluating its cases**. Previous P0-251 exact head: `f61befd2f068003929acd4a676ff05738b871a23`. The original historical finance signer and financial owner are unchanged.

## Why this matters

P0-251 durably publishes a correct synthetic signed v2-CAS *bundle*. Its two-process test races **the same signed transition** and therefore does not test mutually inconsistent successors to the *same historical state*. Storage-level idempotence alone cannot prevent signed-account forks. This increment tests an independent, research-only, owner-selected head/lease mechanism allowing **at most one synthetic committed successor from one predecessor**. It is a supporting prerequisite for safe legacy nonempty-queue migration, not a new operating account or an actual owner handoff.

## Frozen finite acceptance (9 cases; no reseeding or test relaxation)

Use the P0-250 synthetic signer and P0-251 durable bundle publisher unchanged; no historical native account, live keys, private data, target-code execution, real commerce, release or production action. Each test uses freshly generated in-memory ephemeral 32-byte synthetic keys and a private temporary POSIX directory. Account identities are synthetic test strings, **not** alternative financial ledgers. All object formats and budgets remain bounded.

1. **First owner-selected transition:** under an owner-owned exclusive advisory lease, verify owner lock and independently owner-reconstructed signed bundle, then write an HMAC-authenticated, canonical, private, bounded **head** record with ticket digest, source, counter, day, account identity and predecessor `null`. Verify saved bundle and head in a separate read, with the pinned old owner v2-CAS resolver where relevant.
2. **Two different targets race from one predecessor:** two independent processes with the same synthetic account ID / old checkpoint but different to-source descriptors must yield exactly one winning head. The losing fork must fail closed *before* producing another candidate bundle. The original records and liabilities remain unchanged.
3. **Identical retransmission:** reattempting the exact winning source/version and owner record against its registered predecessor is idempotent, with identical head and bundle bytes and no new committed transition.
4. **Valid chained continuation:** a new explicitly owner-locked synthetic record can commit only when its declared predecessor equals the actual signed head, its `from_source` equals the prior `to_source`, its counter increments by exactly one and its day does not go backward. No synthetic balance is reused as real funding.
5. **Stale, fork, downgrade and cross-account rejection:** old head claims, counter gaps/replay, changing to/from source, reverse day, wrong identity or unsigned arbitrary head all reject. Do not create a second authority, reset history or discard queues.
6. **Crash after evidence publication but before head:** a visible bundle without a valid head is **not committed**. An exact retry may publish/commit its same bytes; a contrary fork may not treat the orphan as signed account authority.
7. **Crash after committed head before acknowledgement:** the head remains verifiable and exact retry resolves idempotently, not as an extra transition.
8. **Tamper/links/keys:** malformed, duplicate-key, altered, symlinked or hardlinked HEAD, wrong HMAC key and corrupted committed bundle fail closed. All files must be owner-only regular files under an existing private non-symlinked root.
9. **Liability conservation:** alteration of original cash, outstanding claims, permanent tail or nonempty settlement queue between owner lock and signing fails even in the presence of a valid head. Neither the head nor bundle is a cash ledger.

Run the fixed nine cases once on the exact source head in a no-credentials, ordinary public-repository GitHub Actions runner, including the mandatory job-start marker. If any fails, retain the failure; correct its cause prospectively and qualify a *new* head, not rewrite the original case. Publish a small nonsecret receipt with exact source and tested file hashes and the honest status. No test key or synthetic state bundle in public artifacts.

## Strict boundary and stopping rule

Stop after the nine registered checks and report **PASS only for synthetic cooperative lease/head fork exclusion** if all pass. It does **not** repair PR #40's old key-bearing signer, acquire the actual native-capital task's custody, implement the original JournalAccount writer lock, authenticate the real nonempty queue, validate operating/financial claim ordering, qualify source composition, merge, release or external commerce. An uncooperative writer not honoring this new lease is **not** excluded. Any missing actual owner checkpoint stays explicitly BLOCKED. Historical failures and previous success receipts remain unchanged. No wholesale merge of this research PR into main.
