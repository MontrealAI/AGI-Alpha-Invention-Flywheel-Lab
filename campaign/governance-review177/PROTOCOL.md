# Governance177 — scoped signer-authorization counterexamples (prospective freeze)

Frozen on 2026-11-18 against governance176 candidate `31bce8454faacdc4084602c09220f1b1322856cd` **before adding tests or changing source**. Dependent research review only; no writes to PR #459 owner head, Impact140, canonical native accounts, historical evidence, releases or credential stores. No actual private data, signing keys or real reviewer identities. The prerequisite source's original 13 tests and CI outcomes remain unchanged.

## Safety assertions to disprove

The independent governance review receipt must never attribute an action to a reviewer outside the *signed action's claimed issuance authorization period*. Current source checks the trusted reviewer at evaluation time and the statement between issuance/expiry and evaluation, but appears not to require `reviewer.valid_from_utc <= statement.issued_at_utc`. A properly signed statement claiming a time before externally anchored authority began must fail; this is only claimed-time consistency, **not** a trusted signing timestamp, issuance proof, historical identity, or an attestable real-world event.

An independently anchored reviewer trust registry must not map one Ed25519 verification key to two distinct attributed reviewer identities. If it does, signatures cannot distinguish those identities; even a valid cryptographic signature cannot substantiate which individual signed. A duplicate key must reject regardless of disjoint role scopes and reviewer IDs. Public PEM serialization differences must not be accepted as evidence of distinct key identity if they represent the same encoded Ed25519 key.

## Frozen exact tests (no sample choice)

- R177-A: Construct the unchanged valid synthetic governance176 fixture and change the signed statement's `issued_at_utc` to `2026-10-31T14:00:00Z`, before the pinned reviewer's `2026-11-01T00:00:00Z` role start. Re-sign using the same fixture ephemeral key. Evaluate at the original `2026-11-18T15:00:00Z`. This must raise an authorization-period error, rather than return a provenance receipt.
- R177-B: Construct the unchanged valid fixture and replace reviewer's r2 anchored public key with r1's same key while leaving their distinct IDs and valid reviewer roles unchanged. Recompute the expected *externally assumed* trust-record digest for the registered test. This must reject as a nonunique public key, rather than attribute an ambiguous signer. The adversary does not control the actual external trust anchor in deployment: this checks the trust administrator's malformed-but-anchored input, not malicious digest substitution.
- R177-C: Preserve the original positive T01 and all 13 original tests unchanged and verify no compliance approval, financial action, persistent private key or account modification. Validate under the existing source-matched standard-runner workflow; report any genuinely failed workflow as failed.
- R177-D: If the initial unchanged source fails R177-A/B as expected, preserve the red exact-head artifact/trace and then repair *only* scoped review authorization handling on this dependent branch. Require both unchanged tests and new tests to pass prospectively, with fresh exact-head qualification. Never convert historical failures to passes.

## Nonclaims and integration

This cannot assert when a signature was really made, an actual person's identity, nonrepudiation, cross-run anti-replay, tamper-proof external trust, government compliance or buyer advantage. Primary competent alternatives (ordinary signed files with access controls and established GRC platforms) and no-bid/no-deploy remain eligible. The dependent branch is not merged into main or the PR459 owner branch automatically. No new spending, outreach, transaction, production deployment or credentials.
