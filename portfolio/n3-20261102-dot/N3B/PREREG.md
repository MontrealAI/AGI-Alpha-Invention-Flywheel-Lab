# N3B: Measured spatial process interface → inverse exposure masks

## Source and prospective split
Use NIST dataset DOI **10.18434/mds2-2950**, version 1.0.1. Preserve the authors' **1,030 training pairs, 114 development pairs and 300 test pairs**. The test set comes from physical slide **51497**; 300 patches are not 300 independent deployments. Training and development patches come from four other slides. The development split is not independent batch validation.

The exact member manifest binds filenames, ZIP offsets, CRCs and sizes. Extracted members receive SHA-256 hashes. The full training archive is 441,187,839 bytes, but its PNG payload is only about 4.46 MB. Separate ranges permit training and development access without decoding test heights. The full archive SHA is publisher metadata, not a claim that we downloaded and hashed the whole archive. This is retrospective public-data work with procedural separation, not secret or inaccessible truth.

## Physical coordinates established by source code
The left half of each 128 × 256 pair is the mask; the right half is measured height. Each half is 128 × 128 pixels. An 8 × 8 native pattern has four black border pixels on each side, making a 16 × 16 native field. Native pitch is 80 µm. The active region is `[32:96, 32:96]`; the full field is 1,280 µm square and the active field is 640 µm square. Masks use nearest-neighbor expansion. Height values 0–255 correspond to 0–280.83 µm. Exposure is fixed at five seconds under the source material, printer and process. There is no cross-printer, arbitrary-exposure, material-transfer, multilayer-strength or deployment claim.

## K1: Frozen spatial interface and controls
K1 maps a mask to a spatial height prediction. The effective model operates on a 64 × 64 grid. Gaussian-filtered mask fractions use sigma values 0, 0.5, 1, 2 and 4 model pixels; each model pixel spans 20 µm. Features are an intercept, the first three powers of each filtered field, and products of the unfiltered field with each other field. This gives 20 coefficients. Ridge regularization is fixed at alpha 1, with the intercept unpenalized. Fit only the 1,030 training pairs.

Ordinary controls receive identical data: a pointwise cubic response and four single-blur cubic responses. Choose the blur by full-field RMSE on the 64 × 64 model grid using only the 114 development pairs. This already-used development rule remains unchanged; held-out active-region metrics cannot retrospectively choose another blur. The candidate family and regularization are not selected using test outcomes. These are ordinary numerical methods, not a claim of algorithmic novelty or AI-specific superiority.

Compare archived author outputs from the published 200-epoch pix2pix/cGAN, L1 U-Net and MSE U-Net. These are existing strong methods, not our invention. The `test_200` directory labels the saved-output comparator; a stored later options file does not establish the exact historical run configuration. This is a source-bound archived-output comparison, not a reproduced training run. Bind each output to the same numeric source filename, with no permutation or best-error matching. Verify the saved input image against either the exact source mask or the single, source-derived float32 normalization roundtrip. Report exact matches, transformed matches and mismatches. Any unmatched case makes that baseline unqualified; do not silently discard unfavorable cases. Published test predictions cannot inform fitting, model selection or target design.

## K2: Independently specified inverse tasks
The verifier's `INVERSE_REQUEST.json` fixes three targets before outcome access: a 50 µm continuous ridge, a 100 µm closed wall, and a 50/100 µm terrace. These are authored engineering requests, not evidence of paying customers.

For each frozen model:

1. Predict all 300 archived test masks without using their measured heights. Select the exact historical recipe minimizing active-region mean squared target error, with lexicographic ties. Persist choices and prediction hashes before evaluating actual printed heights. This is retrospective inverse recipe selection, not new manufacture.
2. Generate a genuinely new 8 × 8 grayscale mask using bounded L-BFGS-B, 64 variables in [0,1], a fixed 0.5 starting point, at most 100 iterations and 20,000 function evaluations. The objective is active-region target error. Quantize to eight bits. Save PNG and SVG masks with an 80 µm pitch, five-second recipe, source identity and coordinate metadata. Audit whether the generated mask exactly matches any archived mask.

New masks remain **MODEL ONLY**, even if forward predictions agree with held-out data. They have not been printed. Optimizer failure or nonfinite output means **COMPUTATIONAL HOLD**. There is no numerical physical-release threshold. Optimization may exploit model errors. A separate checker tests coordinates, numerical predictions, quantization and labels; it does not create physical truth.

## Metrics and denominators
Report full-field 128 × 128 and active-region 64 × 64 RMSE in micrometres. Upsample our coarse predictions bilinearly; retain the authors' original 128 × 128 outputs. For held-out comparisons and archive selection, quantize our predicted heights through the same eight-bit truncation convention and 0–280.83 µm mapping as the published outputs. Active-region error is the primary spatial diagnostic; full-field error is also mandatory, not a substitute that benefits from the large black border. Report per-patch results and input-defined uniform-white fiducials separately because fiducials were excluded from training but included in testing. All 300 cases remain in the denominator.

Audit exact and rotation/reflection mask duplicates across splits. One held-out physical slide limits generalization. Do not convert the source's approximately 40 µm fiducial repeatability observation into an arbitrary acceptance threshold. No certified or SI-traceable release claim follows from these metrics.

For each of the three inverse requests, report selected-recipe active and full-field RMSE, error on target features, excess height in zero-target regions, and the selected recipe's prediction error. The hindsight-best physical recipe is an explicitly unavailable-to-policy oracle diagnostic, not our achieved result. Equal-content human/classic-software reuse is a valid outside option; do not invent human timing or cost advantages.

## Admission and accounting boundary
This constructs a spatial interface and inverse artifacts. It does not prove a newly economical industry. The 2023 paper already demonstrates spatial prediction; residual integration, qualification, automation cost, willingness to pay and customer acceptance remain unqualified.

No commercial collection, native business account, physical actuation, paid API or new spend is triggered. Historical physical measurements, materials, instruments and labor are not free future production. Preserve the terminated N3A development record: 30 of 42 calibration acquisitions completed, zero of 52 validation acquisitions opened, and no manufactured-mask result.

Publish the final source, fitted parameters, targets and generated artifacts before accessing test heights or published test predictions. Stop after the finite 300-case, three-request evaluation. No outcome-driven refitting, target revision or denominator changes.
