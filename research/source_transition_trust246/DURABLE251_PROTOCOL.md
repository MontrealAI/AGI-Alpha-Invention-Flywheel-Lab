# P0-251 — owner-selected durable evidence transport, frozen protocol

Frozen before implementation on 23 November 2026, after the independent P0-250 source-matched synthetic HMAC result at `42b2df0e3e8f8be96e413c089935a897ffc24ee9`.

## Flagship dependency and scope

The nonempty operating-queue migration still lacks a safe handoff from the real native-capital owner. One blocker is the historical PR #40 signer executing successor-controlled `codec_source` inside the old account's key-bearing process. P0-250 demonstrates no-target-code synthetic signing; it leaves all evidence only in memory. This increment tests an owner-selected *durable evidence transport* that does not invoke successor code, issue a second account or access historical credentials. It is supporting engineering, **not** finance-owner integration, actual source migration, commerce or deployment.

## Pre-registered finite acceptance (one run, no reseeding)

Use only freshly authored synthetic nonempty claims/permanent tails/settlement queues and ephemeral in-memory random HMAC keys. No private account, target-root import, network API, paid service or owner source modification.

1. Produce the existing P0-250 owner-locked synthetic ticket and in-memory v2-CAS blobs. A trusted storage helper must persist precisely the signed ticket and all addressed blobs into a private, owner-selected local directory, with bounded sizes, no links, no external paths and no target code.
2. Stage and fsync all blobs/ticket before one atomic publication rename; fsync the containing directory. Interruption immediately before publication must leave **no visible committed bundle**, no changed original values and no falsely successful receipt. An unrelated staging orphan is a failure artifact, not an authorized account reset.
3. A separate read must verify the exact published file set, blob hashes/lengths, original-owner-record equality and HMAC before accepting; exact repeat publication is idempotent. Corrupt, missing, extra and symlink-swapped files must fail closed.
4. Two synthetic processes racing to publish the exact same signed bundle must not corrupt or produce conflicting committed bytes. This is *not* proof of the original native account's exclusive writer lease.
5. Altered owner lock, signature or original nonempty liabilities must be rejected; no downgrade, alternate HMAC, unsigned fallback or direct balance edit.
6. Run all tests in an environment scrubbed of credentials on normal free GitHub Actions, exact PR head, fixed job-start marker and bounded workload. Retain a compact nonsecret digest receipt, no test keys or payload archives. Keep any failures as failed; repair separately before retry.

## Stop/verdict and limits

Stop after this finite engineering acceptance. PASS means only synthetic owner-selected file transport with crash-before-commit, idempotency and tamper checks. FAIL preserves its trace and does not qualify the stage. Neither outcome can repair PR #40, authenticate inaccessible old account state, validate real queue migration, native writer exclusivity or write-ahead account recovery, or qualify release/commercial results. The original task checkpoint and custody remain unknown until an actual source-authority handoff is received. Never merge this research branch wholesale into main.
