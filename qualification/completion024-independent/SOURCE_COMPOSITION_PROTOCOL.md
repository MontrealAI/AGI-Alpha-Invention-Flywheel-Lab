# Frozen independent P0 main/owner/candidate source preflight — 7 November 2026

## Purpose and ownership
Diagnose the exact gap between *currently released main* and the still separately owned native-finance transition implementation before any attempted source composition or account migration. This is additive **read-only** engineering evidence on the independent qualification branch PR #295. PR #40 remains the financial implementation/integration owner. The original signed completion023 account checkpoint and exclusive-writer handoff are not available through our observed interface. Never infer its owner inactive or access, reset, reseed, re-sign or copy its ledger.

## Fixed sources
- Current main reference: `2d1b3a2c1dab8235f2c7bef40bf9a36da1d62d7d`.
- Separately owned PR #40 source: `ced6c1cb004887dcdafaea59a2976020be649f8e`.
- Independent PR #295 candidate before this protocol: `df1f6896b4537f29531d40a6cf7c31d9b18f754d`.
- Existing independent preflight engine: `tools/p0_source_guard.py` from pinned main. Do not modify its checks or redefine success.

## Registered execution and stopping rule
1. Read three distinct public Git trees, using the exact pinned main and owner commits, and the literal PR #295 workflow head. Require a descendant of the pinned independent candidate and equality of its canonical finance blob to the pinned candidate. Sparse source-only checkouts; do not fetch account files, keys or any private runtime state.
2. Invoke the canonical read-only `tools/p0_source_guard.inspect(main, owner, candidate)`, unmodified. Recompute main and owner registry counts, exact finance-path union, missing optional service paths and manifest routes, and changed shared-path SHA-256. Bind the receipt to all Git commit identities and the guard's source hash. The result must include its explicit static-only scope and `semantic_review_and_authenticated_account_migration_required=true`.
3. Record a compact JSON receipt on the transient hosted runner and upload **only that JSON** after successful static preflight; no source archives, recovery material, secrets, tickets, account files or financial balances. Never treat a successful diagnostic runner as a qualified financial composition.
4. The diagnostic itself PASSes only when the three source checkouts, original guard and receipt invariants execute exactly. `registry_complete=false` is a **failed P0 integration gate**, not a failed diagnostic; preserve its exact missing-path list. Conversely, a `true` result only qualifies the lexical registry preflight, never semantic source union, signed account migration or release.
5. Single frozen comparison, no parameter/commit/seed cherry-picking. If code or source changes invalidate the protocol, register a new prospective protocol rather than relabeling this outcome. Stop after the fixed preflight; no account operation, protected merge, new spending, paid API, outreach, release or deployment.

## Necessary P0 exit beyond this test
Resolve all semantic conflicts in the one authoritative canonical source under its existing owner; obtain the actual latest authenticated source/account checkpoint and explicit exclusive-writer boundary; qualify historical replay, nonempty queued source-version continuation, unchanged obligations, claims/maturity, earned-funded operations, real resume/audit, current-source publication binding and normal downloaded release. The historical failed tests and predecessor identities remain unchanged. This preflight cannot substitute for any exit gate.
