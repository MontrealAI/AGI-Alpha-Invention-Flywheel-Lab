# Electrolysis131 — preregistered physical-data virtual-flow plausibility gate

**Registration before code, measurements, tuning or confirmation outcomes.** Source baseline: main `1d64b69dcadb494d60f666c635fbecf74ebeeefc`. Research-only; no account/finance/keys/integration, bidding, instruments, control commands or safety actuation.

## Selection across complete arrangements

1. **Non-safety virtual H2 flow plausibility check (selected test).** Recover a useful *independent informational cross-check* of hydrogen-flow telemetry from existing electrical channels without reading the hydrogen-flow sensor at inference. Strong alternatives: keep both actual calibrated meters, ordinary linear/isotonic power-to-flow calibration, conventional dynamic multi-sensor regression, human laboratory review and no addition. A superior point predictor alone is not a newly enabled physical outcome: offline sensor-removal, hydrogen safety and procurement acceptance are expressly excluded.
2. **Original NRC 25-58133 AEM instrument production.** Strong full incumbent: qualified electrochemical test-station OEM, electrical/gas safety engineering, qualified installation/warranty. The actual tender is closed and requires hardware, approvals, staff/training and years of software support; not executable with available authority and resources. NO BID.
3. **Industrial heat plus water recovery.** Strong full incumbent: qualified heat-pump, thermal storage and brine-processing engineer. Existing portfolio physical/economics gaps remain. No independent feedstock/impurity test or demand. HOLD.
4. **No deployment**, chosen unless the complete intervention clears acceptance, cost, strong incumbent and beneficiary gates.

## Frozen data and temporal test

Physical PEM (not AEM) measured traces: Veatch, Windom and Zdanowicz, Dryad `10.5061/dryad.8931zcs64`, published **3 September 2026**; source repository `HydrogenDude/ERCOT_Electrolyzer_Sim_Engine` at commit `a534d8a89cf5e662f183d91a9b40b7936387c4a2`. Treat it as a single hardware run (not independent buyers or multiple plants). Original data and MATLAB physics/calibration work are the strongest known complete engineering incumbent. Only copy compact code/receipts; do not vendor the underlying data. Frozen Git blob SHA-1 of the exact recorded input files:

- `data/experiment/timestamp.txt`: `7aed2b14ad8e0b6c73051290b51654e13b0306c3`
- `data/experiment/power_command.txt`: `124bbe0a34ba11e87493c2da252490905e7897c5`
- `data/experiment/stack_power.txt`: `8e95d6f8c21c3672b301f6156372722e8a7c982a`
- `data/experiment/smps_power.txt`: `9a4b59d3288398a6982ffa12c7a0265bee52bc99`
- `data/experiment/chiller_power.txt`: `5ace0651239536a785a391ded179d59f71c999e8`
- `data/experiment/subsystem_power.txt`: `efac091237fc7320ba9ba7034ec739a9e6a114af`
- `data/experiment/hydrogen_flow.txt`: `4b8b9e4c0852faf2b7a313144d89e00ec9bf6c23`
- `data/experiment/hydrogen_flow_cs.txt`: `8883060f0c48fea734367f7deed9f36d2d832f36` (cross-check only, never candidate input).

Reject source mismatch, duplicate/missing/nonfinite/misaligned rows, time order reversal, and any source substitutions; no external network retries to get a favorable trace. Hash exact bytes via git-blob SHA1 and SHA256. Chronological raw row split: **60% train / next 20% validation / final 20% frozen test**, no random shuffle; suppress first 15 samples of each segment as feature warmup rather than cross-boundary future lookahead. Freeze feature lags `(0,1,5,15)` **using past and current electrical observations only**. Flow truth is never a predictor or imputation source. Missing/zero-current periods are reported, not discarded to make the score look better.

## Executable comparisons and falsifiers

**Ordinary incumbent** has the same source observations and training budget: choose by validation MAE between (i) constant training mean, (ii) least-squares single-channel stack power with intercept, (iii) second-order static stack-power regression, (iv) full six-channel lagged ridge with intercept and ridge `1e-6,0.01,1,100`. **Candidate** is an independently constructed nonnegative multi-channel causal-lag ridge from the same finite grid, chosen on validation only, and cannot claim a novel algorithm where it ties or loses the strongest incumbent. Report all candidates and the best ordinary baseline, without switching after test.

Predeclared acceptance: on the fixed final holdout, at least **80%** of rows and **80%** of active rows must lie in the training electrical-channel min/max ranges; active means true flow above **5% of training maximum positive flow**, reported also unfiltered. The chosen candidate must have active normalized MAE `<=0.10` of training median positive flow, and must *strictly beat* the strongest ordinary comparator's active MAE by >=5% (relative). Never use test truth for model selection.

**Independent fault-screening falsifier:** set an absolute residual cutoff to the 99th percentile of validation active absolute residuals. On frozen active holdout report unmodified false-alarm rate, and compare synthetic +/-25% miscalibration to the authentic flow truth: only on active test rows. This is injected *synthetic* sensor error, not observed faults. Acceptance additionally requires holdout false alarms <=5% and each synthetic-sign detection >=80%, otherwise HOLD. Report support/units, coverage, p95 errors, resource time, raw cohort counts and all failed arms. Do not shift thresholds, data, splits or case definition after results.

Even meeting these offline engineering thresholds **cannot** substitute for a certified hydrogen safety/flow sensor or validate NRC AEM hardware, calibration drift on other days/plants, actual equipment savings, procurement eligibility, paid buyer, source licensing for redistribution, whole-bill cost, native annual profit or recursive improvement. Any plausible use requires site-specific safety-qualified verification, voluntary buyer need, complete professional alternatives and actual cash/liability authority. Otherwise **NO DEPLOY**.

## Stop and decision

Exactly one source snapshot and one frozen chronological test. Never tune on test, resample, count synthetic faults as observed events or hide loss. If acquisition fails, record **BLOCKED SOURCE**, no fallback dataset. If source passes but metrics fail, retain **FAILED / HOLD**. If engineering passes, label **conditional offline proof only**; still **NO BID / NO DEPLOY** absent complete beneficiary acceptance, sensor safety, demand and cost evidence. Costs/actual model billing unknown, no native account used. Preserve historical failures; never edit P0/PR40 or current release.