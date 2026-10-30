# Explicit physical-center coordinate repair — r2

**Executed ordinary repair; no technical or commercial success claim.** The declared sample-center grid is now numerically consistent. The zero-height plane still beats the frozen whole-field endpoint. Deep diagnostic coverage remains insufficient, and the repaired max-face refit is slightly worse on the shared physical cohort. Both face results and all original failures remain.

## Authority and frozen scope

Root agreed to `PROTOCOL.json`, SHA-256 `26e92db9b0f5b2195c3844db384b15921b7eaac9031dd8ebee6035771490c61c`, before any repaired-field execution. `AUTH.json` records that authorization; `AFFINE_CONSTRAINT_ADDENDUM.json` records the verifier/root requirement to preserve the full original physical affine map, including original centroids. The original 47-file package manifest, SHA-256 `60a275fcf18a4a01e44fed5ac12c6260052125bdc214eaa64f4818ee549b9033`, and every listed file were verified unchanged before and after execution.

This is a developer-written repair of an independently reproduced coordinate representation defect, not autonomous invention or an admitted enabling campaign. It uses the same exposed NASA measurements and original functional delivery: a registered top-visible surface depth field, validity masks, all-valid-overlap mean absolute height disagreement, coverage and missingness. No threshold, buyer tolerance, accepted cohort or success criterion changed. No new protected cases, downloads or paid access were used.

## Defect, intervention and numerical result

The independent reviewer showed that default `scipy.ndimage.zoom(..., grid_mode=False)` aligns endpoint centers after output-count rounding. Thus a nominal7.4µm-to25.8478µm zoom produced actual center spacings25.8682403µm and25.8595186µm. This was an XY bookkeeping discrepancy; its physical height-error contribution was not established.

The repair defines native centers `i*0.0074mm` and target centers `j*0.0258478mm`, with first center0 as a **relative computational convention**, not a calibrated physical specimen origin. It samples the native array explicitly using target-to-native center coordinates. Output counts are `floor(native_center_span/target_spacing)+1` =933×915; no center is extrapolated. This leaves trailing native-center spans19.0504µm and10.7108µm outside the target grid. Both independent linear physical-coordinate ramps now match target coordinates to maximum3.553e-15mm numerical discrepancy. This postcondition establishes computation geometry only, not instrument accuracy.

Values and finite masks are sampled bilinearly separately, retaining the original validity threshold>.999; missing points stay missing. Otsu92, CT depth/support/plane extraction, both faces, and the exact original ordinary registration routine and parameters are held fixed. The depth arrays are reused without segmentation or threshold tuning.

Three arms expose separate effects:

1. The frozen old aligned field and support are transported from the old **actual endpoint-center grid** onto corrected physical target centers.
2. The complete frozen old physical affine map is directly evaluated there, retaining original CT and reference centroids and original transform parameters. `AFFINE_MAPS.json` gives full matrix/translation constants. No repaired-mask recentering is hidden in this arm.
3. The exact original ordinary registration routine is refitted using the repaired reference and its new validity centroid. This is reference-assisted development, not a heldout test.

Transporting a previously interpolated field and directly evaluating the original map have different interpolation order. Reference resampling and mask changes also alter cohorts. Their numerical changes must not be presented as isolated physical accuracy gains.

## Shared physical-cohort results

The following use identical corrected physical target centers, repaired reference values and the intersection of all three arms' valid supports. A zero plane is evaluated on exactly the same points. All values are mean absolute height disagreement in mm.

| Face | Common pixels | Old field transported | Fixed complete old affine | Refit after grid repair | Zero plane |
|---|---:|---:|---:|---:|---:|
| min | 512653 | 0.015754799 | 0.015791337 | 0.015357578 | 0.001382700 |
| max | 531758 | 0.006571766 | 0.006587220 | 0.006703765 | 0.001468729 |

For max face, refit on its own overlap gives0.007101927mm MAE with533846/548444 =97.3383% overall coverage. The measured-depth<-0.1mm diagnostic retains1243/2464 =50.4464% of its reference points and gives0.046534187mm MAE; this is not a true pore mask or an admitted new acceptance cohort. The zero plane on all548444 repaired-reference valid points gives0.002529266mm MAE at100% reference coverage. Thus the flat-majority endpoint remains defeated by a featureless predictor. The coordinate correction does not repair that qualification failure.

## Coverage and changed sample domains

- At the same array indices, old reference validity547749 and repaired548444 intersect at547544;205 old-only and900 new-only indices occur. This is explicitly an **index-only diagnostic**, not a common physical cohort.
- Physically transporting old validity onto the corrected target grid leaves545681 valid support points, all within repaired validity;2763 repaired-only points arise from coordinate/interpolation/support policy. These are resampled locations, not new independently measured data. No discarded old physical reference point is omitted from the union accounting.
- For max-face old-transported versus refit supports on the corrected reference union: intersection531758, old-only2, new-only2088 and neither14596. The all-three-arm common cohort above is still more restrictive; counts are reported separately.
- On shared valid reference support, transported old reference versus direct native-to-target reference differs by0.000471640mm mean absolute value. This is a processing/interpolation comparison, not a measured sensor-error envelope.

`RESULT.json`, face receipts and saved fields retain every arm, all transform alternatives, original result values, depth-stratified coverage, index and physical masks, zero-plane comparisons and numerical ramp outcomes. Common-cohort diagnostics do not rewrite historical results or create fresh confirmation.

## Resources, limits and next executable action

The trusted bounded runner completed with30.990706 waited CPU seconds and31.014932 seconds wall time. Peak child RSS497520KiB; captured output35,680,610bytes. The conservative160CPU-second reservation remains charged; observed CPU is not a budget refund. New downloads, spending and earnings are zero. Research/model/backend prices and full integration, verification, deployment, support and terminal costs remain unavailable, not zero. The small documentary affine derivation has its separate timing in `RESOURCE_LEDGER.json`. No actual background process remains.

Complete physical calibration/repeatability and registration error, true pore domains, internal geometry and unseen specimens remain unavailable. Nominal spacing and exported10µm quantization are not hard measurement-error bounds. The published NASA2024/25 complete routes remain stronger ordinary alternatives than any incomplete local recreation; no method novelty, full-baseline superiority, commercial demand, profit or earned successor capability is claimed.

The next executable action is independent checking of the corrected coordinate/ramp, complete affine map, fields and cohort arithmetic against this frozen new package. Further physical qualification needs the same externally grounded pore obligation and independent error/reference inputs already missing before repair. Do not tune thresholds or rename the flat-majority metric to produce an enabling/business claim.

## Independent procedural review

A separate verifier completed an audit without importing candidate code or reoptimizing registration. It reproduced the coordinate ramp, original47 file hashes, fixed complete affine maps, transported fields, recorded refit transforms/masks, all primary/common/stratum arithmetic and the lack of a primary-endpoint win. Its wrapped observation was3.920434CPU seconds; verifier reservations/costs remain in the separate cumulative campaign account. `INDEPENDENT_REPAIR_REVIEW.json` and its receipt preserve the result. Shared host, model family and numerical libraries mean procedural independence, not external certification. No protected cases or claim-level error budget were consumed.
