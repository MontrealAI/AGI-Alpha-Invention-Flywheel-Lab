# FRONTIER Ω UTC continuation — pre-implementation falsification (17 November 2026)

Source base (qualified reviewer #430): `216d5fd5649614dc5f0353ae679f888e9eba3289`. Original canonical owner: PR #429 head `540abdce2ad3ec0562ade0b452a3e3f5d3203125`. No owner, reservoir, wallet, ledger, private data, released runtime or key changes permitted.

## Concrete failure to reproduce

After the live `watch` advances the canonical research clock past the authored 2026-11-16 catalog date, `python -m frontier_omega.crossings --root ROOT refresh` defaults to historical `--as-of 2026-11-16`, violating the monotonic `inventory_clock` with `REFRESH_CLOCK_REGRESSION_USE_READ_ONLY_PLAN`. An omitted-date `list` silently returns historical research priorities. This defeats unattended multiday continuation of the sensor without providing economic evidence.

## Frozen synthetic schedule and acceptance

Use one test-owned ephemeral SQLite reservoir seeded from the immutable original 40+12 catalog, with no network, models, external customers, native finance, or account mutation.

- T1: advance the reservoir's research clock to **2026-12-31** (an intentionally future-dated deterministic test fixture); patch the CLI's UTC clock to 2026-12-31T14:00:00Z, and issue `refresh` **without `--as-of`**. Require zero exception, original same-authority reservoir, and output report `as_of=2026-12-31`. Preserve queue contents and no retrograde or erased tasks.
- T2: with same 2026-12-31 mocked UTC date, `list` **without `--as-of`** must report the prospective 35-day window's `MONITOR` priorities, not historical `REPLAY_CANDIDATE`.
- T3: `list --as-of 2026-11-16` remains a read-only explicit historical query and returns the historical research priorities. `refresh --as-of 2026-11-16` after moving the stored clock forward must still fail closed, without weakening the monotonic-time guard.

Freeze this file before writing test or correction. First run the tests on unmodified source, retain red findings; then repair only default CLI clock selection, preserving explicit dates and fixed 2026-11-16 `demo` reproduction. Existing 35-day window, source provenance, audit, cost nulls, buyer refusal, permissions, stale-source and authority checks remain unchanged. Hosted exact-head CI and original owner integration are independent gates. A green test is not an actual capability crossing, paying customer, permission to deploy, public release or US$3B profit.

**Stop rule:** If any case fails after correction, retain result as FAILED and do not choose more favorable test dates; diagnose and repair the same registered protocol. No arbitrary spending, credentials, paid calls or external contact.
