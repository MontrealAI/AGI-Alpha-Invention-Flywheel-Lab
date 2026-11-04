# Physical battery 100: offline laboratory screening

A usable command-line tool for audited discharge-capacity extraction and early screening from the first100 measured cycles. It forecasts exact laboratory endpoints500 and1000 using ordinary same-model peer transfer, reports small-sample empirical uncertainty, and explicitly continues testing when unsupported. It does not operate equipment or make safety/warranty decisions.

## Run it

Use Python3.12 from the repository root. Install fixed dependencies:

```sh
python -m pip install --only-binary=:all: -r research/battery_physical100/requirements.txt
python -B -m unittest research.battery_physical100.test_probe research.battery_physical100.test_measurement research.battery_physical100.test_prognosis research.battery_physical100.test_evaluate -v
```

The calibrated model is produced by the reproducible measured-data evaluation below. Once `model.json` is available, screening is entirely offline:

```sh
python -B -m research.battery_physical100.cli measured_cell.bdf.csv \
  --group manufacturer1-endt44198-2024 \
  --model battery100-results/model.json \
  --confirm-matched-lab-protocol \
  --json-output screening.json
```

The file may contain the whole measured history or end at cycle100. Features and data-quality decisions stop at the first row after cycle100. The flag confirms that the named model, nominal1C/35C conditions and publisher cycling/RPT schedule match. Temperature is not measured in the BDF columns, so software cannot check it. Without confirmation the tool returns CONTINUE_TESTING. Unknown models, deficient prefixes, unsupported endpoints or missing calibration remain explicit.

Outputs include readable endpoint forecasts/intervals and screening labels, JSON quality flags, missing endpoints, reference capacity and model identity. SCREEN_PASS/SCREEN_FAIL are research triage only, not permission to end required tests or certify batteries.

## Direct conventional alternatives

The primary method is ordinary adjusted peer transfer, not a new learning algorithm. Run exactly the same offline path with `--method peer`, `persistence`, `recent_linear`, `sqrt_linear`, or `curve_ridge`. Each uses identical observed prefixes and its own nine-cell residual calibration, when available.

For the separate conventional extraction check, invoke unmodified PyProBE-Data2.6.1 through the explicit BDF mapping:

```sh
python -B -m research.battery_physical100.pyprobe_reference measured_cell.bdf.csv \
  --rated-capacity-ah 3.0 --cutoff 100 > conventional-extraction.json
```

This shares the declared contiguous-discharge selection, then uses PyProBE RawData.capacity for range calculation. It reports terminal capacity, first-sample offset, integrated current, duplicate timestamps, Q decreases and numerical disagreement. Agreement is cross-library arithmetic consistency on the same cycler quantities, not independent metrology or algorithmic advantage. Nested RPT steps make unqualified global cycle inference inappropriate.

The curve control transparently adapts the known ΔQ100−10(V) variance idea from [Severson et al.](https://web.mit.edu/braatzgroup/Severson_NatureEnergy_2019.pdf), using fixed ridge regression and this dataset's endpoint-capacity target. No original LFP cycle-life accuracy is transferred.

## Reproduce the measured study

The exact sources, LFS SHA256/lengths, license/metadata identities and outcome-blind27-cell split are in `manifest.json`. [PROTOCOL.md](PROTOCOL.md) freezes extraction, targets, controls, uncertainty, abstention and acceptance. A0067 alone was used for development. The other26 measured payloads remained unopened through pre-freeze code review.

```sh
# Final-extractor development check only, never opens remaining cells:
python -B -m research.battery_physical100.evaluate --development-only --output battery100-development
# Frozen full study: nine train, nine calibration, nine untouched test cells:
python -B -m research.battery_physical100.evaluate --output battery100-results
```

Use a new output directory for each run. The full study downloads229MB of publisher-hashed physical data, not upstream executable code. It fits/calibrates before test prefixes, writes/hash-seals all test forecasts before parsing their targets, then emits `model.json`, `sealed_predictions.json`, `evaluation.json`, `cycle_capacities.csv`, `REPORT.md`, and an actual offline screening example. All27 cells and missing endpoints remain in denominators. Test unit is nine cells, not millions of rows. Public Actions retains compact artifacts plus dependency versions; no raw measurements are republished.

The authored pilot requires all18 endpoints scorable, maximum error≤5percentage points, all18 empirical ranges covering, at least three decisive cycle1000 screens, and no incorrect decisive screen. It is not a buyer contract. Failure remains a failed pilot, even when the CLI works. Same-model historical replicate performance cannot establish new chemistry/manufacturer/protocol or field reliability. No model or threshold is changed after test labels are opened.

## Construction history and provenance

The initial acquisition-only stage below preceded the current executable screening protocol. It is preserved as history, not the current product claim.

Three alternatives were compared before this acquisition probe:

1. **Battery characterization and retention:** Microsoft/LF Energy released measured end-, middle- and multi-tab cell cycling in March 2026. Source: https://lfenergy.org/lf-energys-battery-data-alliance-and-microsoft-release-standardized-battery-dataset-to-accelerate-storage-interoperability/ . This offers a near-term independently checkable technical artifact, subject to actual schema and experiment compatibility. The separate October-2026 field-data survey (https://arxiv.org/abs/2610.05811) exposes other possible releases but does not supply capacity ground truth automatically. The FlashBattery AGV aggregate was rejected for capacity prediction because its fields do not include capacity labels.
2. **Wind-turbine early fault detection:** Fraunhofer CARE provides actual operating measurements, 44 anomaly frames and 51 normal series: https://arxiv.org/abs/2404.10320 and https://zenodo.org/records/10958774 . Its normal-behaviour and autoencoder controls are direct alternatives. More extensive raw acquisition and fault-window validation are needed; released statistics include documented quality defects. This remains a fallback if battery labels are insufficient, not a synthetic substitute.
3. **Sparse industrial CT reconstruction:** measured walnut projections and existing ASTRA FDK/iterative reconstruction: https://github.com/cicwi/WalnutReconstructionCodes . This has real projections and an established full-data reference, but substantial data/compute needs and strong existing reconstruction software. Do not call routine reconstruction a new enabling advantage.

## Stage 0 frozen before acquisition

- Base main: `2874984e93045feed649d8ff13481369402b8388`.
- Upstream BDF snapshot: `754304f6191b06a78a762636f211e98fcf3dc305`.
- Read exactly one **development cell**, manufacturer1 end-tab A0067, 1000x1C at 35 C. Publisher Git LFS declares 8,346,123 bytes, SHA256 `2f9b6c457da76b95b4780c703f90280210f57b818ac677ff0c9ff4968bba49c3`.
- Check exact source identity, then report schema, row count, numeric ranges and two development rows. Do not execute upstream code, fit models, read other cell outputs or claim observed capacity until its measurement fields and protocol have been inspected.
- Other cells, manufacturers and tab layouts are reserved for separately frozen validation. A0067 can never count as untouched evaluation.
- Actual data are **controlled laboratory cycling**, not field operation, actual customer acceptance, physical safety qualification, novel discovery, funding or profit.
- Payload license verified in the upstream `Microsoft/LICENSE`: CDLA-Permissive-2.0, which permits analysis and results. Do not republish raw payloads; reference exact upstream URL/hash and retrieval.
- Acquisition success establishes usable measured inputs only. Stop model design if the fields do not support the intended outcome. Preserve acquisition failure rather than replace measurements with simulation.


## What remains outside this artifact

Future independent cells, actual users, customer acceptance, deployment, complete acquisition/support/model-session costs and paid demand remain unestablished. No actual laboratory cycles/time, money or sales have been saved. A passing historical screening pilot would only identify a bounded counterfactual testing opportunity. The frontier-AI versus human productivity comparison requires separately measured complete workflow costs; this study does not provide it.
