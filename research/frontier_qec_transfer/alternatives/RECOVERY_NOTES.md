# Independent conventional sparse recovery baseline

This is an implementation of established quantum error correction, prepared as
a strong conventional comparison. It is not a new recovery theorem, a physical
experiment, a human labor measurement, or evidence of commercial value.

## Construction

For the ordered code isometry V and error list I, X_q, Y_q, Z_q, form sparse
error images E_i V. Their small Gram matrix must equal C tensor I_K. The code
checks all entries of that condition, including logical off-diagonal entries,
and rejects nonorthonormal encodings rather than normalizing them.

Diagonalize the positive semidefinite overlap matrix C. For each positive
eigenvalue lambda_a and eigenvector u_a, construct

    W_a = sum_i u_ia E_i V / sqrt(lambda_a),     R_a = W_a^dagger.

The standard Knill–Laflamme conditions give W_a^dagger W_b = delta_ab I_K.
Consequently sum_a R_a^dagger R_a is the projector onto the correctable
subspace. Singular overlap matrices are handled by retaining their positive
eigenspace. The unused physical complement is sent to one erasure outcome.
Recovery sums different input branches incoherently and never renormalizes.
Exported rows are direct coefficients, including their conjugation in R_a.

The physical support is compressed to the union of sparse error-image
coordinates. Sparse SciPy products and a small dense overlap eigendecomposition
avoid dense ambient physical operators. All ordinary methods and libraries
were available to the independent candidate as well.

Reference: Emanuel Knill and Raymond Laflamme, *Theory of quantum
error-correcting codes*, Physical Review A 55, 900 (1997),
https://doi.org/10.1103/PhysRevA.55.900;
https://arxiv.org/abs/quant-ph/9604034.

## Independence and evidence

Only the three authorized public files under the evaluator's public directory
were read and copied here. No candidate implementation, private qualification
file or hidden output was read. This source was constructed by an included
assistant as an independently authored conventional algorithm; no human
construction-time or model-inference-cost measurement is claimed.

There was one initial construction and no development repair. The initial
source is retained under `attempts/`; its bytes equal the final frozen source.
`DEVELOPMENT.json` contains visible fixture results only. `FREEZE.json` binds
the final source and public contract before independent qualification.

## Reproduce public development

Use the existing repository resource recorder with a fresh receipt path:

    python3 /absolute/repo/scripts/measure_overnight022.py \
      --receipt /absolute/new-receipt.json -- \
      env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
      python3 -B /absolute/baseline/development.py

The recorded development command passed on Python 3.12.14, NumPy 2.3.5 and
SciPy 1.17.0. The receipt measures the local command and reaped descendants,
not the included assistant's inference, tool transport or complete economic
cost. The finite public fixtures do not establish worst-case performance over
the entire qualified input domain. Numerical rank decisions retain the
contract's well-conditioned, double-precision qualification boundary.
