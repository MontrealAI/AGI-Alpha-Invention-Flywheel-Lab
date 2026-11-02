# Independent paired-acquisition verifier contract

## Status and ownership

This is a prospective **synthetic numerical qualification**. The scientific
verifier has not executed the registered challenge when this contract is written.
The integration owner must freeze the constructor, runner, verifier, this contract,
and the governing protocol before the confirmatory run. A failed case remains in
the denominator. A repair requires an explicit new source record and preserved
failure history; it does not change the historical result.

The independent scientific worker owns only `verifier.py` and this file. The
constructor and integration runner have a different owner. They share a host and
can read the public source; this is procedural separation, **not externally
blinded research or external certification**. The generated truth is supplied to
the verifier alone through the callback interface, but source access is not an
information-security boundary.

The existing five-route work remains untouched. The relevant ancestor is
`experiments/public_portfolio_20261102/interface/` at public commit
[`8c13a60859f58c5b0a332eaa433f2ff84c584e8a`](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/interface).
Its common-gain ratio interface and its coherent gain-mismatch failure are
historical results, not new confirmations in this experiment.

## Consequential dependency and the new construction

Material-specific spatial inspection requires trustworthy attenuation estimates.
The ancestor's sample/reference ratio is insufficient when sample and reference
paths have different unknown gains. More fitting of the same ratio cannot identify
a material-shaped gain error. The proposed missing means is an **additional
specimen/reference exchange acquisition** whose physical meaning would have to be
qualified separately.

K1 produces material areal-density intervals from two paired observations under a
wider declared gain class. K2 uses that acquisition interface for a new decision:
which cells exceed a copper-density threshold, and what interval can be certified
for the total area exceeding that threshold. This differs from the ancestor's
task of locating an authored depleted cell. Fresh spatial fields are generated;
no ancestral reconstruction or defect truth is inherited.

This is a useful, bounded mathematical dependency test. It does not establish a
new physical inspection instrument, a new industry, or superiority over ordinary
measurement engineering.

## Observation contract and independent equations

For each ray and energy, let `a = mu @ m` be the intended attenuation. The
dark-corrected ideal signals are

\[
A_0=F_0g_{A0}e^{-a},\quad B_0=F_0g_{B0},\qquad
A_1=F_1g_{A1},\quad B_1=F_1g_{B1}e^{-a}.
\]

All gains and fluxes are positive. The flux may change arbitrarily between the
two exposures and by energy. Each exposure's flux is shared by its two paths.
The specimen is on A at time 0 and on B at time 1; the other path is a genuine
blank. The specimen attenuation, material basis, spectral response, and intended
ray remain the same across that exchange. A geometric change in a nonuniform
specimen is not silently treated as a valid reversal.

Let `r_t = log(g_At / g_Bt)` and require `abs(r_1-r_0) <= D` separately at every
ray and energy. An observed corrected reading is its ideal signal multiplied by
`1+u`, with `abs(u) <= epsilon < 1`. This is a supplied deterministic bound on
**corrected readings**, including any dark-subtraction, quantization, or numerical
error attributed to acquisition. It is not inferred from nominal signal size.
No Poisson, independent-error, or calibrated physical noise claim follows.

The independent estimate is

\[
\widehat a=\tfrac12[-\log A_0+\log B_0+\log A_1-\log B_1],\qquad
|\widehat a-a|\le\beta=\frac{D}{2}+
\log\frac{1+\epsilon}{1-\epsilon}.
\]

The fixed unequal path gains cancel. The uncanceled drift is `(r_1-r_0)/2`.
The four log-error coefficients have magnitude one half, giving the stated
worst-case error. All inputs must be finite and strictly positive after dark
correction. There is no log clipping that converts an invalid read into evidence.

The supplied research-only coefficient matrix, pinned to the ancestor's
[`instrument.py`](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/interface/instrument.py),
is

\[
\mu=\begin{pmatrix}
0.3681&2.613\\0.1704&0.4584\\0.1378&0.2217
\end{pmatrix}\;\mathrm{cm^2/g}
\]

for the declared aluminum/copper basis at 50, 100, and 150 keV. These numerical
inputs are not measurements of a current device or evidence of deployment rights.
The verifier independently constructs `L = lstsq(mu, I)` and solves the material
inverse problem. Its componentwise bound is `abs(L) @ beta_vector`. The residual
bound is `abs(I-mu@L) @ beta_vector`. Nonnegativity is tested with these bounds;
a residual compatible with the basis does not prove the basis is physically true.

## New spatial decision

The ideal geometry is a 4 by 4 grid of 0.25 cm square cells, nine equally spaced
angles on `[0, pi)`, and eleven offsets from `-1.3*extent` to `+1.3*extent`.
It has 99 rays, including legitimate empty rays. The verifier constructs lengths
by sorting grid-crossing times and assigning segment midpoints to cells. It does
not reuse the ancestor's per-cell slab intersection implementation.

With projection matrix `G`, the verifier solves `G @ density = line_mass` by
least squares. It independently constructs `G_plus = lstsq(G, I)` and propagates
component bounds using `abs(G_plus) @ line_bounds`. The geometry must have full
column rank. Spatial residuals and nonnegative densities must satisfy their
propagated bounds. No reconstruction regularizer, true image, or hidden defect
location is supplied to the candidate.

The purpose is **copper density greater than 0.10 g/cm³**, with 0.0625 cm² per
cell. Given a copper interval `[lo, hi]`:

- Certify **above** only if `lo > 0.10`.
- Certify **below or equal** only if `hi <= 0.10`.
- Otherwise report **uncertain**.

Nonnegative physical density can clip a lower endpoint to zero. Certified area
bounds are the cell area times the number certainly above, and the cell area
times the number not certainly below, respectively. The verifier checks both the
decisions' derivation from reported intervals and their consistency with the
generated truth. It never gives the candidate the true classification.

## Finite registered family

The fixed seed is **202611020153**, using NumPy `Generator(PCG64(seed))`.
`build_challenge()` rejects another seed. The generator is part of the frozen
source; a familiar seed is not a secret holdout. No claim of population frequency
or universal experimental success is made from these case counts.

| Family | Count | Inputs and purpose |
|---|---:|---|
| Exact K1 | 32 | Zero acquisition error and zero ratio drift; independent unknown unequal path gains and changing shared flux. |
| Bounded K1 | 32 | `epsilon=1e-4`, `D=2e-4`; independently generated corrected-read errors and ratio changes inside those bounds. |
| Error-corner K1 | 16 | All sixteen four-reading sign patterns, with fixed alternating signs across the three energies and ratio changes at declared endpoints. |
| Separated K2 fields | 8 | Fresh aluminum density in `[1.8,3.0]`; copper values in `[.01,.03]` or `[.17,.21]`; require a complete threshold decision. |
| Boundary K2 fields | 4 | Same fresh field family with some cells exactly `.10`; require sound decisions and at least one uncertain cell. |

Bulk true masses are generated in `[.25,3.0]` and `[.005,.25]` g/cm² for the two
components. Initial log path gains lie in `[-2,2]`. The second frame has a common
log-gain change in `[-1,1]` plus the specified relative change. Log flux lies in
`[5,12]`. These are authored signal units, not photon counts. The sixteen error
patterns are not all `2^12` joint energy/read error corners. The algebra supplies
the conditional error bound; the finite cases exercise its implementation.

### Named invalid-input and model-boundary controls

The verifier registers these controls before execution:

1. A nonpositive corrected reading on each of the four channels, and one nonfinite
   input: refuse with an explicit false acceptance or `ValueError`.
2. An authored third spectral component outside the two-material span: refuse.
   It is not labeled a measured third material. Its exact construction is frozen
   in source and its positive attenuation is saved in the receipt.
3. Rank-deficient spatial geometry: refuse.
4. Fixed unequal gain with a coherent apparent material shift: the old
   common-gain, single-ratio estimator accepts the wrong material amount, while
   the paired acquisition returns the intended amount. This is a causal scope
   expansion relative to that inherited interface, not a strong-baseline victory.
5. Relative gain change outside `D`, with a material-shaped bias: preserve an
   accepted wrong answer, exposing the conditional scope.
6. A coherent coefficient-basis mismatch: preserve an accepted wrong answer.
7. A supposedly blank reference containing basis material: preserve an accepted
   wrong answer.
8. A spatial threshold ambiguity outside the drift contract: two distinct true
   images generate the same paired observations within numerical tolerance. The
   candidate is called **once** on their common observations. Its common output
   is checked against both worlds; no actual-world identity chooses the policy.

Controls 5–8 test that the stated numerical method's limitations remain explicit.
Their acceptance is not counted as physical success or reliable detection of a
scope violation. An arbitrary coherent mismatch cannot be certified away from
these observations alone.

## Competent comparators and retained evidence

**Ordinary fit on exactly the same observations.** The verifier independently
fits all twelve logarithmic readings with two shared material coordinates and,
for each energy, two source/common-gain levels and one relative path-gain
coordinate. This is a 12 by 11 linear least-squares system. It receives no true
gain, flux, material amount, or image. It is expected to match the constructed
double ratio within numerical tolerance. A tie establishes correct use of known
measurement algebra; it does not establish a superior invention procedure.

**Independently acquired blank calibration.** A conventional control acquires its
own sample/reference frame and blank/blank frame. It estimates attenuation by
the ordinary ratio of sample/reference and blank/reference ratios. Its appropriate
bound is `D + 2*log((1+epsilon)/(1-epsilon))`. Its observations are separately
generated; the control is not granted an exact gain oracle or a free calibration.
The four acquisition errors have magnitude-one log coefficients. It can tie or
outperform under a different qualified dose/stability/cost allocation.
Blank-normalized dual-beam measurement is established instrument practice; see
[Shimadzu's primary instrument explanation](https://www.ssi.shimadzu.com/service-support/faq/uv-vis/instrument-design/22/index.html).
That optical explanation does not itself qualify an X-ray exchange apparatus.

**Equal-content fresh reconstruction.** The runner must supply callbacks that
rebuild the candidate's ordinary numerical operators from the same allowed
coefficient and geometry inputs. The retained and fresh versions must match on
the same observations. If either callback is omitted, aggregate qualification is
false and the missing comparison is reported. Timing differences, if measured by
the runner, are numerical construction costs and do not establish total physical
or economic savings. A saved numerical inverse is not an independent physical
calibration.

## Resource accounting boundary

One ideal spectral paired acquisition has two dual-path frames, four vector
readings, or twelve scalar energy-channel readings. The specimen is exposed in
both frames. A sample/blank protocol also uses two dual-path frames but exposes
the specimen in only the sample frame. The distinction matters when comparing
total photons, specimen dose, detector read noise, elapsed time, and the cost and
preservation effects of exchanging the paths. Equal authored `epsilon` is not a
proof of equal resources or an achieved physical error bound.

Dark acquisition/subtraction, calibration reuse horizon, flux, dose, movement,
geometry qualification, switching/reset costs, detector response, scatter,
polychromatic response, reference uncertainty, maintenance, construction and
failed attempts remain explicit obligations. Unknown costs and physical counts
remain unknown. No paid experiment, account, credential, outreach, or real
apparatus is operated by this verifier. The separately owned economic analysis
must preserve these distinctions; it cannot promote synthetic counts into
measured savings or cash receipts.

## Callback API and qualification gates

The integration runner calls:

```python
receipt = verifier.run_verification(
    pair_decoder,
    spatial_decoder,
    fresh_pair_decoder=fresh_pair_decoder,
    fresh_spatial_decoder=fresh_spatial_decoder,
)
```

Each pair callback takes positional corrected arrays `(a0,b0,a1,b1)` and keyword
arguments `eps` and `drift_bound`. It returns `accepted`, `mass`, `mass_bound`,
and `attenuation`. The spatial callbacks also take `geometry`, `threshold`, and
`cell_area`; they return `accepted`, `density`, `density_bound`, `above`, `below`,
`uncertain`, and `area_interval`. The runner may use thin key/signature adapters.
Acceptance evidence must be a nonempty Boolean scalar or array with the expected
shape: one Boolean per bulk input, and a scalar Boolean for a spatial result.
Strings, empty arrays, and implicit truth conversion are not acceptance evidence.
No callback is passed the synthetic nuisance realization or truth. The verifier
imports no constructor code and owns its forward law, reference equations,
ordinary comparator, projection calculation, case generation, and scoring.

Every valid registered case must pass. Candidate point estimates and propagated
bounds must match the independent reference with `atol=2e-9`, `rtol=2e-9`.
The verifier uses a separate `1e-11` numerical residual allowance. These are
floating-point consistency tolerances, not physical tolerances or confidence
levels. Inflating the claimed bound arbitrarily is prevented by checking it
against the independently derived bound. Generated truths must lie inside the
reported component bounds within the same numerical allowance. Same-observation
ordinary estimates must agree. The acquired blank control must produce valid,
truth-covering intervals; its lower completion rate near a threshold, if any,
must remain in the result. Fresh equal-content comparisons must be present and
match. All named controls must behave as registered.

`numerical_contract_accepted` is true only when all these gates pass. It is not
a physical K1/K2 verdict. The receipt keeps physical qualification, new industry,
commercial viability, measured dose saving, external blinding, and superiority
over the ordinary same-observation method explicitly false. The parent runner
must write a failure receipt and exit nonzero on a failed numerical contract,
and must refuse to overwrite prior evidence. Observation hashes identify the
current generated bytes; they are not claims of cross-platform bitwise identity.
There are eight named control checks and four named limitation witnesses. An
unexpected callback error retains completed rows and records all remaining IDs
as not completed; those controls still count as failures in this finite run.

## Applicable primary manuscripts and their limits

The independent worker read the complete public **OUT-LEARN** revised manuscript
(22 pages, SHA256
`01a8ea668f4c75cd0b5fafe3c5720e445bab7986abf27baee5bbba7d5e77febb`)
and **The World as an Output** (23 pages, SHA256
`2a34c0ad813b6dddf8c6176a475d85f231ea06b53b641496de31626c3d786fde`).
Their byte-preserved public editions are
[`out-learn-20261021.pdf`](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/a1e3751c50c8746d878d6442ae706fae88665247/docs/research/out-learn-20261021.pdf)
and
[`the-world-as-an-output-20261020.pdf`](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/a1e3751c50c8746d878d6442ae706fae88665247/docs/research/the-world-as-an-output-20261020.pdf).

- OUT-LEARN pp. 7–9: retain valid calibration and propagate deterministic feasible
  intervals; calibration scale and future-use scope are real assumptions.
  Pages 13–16: preserve signal-shaped nuisance, changed gain, hardware-range,
  switching and numerical failures; competent existing reversal/filtering methods
  remain strong comparators. This experiment does not claim its particular
  double-ratio equation inherits the manuscript's distinct minimax theorem.
- The World as an Output pp. 3–4: preserve the intended productive state and give
  the interface an explicit permitted-use scope. Page 7: per-query validity and
  downstream decision validity are different claims. Pages 11–14: a successor
  must requalify new dependencies; finite data do not establish structural zeros
  or physical preservation. The present work changes acquisition rather than
  claiming to reproduce that manuscript's protected-reset apparatus.

Both manuscripts explicitly separate supplied model assumptions, synthetic
execution, physical qualification, ordinary specialist comparisons, and commerce.
This verifier preserves those boundaries. Measured spectral-CT archives cited by
the ancestor do not document the paired path-exchange operation used here; they
are not substituted for missing physical observations.
