# NASA paired-measurement ordinary baseline, recovery cycle

**Decision: INVESTIGATED; not admitted as a new enabling campaign.** A real paired-modality surface comparison was constructed and executed. The frozen whole-field endpoint is defeated by the simplest zero-height plane comparator; it cannot qualify consequential pore support. No consequential means beyond the published ordinary route, physical qualification, calibrated error guarantee, commercial offering, earnings or successor funding was established.

This bounded independent alternative began at 2026-10-30 07:21 UTC after the earlier scratch interruption. It continues the public PR #12 reviews, including the full-view obstruction and the previous NASA intake; it does not reset the overnight allocation or replace the original mission with image-processing success. No root campaign or public repository files were edited.

## Frozen delivery and comparison

`PROTOCOL.json` was written before baseline execution and is bound into both result receipts by SHA-256 `3aedc0a4c661c6ee3c03b2d58e398032d1149d3b985580e869dbd8212498e25e`. The development delivery is a registered top-visible surface depth field from reconstructed XCT, a validity mask, and measured disagreement against the separate optical profilometry. The primary endpoint remains mean absolute height disagreement over valid geometric overlap, with coverage and missingness. It has no invented buyer tolerance, physical error threshold or statistical success criterion. All cases and fitting inputs are exposed DEVELOPMENT; no confirmation or new error budget was consumed.

NASA's physical Ti-6Al-4V disk is measured by independent XCT and optical-profilometry modalities. This addresses the narrow reference-source problem of comparing projections with a reconstruction of the same scan. It does not solve calibration, registration uncertainty, internal-defect truth, or acquisition economics. `ACQUIRE.json` gives original URLs, exact lengths and hashes. NASA NTRS marks the dataset US Government work with public use permitted.

The 2024 complete route includes supervised segmentation and Otsu, plane fitting, registration and a manually traced pore comparison; Otsu tied its best MLP average pore error. The 2025 route adds opaque visibility and an ImageJ Segment Anything workflow. Those already provide the proposed means. The new implementation uses available ordinary NumPy/SciPy/Pillow methods, with global Otsu, first visible ray intersection, robust plane detrending, subvoxel threshold interpolation and rigid feature registration. This is ordinary implementation and reuse. It is **not a reproduction of all published methods**: exact manual training labels, traced pores and transformations were absent; this is a bicubically downsampled volume; rays follow the CT axis rather than fitted-plane normal. Therefore it cannot establish advantage over the full published route.

## Strong simple comparator and endpoint falsification

`plane_comparator.py` predicts zero height relative to the supplied surface plane; it identifies no pores. This competent simple baseline achieves MAE **0.00252717 mm at 100% finite-reference coverage**, and **0.00160724 mm on exactly the refined method's overlap**, beating the refined method's 0.00705542 mm on the frozen primary endpoint. The sparse depression signal and flat majority make whole-field MAE insufficient for the intended consequential feature claim. The endpoint is retained and this failure is explicit; no threshold or customer outcome has been changed to manufacture success.

The refined reconstruction does reduce disagreement on retained measurements deeper than 0.1 mm (0.0440433 mm versus the plane's 0.167256 mm), but retains only **1260/2446 = 51.5%** of that original reference stratum. The 97.46% overall overlap hides strongly unequal coverage. `STRATIFIED_COVERAGE.json` preserves every face/version's coverage by depth. These depth strata are diagnostics, not verified pore masks or a new acceptance cohort. This is a failed qualification endpoint and incomplete feature coverage, not a newly proven enabling opportunity.

## Executed results

| Ordinary method, XCT face | Whole valid-overlap MAE (mm) | Overlap / finite reference | MAE where measured depth < -0.1 mm |
|---|---:|---:|---:|
| Integer Otsu rays + initial registration, min face | 0.01915997 | 528,369 / 547,749 (96.46%) | 0.13537443 |
| Integer Otsu rays + initial registration, max face | 0.00965580 | 533,184 / 547,749 (97.34%) | 0.12453713 |
| Conventional subvoxel rays + feature registration, min face | 0.01767962 | 514,574 / 547,749 (93.94%) | 0.22408953 |
| Conventional subvoxel rays + feature registration, max face | 0.00705542 | 533,826 / 547,749 (97.46%) | 0.04404329 |

The first construction had visible integer-height bands and a flat-dominated registration objective. The ordinary repair removes the bands and improves matching of surface depressions. Both opposite-face results and original outputs remain. This comparison is a development engineering improvement between conventional implementations, not autonomous invention or proof of physical accuracy. The max-face registration uses exposed data and is selected after comparing both face conventions.

`ordinary_comparison.png` and `refined_comparison.png` show the paired fields and residuals. `ORDINARY_RESULT.json` and `REFINED_RESULT.json` preserve masks, residual summaries, transforms, alternatives and resource use. An arithmetic checker that imports no builder functions recomputes all four MAEs using `math.fsum` from saved arrays. This is a same-author procedural self-check, not independent organizational verification or a fresh-data test.

A declared threshold sensitivity at fixed registration used 84, 88, 92 (Otsu), 96 and 100. The whole-field MAE ranges 0.00703477–0.00739975 mm; the deep-stratum MAE ranges 0.04080845–0.04849372 mm. All five outputs remain; no favorable threshold is promoted to truth. Separate +/-1 CT pixel and +/-0.1 degree registration scenarios are reported as sensitivity only, not measured uncertainty. The primary endpoint was unchanged; the zero-plane comparator and depth-stratified coverage diagnose why its flat-surface majority cannot qualify a pore-sizing obligation.

## Source and error boundaries

- XCT file: 196,666,399 bytes, SHA-256 `df04431a3230a7e0f11c9e766a462ebf75c3c3e3ecf939083f88b26395b5c3e7`; 931 × 234 × 902 uint8 voxels, spacing 0.0258478 mm. The source supplies a reconstructed/resampled volume, not calibrated raw rays.
- Profilometry ZIP: 21,336,333 bytes, SHA-256 `f64d9139042ba7adc0a7d6a4174a52c9745a7264d0dc1ddb6866d2f1d19913b0`. The height TIFF is 3259 × 3195 float64 despite source prose calling it single precision. Its strip size is 83,300,040 = 3259 × 3195 × 8 bytes. Header-based intake prevents the incorrect float32 interpretation.
- Height metadata states units mm and XY Calibration=7.4. Independently counted: all 6,698,824 finite height values lie on an exact 0.01 mm grid, and 88.7318% are zero. Actual exported quantization is demonstrated. It does not identify rounding convention or total measurement error.
- The primary paper reports 7.4 micrometre lateral sampling and 10 micrometre vertical resolution. Neither is a hard error or confidence bound. Current manufacturer gauge/mode-dependent accuracy and repeatability are recorded in `SOURCES.json`; absent original configuration, stitching, environment and calibration records prevent applying those catalogue values to this scan.
- Missing profilometry is retained, not filled to manufacture ground truth. Validity coverage is a denominator, not a reason to ignore unmeasured pores. Manual pore boundaries and true internal material geometry remain unavailable. Surface agreement cannot qualify internal defect measurements or fatigue predictions.

## Outcome, cost and next action

No supported unmet means survived this cycle for the simple surface-comparison offering: the ordinary route already constructs it and published work goes further. The zero-plane comparator additionally defeats the primary endpoint, so this cycle cannot admit a consequential pore-support result. The important remaining obligation is **a calibrated, independently validated feature claim**, particularly transfer from visible surface to internal defects. It is unknown here; this dataset cannot supply internal-pore truth merely by more threshold tuning. Do not admit a flagship or simulate earned commercial funding from these pixels.

The next discriminating construction, if this direction receives another explicit allocation, is to freeze a real pore-level delivery and separately supplied calibration/registration error budget, supply the exact published manual pore domains or a source-qualified equivalent to every comparator, and test the strongest occlusion-aware ordinary route on untouched measured specimens with independently characterized defects. If only this exposed single-part data remain, continue conditional development with the missing error stated; do not relabel it physical confirmation. A truly new instrument would need to remove the internal-calibration or economically inaccessible measurement obligation, not reimplement the existing surface workflow.

`RESOURCE_LEDGER.json` records 218,003,291 source download bytes and 51.38 instrumented function CPU seconds. Interpreter/import, research/model calls and complete monetary costs are unavailable, not zero. Peak measured process RSS was 1,753,732 KiB during intake, below 2 GiB. No paid API, spending, new access, outreach or real commerce occurred. Simulated earned funds remain zero. A syntax error and its ordinary repair are preserved in `sensitivity_syntax_failure.log`; no failed experiment or face convention was erased.
