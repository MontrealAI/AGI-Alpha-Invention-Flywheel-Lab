# P0-202 source-selected transition-target identity — prospective protocol

**Frozen before implementation, 20 November 2026.** This separate, additive, READ-ONLY source-conformance reference is not a native account transition, source-signing authorization, original task custody, alternate financial verifier, owner-branch modification or a release request.

* Qualified target: `main` at `f0987aa48d5c9136b28540f54eabf5367e63bbe6`; selected `connected_enterprise/finance.py` Git blob `02c81396ad90dbd31efbfeeb1a973fbbdb428bb4`.
* Original owner candidate: PR #40 `ced6c1cb004887dcdafaea59a2976020be649f8e`; its `connected_enterprise/upgrades.py` blob `9866d004c412fc05c9f6292cf898307f177359df`. Its historical `authorize_upgrade` calls `source_identity(target_root)` and repeats this at post-signing recheck. Owner PR #40 is unmerged, based on closed PR #35, and retains sole control of its own code and account; no overlap authorized.
* Historic negative witness PR #496 is preserved without changing its failed/negative findings. The new question is whether a **prospective positive reference** built entirely from the current main source resolver selects ALL and ONLY executing producer dependencies according to the actual service manifest, and can be ported selectively into the owner path after independent composition.

## Fixed tests, before implementation

1. Main source resolver is imported from current exact source and returns the default, production060 and inventory061 selected closures with **42 / 48 / 61** files respectively, including their separate producer dependencies.
2. Under each selected manifest, all files are content-hashed, and modifying an optional selected producer in a temporary isolated copy changes the matching SHA; the default closure stays unchanged. In particular, check `production060/service.py` and `inventory061/quality_constructor.py`.
3. An omitted manifest (legacy call shape) does not authenticate a production060 or inventory061 selected target. A source-version ticket therefore cannot be construed as authenticating the current active producer merely because its default closure matches.
4. An unrelated file outside the selected closure does not change a selected source SHA. Missing/changed selected producer and symlink conditions fail closed in the real main resolver.
5. The original owner `upgrades.py` blob is pinned. A read-only AST witness checks BOTH original target-construction and post-signature recheck source calls omit `manifest`; the test fails if owner source changes rather than silently reusing this diagnosis.
6. Positive reference should explicitly select `source_identity(target_root, manifest)` at BOTH boundaries. The owner code needs a reviewed manifest-aware `source_identity` composition first, since its historical own function accepts only one argument. No production code/account or signing operation is replaced.
7. The tests must run on ordinary GitHub public hosted runner, 360-minute platform window, first-step clock marker, no secrets, money, external APIs or live services. Preserve any failed original run; repairs receive new source commits and exact-head qualification.

**Verdict boundary:** a pass proves only source closure selection and a nonconflicting port reference against pinned source. It is NOT verified original-account custody, signed source transition, nonempty queue migration, maturity, earned reinvestment, real paid commerce or a qualified release. Retain original owner and all historical liabilities. Next action after pass: offer selective exact patch plan to finance owner; do not overwrite/migrate on their behalf.
