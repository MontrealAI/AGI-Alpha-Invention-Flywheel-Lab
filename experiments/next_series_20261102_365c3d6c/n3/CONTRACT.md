# N3-METROLOGY-365C: frozen construction and acceptance contract

## Purpose and delivered outcome

K1 is an **engineering-analysis artifact**: determine whether a proposed reduced measurement set can establish a specified local normal-stress functional, supply an independently checkable ambiguity witness when it cannot, and specify the measurement that removes the demonstrated ambiguity. The prospective beneficiary is a manufacturing qualification engineer deciding whether retained metrology/model evidence can replace a particular additional measurement. No industrial release threshold, fatigue lifetime or customer price is invented. A sign distinction in an authored witness is a mathematical diagnostic, not a part acceptance criterion.

The larger possibility is reusable qualification evidence across changes in parts and processes. Bulk residual-stress simulation and commercial inherent-strain methods already exist. The obstruction investigated here is loss of target-relevant information, reference calibration and spatial applicability. Neither a fit nor an evidence package by itself removes it.

## Source contract, read before numerical outcomes

Primary context: NASA/FAA/NIST CM4QC Strategy, March2026, DOI/report NASA/TM-20260001729, §3.3 and Appendices V–VI; https://ntrs.nasa.gov/api/citations/20260001729/downloads/NASATM-20260001729.pdf . Its transferability problem is motivation, not validation of this instrument.

NIST AMB2022-01 methods: https://www.nist.gov/ambench/amb2022-01-benchmark-measurements-and-challenge-problems , §3.3 and §4.2.1. Dataset DOI https://doi.org/10.18434/mds2-2711 , version1.0.0. README SHA256 `6da6531af5871cdc0c000352a5373a9d7eb7c2aed7c6b843d6d376c538d36dc6`. Build metadata DOI10.18434/mds2-2607 README SHA256 `907c1a85f15ffb05951a3fa7b8ae2538cdc78e264f1c866b686e783405101fc7`.

Detailed primary methods: Phan et al., *Elastic Residual Strain Measurements...*, published8January2025, https://doi.org/10.1007/s40192-024-00388-w . The original benchmark was intentionally a comparison of spatial strain variations. Its mean correction is not an author error. **Mean-corrected scoring does not validate absolute strain**, and raw published strain estimates are not claimed to have been mean-erased. The method reports effective multi-peak diffraction strains; it explicitly does not establish one unique representative bulk elastic strain. XX/ZZ directions are tilted approximately3.45°/3.22°, the rhomboidal gauge has longest dimension approximately3.2mm, and acquisition is60s/location. Actual specimen positions were adjusted to measured geometry. Statistical uncertainty is not a bound on every systematic error.

NIST describes2248 EDD locations on B7-P3. Neutron measurements are on nominally identical B7-P4, not the same specimen; d0 specimens originate in B6-P3. Current data metadata lists EDD results and deflection documents, not independent numerical contour/neutron truth. Aliases of the EDD TXT have identical advertised SHA256 `ce098ee2303a93ca2e66b769d81d60f9e31287689164bb9d6b4bcccd18e5e855` and79506bytes; this is **metadata identity, not verified downloaded bytes**. No strain rows are needed to decide the missing-observable prerequisite, so this stage does not retrieve them or count2248 empirical rejections.

## Forward models and units

The first construction is an explicitly authored isotropic, infinitesimal, linear-elastic model. E in MPa, stress in MPa, strain dimensionless, directions unitless. No E or Poisson ratio is represented as a measured property of the NIST object. Stress vector order is `(xx,yy,zz,xy,xz,yz)` with tensor shear, not engineering shear. For unit q,

`e_q = [(1+nu) q^T sigma q - nu tr(sigma)] / E`.

Exact-axis two-component observations leave normal stress null direction `(nu/(1-nu),1,nu/(1-nu),0,0,0)`. They identify `sigma_xx-sigma_zz` under common support and the declared material law, but not `sigma_xx` when nu is nonzero. Tilted directions introduce unobserved shear; the simple difference formula no longer has that guarantee. A matched third exact-axis strain identifies normal stresses. Six declared independent directions identify the full symmetric stress tensor in this local model. These are conditional observation operations, not acquired hardware.

A second, spatial witness uses a compact stress potential on an interior box with halfwidths a,b,c in mm. Let `f(t)=(1-t^2)^6` inside(-1,1), zero outside, and `phi=A f(x/a) f''(y/b) f(z/c)`, where A has units MPa mm². Define `sigma=I laplacian(phi)-Hessian(phi)`. This field is symmetric, divergence-free, compactly supported, has zero exterior traction and finite elastic strain energy. Set u=0 and eigenstrain=-S sigma so total strain is compatible. This admits unknown residual manufacturing eigenstrain; it is not a compatible purely elastic no-eigenstrain displacement model. All full-support uniform y-averages vanish while central sigma_xx can be nonzero. The uniform kernel is an authored idealization, **not the actual NIST diffraction kernel or a validated part field**.

## Finite registered cases

Use E=200000MPa, nu=0.3 as a generic model, not IN718 calibration. Seven observation cases: exactXZ targeting xx; exactXZ targeting xx−zz; exactXYZ targeting xx; tiltedXZ targeting xx−zz; six directions targeting xx; six directions targeting xy; and exactXZ targeting xx with nu=0. The final case checks the important exception that missing YY does not prevent identifying every particular target. Reference stress vector `(120,-40,70,25,-15,10)`MPa is fixed, not fitted. Per-channel error envelope is1e-6strain, a deterministic authored box with no statistical coverage claim. Identified intervals must include every admissible noise perturbation; independent verifier derives labels without fitting. Unidentified cases must provide null witnesses and abstain. Equal-content conventional linear algebra receives the same operations and may tie.

Spatial witness cases: halfwidths `(1,1,1)`, `(1,0.5,2)`, `(2,1,0.5)`mm crossed with central sigma_xx `-100,+100`MPa: six cases. Check independent polynomial/quadrature averages, exterior traction, divergence, center value, and finite energy. Polynomial identities establish the declared continuum property; sampled numerical checks are implementation checks, not a global physics certification. An independently calibrated point observation at the center distinguishes each sign pair; another uniform gauge average does not.

Mean-correction control: three declared effective-strain values `(-2e-4,0,3e-4)` and offsets `-1e-3,0,+1e-3`strain: three cases. Mean-corrected residual must be invariant while absolute error changes. This is a diagnostic of transferring an evaluator to a different target, not a criticism of the correctly scoped AM-Bench challenge.

Invalid inputs: nonfinite E, E<=0, nu>=0.5, nu<=-1, nonunit direction, nonfinite measured strain, negative uncertainty, nonfinite target, nonpositive box width, nonfinite center amplitude: ten separate rejection cases. Source-admission checks remain a distinct dataset-level prerequisite rejection, not a numerical accuracy denominator.

## Independent acceptance and source application

Accept the **model instrument** if all seven operator cases, six spatial witnesses, three centering controls and ten invalid-input cases meet the frozen contracts, and a separate verifier confirms algebra, units, ambiguity and boundary properties. Report every failure and original attempt. No changes after outcomes may be presented as original confirmation; exploratory repairs require a new frozen source and explicitly separate reproduction.

Reject physical promotion if effective diffraction-to-bulk constitutive calibration, exact direction/shear closure, common spatial support, absolute d0 systematic uncertainty, specimen/geometry identity, independent target truth or a beneficiary acceptance criterion is missing. Do not fill these with convenient values. NIST receives **one dataset-level scope verdict**; no raw-row outcome count, empirical error rate or independently validated physical stress reconstruction is asserted.

Baseline: competent conventional specialists with the same algebra, finite elements, metrology, sources, calibration and measurement permissions. No artificial invention tax, slowed software or invented human hours. No-retention rebuilding and equal-content ordinary reuse have the same information; any time or monetary advantage remains unmeasured.

## Distinct successor and stopping

Candidate K2 is selecting a support/cut or process-compensation plan that preserves a dimensional/structural envelope, using retained source/measurement contracts. It is a different function, needs independent before/after truth and process/downtime/obligation accounting, and is **not executed** if K1's physical/transfer prerequisites remain unmet. Bulk stress reconstruction alone does not qualify this successor. No experiment is rerun until positive.

Research stops after the declared metadata/method routes and this finite model test. No large ideal sweep, full laser-command archive, new sensor acquisition, laboratory contact or paid evidence. Additional physical investigation needs a same-specimen registered reference with known kernels and absolute calibration, or another separately selected arrangement. All model/inference/research costs and conventional human effort not measured stay UNKNOWN. Resource telemetry is not an invented platform quota.
