# Calibration correction: frozen before evaluation access

The registered ideal-physics proposal is **REJECTED on development**. At 76
patterns its worst training inclusion-signal error is 8.191835%, exceeding the
unchanged 5% criterion; at 15 patterns it is 32.521353%. An unrestricted linear
map also fails (8.034930% at 76). Repeated acquisition count search cannot fix an
incomplete response model. The entire original development denominator is retained.

The homogeneous reference has a 4.304455% projection residual outside the declared
current subspace. Its voltage matrix has a sixteenth singular value about 0.400,
followed by about 0.014, although the current matrix has rank 15. This supports a
testable missing-mode hypothesis. It does not identify a hardware fault, a particular
electrode defect, nonlinearity or the physical cause.

## New construction

Fit exactly one additional right-singular mode from the reference voltage residual
after projection onto the known current row space. Retain the 15 known current
directions plus this one measured mode. Fit fresh specimen coefficients solely
from its acquired measurements; never inherit the reference's specimen values.
The result is a calibrated response-subspace model, not a theorem about arbitrary
conductivity or a physically identified extra source. No reciprocity constraint is
imposed on the added mode whose physical semantics are unknown.

Compare the following complete conventional constructions with equal access to
the 76-pattern homogeneous calibration:
- The proposed physics-plus-one-mode basis.
- A standard rank-16 SVD basis learned directly from the same reference matrix.
- Current-only recovery using the proposed pattern indices (structural ablation).
- A standard adjacent-current basis and the original ideal-physics results.
- Direct full acquisition, retaining its actual information and noise.
- An ordinary implementation of the same calibrated algebra (parity, no AI edge).

Acquisition counts are 16, 20, 24, 31, 36, 40, 48, 64 and 76. Select the smallest
count for which all four training cases satisfy the original 5% contrast-relative
RMS limit, using the proposed basis only. Freeze it and the source before opening
EvaluationData_full.zip. Confirm on all 21 targets with the original criteria:
at most 40 patterns, at least 20/21 at <=5% error, all at <=10%. No evaluation
case may tune the basis, count, tolerance or comparator. If no candidate passes
training, retain direct acquisition and report failure.

Full reference acquisition remains a setup cost. Basis identity binds both current
geometry and exact calibration bytes. A changed geometry or reference needs a new
plan and fresh acceptance. Confirmation is an offline reconstruction check using
held-out measured responses; it is not an online guarantee without those responses.
Any subsequent image comparison remains separately labeled secondary evidence.

This amendment responds to a disclosed development failure. It does not relabel
the original model as correct or convert naturally measured modes into new physics.
No evaluation target has been inspected at registration of this amendment.
