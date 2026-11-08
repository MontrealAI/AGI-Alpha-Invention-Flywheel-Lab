# Restore and operate the fixed pretrained alternative

This is the separately registered **CellposeDINO practical alternative**, using
the existing `cpdino-vitb` learned weights. It is outside the six classical
recipe arms; their primary comparison uses the same donor records. Successful
operation does not demonstrate that the local
construction procedure learned a superior method.

## Install the exact registered CPU environment

Use a POSIX environment, **Python 3.12.14**, and new absolute paths outside the
repository or extracted source edition. The installer creates an isolated
virtual environment by default; an existing virtual environment can also be
verified and completed.
Acquire the five public microscopy archives through `data.py fetch` or reuse an
already verified data cache. The installer never downloads the microscopy data
again.

From this construction directory:

```sh
python3.12 setup_incumbent.py \
  --venv /absolute/work/incumbent-venv \
  --cache /absolute/work/incumbent-assets \
  --output /absolute/work/incumbent-setup-001 \
  --data-cache /absolute/work/microscopy-data
```

The package/model cache is separate from the microscopy data cache. Required
public inputs are the registered Cellpose 4.2.1.1 wheel, the **tar.gz** archive of
DINOv3 commit `6876159a11b4df116f30f667f8c9888617df0751`, and the 343,599,997-byte
`cpdino-vitb` model at the frozen Hugging Face revision. URLs and SHA-256 values
are in the installer and original protocol. The ZIP representation of the same
DINOv3 commit has different bytes and does not satisfy the registered archive
hash. The installer verifies downloaded or reused bytes and fails on any
mismatch. Neither third-party source nor learned weights are redistributed in
this edition.

`requirements-incumbent.txt` pins all 19 runtime packages named in the original
registration, including `torch==2.15.0+cpu` and
`torchvision==0.29.2+cpu`. Setup verifies their exact versions, the Python version,
the original implementation/protocol bindings, and the aggregate Python-source
hashes for Cellpose and DINOv3. Its model-loading preflight checks that every
learned tensor loaded, permits only the two registered nonlearned compatibility
scalars, uses CPU float32, and performs no image inference. With `--data-cache`,
it also checks the archive identities and registered cohort membership using
metadata, without decoding public image pixels.

Require `SETUP.json` status `READY_FOR_REPRODUCTION`, `CONTRACT.json` status
`PASS`, and the no-inference `PREFLIGHT.json`. Setup records command logs,
download identities, measured setup/child CPU and wall time, its own source,
and a pip report. Transitive dependencies not named in the original registration
are recorded by pip rather than retrospectively described as preregistered.
The recorded new reproduction used an existing dedicated virtual environment
created with `--system-site-packages`, reusing the exact available NumPy, SciPy
and Pillow packages. Its actual `pyvenv.cfg` and pip report are retained. That
environment was not isolated from system packages. These checks establish the
stated versions and Python-source subset, not identity of every transitive
dependency, binary build or host toolchain.

A separate installer validation also created a new environment with
`include-system-site-packages = false` and passed the same exact-version,
source/model and no-inference contract checks. That validates the installer's
default isolated route. The 116-field reproduction retains its own original
environment identity; the separate setup check does not relabel that run.

Keep the environment, model cache and setup receipts outside the source edition.
When run from this repository's canonical `docs/learning-to-build-v1.1.0`
checkout, the installer protects the entire repository. For an extracted source
package, it protects the extracted edition even if that directory happens to
sit inside an unrelated enclosing Git workspace. Resolved symlinks into the
protected source are rejected. `test_setup.py` checks these boundaries without
installing packages or performing inference.

To recheck a completed environment, use `--skip-install` with a **new** setup
output directory. Verified cached downloads are reused. A failed attempt keeps
its receipt, logs and any partial download; inspect and preserve that evidence
before making a separate attempt. Do not weaken a version or hash check to make
an installation pass.

## Reproduce the frozen comparison

The original protocol requires all six primary construction choices to be saved
before this alternative is run. Complete that step first. A later repetition is
a **new reproduction of an already exposed comparison**, not recovery of the
original missing package or a fresh holdout experiment.

```sh
/absolute/work/incumbent-venv/bin/python incumbent.py run \
  --weights /absolute/work/incumbent-assets/cpdino-vitb \
  --cache /absolute/work/microscopy-data \
  --output /absolute/work/incumbent-reproduction
```

The frozen implementation uses one PyTorch intra-operation thread and one
inter-operation thread on CPU. It evaluates the registered 50 source-validation,
50 source-test, four successor-calibration and 12 successor-test fields, without
training or parameter selection. It preserves every mask, per-field receipt,
measurement, registered acceptance decision and measured session cost. Reference
annotations enter scoring after prediction; they are not predictor inputs.

To resume the same interrupted output, repeat that command with `--resume`.
A completed output must return `ALREADY_COMPLETE`, with zero new predictions and
an unchanged completion tree. The completion seal checks saved-file identity;
independent scientific checking is a separate task.

## Use the raw-image operator

```sh
/absolute/work/incumbent-venv/bin/python incumbent.py operate \
  --task nuclei \
  --weights /absolute/work/incumbent-assets/cpdino-vitb \
  --dna /absolute/inputs/dna.tif \
  --output /absolute/work/nucleus-operation
```

This writes `labels.png`, `measurements.csv` and `OPERATION.json`. Measurements
use pixels; physical area requires separately established calibration. For the
whole-cell task, supply `--task cells` and `--actin /absolute/inputs/actin.tif` in
addition to DNA. That command's ability to execute does not establish that the
whole-cell acceptance contract passed. Supplied RGB observations use the
registered Pillow RGB-to-L projection, which is generally lossy; scalar inputs
are unchanged. The operator needs no reference mask and reports no accuracy
claim for newly supplied images.

`release_operate.py` is the package-operation helper: it chooses the first
official source-test field, operates on its raw DNA channel and checks the saved
prediction bytes. Its required `--origin` flag distinguishes `candidate` from
`downloaded-release`. Use `--origin candidate` for an extracted package before
publication; use `--origin downloaded-release` only after verifying an actual
downloaded release. Keep the corresponding setup and operation receipts in
either mode. Operating that already exposed field is an interface and
reproducibility check, not new scientific confirmation.

```sh
/absolute/work/incumbent-venv/bin/python release_operate.py \
  --origin candidate \
  --cache /absolute/work/microscopy-data \
  --weights /absolute/work/incumbent-assets/cpdino-vitb \
  --incumbent-evidence /absolute/work/incumbent-reproduction \
  --output /absolute/work/candidate-operation
```

## Scope and rights

The frozen result remains a research operation of an established pretrained
method. Possible pretraining overlap with the evaluation datasets is unknown and
has not been excluded. No new image acquisition, participating laboratory,
customer acceptance, revenue or profit follows from a successful run. Upstream
training, authoring and actual host billing are outside the measured process
telemetry and remain unknown, not zero.

The original rights record distinguishes BSD-3-Clause Cellpose code and model
card metadata, documented CC-BY-NC training data, and the separate custom DINOv3
terms. **Commercial permissions are not established by this edition.** Consult
the exact upstream terms for the intended use; installation and research
operation do not grant additional rights.
