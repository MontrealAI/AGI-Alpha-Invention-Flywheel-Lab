# Recovery construction: frozen development submission

## Delivered behavior

`recovery.py` exports `Recovery(n, codewords)`, `encode(logical)`,
`recover(branches)`, and `kraus()` with the public contract's conventions.
The constructor checks orthonormality and the single-qubit
Knill-Laflamme conditions. A common error-Gram eigendecomposition constructs
independent syndrome directions, including nonorthogonal and rank-deficient
error sectors. The exported rows already contain conjugated bra coefficients.
Encoding preserves the supplied scale. Recovery sums branch density matrices
without coherent branch addition or normalization, and reports the remaining
trace as erasure.

The implementation uses sparse physical error columns and dense arrays only
on active coordinates. It never constructs a dense full-physical-space square
matrix.

## Development evidence

- Public `development_example`: passed.
- Reproducible suite: 1,100 channel/state/qubit combinations across six cases.
- Cases: all three supplied fixtures; complex physical and logical basis
  rotations of the seven-qubit and Shor codes; a 20-qubit Shor-plus-ancilla
  case with exactly 4,096 initial nonzero amplitudes.
- Channels: identity, coherent complex unitary, amplitude damping, and random
  complex two- and four-Kraus CPTP channels. Logical norm scales: 0, 0.23,
  1, and 3.1. Every qubit was exercised.
- Five exported-certificate checks covered row orthonormality, completeness
  on the independently generated error span, contraction, fresh-input
  agreement, erasure, coherent correctable/erasure superpositions, branch
  splitting and unitary branch mixing, zero inputs, and copy isolation.
- Seven invalid inputs were rejected, including an orthonormal but
  uncorrectable code.
- Largest logical-density absolute error: 2.22055e-14.
- Largest mass absolute error: 2.30926e-14.
- Logged numerical wall time: 4.396633 seconds.
- Logged process CPU time: 4.391118 seconds.
- Peak measured process RSS: 121212 KiB.

`development_results.json` contains per-case measurements, and
`development_tests.py` reproduces them using fixed seed 41702413. Runs used
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1` with
`CODEX_PRIMARY_RUNTIME_PYTHON`.

There were no failed development attempts and no source repairs. The final
source is identical to the retained initial source. No private qualification
was run or observed. The numerical contract depends on well-conditioned
double-precision rank decisions; no universal singular-threshold decision is
claimed. Inference usage and monetary cost are unknown.

## Freeze

Completion UTC: 2026-11-21T19:13:59.553534+00:00

SHA-256: `f8638af7b2532f8c2161fefe2169bb91788c9fc3a5e3321cf7a05ec717f7c134`

The source, initial copy, and content-addressed final archive are read-only.
No source edits will follow this submission.
