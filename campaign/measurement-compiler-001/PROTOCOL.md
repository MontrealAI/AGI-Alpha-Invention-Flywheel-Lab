# Measurement compiler 001: a physical-data experiment

Registered before examining evaluation targets or running the new numerical model.
Repository base: `8c833ac2f1f164d7f2b0f021113ed0d1bca46e61`.

## Consequential target and present scope

The proposed enterprise would supply application-specific internal-property
measurements for opaque processes through reusable electrical instrumentation.
The missing means investigated here is a measurement protocol that preserves
useful boundary-response information with fewer sequential current injections.
This is a dependency of an interior-property observatory, not a qualified
industrial sensor, new market, paid service, or independent conductivity estimate.

Three materially different possibilities were screened against current work:
passive contact-function construction (already active in PR252), integrated
resource-to-material production (complete incumbent routes already exist), and
interior-property observation (selected for this physical-data experiment).
The existing Blue Sky 064 cards retain the evidence and unresolved conditions.
This experiment does not replace their status or the other owners' work.

## Structural hypothesis

For a stationary linear reciprocal conductor, boundary voltages respond linearly
to injected currents even when the map from conductivity to voltage is nonlinear.
Compile a target-independent acquisition basis, then reconstruct unacquired
responses using superposition and optionally reciprocity. Compare the reconstructed
*inclusion signal*, not only the much larger background voltage, with measurements.

These are established electrical principles and experimental-design methods.
No scientific novelty, stronger discovery policy or AI-versus-human advantage is
presumed. An equally informed conventional specialist may use the identical
construction. Hardware drift, nonlinear response or changed electrode identities
can invalidate the transfer; old acceptance never qualifies a new specimen.

## Data and separation

Use the KTC2023 v3 public physical tank dataset, DOI 10.5281/zenodo.10986692.
Use the four training inclusions and their homogeneous reference in Codes_Python.zip
for development only. The downloaded EvaluationData_full.zip remains unopened until
code, selection policy and development-selected acquisition count are frozen.
The full evaluation population is all 21 released targets, preserving any target
whose parser, physics or acceptance fails. These are author-produced laboratory
measurements; this study does not perform new physical acquisitions.

Archive hashes:
- Codes_Python.zip: SHA256 330d76f3c7148d2840f7f207cd90d7a98eb1d972867b70188096043c9e3261a2
- EvaluationData_full.zip: SHA256 85c47f91c0cd15889a96108b389550edafd8bba46b40fd84447e63a62534ce42

Inspect source schemas and official reconstruction code before implementing the
adapter. Treat published corrected ground truths as current if used. No target
label or unacquired evaluation voltage may enter protocol compilation or prediction.

## Comparisons and frozen acceptance

Acquisition candidates: 31, 36, 40, 48, 64 and all 76 current patterns. Compile a
pivoted-QR current basis, extending it by conventional greedy D-optimal design.
Compare unconstrained linear recovery, reciprocity-constrained least squares,
an adjacent-current basis where available, and full direct acquisition. Include
an ordinary specialist with the same algebra and selection algorithm as an exact
parity control. No optimality claim beyond any explicitly proved linear identity.

Select the smallest candidate count with at most 5% relative RMS error in the
training inclusion-induced voltage change for all four training targets. Freeze
that selection before opening evaluation data. If none qualifies, retain direct
acquisition and report rejection. Primary physical-data confirmation requires:

1. At most 40 of 76 current patterns (at least 47.36% fewer patterns).
2. Relative RMS error of the recovered inclusion signal <=5% in at least 20 of
   the 21 evaluation targets, and <=10% in every target.
3. No use of held-out target responses in construction, calibration or selection.

This threshold is a prospective engineering screen, not an industrial/customer
requirement. Raw-voltage error, unacquired-only error, every target and all counts
remain visible even if the primary result fails. Full physical reference acquisition
is charged separately: it is amortized, not free. Fewer patterns do not by themselves
establish proportionate wall-time, hardware-cost or economic savings.

Mechanism controls: exact synthetic reciprocal operators; a nonreciprocal operator;
rank-deficient current sets; incorrect current/voltage identity; and changed schema.
Use fresh mission inputs and outputs with no inherited proof or authority. Record
the effect of replacing reciprocity with unconstrained superposition. The raw-data
decoder and the independent coefficient-space oracle must agree on exact fixtures.

If feasible, run the authors' released conventional reconstruction on full and
recovered voltages as a secondary check of image-level consequences. Do not use
that extra analysis to change primary acceptance or declare superior tomography.
Released leading methods are strong complete alternatives, not defeated by a
comparison only to the authors' illustrative baseline.

## Resources, economics and stopping

This is included local execution with NumPy/SciPy, public data and no paid API,
outreach, contract, hardware purchase, financial transaction or native account.
Measure compilation, prediction, checking, CPU, wall time and retained bytes.
End-to-end human versus AI engineering costs, actual host/model charges, industrial
adaptation, maintenance, customer value and willing funding remain unmeasured.
Do not assign invented wages, demand, prices or profit. A lower acquisition count
alone does not establish a Blue Sky or commercial admission.

Stop and preserve any invalid data, numerical inconsistency or implementation
failure. Repairs before confirmation are development, not fresh confirmations;
repairs after it require a separate version with the original result retained.
Do not broaden to indefinite parameter search or reset a failed denominator.

## Primary sources

- https://zenodo.org/records/10986692
- https://www.aimsciences.org/article/doi/10.3934/ammc.2024009
- https://fips.fi/data-challenges/kuopio-tomography-challenge-2023/
- https://github.com/alexdenker/eit_fenicsx
- https://pubmed.ncbi.nlm.nih.gov/15709661/
- https://pubmed.ncbi.nlm.nih.gov/18218462/

The public code and report use original explanations and public source references;
private source documents and conversation material are excluded.
