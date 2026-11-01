# Single-frontier quantum decoder: phase-two construction

This is a **separate public CI build and diagnostic attempt**, not a successful
scientific result. The local attempts never compiled and ran zero phase-two
shots. Their failures remain failures; no causal OOM or CPU-limit diagnosis was
established. See the unchanged preregistration in `FROZEN_PROTOCOL.md`.

## Enabling hypothesis
Retain the existing Tesseract search frontier after a valid goal, rather than
restarting independent searches, to expose competing logical classes within the
same bounded candidate pool. The C++ patch validates syndromes, logical labels,
and costs; deduplicates physical error masks; preserves partial valid lists on
caps; and leaves the legacy first-goal path unchanged. List mode disables
residual-only visited pruning. This does not enumerate every coset or establish
exact class probability, latency superiority, hardware utility, revenue or profit.

## Reproduction and qualification
The scoped workflow runs on ordinary `ubuntu-latest`, read-only repository
permissions, official pinned actions, no persisted checkout credentials, no
secrets/API/model calls, and no artifact or cache uploads. Upstream sources and
dependencies are public HTTPS. TLS verification remains enabled; no truststore
changes, remote Bazel cache or remote execution is enabled.

`ci_build.py` obtains Apache-2.0 quantumlib/tesseract-decoder commit
`838d4f64acc16b5c15adda01302a719400329d4b`, pinned Bazelisk 1.30.0 / Bazel 9.3.1,
and builds the pristine extension before applying `terminal_list.patch` in the
same checkout. The pristine `.so` is copied aside, never replaced with a published
wheel. Modified builds reuse the identical compiler, dependency lock and local
build graph; both extension hashes and the lock comparison are logged.
The C++ candidate-list suite, binding checks and cross-build max-goals=1
regressions gate the diagnostic. A failed test stops execution.

Setup and both builds share a prospective 40-minute ceiling, single-core affinity,
Bazel jobs=1, local memory scheduling512MiB and JVM256MiB. These are build settings,
not decoder performance. The complete job has a 60-minute ceiling. The unchanged
diagnostic uses four fixed development syndromes plus16fresh shots, matched
pristine first-goal pruning-on/pruning-off and modified list pruning-off arms,
beam5,queue200000,one order,64goals, single core,2GiB address space,45s per worker,
and15minutes total. No truth enters decoder policy; no shot is postselected.
No parameter tuning follows a correctness failure or absence of competing classes.

Results are compact job logs/summary only: setup/build receipts, actual tests,
first/final costs and timing aggregates, exact stop reasons, fallback/error counts,
and registered denominators. A workflow badge alone is not scientific success.
Draft/public source is not approved, merged, released or deployed.

## Local failed-attempt lesson
Tried official Bazel8.4.2: rules_python2.3.2 flag_alias incompatible; use pinned9.3.1.
Tried pristine extension then narrower core-only9.3.1 builds: both SIGKILL before
compilation at approximately58.27s/55.77s, child peak269572/266348KiB. Launcher
allowed1400s, RLIMIT_CPU/AS unlimited; kill cause remains unknown. Existing Java
CA path resolved a local PKIX issue without disabling TLS or changing trust.
Further undifferentiated local retries stopped. This CI attempt is independently
registered on an existing authorized public build runner, not a relabeling of
those failures or a new paid service. Host/model costs not observable stay unknown.

## Attribution and novelty boundary
Patch context derives from Google/quantumlib Apache-2.0 Tesseract code; the original
source retains its license and notices. Obtain license at the pinned upstream
checkout (`LICENSE`). The added code/harness is original experimental work.
Tesseract: https://arxiv.org/abs/2503.10988 . List/multi-goal decoding and class
partition sums are prior art, including https://arxiv.org/abs/2512.07057 and
https://arxiv.org/abs/2608.25545 . IonQ implementation was not accessed or used.
The narrow frontier-reuse hypothesis remains untested until executable receipts
establish otherwise. Neither generic list decoding nor a broad novelty claim is
asserted. No vendor worktree, binary, shot archive, private input or credential is
committed here.

## First public CI attempt (failed, retained)
Run41356814542 compiled both variants and passed all six candidate-list C++ tests
and three upstream regressions. Pristine compilation431.07s, modified56.19s.
Python binding tests then failed before importing: `PyObject_ClearManagedDict`
undefined. Upstream MODULE selectsPython3.13 but initial hosted runtime was3.12.
Cross-binary Python checks and diagnostic shots did not run. The next attempt
aligns runtime3.13 with upstream; no kernel or frozen scientific setting changes.
Compact source-bound evidence is in `CI_ATTEMPT_1.json`; full public job logs remain
on GitHub. This research is not an established industry flagship or evidence of
newly economical useful computation or profit.
