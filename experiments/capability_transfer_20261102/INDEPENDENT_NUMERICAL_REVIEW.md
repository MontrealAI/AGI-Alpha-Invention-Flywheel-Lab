# Independent numerical review

The frozen Stage B implementation passes its numerical checks. Its proposed pair does **not** establish that another measurement is required for the registered current-prediction task: a common midpoint prediction satisfies both worlds' RMSE and peak requirements. The midpoint policy was selected **after** the Stage B result and is an exploratory diagnostic, not a new prospective confirmation. No physical measurements were used.

## Evidence and scope

The original result has SHA-256 `4c36506559fb88cdcfde81f76a12daf0af3ed369a67b0306499b0ecea2d39a8c`; the [serialization-fix freeze](FROZEN_STAGE_B_SERIALIZATION_FIX.json) has SHA-256 `05bb81b18d96b1e4a6ab1110a26974dfe5cef2002bf8ac33e6141c160ceb408b`. All five source hashes match that manifest. Independent recomputation exactly reproduced both reference-trajectory hashes recorded in the result. This checks local content integrity; it does not independently establish remote publication timing or an inaccessible holdout.

The [prospective specification](STAGE_B.md) fixes two analytic cell hypotheses, 2 Ah and 3 Ah, sharing all admitted short-test responses through 0.4 Ah of discharge. The 4-cell pack uses 8 A total current and a 2,100-second evaluation interval. The verifier implements separate two-rail nodal equations and analytic OCV; the constructor uses an impedance matrix and interpolated OCV. Their shared model assumptions are synthetic, not physical validation or a novel solver claim.

The original receipt reports 128 circuit fixtures, maximum static current disagreement of `3.39e-12 A`, maximum KCL residual of `3.84e-13 A`, maximum KVL residual of `2.67e-15 V`, and maximum complete-trace disagreement of `3.21e-6 A` across the registered step refinements. Both short tests differ between hypotheses by at most `8.88e-16 V`.

## Common prediction

At every registered time and branch, predict the arithmetic mean of the two frozen hypothesis trajectories. This policy receives no actual-world identity and is invariant to hypothesis ordering. Evaluation uses all 4,201 samples at 0.5-second spacing. The [original K2 contract](PREREGISTRATION.md#k2-contract) permits RMSE of 10% of the 2 A per-branch applied-current scale, or 0.2 A, and 10% peak-magnitude error.

| Branch | RMSE in either world, A | NRMSE in either world | Peak error in world A | Peak error in world B |
|---|---:|---:|---:|---:|
| 0 | 0.199170538 | 9.958527% | 0% | 6.009771% |
| 1 | 0.066883396 | 3.344170% | 0% | 0% |
| 2 | 0.066293478 | 3.314674% | 1.331075% | 0.468907% |
| 3 | 0.065999221 | 3.299961% | 1.719129% | 0.871605% |

All eight branch/world RMSE checks and eight peak checks pass. The narrowest RMSE margin is **0.000829462 A**, about 0.829 mA below the 0.2 A limit. The largest pointwise error is 0.401844532 A; pointwise error is not the registered RMSE/peak objective. Current conservation holds to `4.96e-13 A`.

By the triangle inequality, any common prediction has worst-world RMSE at least half the RMS distance between the two true trajectories. The midpoint attains that bound. Its peak errors also pass, so the two candidate worlds admit a common acceptable prediction. This finite conclusion does not establish robustness to additional hypotheses, physical model error, temperature changes or another objective. Constructing and qualifying the candidate-model set remains an unqualified prerequisite whose cost has not been established.

## Probe, comparators and cost correction

The independently checked probe search selects 1.5 A for 1,440 seconds plus 300 seconds rest: **1,740 seconds**, with predicted endpoint separation of 11.103920 mV under the assumed ±2 mV observation error. It is the shortest separating action within the declared 21-option menu. It identifies these two models but is unnecessary for their common accepted current prediction. Initial characterization, reset, SOC preparation and physical qualification remain unresolved costs.

In the recorded world-B comparison, equal sharing fails (worst NRMSE 19.3158%, peak error 27.9702%). The no-interconnect ablation passes the same tolerances (worst NRMSE 5.9058%, peak error 3.4160%); it receives world-B cell parameters. These outcomes establish no accepted-quality advantage over that simpler comparator for this condition.

The frozen cost field treating 20 hours as a lower bound is too strong. Interpret it as an assumed nominal-capacity scenario, not a universal measured bound. For unchanged shared acquisition burden F and per-anchor burden A, reducing ten anchors to four saves `6A/(F+10A)`. A 50% saving requires `F <= 2A`, hence `F <= 2.08 h` for assumed `A = 1.04 h`. The 20.5263% saving at assumed `F = 20 h` is conditional; actual complete acquisition savings remain unmeasured.

Preserve the original failed impossibility claim, frozen code, receipts and [serialization history](EXECUTION_HISTORY.md). The original capability record's unconditional whole-discharge abstention is superseded by this diagnostic only for the exact two-world, 2,100-second contract. Physical K1/K2 qualification, transfer advantage, new industry and revenue remain unestablished.

## Reproduction

Use the original result bytes with the digest above, not a new Stage B result containing different timing fields. From the repository root, with NumPy and SciPy available:

```sh
python experiments/capability_transfer_20261102/run_midpoint_diagnostic.py \
  --result /absolute/path/to/original/RESULT.json \
  --output /absolute/new/midpoint-diagnostic
```

The runner writes `DIAGNOSTIC.json` and `midpoint_reference_traces.csv` from the same already-computed references and common prediction. The CSV is reproducible output, not a repository dependency. With Matplotlib available, reproduce the figure from it:

```sh
python experiments/capability_transfer_20261102/plot_result.py \
  --traces /absolute/new/midpoint-diagnostic/midpoint_reference_traces.csv \
  --output /absolute/new/midpoint-diagnostic/midpoint_result.svg
```

The default freeze is the adjacent `FROZEN_STAGE_B_SERIALIZATION_FIX.json`; `--freeze` can select a relocated copy with the same required digest. The runner verifies the original receipt, freeze, all five frozen sources and pair before computing references. Default mode requires exact historical reference-hash agreement. It uses a new output directory, returns nonzero on failed qualification, refuses existing output paths and never edits original files. The JSON includes runtime versions, the runner's source hash and the CSV digest, but excludes timestamps, run durations and absolute paths. Different numerical environments can fail strict floating-point reference-hash agreement.

The archived CSV-export diagnostic was executed with Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0. Its SHA-256 is `9d97d819d494ac364468c4d92d473747bbc62e39eb2ac4c888fe1691a000a47e`; its CSV exactly matches the initial plot input, SHA-256 `49f6c28db9749423414cbab11e5d4b0b4f0d19bd2d71e086221d9b2bf536aebe`. Before adding CSV export, two runs produced byte-identical JSON and checks confirmed refusal of an existing output directory and an altered original receipt. These historical receipts remain unchanged.

### Explicit portability mode

Hosted run `41489928442`, job `125429977760`, passed the full frozen Stage B but failed the diagnostic's exact historical-reference comparison. Its reported NRMSE and peak error still passed the original scientific tolerances. That failure remains in [execution history](EXECUTION_HISTORY.md); it is not relabeled as a success.

For a different numerical environment, first execute the complete frozen Stage B and then explicitly supply that same-environment receipt:

```sh
python -m experiments.capability_transfer_20261102.run_stage_b run \
  --freeze experiments/capability_transfer_20261102/FROZEN_STAGE_B_SERIALIZATION_FIX.json \
  --output /absolute/new/stage-b-replay
python experiments/capability_transfer_20261102/run_midpoint_diagnostic.py \
  --result experiments/capability_transfer_20261102/results/STAGE_B_RESULT.json \
  --replay-result /absolute/new/stage-b-replay/RESULT.json \
  --output /absolute/new/midpoint-replay
```

The original receipt and frozen-source guards remain mandatory. The replay must have the same complete Stage B schema, freeze, sources and claim map; literal acceptance flags; the registered 128 fixtures and seed; both configurations and all three completed trace grids; and finite errors below the existing `1e-8` static and `1e-4 A` trace limits. The recomputed references must match the replay's hashes **exactly**. No new floating-point tolerance is introduced.

`reference_hashes_match` continues to report historical agreement. `origin_bitwise_reference_mismatch` exposes historical disagreement, while `replay_reference_hashes_match` and `reference_acceptance_hashes_match` identify the explicit acceptance target. The replay's file digest is recorded and checked again after recomputation. A valid receipt from another numerical environment can still fail this exact replay match and produce a retained failure diagnostic. Fresh execution provenance belongs to the producing workflow; unsigned receipt contents alone do not prove when or how it ran. This remains an exploratory diagnostic of the original synthetic pair.
