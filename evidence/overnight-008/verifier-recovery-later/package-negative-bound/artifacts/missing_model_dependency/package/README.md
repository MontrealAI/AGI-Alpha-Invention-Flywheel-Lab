# XCT recovery edition: executed full-view ambiguity construction

This package constructs two nonnegative coarse images compatible with every ray in a real measured 120-view walnut dataset. Their fixed central 6×6-pixel mean attenuation differs by more than the authored 0.005 development threshold. This is a mathematical counterexample to identification under one explicitly declared model; it is not industrial inspection, a physical manufacturing result, a new optimizer, or a commercial offering.

The campaign suffered a scratch-storage loss before later historical XCT sources and witness arrays were published. The public historical v1 review survives under `evidence/overnight-008/xct-independent-v1`. Its lost calibration/source hashes are historical identities, not recovered files. This package is a **new reconstructed model and source edition**, frozen before its new construction, and does not claim an exact replay of those lost bytes. The historical pair-separation failure remains preserved publicly: excluding two old witnesses with an extra angle did not reduce the reoptimized fixed-feature range.

## Inputs, model and physical limits

Hämäläinen, Harhanen, Kallonen, Kujanpää, Niemi and Siltanen, *Tomographic X-ray data of a walnut*, version 1.0.0, DOI [10.5281/zenodo.1254206](https://zenodo.org/records/1254206), CC-BY 4.0. See `DATA_LICENSE.md`, `SOURCES.json` and the preserved primary metadata. No noncommercial CAD data are part of this package.

The source `Data82.mat` provides the nonnegative sparse 9840×6724 ray matrix `A` and 82×120 measured sinogram `m`. Both image and sinogram vectorization follow MATLAB column-major order, as in the source's unexecuted `example.m`. The 2296×2296 uint16 1200-view FBP reference is averaged over 28×28 blocks, divided by65535 and mapped by a clipped affine nonnegative fit to the coarse rays. The newly fitted parameters are `[0.1383073483445313,-0.015937926915817732]`; relative ray residual is 4.53905%. The frozen detector envelope is `1.05*maxabs(A@reference-y across all120 views)+1e-6`, tiled over the angles. The ROI is rows 38:44, columns 38:44, with frozen binary64 coefficient `1/36` on its 36 pixels.

The closed mathematical class is `x>=0` and exact real evaluation of the frozen finite binary64 inputs `abs(A*x-y)<=eps`. The new narrow integer checker adds all binary64 products at common denominator 2^2148. A separate verification-owner checker uses `Fraction`, imports no candidate arithmetic, and checks all original 19680 inequalities. The constructor uses slightly tightened bands only to find interior witnesses; the proof checks the original bands. No uncertain optimality or estimated interval is needed to exhibit a pair.

All 120 views and the 1200-view reference of the same walnut are exposed in calibration. The reference is feasible by construction. This envelope has no independently validated physical coverage and is not a detector-noise confidence interval. A feasible coarse image need not be a physically realizable industrial object. The authored 0.005 threshold is not a customer tolerance or pore-size specification. Retrospective packet compression cannot save the acquisition already consumed. All work is DEVELOPMENT; no protected claim or error-budget reset occurred.

## Actual construction and ordinary control

`construct.py` first executes the ordinary constant-ROI perturbation control with analytic ray margins, the identical full 120 constraints and the same exact checker. Its feasible restricted-family gap is 0.001603362700555123. That smaller restricted-family gap establishes neither full identification nor inability of ordinary methods.

It then executes ordinary diagonally preconditioned PDHG, projecting near the reference while targeting the unchanged ROI mean at reference±0.003. Both endpoints use all rays. The construction is standard convex feasibility and is equally available to a conventional workflow. There is no novelty, autonomous-discovery, policy-improvement or technical-superiority claim. `PROTOCOL.json` was frozen before root agreement and execution; the separate `AUTHORIZATION.json` records that agreement without modifying the protocol.

The new run returned lower mean 0.018552602976608386 and upper mean 0.024552605958438004, exact feasible gap rounded down 0.006000002981829619. Own exact checks returned minimum ray margins 5.88e-7 and 7.19e-8. The run used 7.579 CPU seconds, 7.394 wall seconds and 126092 KiB peak RSS. The separate verification owner independently recomputed all original rays and exact ROI values for the reference and four witnesses using `Fraction`, checked model reconstruction and source identities, and accepted the obstruction. That review took 14.712 CPU seconds inside its own resource accounting. Procedural role separation shares the same host, model and libraries; it is not external certification.

If independently accepted, the same pair is feasible for every subset of these 120 views. Further selection from them cannot establish ROI width≤0.005 under this unchanged class and envelope. This justifies stopping that formulation. A future physical target needs independently justified obligations and calibration coverage; narrowing the envelope after seeing this result would create a new development hypothesis.

## Reproduce from the published package

Requirements are Python 3.12, NumPy 2.3.5 and SciPy 1.17.0 as used here. No installation or paid API call is initiated by the runner. Public raw files are downloaded from fixed primary URLs with exact size and SHA-256 checks; existing local files can be supplied for offline replay. The 17.8MB raw binaries are external inputs rather than Git blobs.

From the repository root, a new online actual replay is:

```bash
python research/xct008/recovery/replay.py --output /tmp/xct-new-construction
```

With previously downloaded raw data, avoid network access:

```bash
python research/xct008/recovery/replay.py --output /tmp/xct-new-offline \
  --data /path/to/Data82.mat --reference /path/to/GroundTruthReconstruction.mat --offline
```

An explicitly proof-only check of existing published arrays is:

```bash
python research/xct008/recovery/replay.py --mode proof \
  --records evidence/overnight-008/xct-recovery/run001 --output /tmp/xct-new-proof
```

`--package` and `--verifier` support other extracted layouts, but all frozen identities must match `PACKAGE_MANIFEST.json`. The default verifier is `verification/xct008_recovery/check_recovery.py` in the same repository. The runner stages source, frozen model and verified data into a new directory, executes the actual constructor, and then invokes that separate checker. Proof-only mode is explicitly labeled and does not claim construction. Existing output directories are refused, failed/partial outputs are preserved, and bounded single-thread numerical execution is used. Trusted fixed-URL acquisition preserves needed proxy/TLS configuration; numerical children use a reduced environment. These limits do not qualify arbitrary downloaded native programs. An outer wrapper must permit the declared child hard limit of 705 CPU seconds and 2 GiB, while the campaign's actual allocation still governs use.

The first runner edition passed an actual fresh-directory offline construction plus separate proof in 24.497 child CPU seconds; proof-only mode passed separately in 15.391 seconds. A deliberately wrong raw input was refused before construction and its partial staging preserved. The first runner source and manifest remain preserved when the network preparation phase is repaired. Later downloaded-public-package tests must be reported separately from these local package checks.

The package has no admitted physical/customer cohort, independent purchase evidence, earned simulated receipts or qualified successor funding. Commercial earnings are 0. CPU timing is not complete monetary cost: model inference, search, recovery, integration, support, physical validation and commercial liabilities remain unpriced. The broader mission is not complete from this useful obstruction.

## Complete ordinary alternatives and provenance

The public dataset already supplies a natural Tikhonov/CG example. Constrained LP, HiGHS simplex/interior-point, natural TV/proximal solvers and ordinary convex feasibility are complete mathematical alternatives when supplied the same model and obligations. Historical timeouts are not evidence of their impossibility or an invention advantage. [SoPlex](https://soplex.zib.de/) supports exact rational LP solution, [VIPR](https://github.com/scipopt/vipr) checks rational certificates, and [VSDP](https://vsdp.github.io/) provides verified numerical optimization techniques; none was executed in this recovery. The ordinary exact-checking primitive is not claimed as an invention. Diagonal primal-dual preconditioning predates this work: Pock and Chambolle, ICCV 2011, [doi:10.1109/ICCV.2011.6126441](https://doi.org/10.1109/ICCV.2011.6126441).

The integration owner suggested the exact-arithmetic repair and feasibility reframing in the previous cycle. These are credited human/team-supplied construction choices. This recovery source is newly developer-written. No system-generated strategy, inherited policy advantage or commercially enabling breakthrough is inferred.
