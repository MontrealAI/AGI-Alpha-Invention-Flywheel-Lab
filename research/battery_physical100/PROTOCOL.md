# Frozen physical-laboratory endpoint screening experiment

## Purpose and scope

Build an offline CLI that turns the first 100 physical laboratory cycles into predictions and an uncertainty-aware screening result for later declared laboratory endpoints. The source is the March 2026 Microsoft/LF Energy controlled-cycling release, not field batteries. No actual testing will be stopped, no equipment controlled and no revenue claimed. This tests useful same-model replicate prediction, not new chemistry/manufacturer/protocol generalization, tab-design causality, autonomous discovery or a superior learning algorithm.

Base source snapshot and all payload hashes, sizes, metadata paths/blob identities and license identity are in `manifest.json`. There are 27 cells from nine model/tab groups. Outcome-blind lexicographic IDs within each group designate one train, one calibration and one test cell. A0067 is exposed development and belongs to train. No other payload had been inspected when this protocol was written. Nine test cells are the independent evaluation unit; rows and cycles are not independent examples.

## Outcome and observation contract

- Prediction sees only cycles 1 through 100. The CSV reader stops at the first later cycle; future voltage, capacity, flags and target availability do not influence features or screening. A full file and its prefix must give identical predictions.
- Reference capacity is the median accepted full discharge in cycles 1–10, requiring at least eight. Prefix eligibility requires at least 95 valid cycles of 1–100 and exact cycles 10 and 100. Never fill missing capacities with future measurements.
- Endpoints are the **actual reported terminal discharge capacities at exact cycles 500 and 1000**, divided by the reference. Missing or rejected endpoint measurement stays a failed/unscorable target in the nine-cell denominator. Do not substitute a nearby cycle.
- These endpoints are protocol-specific. In development, 500 is a regular cycling discharge (step22), while1000 is a post-diagnostic discharge (step57). Diagnostic preparation/rest may differ. No uniform-protocol degradation kinetics or intrinsic state-of-health claim is made. Training peers and validation use the same released full test schedule, and each endpoint has its own forecast and calibration width.
- Temperature35C and nominal1C are publisher filename metadata; no measured temperature field exists. Unexpected/new schedules, unknown groups and field use require continued testing. An offline user must confirm the intended protocol; the software cannot certify it.

## Measurement extraction fixed before remaining payload inspection

Preserve contiguous (cycle,step) episodes, never concatenate repeated step IDs. Enforce finite quantities, nonnegative chronological time, integral nonnegative cycle/step indices and nondecreasing cycles. Repeated equal timestamps add zero integrated charge; inconsistent measurements remain visible through capacity/current checks.

A candidate full discharge has negative current reaching at least0.5 nominal C and a terminal-minus-initial reported capacity increment at least20% of rated Ah. It must have at least three samples, initial accumulated capacity≤0.5% of nominal, and≥98% of elapsed time at average0.85–1.15 nominal C. Reject positive current>0.05C, voltage outside2.5–4.6V, internal step-capacity resets beyond0.0002Ah, negative capacity, gaps>180s, missing full voltage span(start<4.0V or end>3.5V), or terminal capacity>1.3×nominal.

Compare trapezoidal current integration **within the episode only** with reported terminal-minus-initial capacity; reject discrepancy>max(0.5%nominal,1%reported increment). The output uses the instrument's terminal capacity, with initial capacity separately reported. This is internal sensor consistency, not independent metrology: cycler capacity may itself derive from current integration. No physical measurement-accuracy guarantee follows.

Each cycle must contain exactly one accepted candidate full discharge. Missing/multiple/invalid episodes remain flags. Low-current RPTs, pulses and rest are not silently relabeled1C cycles. Voltage anomalies outside qualifying discharge episodes are flagged, not removed to improve forecast metrics. All source cells, failed acquisitions and bad/aborted runs remain in declared denominators.

## Locked ordinary methods

Primary, fixed without looking at test outcomes: **adjusted same-model peer**, own cycles91–100 median retention plus the training peer's endpoint retention minus its own cycles91–100 median. This is ordinary reuse, not an invention claim.

Controls use identical observation prefixes and published training labels: unadjusted same-model peer; persistence; linear fit over accepted cycles51–100; nonnegative sqrt-cycle plus linear-cycle loss fitted to prefix; and a fixed ridge(alpha10, unpenalized intercept) with standardized early capacity and discharge-voltage features. Curve features adapt the known Severson ΔQ100−10(V) variance idea using64 points within3.2–4.1V, only when both measured curves cover that range. This predicts endpoint capacity ratios, not the original paper's LFP cycle-life target; no imported accuracy claim. Missing curve features yield an explicit unavailable control, never invented values. No model selection or hyperparameter search uses calibration/test results. Train leave-one-cell-out is not used to pretend a same-model peer exists after removing the only training cell of that group.

Strong conventional extraction is separately checked by unmodified PyProBE-Data2.6.1 `RawData.capacity` on accepted contiguous episodes. BDF positive discharge accumulation is mapped explicitly to signed net capacity. Global PyProBE cycle inference is inapplicable to the nested RPT schedule and is not used. Conventional analysis can reproduce the same result; its machine-speed automation is not slowed to human time. No measured AI-versus-human productivity comparison is asserted.

## Calibration, abstention and screening

For each method and endpoint, width is the **maximum absolute error across all nine calibration cells**. If fewer than nine usable calibrations exist, that method/endpoint has no supported interval and must continue testing. This is a small empirical residual range, not a distribution-free coverage guarantee: stratified fixed cells and correlated groups need not be exchangeable. No95% finite-sample claim is made.

Unknown model group, an unsupported prefix, or early retention shifted more than10percentage points from the same-model training peer produces CONTINUE_TESTING. Predictions are not clipped to improve errors. For a declared screening threshold of80% capacity ratio, lower bound≥80% gives SCREEN_PASS, upper bound<80% gives SCREEN_FAIL, otherwise CONTINUE_TESTING. These labels are engineering triage, not safety, warranty, qualification or permission to halt mandatory tests.

## Sealed execution and acceptance

The executable pipeline fits train, computes calibration widths, saves the frozen model, generates predictions for all nine test prefixes, and saves/hash-seals those predictions **before** parsing test endpoint labels. The raw payload is downloaded/hash-verified first, but future rows are not given to prediction. No human/agent changes code or models based on test outcomes. Correctness repairs discovered before testing may be recorded prospectively; once test targets are opened, preserve the original verdict and use a separately identified future study for changed scientific rules.

For this finite screening demonstration, assess endpoints separately and jointly: all nine test cells eligible and both endpoints measurable; primary maximum absolute endpoint error≤5percentage points; all18 test endpoint observations inside primary calibration ranges; at least three of nine cells have a decisive cycle1000 screening outcome; zero incorrect decisive screening outcomes. This is an authored pilot acceptance contract, not an actual buyer's signed requirement. Always publish per-cell errors, every comparator, coverage, interval widths, abstention and attrition, including failure.

Only if all gates pass, report a **counterfactual** opportunity to screen before later cycles, with the exact test denominator and restrictions. The historical laboratory work already occurred; no actual cycles, elapsed laboratory time, money or sales were saved here. There is no novel enabling advantage unless compared with the complete strong conventional route; ordinary parity or superiority must remain visible.

## Costs and retention

Run on included tools and standard public CPU GitHub Actions. Report measured bytes, requests, elapsed/CPU time, versions and source identity. Full development, model-session, actual billing, acquisition/support and deployment costs remain unknown, not zero. Download/process one raw file at a time where possible; retain compact derived cycle summaries, model, predictions, test results and a readable report, not unnecessary raw data. No native financial account, ledger, private data, payment, outreach, merge or release action is part of this study.

The CLI requires --confirm-matched-lab-protocol before returning screening results. Missing target endpoints remain explicitly unavailable and cannot contribute to calibration, scoring, or acceptance. Cycle0 is never part of first1–100 model features.
