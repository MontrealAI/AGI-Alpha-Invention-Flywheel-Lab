# Independent XCT development review

Reviewed frozen candidate `c78f0a9e3229f779de91701ba5289719be9c3e40d1acf75d33be22ca1ce42f73` and protocol `e475f6f1b8ec9457fe2cc6cd14300da2b2097b441aecaf5e1a2c6915b81ad2ac`. The reviewer read source and development artifacts and ran a separately authored checker without importing or modifying the candidate. No protected cases were inspected. Shared SciPy/NumPy and host provide procedural separation, not independent certification.

**Decision:** no consequential implementation defect established in the protocol's narrow numerical pair-separation claim. The attempted connection from pair rejection to useful fixed-feature uncertainty reduction is falsified on these real development measurements. No useful-service or industrial qualification follows.

| Question | Executed or source evidence | Result |
|---|---|---|
| Ray and image indexing | Primary dataset documentation specifies `A*x=m(:)` with MATLAB column-major image/sinogram order. Independent checker uses 82-ray blocks per view and F-order ROI vectorization. | No transpose/ray indexing defect established. |
| Initial witness validity | Independent multiplication against source `A,m`, frozen affine calibration and identical residual envelopes. | Both feasible within declared numerical tolerance; ROI range [0,0.17440665865456]. |
| Additional selected measurement | 75-degree view rejects both saved initial witness images. Yet independently checked replacement images remain feasible for all seven admitted views. | Specific pair is excluded, while the same ROI extrema remain possible. |
| Actual fixed-feature consequence | Initial, selected and uniform interval widths agree within 1e-10. Selected difference is negative 5.55e-17 due to rounding; uniform reduction is zero. | No material ROI range reduction established. |
| Full120-view uncertainty | Two independently configured ordinary LPs timed out without primal solution. | UNKNOWN. No conclusion that the full scan cannot identify the feature. |
| Calibration and heldout independence | Affine contrast fit and detector maxima use all120 measured views and the full1200-view FBP of this same object. | Exposed development calibration only; no out-of-sample error coverage or fewer-view cost saving established. |
| Feature meaning | The primary data are a 2D walnut slice; the feature is mean coarse-pixel attenuation in a6x6 ROI. Pixel width is0.513mm. | No pore-size, industrial defect, mechanical integrity or buyer acceptance endpoint. |
| Conventional alternatives | The same ordinary LP produces the witness capability. Generic anisotropic-TV LP timed out45s; a specialized proximal/primal-dual TV implementation was not qualified. | Retain ordinary LP; TV outcome UNKNOWN, not candidate superiority. |

## Why pair separation is mathematically valid but insufficient

If a detector's two predicted responses differ by more than twice its error envelope, no response can lie within the envelope of both predictions. That triangle-inequality certificate is valid within the fitted deterministic set. It does not say that all other images with those feature means are excluded. Here the saved selected-view lower and upper replacements are concrete counterexamples: their ROI means remain0 and0.17440665865456 and their maximum constraint excesses are6.45e-14 and5.02e-14.

**Typed next construction constraint:** `FEATURE_RANGE_REDUCTION`. Hold the ROI, baseline obligations, calibration set and acquisition accounting fixed. A selected measurement or measurement packet must reduce the worst-case feasible ROI range after reoptimization, against competent ordinary selection and uniform acquisition. A score based on a single pair's global detector difference cannot approve the feature outcome. Dual-supported measurement pruning is a justified next causal approach if its bound is independently checked and the same full LP remains a control. This review does not supply that repair or alter the candidate.

## Calibration limits

The residual envelope makes its fitted reference feasible by construction. It is an empirical model-discrepancy allowance for this object, not a detector-noise confidence bound or a guarantee that unmodelled physics is covered. Both calibration acquisitions and their costs must be charged or independently justified for reuse before a sparse-acquisition economic claim. A future protected cohort needs a defensible externally fixed calibration rule. It cannot keep these exposed angles protected retrospectively.

An affine fit is an expressly declared mapping between the full-view image's contrast and the coarse forward model. This review did not establish a ray-scale error from that mapping; nor did it independently establish its physical correctness. The numerical witness claim remains conditional on it.

## Preserved resource failure

`independent_review.py` requested42s for each full120 LP. Actual solver wall times were60.53s and54.76s, and both returned time-limit status with `primal_status=None`. The total receipt reports115.70s wall,116.258 CPU-seconds and667452KiB peak RSS. The configured process limits were110/115 CPU-seconds; the measured receipt exceeded those configured limits. These are preserved actual outcomes, not assumed compliance with a requested limit. No full120 primal or inequality-dual certificate was returned. The construction owner was notified before starting a separately allocated longer solve.

The review source and receipt remain in this directory. Re-running requires a fresh output directory or copy because original results are not overwritten. This review consumes no protected confirmation error budget and provides no commercial or physical success claim.
