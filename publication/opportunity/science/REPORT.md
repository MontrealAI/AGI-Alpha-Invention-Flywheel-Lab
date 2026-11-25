# TOI-216 · Separate-instrument holdout

**Paired attribution ABSTAIN. Forecast qualification ABSTAIN.** The untouched Sector 27 reduction measured one candidate in the registered date band. The real LCOGT photometry file had an unusable clock column and started hours after the fitted transit. The two instruments did not observe the same transit.

The Activation 1.5 pair of revealed ground cases remains outside this test. Archive metadata identified a July 26, 2020 photometry table for the outer planet and put it within TESS Sector 27. The date-only `REGISTRATION.json` hash was recorded before either curve, event timing or observer note was read. Each quoted reduction took only its own flux and time columns. The two arm receipts were frozen before judging agreement. [TESS Sector 27](https://heasarc.gsfc.nasa.gov/docs/tess/sector27_summary.html) · [Original ExoFOP photometry](https://exofop.ipac.caltech.edu/tess/get_file.php?id=74164)

| Observation | Reproduced result |
| --- | --- |
| TESS, Sector 27 | One model measurement of TOI-216 c in the registered date band. Midpoint **2459056.352421992 BJD_TDB**, depth **17.685 ppt**, duration **5.451 h** and conditional timing errors about **91–93 s**. |
| LCOGT SAAO, ExoFOP 74164 | **72** unique `JD_UTC` samples spanning **1.469 h**, from 03:02 to 04:30 UTC on July 26. All 72 `BJD_TDB` entries equal zero. The unchanged ground reduction declined this input. |
| LCOGT archive, external acquisition metadata | **90** public level-91 exposures in observation `119087051`, at SAAO from 02:40 to 04:29 UTC on July 26. This is instrument evidence for the visit. The released photometry is a subset of that visit. |
| Physical pairing | **0/1**. The ground table starts **3.85 h** after the model's fourth contact on the raw clock scales. It still starts **3.57 h** after contact with a conservative 1,000 s clock and light-travel allowance. That is a chronology diagnostic with no fitted ground midpoint. |

The public LCOGT coordinate query across 2024 through November 25, 2026 00:00 UTC returned two isolated reduced exposures on March 17, 2024, and its exact observing-name query returned zero. That archive search used public level-91 exposures within its stated footprint and filter. `ARCHIVE.json` records the input, completeness and returned observation groups. [LCO archive API](https://developers.lco.global/) · [Barycentric time conventions](https://doi.org/10.1086/655938)

Photometry provenance is carried as raw sizes and digests in the two input manifests. `RESULT.json` records the measured and rejected outputs. `FREEZE.json` binds the complete output of each arm. The result adds one TESS-only held measurement and a demonstrated false pairing. It leaves the April catalogue discrepancy and the forecast-adoption verdict unchanged. A later comparison needs independently clocked coverage of the full transit and a held validation cohort for calibrated forecast windows. All computations used public archives and caused no observing commitment.

## Replay

Use the exact repository source for Activation 1.5 and Python 3.12.14 with NumPy 2.3.5 and SciPy 1.17.0 for a byte-for-byte check. Download only the product URLs named by `TESS-INPUT.json` and `GROUND-INPUT.json`. Place the TESS FITS in `data/nasa/` and the ExoFOP table in `data/`, with their original filenames. The reducer validates the source byte digests and pins its imported code.

```bash
OPENBLAS_NUM_THREADS=1 python reduce.py tess --repo "$REPO" --data data --output TESS.json
OPENBLAS_NUM_THREADS=1 python reduce.py ground --repo "$REPO" --data data --output GROUND.json
python adjudicate.py
```

`adjudicate.py` verifies the original arm digests and reproduces `ABSTAIN_GROUND_CLOCK_AND_COVERAGE`.
