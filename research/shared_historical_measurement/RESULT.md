# Result — bounded historical production experiment

**Useful engineering, not a Blue Sky/knowledge-frontier result or a new industry.** No newly feasible complete economic transaction was established. The USD100,000 SIM seed → USD3B native trailing-365 full modeled-profit objective remains unachieved.

| Measured path | Image decodes | Image bytes read | Median local wall seconds |
|---|---:|---:|---:|
| Separate feature recomputation | 738 | 171,800,503 | 37.05325 |
| Competent ordinary shared recomputation | 400 | 94,023,258 | 21.29831 |
| Same shared producer + commissioning envelope/audit | 400 | 94,023,258 | 21.36033 |
| Existing ordinary cached measurements | 0 | 0 | 0.00643 |

Recomputation paths: three counterbalanced repetitions, all **737 rows identical**, derived pavement distances identical (max error 0), canopy GCC within 1e-12 and all quality flags retained. Separate/shared both compute 676 pavement ROI features and 62 canopy GCCs; shared scene computations decrease 676→338. The 400 unique decoded images include 338 summer frames, 61 spring observations and one extra spring calibration image. Commissioning adds five metadata reads (374,167 bytes), 737 source-row checks, envelope hashing and one producer-code read; it does not reduce ordinary shared work. Local timing variance is not a new speedup claim. No model calls or fresh image interpretations were performed; 433 recorded semantic rows were replayed in each recomputation path.

Ordinary cache replay reads two already existing source CSVs (318,459 bytes), preserving the 737 primary observation states/source identities and canopy quality flags. It does not revalidate image content or independently certify physical truth. This is a stronger fulfillment outside option when existing provenance is acceptable, not equivalent assurance to full image recomputation. The main benchmark is expressly fresh-feature recomputation **when required**, not cheapest delivery of already-produced data.

## Window tests
- `disjoint_observables_and_seasons`: {'road': 12, 'canopy': 1}; no overlapping observation images; separate/shared/commissioned decodes **28/28/28**. All delivered rows identical and inside requested windows.
- `disjoint_observation_windows_shared_calibration`: {'road': 12, 'promenade': 11}; no overlapping observation images; separate/shared/commissioned decodes **47/35/35**. All delivered rows identical and inside requested windows.

The disjoint summer/spring case gets no generic sharing discount. Disjoint pavement dates share only the twelve actual calibration frames. Feature keys bind method version, source hash, observable, ROI and normalization; label scopes are never interchanged. Run-local cache only: persistent use needs fuller implementation/library/reference-ROI identity discipline described in README.

## Tests and boundary

18 production/identity/binding unit tests + 11 economics tests pass; 9 full recomputation runs, independent metadata binding audit, 3 cached-delivery runs, and both real window cases pass. Code hash matches the commissioned artifact. No original images were copied; total work folder remains under 1 MB. The binding audit is not authenticated provenance, an independent computational verifier, or physical truth certification.

Complete costs and independent buyer needs/WTP/outside options remain unknown. Acquisition, setup, calibration labor, verification, maintenance, delivery, coordination and model billing must not become zero by omission. Under identical deliveries and participation, commissioning is ordinary sharing plus nonnegative overhead, so its cost-only newly feasible region over that competent competitor is empty. Free copying, a cheap rival and no demand can only further restrict the funding region. No dollar prices, profit, annualized cohort, native admission or substitute ledger was invented.

`producer.py`, `benchmark.py`, `window_experiment.py`, `cache_replay.py`, `audit.py` and `economics/` are compact reusable support code. No canonical core/accounts were touched. This closes the bounded supporting-engineering experiment rather than expanding it into more wrapper experiments.
