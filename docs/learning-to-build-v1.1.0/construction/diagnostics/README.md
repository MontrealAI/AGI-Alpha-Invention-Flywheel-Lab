# Why the six policies converged — and which component to investigate

These two diagnostics explain a **negative, already exposed comparison**. They
do not replace its registration or results. The six arms are deterministic
construction policies over a supplied finite recipe grammar, not six separately
prompted language models.

## What was frozen and executed

`PREREGISTRATION.json` was frozen at **2026-11-08 00:09:29 UTC**, before either
diagnostic executed. `FREEZE.json` records its identity. It binds the exact
diagnostic program, unchanged producer and checker source, original protocol,
all six retained calibration tables/construction summaries, order table, public
image archives and numeric runtime. The original outcomes and order tables had
already been inspected; this is a prospective diagnostic implementation, not a
blinded or fresh confirmation.

Only the four BBBC007 calibration fields were decoded: `A9/A9 p10`, `A9/A9 p5`,
`A9/A9 p7` and `A9/A9 p9`. No target test pixels were decoded. Recipe **r12** was
fixed from the original experiment; no new recipe selection or parameter tuning
was performed. Original thresholds, cohorts, source and raw outputs are unchanged.

## 1. Order intervention: a shared bank with no acceptable candidate

The competing explanations were identical effective ordering, the absence of
an acceptable candidate, a change caused by privileged artifact execution, or
a selector/output-handling defect. The diagnostic first compared every
recipe–field prediction hash and scientific metric across the six original,
separately executed arms. All **96 rows per arm** matched. There were **four
distinct original orders**.

The unchanged `builder.construct` was then called 33 times with the six
observed order/settings, reversed expert order, lexical and reverse lexical
order, and all 24 cyclic shifts of the expert order. These comprise **30 unique
orders**. Only its expensive `builder.evaluate` boundary was replaced in memory
by an explicitly labeled adapter returning frozen per-candidate calibration
scores. Registered files were not edited. This is a **cached-score control-flow
replay**, not new image inference or an execution of retained artifacts.

All **33** calls exhausted **24** candidates, making **792 cached evaluator
calls**, and selected **r12**. All six original selection/count/quality endpoints
were reproduced. No candidate in the bank passed calibration; the highest
boundary F1 was **0.250398**, against the unchanged **0.60** requirement.

The mechanism is therefore specific and testable: a changed order cannot find
an acceptable candidate when none exists in this bank. Exhaustion exposes the
same full set to the same fallback ranking. This explains convergence within
this implementation. It does not show that the task itself is impossible or
that a stronger constructor must converge. The primary accepted-prefix saving
remains **zero candidate evaluations**.

## 2. Component intervention: foreground recovery is the better next lead

The four conditions call the existing `instrument.segment_cells` with fixed
r12 and explicit seed/foreground arguments. Every resulting mask is scored by
both `builder.score_masks` and the separately implemented `check.score`; the
two implementations agree. This is implementation diversity within the project,
not an external audit.

| Calibration condition | Boundary F1 | Foreground Dice | Count error | Numerical calibration gate |
| --- | ---: | ---: | ---: | --- |
| Raw DNA seeds + raw actin branch | 0.250398 | 0.850357 | 0.086298 | Fail |
| Reference nuclei + raw actin branch | 0.195353 | 0.829797 | 0.111399 | Fail |
| Raw DNA seeds + reference foreground | 0.615828 | 0.999903 | 0.090194 | Pass, reference-assisted diagnostic only |
| Reference nuclei + reference foreground | 0.714909 | 0.999903 | 0.165064 | Pass, reference-assisted diagnostic only |

Every field is boundary-bearing, so the all-field and boundary-bearing means
are identical. The gate is the original cohort-level gate: the reference-
foreground condition's `A9/A9 p5` field scores 0.599892 boundary F1. A passing
cohort does not mean every individual field exceeds 0.60.

Replacing foreground alone raises mean boundary F1 by **0.365430**, while
replacing seeds alone lowers it by **0.055045**. The combined change raises it
by **0.464511**. The mean boundary interaction contrast
`both − seeds − foreground + baseline` is **0.154126**.

This favors investigating foreground recovery before a seeds-only repair.
It does not prove that better nuclei are intrinsically harmful. The existing
raw-foreground branch unions its mask with whichever seeds it receives; a seed
intervention can also change that foreground. These are exact software-branch
interventions on four exposed fields, not isolated biological causal effects
or a population estimate. Nearly perfect reference-foreground Dice is expected
when the reference supplies that foreground; it is not evidence of a successful
raw-input construction.

### Controls that passed before interpretation

The raw/raw condition reproduced all four archived r12 calibration prediction
hashes and scientific metric vectors. It also matched a new execution of the
unchanged `builder.evaluate(..., oracle=False)` path, including PNG bytes.

No historical combined-reference calibration output exists. The combined
condition was therefore checked against a **new call to the unchanged producer**,
`builder.evaluate(..., oracle=True)`, on the same four calibration fields. Its
prediction hashes, metrics and PNG bytes matched. That control is not described
as a recovered historical result. The earlier combined-reference **test** output
was not used for the diagnostic.

There were **24 actual segmentations**: 16 component calls plus eight explicit
producer controls. Identical control predictions still incurred execution cost.
The 16 component predictions also received separately implemented rescoring.

## Reproduce and verify

Use the existing construction setup: Python **3.12.14**, NumPy **2.3.5**,
SciPy **1.17.0**, scikit-image **0.25.2**, and Pillow **13.0.0**. Acquire the
hash-bound public archives using `data.py fetch` and extract the main evidence
archive using `python evidence.py --extract NEW_DIRECTORY`, as described in
`../README.md`.
The classical argument names the canonical `classical` directory in the
extracted evidence, not the original raw tree containing unexplained residuals.

From the `construction` directory:

```sh
python diagnostics/run.py \
  --cache /absolute/path/to/data-cache \
  --classical /absolute/path/to/extracted-evidence/classical \
  --output /absolute/new/diagnostic-replay \
  --verify \
  --expected diagnostics/RESULTS.json
```

Successful verification prints `status: COMPLETE`, `order_replays: 33`,
`selected_recipes: ["r12"]`, `segmentation_calls: 24`, and
`expected_numerical_endpoints_verified: true`.

Every invocation requires a new output directory. The verifier binds source,
inputs and runtime, executes both diagnostics, and compares complete numerical
endpoints against `RESULTS.json`. IDs, counts and hashes must match exactly;
floating comparisons use relative tolerance `1e-10` and absolute tolerance
`1e-12`. New runtime measurements are recorded, not forced to equal the original
execution. A mismatch retains `FAILURE.json` and `PROCESS_COST.json`; do not
overwrite a failed run or silently change this registration to fit it.

`OBSERVED_RUN.tar.gz` contains the full first diagnostic output: 137 files,
including all cached replay traces, component/control masks and metrics,
invocation, inventory and timing. `EVIDENCE.json` gives its size and SHA256,
alongside the loose registration, program, results and process-cost identities.
Public raw image archives remain external and hash-bound. The archive contains
only this new diagnostic run; the original experiment remains in its separate
evidence package.

## Cost and conclusions

The initial execution recorded **8.465148 CPU seconds** and **7.058458 wall
seconds** within the instrumented process; process CPU including interpreter
startup was **8.481650 seconds**. CPU can exceed wall time when imported numeric
libraries use multiple threads. The receipt includes hashing, imports, replay,
decoding, all component/control segmentations, scoring and output preparation.
Nested per-condition times are components of this total, not additional costs.

Original donor acquisition, search and failed attempts remain charged in their
original ledger. Their timing was not copied into cached replay rows and must
not be counted again as current inference. Assistant engineering, human
attention, account billing and opportunity costs are unknown; these measurements
do not establish complete-cost savings. No paid model API or new purchase was
used. The first scientific diagnostic attempt completed without failure. A
separate same-author verification then reproduced all endpoints, adding
**8.895572 CPU seconds** and **7.277900 wall seconds**; its receipt is
`REPLAY_VERIFICATION.json`. These are additional execution costs, not a second
independent confirmation. Before freezing the diagnostic, an optional `ruff`
command was unavailable in the shell; source parsing succeeded. That engineering
preflight did not execute image inference, and its duration is unmeasured.

An actionable next hypothesis is a separately frozen ordinary composition:
use the already pinned specialist's raw-input whole-cell mask union as a
foreground proposal for the unchanged r12 DNA-seeded watershed. This diagnostic
does **not** execute or establish that repair; its prospects must be tested
separately. All available cohort cases remain exposed.

The original conclusions stand: the registered classical source and whole-cell
successor remain unqualified, the useful pretrained nucleus route is an existing
specialist, and no fresh retained-method learning advantage is demonstrated.
