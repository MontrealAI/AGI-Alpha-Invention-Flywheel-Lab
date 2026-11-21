# Nondestructive noise identification: development record

The initial source passed all public development checks without a source repair.
This is a construction and public development result, not independent qualification.

## Construction and complete instrument

For each Pauli error E_i and logical basis ket |a>, form B_a[:,i]=E_i|a>.
The exact-code conditions give B_a^dagger B_b=delta_ab G. Diagonalizing the
positive part G=V Lambda V^dagger gives U_a=B_a V Lambda^(-1/2). The columns
of the U_a are mutually orthonormal across both logical and syndrome indices.
Thus every correctable error acts only on a syndrome factor while the logical
factor is retained. No supplied recovery capability was present or used.

For syndrome dimension s, use vectors |i>/sqrt(2s-1), together with
(|i>+z|j>)/sqrt(2(2s-1)) for every i<j and z in {1,-1,i,-i}.
Their outer products sum to identity and span all Hermitian syndrome operators.
The registered branch has direct physical row (U_a v_o)^dagger for logical row a.
There are 2s^2-s outcomes, with one Kraus map per registered outcome.
The erasure flag is implemented by rows of I-P_S, grouped into one classical
outcome. Registered adjoint products sum to P_S and erasure adjoint products to
I-P_S. The optional `apply` method preserves raw subnormalized mass.

Each local Kraus matrix is expanded in I,X,Y,Z. Its corresponding syndrome ket
predicts all outcome probabilities independently of the logical state. Because
the POVM spans the Hermitian syndrome operators, its response matrix attains
the full physically available linear rank. Singular vectors of that response
give the Euclidean identifiable projector, including the normalization direction.

## Estimation

Counts or frequencies are explicitly normalized. An exact model vector uses a
pseudoinverse; when that representative is not nonnegative, a simplex feasibility
linear program uses independent identifiable coordinates. General count data
use constrained least squares on the probability simplex. Duplicate and affine
dependencies retain `unique=False`. Returned weights are feasible representatives;
the identifiable coordinates and predicted probabilities are computed from them.
Zero-total observations are rejected. No optimal experimental-design or
optimal finite-sample efficiency claim is made.

## Public development evidence

Both supplied examples passed. Six independent development cases included the
provided 7-qubit and 9-qubit codes, a five-qubit stabilizer code, complex product
unitary transformations, physical qubit permutations, logical basis changes,
amplitude damping, a random CPTP channel, coherent rotations, depolarization,
dephasing, exact duplicate channels, and affine channel dependencies.

The checks independently constructed full physical Kronecker operators; tested
every registered branch on the full one-qubit Pauli-correctable span; compared
instrument completeness against an independently obtained physical projector;
compared available rank using physical density Hilbert-Schmidt Gram matrices;
verified erasure completion and subnormalized mass; and tested all simplex
vertices plus fresh seeded interior mixtures. They did not inspect private cases.

| Case | Hypotheses | Available/reported rank | Outcomes | Largest ideal error |
|---|---:|---:|---:|---:|
| public_pollatsek_pauli | 22 | 22 | 946 | 1.1e-14 |
| public_shor_pauli | 28 | 22 | 946 | 1.8e-14 |
| perfect_five_pauli | 16 | 16 | 496 | 1.11e-15 |
| complex_rotated_pollatsek_channels | 11 | 8 | 946 | 3.22e-14 |
| complex_rotated_shor_channels | 11 | 8 | 946 | 1.23e-14 |
| perfect_five_channels | 11 | 8 | 496 | 1.3e-14 |

There were 171 ideal mixtures.
The largest ideal coordinate/prediction/unique-weight error was
3.21964677e-14.
The largest full-span nondisturbance error was
1.38777878e-16; the largest complete
instrument error was 3.58145764e-15.
The largest certificate discrepancy against the independent physical Gram
calculation was 4.56309887e-12.

## Finite observations: secondary descriptive results

Each row uses a fresh seeded mixture and multinomial sample. Different rows are
not paired measurements of the same mixture. The complete fitted frequencies,
weights, seeds and errors are preserved in `development_results.json`.

| Case | Shots | Maximum identifiable-coordinate error | Prediction total variation |
|---|---:|---:|---:|
| public_pollatsek_pauli | 10000 | 0.0399136 | 0.0243393 |
| public_pollatsek_pauli | 100000 | 0.00817299 | 0.0062256 |
| public_shor_pauli | 10000 | 0.0244036 | 0.0144483 |
| public_shor_pauli | 100000 | 0.0028153 | 0.00439751 |
| perfect_five_pauli | 10000 | 0.00826933 | 0.0144116 |
| perfect_five_pauli | 100000 | 0.00251757 | 0.00451217 |
| complex_rotated_pollatsek_channels | 10000 | 0.145132 | 0.0122734 |
| complex_rotated_pollatsek_channels | 100000 | 0.0277053 | 0.00423104 |
| complex_rotated_shor_channels | 10000 | 0.226757 | 0.00770981 |
| complex_rotated_shor_channels | 100000 | 0.0312493 | 0.00250144 |
| perfect_five_channels | 10000 | 0.0660626 | 0.00668208 |
| perfect_five_channels | 100000 | 0.0084586 | 0.0011475 |

Close channels can have substantial coordinate uncertainty despite small
prediction error. These finite trials give no universal accuracy guarantee and
did not alter the primary ideal-probability decision.

## Measured resources and failures

The numerical development subprocess used 2.573020 wall
seconds, 2.108821 user CPU seconds,
0.499612 system CPU seconds, and
230724 KiB peak RSS. Thread limits for OpenBLAS, OMP and MKL
were all one. Python executable: `/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3`. NumPy 2.3.5;
SciPy 1.17.0. These measurements include development checks and
their fixture construction, not only the exported constructor.

The first launch attempted to use `/usr/bin/time`, which is absent. That attempt
exited 127 before scientific Python executed. Its stderr is preserved. A standard
library subprocess/resource wrapper measured the successful numerical run.
There were no numerical development failures and zero source repairs.

Model inference calls, tokens, host cost, and total monetary cost are unknown.
Included agent execution is not zero economic cost. Process wall/CPU time is
not model inference compute. Construction interval and hashes are recorded in
`construction_end.json`.

## Sources, assumptions, and limits

Sources read were the assigned TASK.txt, SECOND_CONTRACT.json,
second_public_fixtures.py and public_fixtures.py. No external documentation,
other workspace, prior recovery implementation, private qualification data,
or other agents' results were accessed. The mathematical construction above
uses conventional exact quantum error correction and finite-dimensional
linear algebra; no novelty claim is made.

The implementation assumes the contract's exact, well-conditioned codes and
separated nonzero singular spectrum. It validates orthonormality, the full
Knill--Laflamme error condition and local trace preservation numerically.
The code is qualified only for the stated n<=9 and H<=32 domain. It does not
model hardware, approximate correction, fault tolerance, time-dependent noise,
or optimal shot complexity. No independent qualification has been sought.

Frozen source SHA256: `54d70a7c0f5a48400b4944224c22fa0fbda2ad56a95068e70b8ed64416c4bd1c`.
