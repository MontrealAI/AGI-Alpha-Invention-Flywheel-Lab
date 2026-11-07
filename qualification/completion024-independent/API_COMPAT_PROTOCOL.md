# Frozen independent P0 API collision map — 7 November 2026

## Scope and authority
Research-only, read-only diagnostic on PR #295. The P0 native-capital owner retains the only integration/account authority. Do not edit, import or instantiate any Account, JournalAccount, original signed business, signer, queue or state. This is NOT a migration, release, commerce result, source compatibility certificate or permission to merge. No secrets or recovery records in output.

## Fixed comparative sources
- Released/current main: `2d1b3a2c1dab8235f2c7bef40bf9a36da1d62d7d`.
- Separate native transition PR #40: `ced6c1cb004887dcdafaea59a2976020be649f8e`.
- Read-only diagnostic on a descendant of independent PR #295 head `282243e0b1122a957bd8068a3cbefad492410b27`; its canonical finance bytes must remain identical to those at `df1f6896b4537f29531d40a6cf7c31d9b18f754d`.
- Exactly seven formerly identified same-path financial/source conflicts: `adaptive_enterprise/account.py`, `commercial/ledger.py`, `commercial/native_engine.py`, `connected_enterprise/engine.py`, `connected_enterprise/finance.py`, `connected_enterprise/verify.py`, `vendor/alpha_claim/protected_exchange_prospective_v1.py`.

## Fixed execution and stopping rule
1. Run Python 3.12 AST-only inspection on the seven source files from exact pinned main and owner Git trees. Never execute either financial implementation. Validate file identity with SHA-256 and git commit. Inspect top-level class/functions and direct methods, not dynamic execution. Record all main-only, owner-only symbols and changed callable signatures; do not silently ignore private functions when comparing.
2. Treat signature differences as **migration-review leads**, not proof of runtime incompatibility. Specifically record removed parameters, new owner-required parameters, absent main symbols, and changed bodies even with matching signatures. Signature-only compatibility cannot prove semantics, import resolution, source registry, account durability or replay correctness.
3. Require nonempty changes in the seven fixed files and a compact reproducible machine-readable report. Include the direct interface concerns already visible in source (main's optional `manifest` argument to `source_identity`, `TapeExchange.execute(..., _expected_before=...)`, and main's current `JournalAccount` incremental-audit helpers) as regression probes. These are known development observations, not unseen holdout confirmations.
4. Qualify the diagnostic when all source/checkpoint identity checks, AST parsing and report invariants succeed. An absence of API preservation is **P0 NO-GO** even if the diagnostic workflow turns green. Preserve failures; no retry selecting another source, no retroactive success.
5. Emit only a small JSON source/interface ledger and human-readable summary in the public workflow artifact, with no account bytes, arbitrary source archive, keys, tickets or host/private files.

## Necessary integration decision
The one P0 owner must forward-port authenticated transition/CAS functionality onto current enterprise's complete main contracts rather than replace main's newer financial/account/service APIs with an older source version. Restore the full source/manifest union, preserve all historical obligations and signed operating queue provenance, run actual source-matched regressions and qualified downloadable release before any GO. Original signed completion023 account and exclusive-writer checkpoint remain unavailable; no owner inactivity or authority is inferred.