# Proximal-only reciprocal optical interface

An offline engineering-model construction, not a fabricated instrument or admitted business.
The useful goal is optical access into narrow inaccessible industrial spaces without withdrawing the fibre for distal recalibration. The constructed reflectors remove dependence on measuring bend/temperature mechanics or accessing the far end. They do **not** eliminate calibration of the boundary transmission operator.

## Run

Requires Python, NumPy; independent reviewer additionally uses SciPy. No APIs/devices/accounts.

```sh
python run.py --out new-results-directory
```

Do not replace an existing result directory. The coordinator must publish the preregistration before confirmation. `interface.py` receives only proximal observations, never the truth matrix or object. `run.py` owns authored truth; shared-process procedural separation is not secure blinding. Sources in `source_*` are local reference copies, not required runtime dependencies or proposed public deliverables.

## Instrument algebra

For a reciprocal, linear, stationary-within-calibration, invertible fibre, forward propagation is `T`, return propagation is `T.T` (not conjugate transpose). A calibrated distal reflector `R` produces proximal round-trip operator `C=T.T R T`.

For `R0=a I` and distinct diagonal `R1`, the pencil satisfies
`C0^-1 C1 = T^-1 (R1/a) T`.
Its eigenvectors recover rows of `T` up to scale. Congruence normalization against `C0` fixes the squared scale, leaving independent row signs. This remaining ambiguity does not change target intensity under phase-conjugated focusing, since an entire row sign is only a global phase on that command.

It **does** change coherent image reconstruction. For any diagonal sign matrix `D`, the fibre `D T` gives exactly the same first two round-trip observations, while coherent fields differ by `D`. Additional computation cannot distinguish the two from those observations.

A third calibrated symmetric reflector with nonzero entries on a connected graph gives pairwise sign products. Propagating signs along a spanning tree fixes all relative signs, leaving one global sign. Disconnecting the graph leaves one undetermined sign per component. The supplied tridiagonal reflector is passive by its norm bound (`<=0.46`), but mathematical passivity alone is NOT a fabrication design or a realizability proof. Implementing switchable reflectors without changing the fibre, imaging aperture or wavelength requires external qualification.

## Strong alternatives and claim limits

Full transmission-matrix calibration, generalized eigensolvers, conventional reflector-stack methods and a human specialist can obtain the same algebraic result. Equal-content ordinary reuse ties by construction. Retaining K1 saves recomputation and the **remaining** two calibration sets when extending to K2; total lineage still has three sets, exactly as fresh direct construction. No improved inventor is established.

Direct distal calibration is an equal-information accuracy control and a complete outside option when access is available. Coherent bundles, rigid optics and existing industrial endoscopes are commercial outside options. Whether this geometry/qualification enables a valuable outcome less expensively than those alternatives remains unresolved.

K2 is a distinct coherent-field measurement function, not simply more K1 focusing. Its economic consequence is not assumed. Tests of authored noise, loss and drift establish only finite model behavior. Relative residuals can miss a coherent model error; broken reciprocity is an explicit independent challenge. No clinical use, therapeutic design, actual physical action or revenue is represented.

## Precedent

[Gordon et al., reflector-stack calibration](https://arxiv.org/html/1904.02644) supplies a prior non-unitary reciprocal optical model and existing competing method. Their practical spectral construction compensates wavelength variation; this minimal implementation instead assumes selectable reflectors and a common transmission matrix. The difference is a major unresolved engineering obligation, not a free simplification of a physical claim.

Paper mechanisms applied: purpose-preserving change of required access (Transformational Intelligence sections4–6); scope-qualified repeated operation and changed successor obligation (The World as an Output sections2,4,7,8); bounded constructor/independent validator/source evidence (AGI ALPHA organizational architecture). This implementation does not inherit any manuscript's physical or economic claims.
