# Historical measurement instrument (opt-in research)

A query-specific, provenance-bound instrument for extracting **sampled historical
observations** from public USGS photographs. This is distinct from the weather-CSV
website. It is not connected to financial accounts, the enterprise runtime, a
model API, deployment, or operational safety decisions.

## What was measured

| Query | Frames | Water / exposed / unknown |
|---|---:|---:|
| Shepard Road pavement patch | 338 | 71 / 251 / 16 |
| Riverside promenade patch | 338 | 71 / 261 / 6 |

The two water queries cover selected daylight observations June 15–July 14, 2024.
The third query measures one incidental tree crown over **61 daily frames,
April 1–May 31, 2024**, near 18:00 UTC / 13:00 CDT: ordinary green chromatic
coordinate (GCC) gives 24 leafless, 10 partial and 27 leafed proxy classes. Its
output retains 11 native-uncertain rows, 6 method disagreements and 44 agreements.
Every generated observation carries its original public image URL and SHA256.

**These are machine interpretations, not physical ground truth.** Water durations
require an explicit between-frame persistence assumption; nights, gaps and
unknowns remain unassigned. GCC's sampled transition is May 4–5; semantic vision's
is May 11–12. Neither is an exact biological leaf-out date, shade or health measure.

## Run without downloading large files

Python 3.12 is the repository-supported runtime. From this directory:

```sh
python -m unittest -v test_replay
python replay.py
```

Replay uses the **recorded actual semantic responses and cached image-derived
features**. It makes no network/model calls and checks four exact historical CSV
hashes. It is not fresh inference. Generated CSVs and interval summaries are
ignored by Git rather than stored again:

- `v2/production_measurements_zoned.csv`: preferred water observations, explicit
  UTC/local IANA time zones, routes, evidence, source URLs/hashes.
- `v3_canopy/selected_measurements.csv`: selected GCC proxy and native uncertainty.
- `v2/production_measurements.csv`, `v3_canopy/measurements.csv`: intermediate views.

Only if pixel recomputation is needed (NumPy and Pillow must already be installed):

```sh
python fetch_sources.py --cohort canopy
python v3_canopy/recompute_image_features.py
python replay.py
```

This fetches the 61 originals plus three exposed reference probes and verifies
hashes before saving. Pixel recomputation still uses cached semantic responses.
`--cohort water` retrieves the 338 water originals; `--cohort all` is roughly 95 MB.
No package installs, credentials, account access or separately billable calls
are made by these commands. Do not commit downloaded images.

For fresh water feature/queue construction on this historical cohort:

```sh
python fetch_sources.py --cohort water
python v2/build_queue.py --phase production
```

This creates crops and a semantic queue; it does **not** invoke a model. New images
require new actual semantic review, a new manifest and new acceptance evidence;
never pass off these responses as predictions on different sources. The v1
`instrument.py` and frozen v2 `hybrid.py` preserve the original classifiers.

## Results and failures, not a success-only sample

- **V1 failed the joint acceptance gate:** road coverage failed; sidewalk passed.
  Preserve `independent_visual_validation/comparison.json` and the adverse nearby
  gauge comparator in `validation/gauge_comparison_results.json`.
- **V2 repair:** frozen high-margin dry fast path plus native semantic fallback
  passed a fresh 24-frame 2024 sample on both queries, including five wet frames.
  Another 24-frame 2025 sample passed, but every frame was negative: this does not
  validate cross-event flood recall. The proposed 2023 archive cohort was empty;
  substitution was declared before inspecting 2025 images.
- **Strong ordinary vision tied v2.** Lower target-reading counts are not proof of
  lower total cost. Retain `v2/ordinary_baseline_comparison.json` and the two
  `v2/independent_validation/**/independent_metrics.json` receipts.
- **Native canopy vision failed coverage:** only 18/24 jointly decisive. The
  already-frozen ordinary GCC comparator was selected after this failure, not
  renamed a novel method. Same-season confirmation planned 35 frames; two
  prediction-exposed dates were excluded before labeling. The remaining 33 had
  29 jointly decisive and 28 agreements. Four reviewer-unknowns remain in the
  coverage denominator. Receipts live under `v3_canopy/independent_validation/`.

The receipts contain compact per-case comparisons and historical hashes, not
private reviewer conversations. Their original source hashes describe original
artifacts; omitted source artifacts are **not** asserted to be present. JSON was
compacted without changing values; the compiled-input CSV uses LF line endings. `historical_source_hashes.json` records the
pre-compaction portable artifact bytes, not hashes of current compact files.
The portable original already replaced absolute workspace paths. Current source
changes are limited to retrieval, publication tests/docs and removing duplicate
production sample input; historical output hash checks remain unchanged.

## Costs, lessons and claim boundary

Production used 372 semantic target readings (27 reused exact-source repair
readings, 345 new) and 304 compiled fast paths. A full 676-reading ordinary
production baseline was **not executed**. The executed benchmark used 53 hybrid
versus 96 ordinary target assessments across 40 versus 48 image exposures;
montage/tool-call differences make call counts an unfair cost ratio. Construction,
failed v1, calibration, repair, independent checks, re-views and maintenance all
cost work. Exact model tokens, billing and complete costs are unknown, not zero.
No total-cost saving, customers, revenue, profit or $3B outcome is established.

**Tried → outcome → lesson:** color-only water detection failed → retain semantics
and abstentions; hybrid tied ordinary vision → prefer the simpler method unless
full costs justify routing; canopy vision failed coverage while ordinary GCC
passed a bounded confirmation → retain the useful ordinary instrument, uncertainty
and method-dependent transition, not a claim of general ecological validity.

This demonstrates a bounded reusable historical-measurement capability. It does
not prove a new industry, previous economic impossibility, general autonomous
invention, exact physical states, or economic demand. One camera/season and
independent AI annotations are limited evidence. No historical paper or financial
claim is rebound to this contribution.

## Qualification and source closure

Based on main `e92381ce49a23933999443afee73cb04b975aa12`.
`connected_enterprise.runner.source_paths` was executed: **none of these research
paths enters its 277-file canonical source closure**. No source authority,
financial runtime, ledger, existing workflow or guard is modified. A separate
read-only, five-minute CI job runs only the eight offline regressions. This is deliberately
opt-in research, not integrated enterprise production.

Focused replay/regression tests do not establish full-repository qualification.
Historical original tests and image recomputation are historical evidence, not
silently relabeled checks on this publication tree. Merge, release and operation
from a release remain separate unperformed steps.
