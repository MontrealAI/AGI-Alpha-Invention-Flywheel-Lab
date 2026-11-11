# P0 composition135 — prospective main-feature preservation (frozen before tests)

**Registration date:** 2026-11-11 UTC. **Parent:** `7287ed23aee97e52cc822bbb2c22688cc0dc71b7`, qualified public main. **Owner:** independent additive integration-compatibility review, not original native-capital owner task `01a18fa7-ffc6-7384-8bb4-ea6012cfb0f7` or PR #40. This branch must not be merged wholesale into the owner source or presented as the authenticated migration. No account state or ledger file in the branch.

## Named flagship dependency and genuine blocker

A trustworthy same-account operating upgrade is a prerequisite for funding new productive means without erasing obligations. PR #40 at `ced6c1cb004887dcdafaea59a2976020be649f8e` is a separately owned migration candidate, not a current-main release. Current main exposes `fresh_account_config`, `_offer_menu`, `_resource_units`, `native_engine`, `_service_manifest`, `genesis_release_paths` and `quote_release_paths`; these exported behaviors are absent in the older owner branch. Replacing main engine/runner/registration wholesale would silently remove newer business capabilities and registered account-engine isolation. The prospective test is an integration boundary witness, **not** a migration, a productive invention, customer, or profit.

## Frozen six checks (one source-matched run; no seed selection)

1. Under exact-integer-v2 config, a legacy-permanent-v1 manifest must be refused by canonical `run_world` with `FRESH_POLICY_NATIVE_ENGINE_REGISTRATION_MISMATCH` **before** any new account database is created.
2. A prospective-policy config and exact-permanent-v2 manifest must likewise be refused before opening an account (only if the main prospective policy fixtures are available); if constructing a valid policy fixture is not possible, explicitly report NOT EXECUTED instead of manufacturing an invalid config.
3. Mixed exact and legacy config maps must fail `registration.native_engine` with `ONE_SOURCE_BOUND_SERVICE_MANIFEST_ENGINE_REQUIRED`; a single exact map must return `exact-permanent-v2`.
4. `runner._service_manifest` must bind exact-v2 to the frozen configs and retain legacy behavior for a legacy map without mutating the caller-supplied manifest.
5. `engine._resource_units` must return the offered capacity units for a complete-offer policy, while a legacy config returns 1; fake capacity cannot be hidden by silent fallback.
6. `runner.genesis_release_paths` and `quote_release_paths` must remain source-bound and be included in `runner.source_paths` when present; no bypass of missing dependency guards.

All behavioral tests must run using fresh ephemeral values, with no real account, recovered key, registered business, private data, or paid resource. The decisive negative control is source-level PR40/main comparison, **not** a claim that PR40 already fails some tested runtime: the owner has additional migration semantics not executed here. Avoid brittleness from exact private filesystem paths; demonstrate main behavior using existing public functions.

## Stopping, disposition and acceptance

Exactly the existing six test topics, no new random seeds, no renamed failures; run `python3 -m unittest tests.test_connected_p0_composition135 -v` and its optimized-Python counterpart, followed by existing applicable hosted PR CI. Failed attempts remain failed. **ACHIEVED** requires passing frozen checks against exact main-composed head plus source-matched workflows; otherwise **PARTIAL/FAILED**. No formal merge, source upgrade, archived guard increase, release, downloaded qualified operation, or P0 exit is claimed from tests alone. The original signed operating STATE, queues, financial authority and liabilities remain protected. Maintain owner-safe handoff, and prohibit merging this candidate into current main until independent review and normal protections are satisfied.

This is a directly named blocker-removal dependency for AGI ALPHA's trustworthy productive capital, but not a substitute for the Blue Sky commercially accepted flagship: no buyer, funded invention, net-profit, recursive successor or US$3B T365 claim. No extra CI workflow file is added: use existing PR workflows without crowding the near-limit archive.
