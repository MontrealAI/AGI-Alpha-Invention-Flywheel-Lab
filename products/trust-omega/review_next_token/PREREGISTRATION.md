# TRUST Ω independent complete-reply replay review — frozen before tests

Date: 2026-11-16. Baseline owner PR #415 at `744d6e70614ae792d7138ea0777cbf2fd3bba139`. Parent branch: `research/trust-omega-proof-evidence-20261116`. This is a dependent **review**, not an alternate product/ledger, released claim or owner integration.

## Concrete problem and expected RED

The pinned official FlashProve checker `integrations/check_proof.py` at `9e2bdd8ff5bf9c62f18263d7dac189b0400b260c` accepts a client-specified last token via `--next-token` when `--reply` reaches the end of a request. The owner adapter exposes `--reply` and explicit EOS IDs but **does not offer or pass a client-controlled `--next-token`**. Thus it cannot check the complete four-token stored synthetic reply `--reply 61:4 --next-token 199` against `example.req`, and the owner CI bypasses the adapter, testing only upstream. A mock invocation regression must first fail against frozen baseline. This is a missing exact-scope interoperation case; it is **not** a proof forgery, an attack on FlashProve, or a real-model result.

## Frozen test/implementation contract

1. Add test first: call adapter's real CLI in a trusted synthetic isolated test environment or capture the child command at the verified boundary; require that `--next-token 199` is passed when explicitly client-specified, and reject an invalid negative or ≥2^32 token before invoking the checker. Preserve all original five tests unchanged.
2. Add a **source-bound full adapter smoke** to the existing GitHub workflow: check out the pinned official upstream commit, build the ordinary CPU verifier, use the official stored synthetic accepted proof, construct a local example response directory with `proof.bin` and `y.bin` (never change their contents), use the pinned official file hashes in a deliberately labeled **synthetic-only** trust anchor, invoke the actual adapter with `--reply 61:4 --next-token 199` and synthetic EOS list `[199]`. Check acceptance and replayability against exact source; then execute wrong next-token or wrong commitment with mandatory rejection. This is not independent model-identity certification; hashes from one CI checkout do not substitute for an external anchor.
3. Correct only argument plumbing and, if necessary, honest scope labeling. Do **not** turn weaker `within-limits` into exact, rewrite the original owner five tests, accept missing EOS for a complete reply, relax checks, import private keys or fund anything.
4. Stop at one frozen synthetic accepted proof and the declared negative mutation(s). Any failure remains immutable; repair only the diagnosed cause before new source-matched CI. Report costs including unknown CI/host bills.
5. Owner PR #415 retains all merge/release and customer integration decisions. No new credential/spending/outreach/real provider.

## Strong alternatives and no-deploy

Compare (A) upstream checker directly with the documented argument contract (strong engineering control), (B) this adapter wrapping it with a trustworthy independent anchor (candidate), (C) independently recomputing outputs / hardware attestation and other modern proof systems (external complete alternatives), and (D) no deployment. The candidate must match (A) on the same stored proof, but no superiority or buyer benefit is inferred; D remains default absent proof and demand. Future 1,000 genuinely fresh customer/prover challenges remain separate, not satisfied by this fixture.

## Acceptance matrix

- Protocol frozen before implementation/tests: check commit.
- Same pinned original tests and **new prospective RED**: exact hosted run, no retroactive pass.
- Full adapter synthetic end-token pass + wrong-token rejection: required exact-head CI.
- Other repository workflows: separately report failures.
- Real model, real buyer, accepted price, native account migration, complete-cost profit, US$3B T365: unqualified/unachieved.
