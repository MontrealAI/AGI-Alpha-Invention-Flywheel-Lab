# TOI-216 independent ground-evidence follow-up

**April attribution and forecast adoption remain ABSTAIN.** The exact April archive search returned empty public observation pages. The new November ground visit contains 408 valid observations and supports no transit timing in the registered analysis. The observer's result agreed on the same photons.

## April source coverage

The late-April dispute involves a timing assigned to TOI-216 b near the measured TOI-216 c event. The full public April 2023 LCO coordinate searches for raw level 11 and reduced level 91 EXPOSE records both returned zero rows with no continuation page. The ExoFOP target's instance dated April 6 is an upload of the February 13 ground visit. Its observation date remains February 13. The three April observations in ExoClock's two planet tables are attributed to TESS. These sources supply no separately clocked, contemporaneous ground light curve for the April event within their stated coverage.

[Original April diagnostic](../../factory/REPORT.md) · [ExoFOP target index](https://exofop.ipac.caltech.edu/tess/target.php?id=55652896) · [ExoClock .01](https://www.exoclock.space/database/planets/TOI-216.01/) · [ExoClock .02](https://www.exoclock.space/database/planets/TOI-216.02/)

## New ground-only diagnostic

The TOI-216 b visit of November 10–11, 2023, was selected from the schedule and file metadata. The plan was recorded before the raw flux or observing notes were read. The full original AstroImageJ table contains 408 valid samples with explicit, strictly increasing `JD_UTC` and `BJD_TDB`. The recorded offset remains between **124.788 and 124.950 s**. The observation spans **19:40:20 UTC on November 10 to 02:28:41 UTC on November 11**. The offset check establishes internal consistency of the recorded clocks.

The independently acquired source-instrument archive returned all five cursor pages. Its 451 public level-91 records across the query belong to observation `560776150` at SAAO. They bracket the acquisition of the photometry samples. These are frame metadata for the same visit and a different count from the photometry table.

The frozen b geometries, separate baseline and alternative trapezoid were fit on only the ground photons. The three improvements in weighted squared residuals over their corresponding no-transit baselines were **0.290, −0.716 and 1.000**, against the registered threshold of 36 per model. All put depth on its lower bound. The primary center landed at the first cadence. The fitted centers spanned about 10,017 seconds. The observer note opened after fit freeze documented non-detection and no measured midpoint. That is independent analysis of the same observation, useful for checking the decision to withhold timing.

[Selection and test registration](NOVEMBER-REGISTRATION.json) · [Executed fit](NOVEMBER-RESULT.json) · [Photometry 948869](https://exofop.ipac.caltech.edu/tess/get_file.php?id=948869) · [Observer note 948870](https://exofop.ipac.caltech.edu/tess/get_file.php?id=948870)

The diagnostic adds a resolved ground-evidence decision on a separate epoch. An observing recommendation still requires distinct admitted physical coverage, multi-epoch prediction calibration and independent acceptance. No observations or funds were committed by this work.

## Replay

Download the original table and verify SHA-256 `6a8253d0f22497d719676936d3efaeb0657b3f8baa4222f0c6349e257fa7d18e`. In a checkout of the released reference, run the fit from the repository root. The companion diagnostic uses the same b families from the existing joint-transit workbench. It does not import a TESS light curve or a reference event time.

```sh
PYTHONPATH=products/frontier-member-tools/activation OPENBLAS_NUM_THREADS=1 \
  python3 publication/mission-executor/opportunity/ground_diagnostic.py "$WORK/NOVEMBER-GROUND.tbl"
```

[April and November acquisition receipts](SCIENCE-ACCESS.json)
