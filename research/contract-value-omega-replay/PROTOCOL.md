# CONTRACT VALUE Ω · Independent source-to-finance replay (registered before implementation)

Registration date: 2026-11-16 UTC. Parent: PR #405 exact head `7a0b7372d5169c8c0886c9beb33df704192b9c3c` on `product/contract-value-omega-private-recovery`.

Scope: supplemental, **non-mutating** independent math/evidence gate for a buyer-runnable offline commercial product. No canonical native financial Account, source migration, customer data, keys, real buyer or vendor communications. Existing PR #405 owns product integration; this branch only adds separate verifier/tests/workflow. Research product qualification is NOT the Blue Sky science flagship or external commerce.

## Frozen vulnerability hypothesis
The existing `verify.verify()` checks source/output hashes, line arithmetic and aggregated consistency but does not independently reconstruct the correct contracted unit ceiling, monthly authorization allocation or per-line expected charge. An adversary able to regenerate output files and ordinary unkeyed SHA-256 manifests can alter a source-derived expected amount and produce a fictitious but arithmetically self-consistent recoverable candidate. This is a **local-report integrity** weakness, not proof an external adversary has accessed a buyer's data.

## Registered demonstrations and acceptance
1. Run the unchanged fictional 10-line buyer fixture. Original verification and new gate must accept; amounts remain exactly CAD 20,700 screened, CAD 16,700 full-payment classification, CAD 0 actual cash recovered. Buyer-visible files remain unchanged.
2. Forge one line's `expected_cents` (A-001) to 0, consistently regenerate gross/net, summary, CSV, HTML, supplier packets and ordinary output checksums using the original writer. The original checker is expected to accept the *self-consistent* fake; the supplemental source replay **must reject** it. Do not describe the planted dollars as customer savings.
3. Tamper rate, usage quota, duplicate classification, provenance, and buyer packet while rehashing whenever feasible: reject incorrect source-derived financial rows or any output that differs from deterministic buyer presentations.
4. Missing source bytes, changed post-report inputs, contradictory/tampered outputs and malformed manifest must fail closed.
5. The gate may reuse the original parser (file format and identity checks) and deterministic presentation writer, but must **independently derive all disputed line-level financial amounts and case classifications**, without invoking `core.audit()` to derive the expected rows; label shared-parser scope honestly.
6. Preserve all prior failures and negative conditions, require a clean GitHub-hosted exact-head workflow using standard free Linux runner and no paid network or external data. No release/merge until owner review and qualification.

Decision rule: accept only as supplemental offline buyer arithmetic verification. No legal refund approval, signing, immutable authorization, forensic certification or paid customer acceptance is inferred. Failure means HOLD / owner handoff, never weaken assertions to win.
