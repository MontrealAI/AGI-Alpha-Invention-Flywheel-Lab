# Operate and reproduce the microscopy construction

This companion turns public microscopy images into inspectable instance masks,
counts and measurements in pixels. It also tests whether one supplied way of
using construction experience beats an ordinary method given the same records.
The [results](RESULTS.md) report those as separate questions.

Start with the [practical brief](CONSTRUCTION_BRIEF.md) for the purpose and
acceptance contract, or the [opportunity comparison](OPPORTUNITY.md) for the
alternatives considered. This is a research instrument and an exposed-data
reproduction. New images require their own suitability and acceptance evidence.

## Choose the operation you need

| Purpose | What executes | What a successful command establishes |
| --- | --- | --- |
| Check the installation | Tiny generated fixture | The classical command interface works; no public-data scientific claim. |
| Inspect the released evidence | Archive identity check and extraction | The complete retained file inventory matches its manifest. |
| Verify the scientific report | Independent reference decoding, scoring and full classical replay | The reported predictions, denominators, recipe selections and acceptance decisions follow from the specified inputs. Neural inference is not rerun by this checker. |
| Reproduce the classical comparison | 2,400 donor recipe-field evaluations, six calibration searches and saved predictions | A new execution of the already exposed frozen comparison. |
| Reproduce the pretrained alternative | The fixed CellposeDINO model on all 116 registered fields | A separate execution of an established learned model; it is outside the six equal-content arms. |
| Use an instrument on your images | Raw-channel segmentation and pixel measurements | Actual operation and inspectable outputs; accuracy on a new assay is not inferred. |

## 1. Prepare the classical environment

Use **Python 3.12.14** for the registered scientific reproduction. The four
scientific dependencies are pinned in `requirements.txt`. Choose an absolute
work directory outside the repository or extracted edition. Commands below run
from this `construction` directory; replace the example work path once.

```sh
export LTB_WORK=/absolute/new/learning-to-build-work
mkdir -p "$LTB_WORK"
python3.12 -m venv "$LTB_WORK/classical-venv"
"$LTB_WORK/classical-venv/bin/python" -m pip install -r requirements.txt

"$LTB_WORK/classical-venv/bin/python" -B run.py \
  --fixture --output "$LTB_WORK/fixture"
```

The fixture is deliberately small and generated. Do not report its completion
as microscopy qualification. Every operation uses a new output directory unless
the command explicitly supports resuming an identified run.

## 2. Acquire the pinned public inputs and inspect retained evidence

```sh
"$LTB_WORK/classical-venv/bin/python" -B data.py fetch \
  --cache "$LTB_WORK/data" --output "$LTB_WORK/FETCH.json"
"$LTB_WORK/classical-venv/bin/python" -B evidence.py \
  --extract "$LTB_WORK/retained"
```

The five public archives total **87,775,682 bytes**. Their SHA-256 identities,
source URLs and cohort rules are fixed in the effective protocol. Acquisition
reuses matching bytes and rejects mismatches. The evidence archive contains
generated masks, measurements, choices, source identities, failure records and
execution receipts. It does not redistribute those public input archives or
third-party learned weights.

The retained evidence is a **new reproduction of a previously exposed
comparison**. The original registered sources and amendments were recovered;
the earlier session's unpushed full result package was not. This edition does
not present new files as that missing historical package. Read
`retained/REPRODUCTION.json` for the exact provenance and cost boundaries.

## 3. Independently verify the scientific report

```sh
"$LTB_WORK/classical-venv/bin/python" -B test_integrity.py -v
"$LTB_WORK/classical-venv/bin/python" -O -B test_integrity.py -v
"$LTB_WORK/classical-venv/bin/python" -B test_evidence.py -v

"$LTB_WORK/classical-venv/bin/python" -B check.py \
  --cache "$LTB_WORK/data" \
  --classical "$LTB_WORK/retained/classical" \
  --incumbent "$LTB_WORK/retained/incumbent" \
  --output "$LTB_WORK/INDEPENDENT_CHECK.json"
```

The default checker regenerates all 2,400 donor predictions and every classical
calibration search as well as the saved classical masks. Its reference decoder,
metrics, aggregate calculations and acceptance logic are separate from the
producer. It pins the registered programs, protocols, recipe bank, input bytes
and numeric runtime. The neural section independently scores all 116 saved
predictions, reconciles their measurements and checks the completion inventory;
it does **not** establish model execution merely by checking hashes. The actual
116-field run and separately observed raw-image operation supply that different
evidence.

`--saved-masks-only` omits donor and calibration regeneration. Its report is
explicitly `LIMITED`; use the default for full classical verification. Neither
mode certifies historical elapsed time, an independent institution's acceptance,
commercial permission, new-domain performance or demand.

An explicit projection in the retained record separates the canonical completed
classical checkpoint from unexplained residual attempt-file copies observed
after completion. The original observed files and their mapping are preserved,
their matching bytes are checked, and their cause is not asserted. No scores or
measured costs are edited to make the checkpoint pass. The raw-tree inventory
rejection is retained alongside the projected-tree verification.

## 4. Run the classical comparison yourself

```sh
"$LTB_WORK/classical-venv/bin/python" -B run.py \
  --cache "$LTB_WORK/data" --output "$LTB_WORK/classical-run" \
  --stop-after donor

"$LTB_WORK/classical-venv/bin/python" -B run.py \
  --cache "$LTB_WORK/data" --output "$LTB_WORK/classical-run" --resume

"$LTB_WORK/classical-venv/bin/python" -B check.py \
  --cache "$LTB_WORK/data" --classical "$LTB_WORK/classical-run" \
  --output "$LTB_WORK/CLASSICAL_CHECK.json"
```

The first command deliberately stops at a completed checkpoint. The second
resumes that exact source and data contract. Without `--stop-after`, one command
executes all stages. `RUN_STATE.json` records attempts, stage costs and file
identities; `STATUS.json` distinguishes completed execution from scientific
qualification. Inspect `RESULTS.json`, per-field CSVs and the actual masks.

All six builders may evaluate the complete 24-recipe bank. A ranked search stops
early only if a recipe meets every calibration criterion. The greedy-coverage
and empirical-order arms receive exactly the same donor records. A failure to
find an acceptable recipe is retained; the experiment does not shrink the
ordinary builder's budget to manufacture an advantage.

## 5. Restore and use the pretrained specialist

Follow [INCUMBENT_SETUP.md](INCUMBENT_SETUP.md). It gives the exact CPU setup,
343,599,997-byte model identity, separate package/model cache, research-rights
scope and raw-image command. Complete and seal all six classical choices before
running its full registered comparison. Its setup preflight performs no image
inference; the subsequent `incumbent.py run` performs the 116-field comparison.

No GPU, paid API or new financial account is needed. The measured reproduction
uses a dedicated exact-version virtual environment that reuses selected system
packages; it is not described as an entirely isolated or completely frozen
binary/transitive environment. The installer defaults to an isolated environment
and records the environment actually used.

The one-field `release_operate.py` helper requires `--origin candidate` for a
candidate-package gate or `--origin downloaded-release` after an actual release
download. It chooses the first official test field without consulting scores,
operates on raw DNA, and compares the generated mask with the retained bytes.
That operation verifies packaging and the interface on an exposed field; it is
not another scientific holdout.

## 6. Operate an emitted classical instrument

The retained source instrument is under `retained/classical/source/instrument`.
It remains unqualified under the complete source contract. A successful command
does not change that verdict.

```sh
"$LTB_WORK/classical-venv/bin/python" -B \
  "$LTB_WORK/retained/classical/source/instrument/instrument.py" \
  --recipe "$LTB_WORK/retained/classical/source/instrument/instrument.json" \
  --dna /absolute/inputs/dna.tif \
  --output "$LTB_WORK/classical-nucleus-operation"
```

The corresponding successor instruments live under
`retained/classical/successor/ARM/instrument`. Whole-cell operation also requires
`--actin`. These emitted classical programs expect two-dimensional scalar
observations. For an RGB input, first use the registered observation adapter on
each channel:

```sh
"$LTB_WORK/classical-venv/bin/python" -B data.py canonicalize \
  --input /absolute/inputs/raw-dna.tif --output "$LTB_WORK/scalar-dna.tif"
"$LTB_WORK/classical-venv/bin/python" -B data.py canonicalize \
  --input /absolute/inputs/raw-actin.tif --output "$LTB_WORK/scalar-actin.tif"
```

Scalar observations are unchanged. RGB-to-L uses the frozen Pillow conversion
and records a sidecar receipt; it is generally lossy and does not recover
physical radiometry. The pretrained operator applies that adapter internally.
No reference annotation is passed to either ordinary operator.

## Failure handling and maintenance

| Observed condition | Response |
| --- | --- |
| Input, source, model or runtime hash/version differs | Stop that attempt and preserve its receipt. Acquire the specified bytes or define a separate future protocol; do not weaken the current identity checks. |
| Interrupted classical run | Resume the same output and source contract. Incomplete attempts and unmeasured interruption work remain visible. |
| Interrupted pretrained run | Use `--resume` with the same cache, weights and output. Independently check the completed masks and metrics; resume's identity checks alone do not recompute scientific scores. |
| Results exist but the pretrained completion seal is absent | Treat the output as incomplete. Preserve it and investigate; do not manufacture the missing completion file. |
| Completed output | Resume must be idempotent and create no new predictions. Keep before/after identity receipts separate from the immutable result tree. |
| Unexpected files or directories | Preserve the observed tree and investigate. Any projection used for checking must explicitly retain and map the omitted bytes. |
| Earlier boolean-outline or RGB-format failure | Run `replay_historical_failures.py --cache PATH --output NEW_JSON` to reproduce the focused failure with the preserved source snapshot. This does not reconstruct the unavailable earlier full run or its costs. |
| New assay, annotation convention or dependency | Declare a new acceptance question and freeze changes before confirmation. Keep this version and its adverse results intact. |

The published source contains no signing keys, financial accounts, model API
credentials or user images. Setup and operation logs are retained by the normal
publication workflow, including failures. Actual host billing, total authoring
effort, upstream pretraining and missing historical execution costs remain
unknown. There are no observed customers, transactions or commercial receipts.

## Next decision

The current finite bank is exhausted: another ordering of the same recipes
cannot supply the missing whole-cell boundary method. Preserve the ordinary
comparison and the strongest measured practical route. A worthwhile next
experiment must introduce a justified observation, representation or algorithm,
then compare complete alternatives on a genuinely unexposed cohort with the
learning and economic questions stated separately.
