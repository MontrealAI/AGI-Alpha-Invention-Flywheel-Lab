# P0 branch-pair source preflight 114 — frozen read-only protocol

Registration: 2026-11-09 UTC. Current released main: `ada84f88d0c852609087fdc838c071917c8a02b8`. Independently owned financial-transition proposal: draft PR #40 exact head `ced6c1cb004887dcdafaea59a2976020be649f8e`. This file is committed before the implementation/workflow. Earlier failed campaigns and account history remain unchanged.

## Specific decision

Does either **unchanged existing tree** (current main alone or the owner's older PR #40 head alone) contain the complete static source-registry union and active main-side manifest dispatcher needed before an authenticated operating migration could even be considered? Use the *existing* `tools.p0_source_guard.inspect` and its prior adversarial regression, not a new issuer, ledger, or substitute financial verifier.

Registered test cases, no seed selection: (A) `main=ada84f…, transition=ced6c1…, composed=ada84f…`; (B) same main and transition, `composed=ced6c1…`. The expected engineering finding is that both unchanged trees are **not safely composable**, not a positive migration outcome. Preserve the exact returned source lists, missing routes, changed-file hashes, and parse errors. If either unexpectedly reports `registry_complete=true`, mark the registered expectation **FAILED** and investigate; never relabel it as financial success. Do not change this protocol after viewing outcomes.

Retrieve two independently checked-out pinned public Git commits, with `persist-credentials: false` and no Account/private state directories, and retain only a key-free JSON comparison receipt. Record source commit IDs, test command results, number of routes and file differences, direct source URLs, and unknown billing. Use Python 3.12 on a standard public hosted runner; do not use paid APIs, purchases or secrets. The source preflight is read-only. GitHub workflows on the new PR may run existing repository tests independently; do not infer those historical tests are fresh commercial experiments.

## Scope/stop conditions

The preflight **cannot** attest the HMAC transition ticket, original signing authority, nonempty original queue migration, crash recovery, due financial chronology, semantic source composition, service quality, voluntary paid demand, actual earnings or the US$3 billion T365 objective. In particular, a static route inventory does not prove active execution or a mergeable patch. Existing current-main dynamic source-hash test (P0 live-manifest111) is a separate already-qualified control.

Stop this fixed two-tree comparison after both cases, retaining any failure. Recommended next owner decision is a genuine reviewed semantic composition retaining both source interfaces plus original authenticated-state migration and native audit, not a workaround account or changed source guards. Do not mutate PR #40, main, the original native-capital task, private accounts, or unrelated owners. No merge/release claim for this additive research gate without normal complete checks and public downloaded verification.
