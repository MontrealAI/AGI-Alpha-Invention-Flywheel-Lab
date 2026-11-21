# Nondestructive noise-mixture experiment

## Delivered capability

`noise_experiment.py` exports `NoiseExperiment(n, codewords, hypotheses)` and
the four contracted methods: `measurement_operators`, `response_matrix`,
`identifiability`, and `estimate`. It also provides `erasure_effect` and
`measure` to expose and execute the complete instrument, including raw erasure
mass on arbitrary subnormalized physical inputs.

The unchanged supplied `recovery.py` is a required sibling dependency. The
frozen archive includes both modules. NumPy and SciPy are the only other
nonstandard dependencies. There is no execution-time network access.

## Construction and mathematical justification

The supplied recovery operators are denoted R_s, with syndrome dimension r.
They satisfy R_s E_a V = alpha_(s,a) I on the complete one-qubit Pauli error
span, and sum_s R_s^dagger R_s is its physical projector P_S. Their rows also
obey R_s R_t^dagger = delta_(s,t) I. These properties separate syndrome from
the arbitrary logical input.

The measurement uses an explicit rank-one informationally complete syndrome
POVM. Its coefficient rows are e_j/sqrt(r), and, for each j < k,
(e_j +/- e_k)/(2 sqrt(r)) and (e_j +/- i e_k)/(2 sqrt(r)). There are
r(2r-1) outcomes. The coefficients obey C^dagger C = I: basis outcomes
contribute 1/r to each diagonal and the pairs contribute (r-1)/r. The
registered physical-to-logical operators are M_o = sum_s C_(o,s) R_s.
Consequently sum_o M_o^dagger M_o = P_S exactly in exact arithmetic.

Every supported channel Kraus operator F obeys R_s F V = beta_s I. Therefore
M_o F V is a scalar identity, and the logical output of each outcome is its
probability times the unchanged input logical density. This proves
nondisturbance for arbitrary logical inputs, including coherent superpositions
and inputs entangled with a reference. No postselection is used.

The classical erasure effect is Q = I - P_S. The map sending rho to
Tr(Q rho) times a fixed classical erasure flag is completely positive; together
with the registered branches it is trace preserving. `measure` keeps this raw
mass rather than normalizing it away. Roundoff can produce a tiny negative
erasure residual on a fully correctable state; the value is deliberately not
used to renormalize the logical output.

Each noise hypothesis induces a syndrome density tau_h. The response is
A_(o,h) = C_o tau_h C_o^dagger. Basis outcomes determine all diagonals of tau;
differences between the real and imaginary pair outcomes determine both
components of every off-diagonal. The map from Hermitian syndrome matrices to
these probabilities is thus injective. Its column rank equals the physically
available rank of the hypothesis densities. The returned Euclidean row-space
projector is formed by SVD of A. Because its columns sum to one, mixture
normalization belongs to its row space. Duplicate channels and nonduplicate
affine dependencies are preserved as unidentifiable directions.

The estimator explicitly normalizes counts and first solves least squares on
the affine sum-one hyperplane. If this minimum-norm representative is negative
in a deficient model, a linear program searches its full observationally
equivalent class for a nonnegative representative. Observations outside the
mixture hull use convex least squares over the probability simplex. Returned
identifiable coordinates and fitted frequencies are computed directly from
the returned feasible representative. This is a least-squares estimator, not
a likelihood estimator or an optimal experiment design.

## Public development evidence

The initial source passed the supplied development example and all development
checks without a repair. The exact initial bytes were preserved before the
first numerical run. No failed construction attempts occurred.

The independent checks reconstruct physical error spans and physical channel
densities from the supplied codewords and local channel matrices. They verify
every M_o E_a V, rather than only a particular logical probe; compare the sum
of measurement effects with an independently constructed span projector; test
the erasure completion; compare predicted responses with executed operators;
and compare reported identifiability with physical density ranks and row spaces.

| Case | Hypotheses | Available/reported rank | Unique |
| --- | ---: | ---: | :---: |
| Pollatsek–Ruskai 7, Pauli library | 22 | 22 | Yes |
| Shor 9, Pauli library | 28 | 22 | No |
| Complex local and logical rotation of PR7, random CPTP channels | 32 | 32 | Yes |
| Complex local and logical rotation of Shor9, random CPTP channels and duplicates | 32 | 30 | No |
| Single amplitude-damping hypothesis | 1 | 1 | Yes |
| Eight identical amplitude-damping hypotheses | 8 | 1 | No |
| Identity, bit flip, and a known mixture of the two | 3 | 2 | No |

All these codes have syndrome rank 22, giving 946 registered outcomes.
Across the six principal cases, the largest instrument-completeness spectral
error was 3.81e-15, the largest full-span nondisturbance residual was 2.12e-16,
the largest physical-certificate entry error was 2.11e-15, and the largest
ideal-mixture coordinate error was 6.77e-15. The supplemental affine-dependence
test explicitly exercised feasible recovery from a negative minimum-norm
representative, and an outside-hull count vector exercised constrained fitting.

Fresh seeded multinomial samples used 60,000 shots per principal case. Their
identifiable-coordinate Euclidean errors were approximately 0.02661, 0.01085,
0.04996, 0.05116, 0, and 7.85e-17 in table order. Full weights, observed counts,
fitted probabilities, probability errors, and fitting methods are retained in
`development_results.json`. These are descriptive realizations, not universal
accuracy bounds. They did not alter the ideal-probability pass decision.

## Resources and provenance

The primary numerical subprocess took 2.322845169 seconds wall time, with
1.980829 user CPU seconds, 0.372366 system CPU seconds, and 201,192 KiB peak
resident memory. The supplemental process had a 0.446881862-second observed
tool/process duration and 66,616 KiB peak RSS. Its instrumented test-body wall
time excludes import time; CPU accounting includes process startup/imports.
All scientific Python invocations used CODEX_PRIMARY_RUNTIME_PYTHON with
OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1, and MKL_NUM_THREADS=1.

Sources were the supplied `SECOND_CONTRACT.json`, `PRIOR_ASSET.txt`,
`recovery.py`, `public_fixtures.py`, and `second_public_fixtures.py`. The POVM,
estimator integration, and checks were constructed for this task from these
public materials and ordinary matrix identities. No outside research,
downloads, additional packages, credentials, or private data were used.

Only the assigned workspace and permitted system runtime paths were accessed.
No parent/sibling workspaces, evaluator files, construction materials, other
agents' results, or tool/conversation histories were inspected. No delegation
or contact with sibling agents occurred. This is procedural blinding on a
shared filesystem, not an operating-system isolation claim.

## Limits and accounting

The supported contract is two logical codewords, n <= 9, at most 32 local CPTP
hypotheses, exact well-conditioned one-qubit-correcting codes, and a separated
nonzero singular spectrum. Numerical tolerances do not claim robust rank
identification for arbitrarily ill-conditioned or approximate codes. Public
development is not independent qualification, physical implementation,
fault tolerance, novelty, or a transfer-effect result.

Construction start/end, hashes, source sizes, repairs, process receipts, and
dependency identity are recorded in `construction_end.json`. Model inference
calls, tokens, model compute, host cost, prior acquisition/qualification cost,
and monetary totals are unknown: no receipts expose them here. Included-agent
execution is not assigned zero economic cost, and measured process/tool wall
time is not model inference compute. Prior capability cost must remain in any
cumulative comparison performed by the parent experiment.
