# P0-196 — prospective source-identity coverage under service manifests

**Registration before implementation and execution (20 November 2026 UTC).** Independent negative integration witness, not a financial account migration, a commercial flagship, or a request to merge this research branch into main.

## Immutable input identities

- Current published-main target commit `f0987aa48d5c9136b28540f54eabf5367e63bbe6`.
- Target `connected_enterprise/finance.py` Git blob `02c81396ad90dbd31efbfeeb1a973fbbdb428bb4`.
- Historical P0 owner PR40 checkpoint `ced6c1cb004887dcdafaea59a2976020be649f8e`; owner `connected_enterprise/upgrades.py` Git blob `9866d004c412fc05c9f6292cf898307f177359df`; owner `connected_enterprise/finance.py` blob `c01e5cd97fb32b3e5fcd5cea190424d8f4f5d5ec`.
- All are public GitHub source objects, *not* the actual active native-account or exclusive-writer checkpoint.

## Single frozen question and tests

Can a source transition target derived from `source_identity(target_root)` without a service manifest cryptographically cover the same file set as the current qualified `source_identity(target_root, manifest)` on services whose producer is manifest-selected?

Fixed tests (no seed selection): current default manifest `None`, production manifest `production060/native-services/v1`, inventory manifest `inventory061/native-services/v1`. Extract actual `SOURCE_PATHS`, `PRODUCTION_SOURCE_PATHS`, `INVENTORY_SOURCE_PATHS` and `source_paths_for_manifest` from the *verified* current finance blob using Python AST, without importing financial modules. Prove (or falsify) whether changing only a service-specific source file in a synthetic source map leaves the default fingerprint unchanged yet changes the matching manifest-specific fingerprint. Check actual historical owner upgrade target call syntax and whether it passes a manifest. Bind source hashes; reject drift, missing paths and changes to the preregistered schema/paths. No original account data, key, native journal, funds or balances used.

**Expected negative:** default file selection omits `production060/service.py` and `inventory061/service.py`; the matching manifest includes each. Historical owner `authorize_upgrade` calls `source_identity(target_root)` without manifest. This is a *future-forward-port binding hazard*; it is not proof that any already-signed original-account ticket exists with that omission, that protected finance can be bypassed, or that existing P0 owners are inactive.

Controls: changes to one SOURCE_PATHS file affect all fingerprints; changes to a production-only source affect the production manifest fingerprint but not the default; changes to inventory-only source affect inventory manifest but not the default. The best ordinary fix for consideration is to build and audit target authority against the *exact manifest-specific executing closure* while preserving the original old-source replay and canonical HMAC/account guard. No replacement ledger, source re-signing or safety bypass.

## Stopping, qualification and outcomes

One fixed source inspection, one synthetic selection/negative/control experiment, one offline unit suite and one exact-head standard public Actions run. Retain a rejected/failing outcome; correct implementation bugs prospectively with an explicit correction commit, not source, scenario or expected-outcome substitution. Preserve historical CI failures unchanged. Run ordinary `ubuntu-latest` / 360-minute job, starting execution-clock marker, no paid services, API credentials, spending, outreach, private data, customer contact, signing material, account mutation, deployment or real transactions.

Report this checker as **SUPPORT ONLY** for P0 authenticated migration and ultimately the Blue Sky native enterprise. Acceptance of the negative witness is not qualified transition, nonempty-queue migration, commercial evidence or the US$3B native trailing-365-day milestone. No merge/release until the actual original financial owner recovers the live authenticated source/account/writer/queue checkpoint, selectively composes with present main, and independently qualifies protected downloaded-byte operations.
