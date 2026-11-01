# Focused publication validation — 2026-11-01

Executed on the exact eight unchanged candidate Python sources, using Python 3.12
and the already installed dependencies fingerprinted in `PROVENANCE.json`. No new
software was installed. No paid API, hardware experiment or full performance rerun
was used for publication validation.

- `python -m unittest discover -s . -v`: **5/5 passed** (0.006 seconds).
  Tests: exact class mass; moves/fallback; normalized index contract; constrained
  parity integrity; pool syndrome preservation, deduplication and API mapping.
- `python independent_semantics_oracle.py`: **PASS**. Enumerated six original
  mechanisms and four normalized mechanisms; maximum joint probability difference
  `1.1102230246251565e-16`. Checked XOR merging, distinct logical effects, correlated
  separator cancellation, zero-probability removal/index dimensions, complete toy
  class mass, actual forced-invalid fallback witnesses, and constrained alternatives.
  Expected Stim warning: the toy circuit has errors that flip no detectors.
- Every retained original source/result file matches its immutable archive bytes.
- Pinned upstream revision, circuit hashes, metadata fingerprints and all JSON
  syntax checked locally. Publication manifest hashes every file except itself.

This is a focused mathematical/source check, not full-repository CI, new benchmark
confirmation, a release qualification, or a claim of hardware/latency/economic value.
Historical results remain negative and are not relabeled by these passing tests.
