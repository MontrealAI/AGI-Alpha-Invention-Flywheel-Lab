# TRUST Ω independent verification-key identity review — preregistered 2026-11-16

Baseline: dependent reviewer PR #416 exact head `50f0a4c58721c4e780c74d8efc7d244dd615a71e` (16/16 exact-head GitHub workflows PASS). Product owner: PR #415, not this reviewer. The earlier reviewer synthetic accepted/negative examples remain immutable.

## Source-observed binding gap

The current anchor pins the upstream checker, compiled verifier, parameter, scales, layout, and model commitment ID but leaves the **public verification-key directory** uncommitted, even though the adapter passes `--public-key-dir` to the trusted checker. A provider-supplied mutable directory therefore can change verification inputs without changing any current `trusted_sha256` value or any listed `evidence_sha256` field. This is a trust-boundary gap, **not** an independently demonstrated cryptographic forgery.

## Frozen, finite test-first experiment

1. Add a test using a synthetic local key directory with at least two files, including a nested path. The exact old verifier accepts an ordinary mocked upstream success before and after one verification-key byte is changed; this documents the missing pin, not valid forged cryptography. New test MUST demand rejection of the changed key directory without invoking upstream, plus rejection of missing/extra/renamed keys and symlink tricks.
2. Add a `trust-omega-anchor-v2` schema that requires `public_key_tree` in externally pinned SHA256 values. Define a canonical, deterministic complete sorted relative-path+content-hash tree commitment over ordinary files, reject symlinks, non-files, empty dirs, unsafe names and tampering; hash actual bytes rather than owner-supplied manifest claims. The output audit record must bind the observed public-key-tree hash.
3. Retain v1 parser compatibility in `read_anchor` for its original five unchanged unit tests, but **fail closed in `verify` on v1**: never issue new positive receipts without the mandatory key pin. Upgrade only the controlled synthetic smoke anchor to v2. The original five tests and two prior reviewer tests remain unchanged.
4. Observe one test-first hosted workflow failure (registered RED) before modifying implementation; preserve it. After repair, require exact-head full seven prior tests plus new negative cases, and real upstream accepted/rejected synthetic replay through v2. Do not change known upstream proof bytes, policy strength, return-code checks, or prior test expectations.
5. Stop after this fixed engineering qualification. No customer/model provenance certification, live prover, performance superiority, real commerce, annual profit or new Blue Sky achievement is claimed. Complete costs/hosting billed cost remain unknown. Other existing sources/ledger/keys/queues are out of scope.

## Complete alternatives and commercial decision

(A) Official upstream checker with separately secured verification keys is the strong correct engineering incumbent. (B) TRUST Ω's complete independent key pin is the prospective adapter convenience, not evidence of proof-system novelty or economic superiority. (C) Independently recomputed inference and TEE-attested providers are alternative controls with different trust models. (D) No deploy remains the default if adequate real proof-generation and independent buyer benefit cannot be established. No fabricated partner/buyer or priced contract.

## Acceptance matrix to fill prospectively

- Previous reviewer exact head 50f0a4: qualified 16/16; not retroactively revised.
- New protocol: FROZEN at this commit before tests/implementation.
- Test-first RED: PENDING.
- Prospective pin correctness, strict refusal, and real synthetic replay: PENDING.
- All source-matched CI: PENDING.
- Owner integration, protected release, clean downloaded public asset audit: NOT ATTEMPTED, separately owned.
- Actual buyer, model provenance, original P0 account migration, US$3B T365: UNQUALIFIED / UNACHIEVED.
