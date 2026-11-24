# P0-261 — completed historical service closure qualification (24 Nov 2026 UTC)

Decision: **retain the manifest-bound service-data staging rule for synthetic native signer/audit qualification; do not integrate financial source yet.** This closes the registered canonical loader trial, not the execution closure of the whole historical financial verifier.

## Immutable evidence
- Historical owner source: `ced6c1cb004887dcdafaea59a2976020be649f8e`. Original account and writer custody remain UNKNOWN; no inactivity inference.
- Frozen protocol blob `2bfd81b4057e497ca72909d8b112bb263ea61795`; probe blob `755e8a83afae4b53de11e55f5a1b98b512fca263` at executing workflow head `3947f0bb3882dbd91396ea7d2f7dab8d346a7105`. Probe SHA-256 as recorded by execution: `dc75d337eddbed11dc0b01a462786c021521fcda6aea17698bff8de9b26af774`.
- [Run 45346458650](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45346458650), job 138282097732, completed success; logs independently inspected. Python 3.12.16, cryptography 50.0.2, cffi 2.1.1, pycparser 3.11 installed offline from prior hash-pinned wheels.
- [Artifact 14898481571](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45346458650/artifacts/14898481571) independently downloaded; 2,311 ZIP bytes, SHA-256 `a33da18e4e7976c2f52198b41c43880a4d4a8ddd6245bdbca860013279609af7` matched GitHub metadata. ZIP CRC verified. Sole member P0_261.json SHA-256 `32bed731989fe0b10a88be9c07eb62347dcd9ed6f872f55a80f2b151b11065f1`. Independently checked all six case conditions, denominator, unique IDs, exact identities/digests and scope flags in downloaded receipt; not a second run of the producer.
- 523 inventoried Python files and 312 distinct bound data files (835,906 bytes). 104 synthetic job IDs: 32 evidence_matrix, 32 kpi_variance, 32 reconciliation, 8 operations_bundle. Not orders, buyers, deliveries or commercial scope beyond this manifest.
- Python inventory SHA-256 `aeb1c17e78a72c2a89ab74d23be6867e4421c62bb7bed576d5c6733185f42e30`; finance identity `a664f8b897b58254bf8ecae2008563384b490ecbff1f39a709b5d26d3ddc956b`; data inventory SHA-256 `1ea2610c8764472e0502fae869235193f747de39463024129fae16801421c102`; manifest SHA-256 `4e650f54390a29891148275a72be7989338a5dfb2293cf58b89f1fdefd947cb3`; accepted outcome digest `7e1ecca66c5356852b328396699c3b46fd3e8bbdcd01a7f9ebf5451ae2a13608`.

| Registered case | Verdict | Measured child wall seconds |
|---|---|---:|
| Original canonical loader | PASS, 104 IDs accepted | 0.643081286 |
| Python-only relocation | PASS, required data missing | 0.106782831 |
| Complete stage | PASS, exact original IDs and digests | 0.198678146 |
| Remove bound input | PASS, FileNotFoundError | 0.161864135 |
| Change bound receipt | PASS, SOURCE_OR_ARTIFACT_CHANGED | 0.162559250 |
| Restore | PASS, exact original IDs and digests | 0.197958660 |

All six child exit codes zero (expected rejections captured by probe). Six cases passed; no failed or omitted registered cases. Total waited-child CPU 1.332041 s; probe elapsed wall 1.609578353 s. Whole hosted job, model and human economic cost not established, actual billing unknown. No new paid services or spending.

## Interpretation and next boundary

The actual canonical loader requires both Python and manifest-bound data. Missing or altered data cannot be treated as a new acceptable closure. A complete stage reproduced all canonical outcomes without relaxing the historical verifier. This does not prove the Python interpreter, OS loader, standard library, mutable filesystem, nested historical executions, evidence-store contents or audit cache are secured. Existing P0-256/257/258/260 findings remain relevant. Historical owner upgrades.py blob `9866d004c412fc05c9f6292cf898307f177359df` still inherits environment and executes historical subprocesses at lines 89 and 164; the audit cache at lines 73–76 does not bind execution closure. Keep the historical source unchanged. Next separately registered synthetic native fixture must exercise both canonical authorization and audit with isolated staged source/dependency/data closure, explicit nested scope, no successor-controlled code, and cache validity before reuse; preserve all failures. Any real adoption requires authenticated actual source and exclusive owner custody.

## Acceptance matrix
- ACHIEVED: 6/6 actual canonical service closure cases; independent download and semantic receipt checks.
- ACHIEVED (existing engineering evidence only): main refreshed at `39e76570c851b3527d78a526053a9ea2a611a993`; [release workflow 45327425758](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45327425758) all three qualification, publication and downloaded-operation jobs successful; no rerun. Current repository instructions, release workflow and durable handoff consulted.
- PARTIAL: full execution closure of historical authorization/audit, including nested scopes and cache-context integration.
- BLOCKED: actual original native-capital task checkpoint, authoritative source, exclusive writer/custody; PR40 remains open draft at ced6c1cb. No competing operating account or authority assumed.
- UNQUALIFIED: protected financial integration/release, native lifecycle on released composition, P1/P2, actual commerce, recursive improvement and US$3B trailing365 complete-cost profit milestone.
- Historical failures and financial obligations unchanged; no original account, keys, private data, spending, outreach, transactions or deployment. This is an independent research branch receipt, not a release or new economic proof.
