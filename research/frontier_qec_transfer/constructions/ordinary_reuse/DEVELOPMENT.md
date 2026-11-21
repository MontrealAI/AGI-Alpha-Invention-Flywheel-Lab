# Nondestructive noise experiment: public development record

## Outcome and scope

The initial implementation passed the supplied development example and seven
additional public-contract cases on its first numerical execution. No repair
was made. This is a construction and public-development result, not independent
qualification or evidence about other comparison arms.

The executable deliverable is `noise_experiment.py`, exporting
`NoiseExperiment`. It imports the supplied, unchanged `recovery.py`. Both exact
source files are included in the final SHA256-addressed freeze. The code uses
only the standard library, NumPy, and SciPy, on CPU, without runtime networking.

## Construction and mathematical certificate

The prior recovery asset provides orthogonal syndrome decoders R_a satisfying
R_a E V = c_a(E) I on the entire single-qubit Pauli-correctable span. Its public
`kraus()` API is used; no internal implementation attributes are required.

For syndrome dimension r, the new code constructs these row vectors:

- e_a / sqrt(2r-1), for each a;
- (e_a + phase e_b) / sqrt(2(2r-1)), for a < b and
  phase in {1, -1, i, -i}.

There are 2r^2-r outcomes. Their effects sum to identity: the basis rows
contribute I/(2r-1), and the four rows for each pair contribute
2(e_a e_a* + e_b e_b*)/(2r-1). The registered physical operator is
M_o = sum_a w_oa R_a. Thus every branch on E V is a scalar times I, and
sum_o M_o* M_o = P_S. This proves logical nondisturbance and completeness on
the entire correctable span, including coherent error superpositions.

The classical erasure effect is I-P_S. `erasure_operators()` supplies its rows
as Kraus operators into a one-dimensional flag; they collectively implement
the single erasure outcome because (I-P_S)^2 = I-P_S. `measure()` executes the
registered outcomes and returns the residual erasure mass without normalization
or postselection. Subnormalized inputs retain their raw mass. Tiny signed
roundoff residuals are reported explicitly.

For a channel with local Kraus matrices K_t, its syndrome state is
tau_h = sum_t c(K_t)c(K_t)*, and A_oh = w_o tau_h w_o*. The basis outcomes give
every diagonal entry. Differences between real and imaginary pair outcomes
give every off-diagonal real and imaginary entry. Consequently the measurement
is injective on Hermitian syndrome matrices and retains every physically
available linear combination of the hypotheses. Recovery identifies the
fixed-logical-state physical density model with this syndrome model by an
isometry. The implementation checks agreement of the two numerical model
ranks, and returns the orthogonal projector onto row(A).

`estimate()` explicitly normalizes classical counts, including very small or
large finite scales. Nonnegative least squares provides feasible exact-model
representatives. Noisy observations are fitted over the probability simplex
with constrained least squares. Deficient-rank estimates expose only the
identifiable quotient as determined by the returned projector. An optimizer
fallback is labeled `feasible_nonnegative_fit`; this fallback was not used in
the recorded development cases. Zero-total observations are rejected.

## Independent public-development checks

`development_checks.py` uses the supplied physical local-operation fixture and
an independent SVD of all physical Pauli images. It reconstructs exported
operators from their sparse direct coefficients. It checks operator
completeness spectrally, scalar action for every Pauli error on both logical
basis vectors, direct physical channel probabilities, independent density-model
rank and projector, unknown-logical-state probability invariance, raw mass,
complement erasure, and executable erasure Kraus operators.

Additional cases are reproducibly constructed from the public codes with local
complex unitaries, qubit permutations, complex logical basis rotations, random
CPTP channels, amplitude damping, coherent errors, exact duplicates, and convex
dependencies. No private data or outside construction source is used.

| Case | Hypotheses | Available rank | Registered outcomes |
|---|---:|---:|---:|
| Public Pollatsek-Ruskai Pauli model | 22 | 22 | 946 |
| Public Shor Pauli model | 28 | 22 | 946 |
| Rotated/permuted complex PR, general channels | 32 | 32 | 946 |
| Rotated/permuted complex Shor, general channels | 32 | 32 | 946 |
| Coherence, duplicates, and convex dependencies | 15 | 12 | 946 |
| Three identical channels | 3 | 1 | 946 |
| One channel | 1 | 1 | 946 |

Across the seven cases, the largest recorded operator/response/certificate error
was 6.2450045135165055e-15, and the largest ideal identifiable-coordinate error
was 2.192690473634684e-15. Each case used nine ideal mixtures, including boundary
and sparse mixtures, with observation scales 1, 1e-280, and 1e307. The provided
development example was also executed separately and passed.

Seeded finite-count results are descriptive, not primary acceptance thresholds.
The following are Euclidean errors in identifiable coordinates:

| Case | 2,000 shots | 20,000 shots |
|---|---:|---:|
| Public PR Pauli | 0.094799 | 0.031138 |
| Public Shor Pauli | 0.029801 | 0.011160 |
| General 32-channel PR | 0.206277 | 0.100989 |
| General 32-channel Shor | 0.168977 | 0.088120 |
| Dependencies and coherent channels | 0.177627 | 0.152453 |

Each finite-count record uses a fresh seeded mixture, so these columns are not
a controlled convergence curve. Full observations, fitted probabilities,
feasible representatives, residuals, and seeds are preserved in
`development_results.json`. Conditioning and shot noise can produce substantial
weight error even when fitted observation error is small. No finite-sample
accuracy guarantee, optimal-shot design, or novelty claim is made.

## Measured resources and accounting

The complete numerical subprocess finished successfully in 3.1428300339975976
wall seconds, with 2.760883 user CPU seconds, 0.37431299999999995 system CPU
seconds, and 175760 KiB maximum RSS. The test body's measured interval was
2.682159378997312 wall seconds. All scientific Python commands used the primary
runtime with OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1, and MKL_NUM_THREADS=1.
No engineering timeout or timing target was imposed.

The implementation contains 313 lines and 16020 bytes. Its initial exact bytes
were preserved before the first meaningful execution. There were zero repairs
and zero meaningful failed development attempts. Construction start/end and
elapsed wall time are separately recorded in the JSON receipts. Process time
is not model inference compute. Model inference calls, tokens, host cost, and
total monetary cost are unknown. Included agent execution and the prior asset
are not assumed to have zero economic cost. Prior acquisition/qualification
costs must be retained by the overarching comparison.

## Sources, assumptions, and limitations

Accessed task sources were `TASK.txt`, `SECOND_CONTRACT.json`,
`PRIOR_ASSET.txt`, `second_public_fixtures.py`, `public_fixtures.py`, and
`recovery.py`, all within the assigned workspace. The recovery source cites
Knill and Laflamme, Phys. Rev. A 55, 900 (1997),
https://doi.org/10.1103/PhysRevA.55.900. That citation came from the supplied
asset; no outside paper, implementation, repository, or web documentation was
accessed during this construction. The explicit frame proof above suffices
for the new measurement construction.

The registered domain is n <= 9, two orthonormal codewords satisfying full
single-qubit correction, at most 2048 amplitudes, at most 32 local CPTP channel
hypotheses, and separated nonzero singular spectra. Numerical thresholds do
not establish identifiability for arbitrarily ill-conditioned limiting models.
The full informationally complete frame may use many more outcomes than a
specialized experiment; no efficiency optimality is asserted. No hardware,
fault tolerance, physical calibration, or monetization claims are made.

Blinding was maintained: no parent/sibling directories, evaluator source,
private qualification data, other agents' results, project histories, or
outside project instructions were inspected. No delegation or sibling-agent
contact occurred. The source is frozen before any private qualification and
must not be repaired using private feedback from this comparison.
