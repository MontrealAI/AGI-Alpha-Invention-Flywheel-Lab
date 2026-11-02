# Stage C HPPC only acquisition experiment

Prospective specification, 2 November 2026. Freeze executable source, exact eligible files, exclusions and evaluation split before scoring. This is a new acquisition hypothesis; it does not revise earlier gates or results. No measurement scores have been used to specify it.

## Information contract

K1 receives only isolated-cell HPPC/MultiSine files, cell identity/chemistry and public protocol metadata. The [primary descriptor](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/91.pdf), Table 2 and Section 3.1, documents `CurrentData`, `VoltageData`, `TempData`, `TimeData`, `StepIndex` and `CycleIndex`, with different logging intervals during pulses and other phases. Verify these fields and the step mapping against actual files; missing or incompatible structure causes an explicit parser abstention.

K1 cannot read separate C/20 voltage, capacity, fitted curves, normalized coordinates, or derived labels. An independent scorer owns those references. Reserve whole MultiSine voltage groups for prediction checks; their imposed currents remain known inputs. Public-data visibility and shared infrastructure limit holdout independence and must be disclosed.

## Extraction and fitting

1. Validate finite, aligned arrays and monotone elapsed time. Resolve the current sign from documented charge/discharge steps and measured transitions; reject ambiguity. Integrate signed discharge current by trapezoids using actual time intervals: `q(t) = integral I_discharge(t) dt / 3600`, in Ah. Include charge pulses negatively. Never substitute sample counts for duration.
2. Establish `q=0` at an evidenced fully charged conditioning endpoint before the HPPC traversal. Missing conditioning evidence leaves absolute charge origin unresolved. Do not derive state of charge from C/20 capacity, nominal ten-percent labels, or the observed partial trace length.
3. Segment complete rests and HPPC pulses using verified flags and current behavior. For rests lasting at least 1,800 seconds, fit the final half with a constant-plus-decaying-exponential relaxation; also retain its final-window mean and slope as an ordinary control. Profile the asymptotic voltage and time constant. An effectively flat likelihood, unresolved drift, or incompatible relaxation fits yields an uncertain anchor rather than an exact OCV value.
4. Fit a nonincreasing piecewise-cubic voltage curve `E(q)` through identified rest anchors. Fit positive one-RC polarization and series-resistance parameters jointly against HPPC pulses, using the curve and integrated charge as inputs. Use pulse transitions for initialization, not a claim of ideal instantaneous resistance. Freeze parameter bounds, regularization, numerical solver and uncertainty construction before evaluation; unresolved parameter directions must propagate to predictions.
5. Export `E(q)`, pulse-response parameters, uncertainty, source identities and the supported charge/temperature envelope. Predict held-out MultiSine voltages and, only after K1 acceptance, module branch currents. Extrapolation outside supported charge is abstention unless a separate prospective model is independently qualified.

## What capacity can mean

An observed traversal from known full conditioning to the specified loaded voltage cutoff identifies **usable charge for that protocol**, subject to current calibration. It does not identify equilibrium or C/20 capacity: polarization can trigger cutoff before the slow-discharge tail is exhausted.

If the HPPC record ends before a verified voltage-cutoff exit, `q_end` is merely traversed charge. A truncated file, timeout or limited charge window cannot establish remaining capacity. Abstain on full-capacity output and any successor requiring it; do not set `Q=q_end`. Retain a partial `E(q)` instrument only with its restricted scope prominently declared.

## Controls and acceptance

Compare (a) strong conventional full C/20 plus HPPC characterization; (b) equal-information HPPC rest-end interpolation and ordinary one-RC fitting; (c) the proposed relaxation/uncertainty method; and (d) no cell-specific retained characterization. Give all appropriate controls identical public metadata, solver access and costs.

The independent scorer aligns curves by absolute discharged Ah from independently verified conditioning, never by truth-derived normalized SOC. Report C/20-reference voltage error, supported fraction of its charge range, capacity interval coverage/abstention, and held-out dynamic voltage errors. C/20 is a measured pseudo-OCV reference, not exact equilibrium truth. Retain the parent 30 mV and comparator-quality gates where applicable; additionally require coverage of at least 80% of the reference charge span for an accepted characterization result. These are experimental thresholds, not safety standards.

## Time and economic gate

Charge actual HPPC duration, conditioning, rests, calibration, fitting, verification, failed attempts and fallback characterization. Report common conditioning separately without omitting it. Withholding C/20 bytes establishes an information comparison, not a guaranteed 50% physical saving. Changed conditioning or acquisition order requires prospective physical validation. A cost advantage remains unresolved until accepted-quality acquisition savings survive complete accounting.
