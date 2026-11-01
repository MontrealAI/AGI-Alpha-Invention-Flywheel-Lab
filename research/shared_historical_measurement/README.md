# Source-bound shared historical-measurement production

A real local batch producer for the existing public historical road, promenade, and canopy observations. It recomputes image features from hash-checked original USGS frames and delivers three separate scopes. **Recorded native semantic observations are replayed, never represented as fresh model/API inference.** No buyers, revenue, financial admission, or mission success are claimed.

## Run

Dependencies already present in the tested environment: Python 3.12, NumPy, Pillow. No network or credentials required for execution.

```sh
python -m unittest discover -v
(cd economics && python -m unittest -v)
python ../historical_measurement/replay.py  # reconstruct frozen baseline CSVs first
OPENBLAS_NUM_THREADS=1 python benchmark.py --source ../historical_measurement --data ../historical_measurement --out evidence --rounds 3
python audit.py --source ../historical_measurement --evidence evidence
python cache_replay.py --source ../historical_measurement --evidence evidence
python window_experiment.py --source ../historical_measurement --data ../historical_measurement --out evidence/windows.json
```

`--source` points to the existing public historical-measurement metadata/code artifact; `--data` points to its already acquired originals (`images/`, `v3_canopy/images/`, `v3_canopy/probes/`). Source acquisition is an explicit separate process in that artifact, not hidden in this producer. The optional probe fallback is `portable_result/v3_canopy/probes/`. Nothing here downloads sources/models or calls an API.

## Fair fresh-feature-recomputation protocol

- **Separate:** competent independent requests, each reuses its own calibration features, rather than repeatedly decoding calibration images.
- **Ordinary shared:** one pass across common images, same exact ordinary features, calibration, ROI computation and recorded labels.
- **Commissioned:** exactly the ordinary shared implementation plus a versioned request/output envelope and source-metadata verification. No fictitious extra model savings or arbitrary shared-cost discount.
- Three counterbalanced-order repetitions; warm filesystem cache. Bytes are actual Python file reads, **not measured physical disk I/O**, bandwidth, or a dollar cost. CPU/wall seconds are local observations, not portable performance guarantees. Output equivalence comparison is separately executed outside each mode's runtime; commissioned envelope/source audit is inside its runtime.
- Summer road/promenade share 338 frames. Spring canopy has 61 observations plus one additional calibration frame; two other canopy calibration images coincide with observations and are reused. Spring and summer do not share image bytes.
- Each feature cache key binds source hash, method version, exact observable, ROI, and normalization. Road/promenade labels are never interchangeable. Each output retains the request-specific original timestamps, URL and hash. Window-restricted outputs preserve calibration costs; non-overlap never earns a generic discount.

## Interpretation and remaining costs

This is new computation over old source images, with old semantic responses explicitly replayed. The ordinary feature algorithms, shared decoding, common-subexpression reuse, and cost sharing are ordinary competitors, not a newly established industry. Physical correctness remains limited by the original validation/uncertainty reports; byte agreement is not external truth certification. No continuous exposure, safety, biological budburst or shade service is inferred from sampled frames.

Acquisition, calibration/setup labor, independent physical verification, maintenance, fulfillment, and unknown historical/future model billing remain unpriced. Do not equate a local decode saving with a complete profitable transaction. `economics/README.md` gives the complete-cost funding region, voluntary outside options, budgets, leakage/free-copy, cheap rivals, no demand and unknowns. For identical delivery and participation conditions, commissioning adds nonnegative overhead to competent ordinary sharing; therefore **its cost-only newly feasible region versus that competitor is empty**.

A meaningful next gate is independently evidenced requester need/acceptance and outside option plus complete cost ranges—or measured coordination/contracting benefits not already available to an ordinary shared producer. Conditional SIM remains possible with declared assumptions, but no customers or empirical prices are fabricated here. Native financial admission is not implemented by this research artifact. No canonical core or accounts were touched.

The exact historical outputs already exist. `cache_replay.py` measures the stronger ordinary cached-delivery outside option without recomputing images; this is the relevant cheapest fulfillment option when cached provenance is acceptable. The main benchmark is therefore a **fresh-feature-recomputation workload when that is required**, not the globally fastest way to deliver these already-produced observations. New commissioning does not manufacture new demand or a new transaction from cached labels.

The binding audit is not a trusted signature/attestation: mutually rewritten contracts and outputs can be self-consistent. `audit.py` reports whether the current producer code hash matches, but its `passed` field concerns source/output binding only. Cache identity is currently run-local; any persistent reuse requires an implementation/version bump for changes to the reference river polygon, resampling behavior or library versions. Windows accept lexically sortable archive-format timestamp strings (or ISO date boundaries); this is a research interface, not a hardened public schema. Commissioning additionally reads its producer source once for the code hash; that small file read is not included in image or metadata counters.

Files in `evidence/` are compact source-bound outputs and local receipts, not an independent financial ledger. No original images are copied. The exact USD100,000 SIM seed → USD3B native trailing-365 full modeled-profit objective remains unachieved.

## Public inputs and retained scope

Use the existing [PR 113 historical instrument](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/113), pinned to [2b190fdbf1073bee73542b2c8f2e8e51acd860ec](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/2b190fdbf1073bee73542b2c8f2e8e51acd860ec/research/historical_measurement). Its manifests contain original public image URLs and SHA256 hashes. Acquire originals only through that instrument's explicit opt-in fetch procedure. This branch adds no original images, raw datasets, label caches, accounts, private source, native adapter, workflows or production integration. Generated delivered observation files are intentionally omitted; regenerate locally if needed. Retained evidence is compact timing/count/hash receipts. Publication is branch-only, not a qualification, merge or release.
