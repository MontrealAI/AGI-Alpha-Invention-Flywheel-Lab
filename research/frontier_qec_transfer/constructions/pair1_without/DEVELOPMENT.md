# Nondestructive noise-identification construction

## Frozen deliverable

`noise_experiment.py` exports the required `NoiseExperiment` class. It is a
self-contained implementation using NumPy and SciPy. No prior recovery asset
was present or used. The initial implementation passed the public development
checks and was frozen without source repairs. Its SHA256 is
`05e989ca4e8c5512c375bb7eeb19e9b1b98c16cc763a5048a772a2da05ac6ae9`.

The module provides all four required methods: `measurement_operators()`,
`response_matrix()`, `identifiability()`, and `estimate(observed)`. The additional
methods `erasure_effect()`, `erasure_operators()`, and
`apply_instrument(physical)` expose an executable completion on the orthogonal
complement of the correctable span. Logical outputs and the erasure probability
retain their raw mass for subnormalized inputs.

## Mathematical construction

Let V encode the two logical basis vectors, and let E_a range over identity
and all physical one-qubit X, Y, and Z operators. Correctability supplies

    V† E_a† E_b V = C_ab I.

The implementation verifies these equalities, diagonalizes the positive error
Gram matrix C = W Λ W†, and retains its nonzero eigenspace. The resulting
operators B_s = sum_a E_a V W_as / sqrt(Λ_s) satisfy

    B_s† B_t = δ_st I,     sum_s B_s B_s† = projector(S).

Thus S factors into syndrome and logical subsystems. Every supported local
Kraus operator has K V = sum_s b_s B_s. A supported channel has syndrome
density σ_h = sum_k b_hk b_hk†, independently of the logical density ρ.
Within S its physical output is isometric to σ_h tensor ρ.

For syndrome dimension r, use the coordinate vectors e_j and, for each j < k,
the four vectors (e_j ± e_k)/sqrt(2) and (e_j ± i e_k)/sqrt(2). Divide every
vector by sqrt(2r - 1). These L = 2r² - r vectors form a rank-one tight POVM:
their projectors sum to identity. Their projectors span all Hermitian syndrome
matrices, because coordinate probabilities determine diagonal entries and
differences within each signed pair determine the real and imaginary parts of
each off-diagonal entry.

The exported registered branch is

    M_o = sum_s conjugate(v_os) B_s†.

Consequently M_o K V = <v_o, b> I. Every branch returns the same arbitrary
logical state, with a scalar amplitude depending only on the noise and the
outcome. Summing branch effects yields projector(S). The complementary effect
I - projector(S) gives the classical erasure flag. Rows of that complementary
projector are an explicit scalar-output Kraus representation of the flag.
Together these maps preserve total raw mass on the entire physical space.

The response is A_oh = v_o† σ_h v_o. Because this syndrome measurement is
informationally complete, its linear map on Hermitian matrices is injective.
Therefore rank(A) equals the rank available from the physical output density
matrices for any fixed encoded pure logical state. A singular-value
decomposition gives the Euclidean projector onto row(A). Since each response
column sums to one, this row space includes the normalization direction.
Duplicate channels and more general affine channel dependencies remain
unidentifiable and are reported as such.

## Estimator

Observations are explicitly normalized after scaling by their largest entry,
which also avoids overflow from very large count units. Zero total mass is
rejected. Exact model frequencies are inverted in the identifiable singular
subspace. If the minimum-norm inverse is not nonnegative, a simplex-constrained
linear feasibility problem supplies a representative. The nontrivial affine
dependency test exercises this path: identity, X, and their equal mixture have
rank two, and a pure identity observation has a negative component in its
unconstrained minimum-norm inverse.

Other observations are fitted by constrained ordinary least squares on the
probability simplex. The returned coordinates are explicitly P times the
returned feasible weights, and the fitted frequencies are explicitly A times
those weights. Rank-deficient models always return `unique=False`.

## Public development evidence

The provided `second_public_fixtures.development_example` passed. Additional
tests use the public sparse physical-action routine to construct actual channel
outputs and the full Pauli-correctable span. They reconstruct every exported
operator from its direct row dictionaries; check the full-span branch maps,
operator completeness, logical nondisturbance, response probabilities,
identifiability projector, raw-mass erasure completion, and independently
computed physical density rank; and test zero-observation rejection.

| Development case | Physically available / reported rank | Hypotheses |
|---|---:|---:|
| Pollatsek–Ruskai Pauli library | 22 / 22 | 22 |
| Shor Pauli library | 22 / 22 | 28 |
| Complex locally and logically rotated Pollatsek–Ruskai, general CPTP channels | 30 / 30 | 32 |
| Complex locally and logically rotated Shor, general CPTP channels | 30 / 30 | 32 |
| Seven identical amplitude-damping channels | 1 / 1 | 7 |
| One amplitude-damping channel | 1 / 1 | 1 |
| Identity, X, and their equal mixture | 2 / 2 | 3 |

All seven cases passed. All use syndrome dimension 22 and export 946 registered
measurement branches. There are 70 fresh seeded ideal-mixture checks and 14
seeded finite-count observations, with 2,000 or 20,000 observations per trial.
Detailed weights, fitted probabilities, errors, spectra, and timings are in
`development_results.json`; the pre-extension results are retained separately
under `submissions/`.

For the initial six-case run, the largest completeness spectral error was
4.15e-15, full-span branch error was 1.39e-16, response error was 2.09e-17, and
ideal identifiable-coordinate error was 4.45e-15. The seventh case also passed
the same registered tolerances. These are public development measurements,
not independent qualification.

Finite counts are descriptive only. For example, quotient-coordinate L2 errors
for the two general-channel cases were approximately 0.205 and 0.186 at 2,000
observations, and 0.0801 and 0.112 at 20,000 observations. Each trial uses fresh
weights as well as fresh multinomial observations, so these numbers do not
constitute a controlled convergence-rate comparison. The fit is feasible, but
no universal finite-shot accuracy guarantee or optimal shot complexity is
claimed. Full fitted probability vectors are preserved in the JSON evidence.

## Versions, failures, and resource accounting

The initial source was copied byte-for-byte to `submissions/initial.py` and made
read-only before its first development execution. Source repair count is zero.
There were no scientific test failures. An attempted launch using
`/usr/bin/time` failed with exit 127 because that executable is absent. No
scientific subprocess ran in that attempt. The command was replaced with a
standard-library subprocess/resource wrapper; the failed launch and correction
are preserved in `development_launch_failure.json`. The first test log also
preserves a NumPy `row_stack` alias deprecation warning in the development
harness; it did not affect the source or results.

The main measured scientific subprocess took 3.2266 seconds wall time,
2.7224 seconds user CPU and 0.4991 seconds system CPU, with peak RSS 184,396 KiB.
The additional affine-dependency subprocess took approximately 0.6216 seconds
within its measured interval, 0.4086 seconds user CPU and 0.2474 seconds system
CPU, with peak RSS 93,064 KiB. Its Python startup precedes the internal interval;
the main subprocess receipt includes its full child lifetime. All scientific
Python invocations use `CODEX_PRIMARY_RUNTIME_PYTHON` and set
`OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, and `MKL_NUM_THREADS=1`.
The installed numerical versions were NumPy 2.3.5 and SciPy 1.17.0.

The implementation is 362 lines and 18,468 bytes. Final construction elapsed
wall time and immutable paths are recorded in `construction_end.json`. Model
inference calls, tokens, host cost, and monetary cost are unknown. Included
agent execution is not zero economic cost; subprocess timing is not model
inference compute.

## Assumptions and limits

The accepted finite domain is an exact orthonormal two-dimensional code with
n <= 9, at most 2,048 supplied code amplitudes, and at most 32 specified local
CPTP hypotheses. Full one-qubit correctability, numerical conditioning, and
separated nonzero singular spectra are required by the contract. Input checks
reject materially invalid codes and channels. Extremely near-degenerate
spectra outside the qualified domain can make numerical rank unstable.

The syndrome POVM is informationally complete but deliberately makes no claim
of minimum outcome count, minimum experimental complexity, or statistically
optimal design. It uses modest dense linear algebra and sparse exported rows.
It is a CPU simulation and mathematical protocol, not a hardware implementation
or a fault-tolerance result. No independent qualification, novelty,
cross-arm comparison, or transfer claim is made here.

## Sources and blinding

Authorized sources read were `TASK.txt`, `SECOND_CONTRACT.json`,
`second_public_fixtures.py`, and `public_fixtures.py` in this workspace. The
algorithm and mathematical explanation were constructed directly from those
requirements and the standard correctability algebra above. No external
research, downloads, paid service, runtime network, or prior recovery asset was
used. No parent or sibling directory, private qualification data, other
implementation, agent history, or evaluator source was inspected. No additional
agent was contacted or delegated work. These are procedural blinding
attestations on the shared filesystem.
