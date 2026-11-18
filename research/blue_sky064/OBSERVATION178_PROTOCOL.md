# Blue Sky 178 — prospective two-load physical observation contract

**Source:** published main `172ea7a9b96ad123a879dde76101b944aa9cf131`. **Status:** pre-implementation frozen protocol. **Purpose:** remove the first *information* obstacle to experimentally testing a passive two-family static-hold/dynamic-slide function. **This is not evidence that an assembled surface exists or works.**

## Registered consequential dependency

A proposed passive interface would switch its static/dynamic force ratio as the contact load changes, potentially permitting passive holding versus sliding without a powered controller. The current [Blue Sky 064](../../campaign/blue-sky-064/CANDIDATES.md) mixed-family hypothesis is only a computational composition from published *single-contact* data. Its source-derived nominal ratio increase is about 0.1721, yet the existing independent coefficient endpoint check has negative worst-case change. Three of six source calibration blocks also require added discrepancy under the existing row-error interpretation. No source-grounded calibration guarantees the assembled mixed surface.

**No acceptance target or simulation seed is being changed.** Reuse the original registered family geometry, low/high indentations `0.01/0.10 mm`, and necessary increase `0.05` from frozen `MIXED_REGISTRATION.json`; reuse the existing verified CC-BY-4.0 public fixture and original code. Those are exposed developmental sources, *not new held-out physical observations*.

## Missing-means construction

Design and implement a portable two-load assembly-level measurement contract, to be used **if a permitted physical experiment later becomes available**:

1. At the exact lower/upper indentations, observe four independent externally measured total forces (static and dynamic at each load), and a separately established worst-case *absolute force-error bound* `epsilon_N` covering acquisition, zero offsets and relevant uncertainty. No unsigned simulated source prediction may substitute for these readings in a real certificate.
2. Form rigorously outward bounds `Fs_high/Fd_high - Fs_low/Fd_low` by the monotonic ratios of positive force intervals. Return CERTIFIED only if the **lower** bound is at least the original +0.05 threshold, otherwise INDETERMINATE or REFUTED when the upper bound is below threshold. Fail on nonpositive denominator intervals, invalid units, nonfinite/bool inputs, missing observations, duplicated load labels or failed source checks.
3. For an explanatory (not acceptance-authorizing) component diagnostic, use the original contact-area matrix at both loads. Check full column rank before inferring effective assembly coefficients `A` and `B` independently for static/dynamic. Propagate worst-case measurement errors through the difference. **Do not** assert the coefficients transfer across specimens, contact velocities or unmeasured loads.
4. On the frozen *modeled* 064 nominal forces only, compute the maximum absolute per-reading error that would still allow a +0.05 certificate. This is a **sensor/measurement requirement conditional on the model**, not a measured sensor accuracy, a guaranteed physical margin or a buyer-accepted functional asset. Report normal-force model scale separately from measured quantities.

## Strong complete controls / no-bid choice

- **Conventional direct test:** a competent specialist using an ordinary four-reading paired-load protocol achieves the *same* direct acceptance bound. The proposed program has no algorithmic superiority claim against it.
- **Reduced-information control:** repeated only-low or only-high measurements cannot identify the difference or both family coefficients; the instrument must reject rather than invent the unobserved load. More precision at one load does not replace the other measurement.
- **Full alternative:** an existing passive clutch/gripper or powered closed-loop hold/slide apparatus may already meet the true beneficiary end-use. Its complete delivered price, lifecycle costs and access are unknown; it remains eligible. **NO DEPLOY/NO BID** without acceptance, buyer consent, financial authority and complete costs.

## Frozen engineering acceptance and stopping

A new read-only Python module and standard-library test suite shall: compute exact interval bounds with adversarial positive-force boundary tests; find critical epsilon by monotonic bisection without silently relaxing the 0.05 threshold; test rank failure versus full-rank decomposition; verify propagation under extreme reading errors; reject malformed/false authority inputs; verify the original registered source hashes; expose a CLI explicitly labeled modeled design or external unverified input; and never write the canonical account or represent predictions as physical measurements. All controls—including negative and inconclusive outcomes—stay in the permanent result. Source-matched standard GitHub Actions must pass for the exact head. A failed test remains failed and receives a prospective correction, not a revised old protocol or cherry-picked load.

**Stopping condition for this cycle:** after one source-pinned engineering design and its tests, decide whether the specified measurement is logically sufficient and what physical calibration and strong alternative evidence are still missing. Do not simulate a new physical result, invent economic prices, execute external actions or treat a source-derived margin as new market evidence.

**Commercial cost and authority:** actual measurement apparatus, mixed-surface fabrication, sensor calibration, failure, verification, servicing, human labor, host/model cost and buyer willingness are **UNKNOWN**. Zero real transactions, no new spending, no outreach and no account/signing changes. The owner of P0 native-capital source, ledger, queues and liabilities remains untouched. The US$3B trailing-365-day complete-cost profit goal remains unachieved.
