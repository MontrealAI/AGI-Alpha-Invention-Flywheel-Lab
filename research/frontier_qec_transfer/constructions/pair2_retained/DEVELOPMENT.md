# Nondestructive noise-mixture identification: development record

## Delivered capability

`noise_experiment.py` exports `NoiseExperiment(n, codewords, hypotheses)`, with all four required methods: `measurement_operators`, `response_matrix`, `identifiability`, and `estimate`. It also exports executable raw-mass accounting through `execute(branches)` and the complementary classical erasure effect through `erasure_effect()`.

The only project dependency is the supplied, unchanged `recovery.py`. NumPy, SciPy, and the Python standard library supply ordinary numerical and optimization routines. There are no runtime downloads, paid services, network calls, or extra packages. Keep the two Python files together when importing from the frozen archive.

## Construction and mathematical justification

The retained recovery returns operators R_s satisfying R_s E_a C = alpha_sa I for the entire single-qubit Pauli error span. Their stacked adjoints form an isometry from logical space times syndrome space into the physical correctable subspace S. For each local channel, its Kraus action on codeword zero therefore determines a positive syndrome matrix sigma_h with unit trace, independent of the logical state.

In syndrome dimension r, the constructor starts from r^2 bras: every coordinate bra, every pair sum divided by sqrt(2), and every pair sum with imaginary relative phase divided by sqrt(2). Their outer products span the Hermitian matrices: diagonal entries come from coordinate effects, real off-diagonal entries from real pair sums, and imaginary off-diagonal entries from imaginary pair sums. Right multiplication by the inverse square root of the frame operator makes a Parseval frame without changing this spanning property.

If f_o is a resulting bra, the measurement operator is M_o = sum_s f_os R_s. Thus each M_o E_a C is proportional to the logical identity. Since the frame is Parseval, sum_o M_o^dagger M_o = projector(S). The additional classical erasure branch has effect I - projector(S), which makes the full instrument trace-preserving. `execute` accepts sums of unnormalized pure-state branches and returns unnormalized outcome densities, their sum, and the complementary raw mass.

The observation model is A_oh = f_o sigma_h f_o^dagger. Informational completeness makes this linear map injective on Hermitian syndrome matrices, so the real linear rank of A equals the rank available in the physical channel outputs. An SVD returns the Euclidean projector onto row(A); weight normalization belongs to this row space because every column of A sums to one. Duplicate and affinely dependent hypotheses remain nonidentifiable.

The estimator explicitly normalizes the classical observations, forms inverse-model identifiable coordinates, imposes weight normalization, and returns a nonnegative simplex representative. Exact feasible quotient coordinates can require a different nullspace representative; a linear feasibility program handles that case. For observations outside the feasible model, the estimator uses simplex projection or a constrained quadratic fit in identifiable coordinates. This is not a maximum-likelihood or statistically optimal experimental design claim.

## Public development results

The preserved initial source passed without a source repair. The supplied public development example also passed. The additional checks used public code families, deterministic local and logical rotations, a five-qubit stabilizer code built in the development harness, and fresh reproducible channel/mixture/count seeds.

| Case | Hypotheses | Outcomes | Available and reported rank | Unique |
|---|---:|---:|---:|---|
| Pollatsek–Ruskai, Pauli channels | 22 | 484 | 22 | Yes |
| Shor, Pauli channels | 28 | 484 | 22 | No |
| Rotated Pollatsek–Ruskai, general channels | 32 | 484 | 30 | No |
| Rotated Shor, general channels | 32 | 484 | 30 | No |
| Five-qubit code, general channels | 32 | 256 | 30 | No |
| Affinely dependent channels | 4 | 484 | 2 | No |
| Single hypothesis | 1 | 484 | 1 | Yes |

Each case verified the direct exported operators on the full Pauli-correctable span, completeness in physical space, the erasure effect, the response model, an independently computed physical-model rank, the row-space certificate, subnormalized supported states, arbitrary physical input mass, zero-observation rejection, and large-count normalization. Across 235 ideal mixtures, including every hypothesis vertex, the largest identifiable-coordinate error was 8.78e-15 and the largest fitted-probability error was 3.68e-16. The largest physical/operator/certificate residual was below 8.15e-15. The finite development suite is evidence, not independent qualification or exhaustive proof of floating-point behavior.

`development_results.json` preserves all case residuals and 42 seeded finite-count trials, including true weights, observed counts, fitted weights, fitted probabilities, and errors. Mean identifiable-coordinate Euclidean errors across three trials at each sample size were:

| Case | 1,000 observations | 10,000 observations |
|---|---:|---:|
| Pollatsek–Ruskai, Pauli | 0.14995 | 0.04960 |
| Shor, Pauli | 0.05542 | 0.01858 |
| Rotated Pollatsek–Ruskai, general | 0.33035 | 0.16255 |
| Rotated Shor, general | 0.26635 | 0.11048 |
| Five-qubit, general | 0.33645 | 0.18365 |
| Affinely dependent | 0.02241 | 0.00627 |
| Single hypothesis | 0 | 0 |

These are descriptive results for the recorded trials. General-channel estimates can have substantial finite-sample error even when the ideal model is identifiable. No universal finite-sample accuracy, confidence interval, shot-complexity optimum, hardware capability, fault tolerance, or novelty is asserted.

## Execution and failure accounting

All numerical Python execution used `CODEX_PRIMARY_RUNTIME_PYTHON` with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`. The test body measured 1.47250 seconds wall time, 1.50863 seconds process CPU time, and a peak resident set of 152,656 KiB (about 149.08 MiB). Bash measured 2.042 seconds for the complete subprocess including import/startup, with 1.716 seconds user CPU and 0.360 seconds system CPU. These are process measurements, not model inference compute or total construction time.

The first launch tried `/usr/bin/time`, which is absent in this environment. It exited with code 127 before Python ran. The preserved `development_launch_failure.log` records the actual error. Retrying with Bash's built-in `time` changed only the launch command. There were no failed numerical checks and no source repairs. Every meaningful development result and the launcher failure are retained; initial source bytes are in `submissions/initial.py`.

The model's inference calls, tokens, hosting cost, and total monetary cost are unknown because no receipt exposes them. Included agent execution and the prior capability are not treated as economically free. The supplied asset's acquisition and qualification costs must be included by the parent comparison; this arm has no receipt for them.

## Sources, assumptions, and limits

Sources read were `TASK.txt`, `SECOND_CONTRACT.json`, `PRIOR_ASSET.txt`, the supplied `recovery.py`, `public_fixtures.py`, and `second_public_fixtures.py` in this assigned workspace. No external research was used. The construction follows the supplied recovery API plus the explicit frame and linear-algebra derivations above.

Assumptions match the registered domain: n <= 9, exactly two orthonormal codewords, valid single-qubit-correcting well-conditioned code families, at most 32 local CPTP hypotheses, and a separated numerical rank spectrum. Invalid inputs are rejected; the code does not silently normalize codewords or channels. Every mathematical real rank is interpreted using documented floating-point SVD tolerances. The full r^2-outcome syndrome measurement prioritizes completeness and a clear certificate, without minimizing the number of outcomes or optimizing statistical efficiency.

Procedural blinding was observed: no parent-directory contents, sibling workspaces, other constructors, private fixtures, evaluators, or agent results were inspected. No sibling was contacted and no delegation occurred. The final source and unchanged prior dependency are archived under the final source SHA256 and made read-only before reporting. No private feedback drove a repair, and this record does not claim independent qualification.
