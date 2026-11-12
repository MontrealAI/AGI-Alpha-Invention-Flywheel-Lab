# N3B independent verification contract

This is a source-bound, retrospective single-slide spatial-response and inverse-mask construction experiment. It is not evidence of a commercially qualified production foundry.

## Frozen independent requests
Three prospective targets are fixed in N3B_INVERSE_REQUEST.json: 50 µm ridge, 100 µm closed square wall, 50/100 µm terrace. Source code confirms an 8×8 native pattern with four-pixel black padding; 80 µm/native pixel; fixed 5 s exposure. PNG pair LEFT is mask, RIGHT is measured height, represented as 0–255→0–280.83 µm. No independent SI calibration is claimed.

## Physical truth and limits
Preserve all 1030 training, 114 development and 300 test members. Test belongs to a separately printed physical slide 51497. Pixels and patches are not independent production deployments. Anonymous training members prevent a new slide-disjoint development split. Exact/dihedral source-mask repeats and white fiducials are reported separately without removing unfavorable measured cases. Archive range CRC/member hashes establish member identity, not the publisher's whole-archive SHA.

## Claims that may be accepted
1. Complete provenance and exact fixed denominator.
2. Same-domain heldout forward errors, measured in source instrument-scaled µm, against all three fixed published 200-epoch models and conventional local controls.
3. Three target-dependent archived recipe choices made from masks plus frozen predictions only, decisions recorded before measured-height evaluation. Physical error of chosen historical recipe is measured; oracle best library choice is a separate unavailable-to-policy diagnostic.
4. New 8-bit spatial masks and source recipes are actual constructed artifacts. Software tests may establish valid range, shape, border, unit metadata, polynomial numerical consistency and novelty relative to archived masks. Their printed geometry remains MODEL ONLY. Computational failure is HOLD, not suppressed.

## Claims not established
No manufactured new-mask truth, physical functional acceptance, cross-printer/resin/time transfer, mechanical performance, multilayer capability, uncertainty coverage, autonomous economic advantage, paid beneficiary acceptance, earned revenue or enterprise scale follows from this test. A low test RMSE does not protect inverse optimization from exploiting model misspecification. Existing published spatial predictors are strong outside options, not new inventions here.

## Independent implementation
check_n3b.py constructs targets separately, checks exact source denominator, masks and lineage, selects archive recipe with lexicographic ties, recomputes physical target errors, audits source mask repeats, and directly evaluates the frozen spatial polynomial for generated masks. Shared SciPy Gaussian convention is explicitly not independent physical truth. Analytic software self-tests were executed before N3B image outcome access. Constructor must not import checker functions as its own implementation.

## Final source checks
Author baseline input normalization induces deterministic quantization. Source base_dataset.py (SHA256881e5a682538fe55be883f9fa4e9cc5abc6576dfddb9623bd6bb3109d03c300f) confirms ToTensor then Normalize(.5,.5); util.tensor2im returns float32 scaled uint8. Binding uses the precommitted exact roundtrip lookup or raw identity, not outcome-favored alignment or arbitrary per-pixel tolerance. All 300 inputs for each fixed baseline must bind; failures remain explicit baseline qualification gaps. Constructor clarified both inverse and archive selection objectives as active-region error before heldout outcomes; fullfield error remains reported separately.

Archived baseline directory labels are test_200, but a stored test_opt.txt describes a different later256/latest run. That options file cannot certify these exact archived run hyperparameters. Accept only a saved-output comparison conditional on all300 source-index input identities; do not call this independently reproduced training/checkpoint provenance. The source basename pipeline preserves indices even when fiducial inputs repeat. No free permutation by mask similarity is allowed.
