# Nondestructive noise experiment: public development record

## Frozen result

- Source: `noise_experiment.py`, exporting `NoiseExperiment`.
- SHA256: `7adbfc0ea64d7ea48990a7f922752b0ad86d4cc1a8b3aae0be7cdf14cdeec9e7`.
- Initial source was copied byte-for-byte to `submissions/initial.py` before any import or meaningful development execution.
- Source repairs: **0**. The initial implementation passed all public development checks.
- Supplied prior capability: **absent**. No recovery implementation was read, imported, acquired, or reused.
- This is public development evidence, **not independent or private qualification**.

## Construction and assumptions

The qualified inputs are those in `SECOND_CONTRACT.json`: two orthonormal logical codewords, correction of arbitrary one-qubit errors, physical qubit zero the most-significant bit, local CPTP hypotheses, and at most nine physical qubits and 32 hypotheses. The module validates basic shape, finiteness, normalization, trace preservation, and the full Knill--Laflamme relations. Its numerical rank thresholds assume the contract's separated nonzero spectra and well-conditioned exact-code families.

Let `E_a V` denote the code isometry acted on by identity and all one-qubit X, Y, Z errors. Correctability gives `V† E_a† E_b V = G_ab I`. Diagonalizing the positive Gram matrix G and retaining its support constructs orthogonal syndrome isometries F_j. Their concatenation W is an isometry from syndrome tensor logical space to the entire correctable physical span S. A local Kraus matrix is expanded coherently in the Pauli basis, retaining complex coefficients. Consequently `W† K V = b_K tensor I`.

The experiment constructs r squared rank-one syndrome effects from the computational vectors, each pair's real superposition, and each pair's imaginary superposition. Their unnormalized effects span all Hermitian r by r matrices. Applying the positive inverse square root of their frame operator makes them sum to identity; this invertible congruence preserves the Hermitian span. Each registered measurement operator is `(c_o tensor I) W†`, exported as two dictionaries of direct row coefficients.

For each supported Kraus matrix, `M_o K V = (c_o b_K) I`. Therefore every branch returns the same unknown logical state multiplied by a scalar, including all logical coherences. Summing registered effects gives `P_S`; the complementary erasure effect is `I-P_S`. The additional `apply` method implements all branches and the classical erasure outcome on pure vectors and density matrices, preserving raw subnormalized mass. The erasure instrument is the completely positive map `rho -> Tr((I-P_S) rho) |erasure><erasure|`.

For hypothesis h, let its syndrome density be `sigma_h = sum_K b_K b_K†`. The response is `A_oh = Tr(effect_o sigma_h)`. Since the syndrome POVM spans the full Hermitian space, a linear combination of response columns is zero exactly when the same combination of syndrome densities is zero. The isometric tensor factorization then gives exactly the linear rank available in the physical channel outputs for any fixed pure encoded logical state. This proves maximal linear identifiability without assuming orthogonal errors. Column normalization also puts the all-ones hypothesis vector in the response row space.

The identifiability certificate is the Euclidean row-space projector from a real response SVD. Estimation explicitly normalizes observations. Ideal observations use a pseudoinverse followed, when necessary, by a nonnegative feasibility linear program. Finite frequencies use simplex-constrained least squares. Nonunique mixtures are reported as feasible representatives, with their identifiable projection and fitted observation frequencies.

## Public development evidence

The provided `second_public_fixtures.development_example(NoiseExperiment)` passed. Additional checks independently apply physical Kraus matrices using the supplied sparse-coordinate physical convention; they do not use implementation internals. They inspect every branch on every identity/X/Y/Z image of both logical basis states, compare the complete physical-span projector, obtain the physically available density rank from Hilbert--Schmidt overlaps of independently calculated channel outputs, and check the full erasure completion on subnormalized pure and mixed inputs.

| Case | Hypotheses | Physical / reported rank | Outcomes | Unique |
|---|---:|---:|---:|---|
| pollatsek_ruskai_paulis | 22 | 22 | 484 | true |
| shor_paulis | 28 | 22 | 484 | false |
| rotated_pollatsek_ruskai_general | 32 | 29 | 484 | false |
| rotated_shor_general | 32 | 29 | 484 | false |
| identity_only | 1 | 1 | 484 | true |
| convex_dependent_boundary | 4 | 2 | 484 | false |

Each case uses seven ideal mixtures, including simplex boundary points, uniform weights, and seeded fresh random mixtures. Thus there are 42 independently checked ideal-mixture examples in addition to the supplied development example. They check feasible weights, normalization, identifiable coordinates, predictions, actual weights whenever full rank, and rejection of zero observations. The convex-dependent example exercises physically dependent channels at boundary weights. The transformed-code examples use independent physical local unitary changes and a logical basis rotation, with coherent unitary, random two-Kraus CPTP, amplitude-damping, duplicate, and convex-dependent hypotheses.

- Largest recorded physical/operator/response/certificate error: **8.1858749600544682e-15**.
- Largest ideal identifiable-coordinate error: **7.7082784599724619e-13**.
- Required public physical tolerance: 2e-8; ideal coordinate tolerance: 2e-6.
- Six public/extended cases passed; no meaningful algorithmic failure occurred.
- Full records, mixture estimators, multinomial counts, fitted probabilities, and errors are in `development_results.json`. Console output is in `development_stdout.txt`.

### Descriptive finite-count results

Seed: 20261121 for one deterministic development stream. These are fresh multinomial observations at each shot count, not coupled nested samples. Higher shot count need not improve an individual sample. Results are descriptive and do not determine the primary ideal-probability pass.

| Case | Shots | Identifiable-coordinate L2 error | Fitted-probability L2 error |
|---|---:|---:|---:|
| pollatsek_ruskai_paulis | 2000 | 0.0929768 | 0.00512328 |
| pollatsek_ruskai_paulis | 20000 | 0.0287969 | 0.0014147 |
| shor_paulis | 2000 | 0.0556102 | 0.00361951 |
| shor_paulis | 20000 | 0.0195584 | 0.00142858 |
| rotated_pollatsek_ruskai_general | 2000 | 0.18111 | 0.00446068 |
| rotated_pollatsek_ruskai_general | 20000 | 0.0796527 | 0.00149206 |
| rotated_shor_general | 2000 | 0.205642 | 0.00387398 |
| rotated_shor_general | 20000 | 0.0953216 | 0.00152943 |
| identity_only | 2000 | 0 | 2.11779e-16 |
| identity_only | 20000 | 0 | 2.11779e-16 |
| convex_dependent_boundary | 2000 | 0.0043378 | 0.000614053 |
| convex_dependent_boundary | 20000 | 0.0087108 | 0.00123309 |

No optimal-shot-complexity or globally optimal design claim is made. An informationally complete POVM can have substantial sampling variance; sparse or specially structured hypotheses can admit more economical designs. No confidence intervals or universal finite-sample guarantee are asserted.

## Execution and failures

The recorded numerical subprocess used `CODEX_PRIMARY_RUNTIME_PYTHON` and `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`.

- Whole numerical subprocess wall time: 4.224026099 seconds.
- User CPU: 3.857510000 seconds; system CPU: 0.394416000 seconds.
- Maximum resident set size: 173632 KiB (Linux resource receipt).
- Exit code: 0.
- Receipt: `numerical_process_receipt.json`; no discretionary timeout was imposed.

An initial attempt to use `/usr/bin/time -v` failed with exit 127 because that executable was absent. It did not execute the implementation. The exact error is preserved in `infrastructure_failure_time.txt`. The measurement wrapper was replaced with a standard-library subprocess/resource wrapper, without changing the implementation. This is one infrastructure attempt, zero scientific implementation failures, and zero source repairs.

Construction elapsed time is measured separately using the start and completion monotonic timestamps in `construction_start.json` and `construction_end.json`. Tool/process elapsed time is not model inference compute. Model inference calls/tokens, host cost, agent economic cost, and total monetary cost are **unknown** because no real receipt exposes them; included execution is not assumed to cost zero.

## Sources, scope, and blinding

Sources read: `TASK.txt`, `SECOND_CONTRACT.json`, `second_public_fixtures.py`, and `public_fixtures.py` in this assigned workspace. Mathematical construction and correctness arguments above are explicitly derived here using conventional finite-dimensional linear algebra, the correctability relation, and convex feasibility/least squares. No web research, downloads, package installation, paid service, credentials, runtime network, or other agents' results were used.

No parent or sibling workspace, evaluator, private qualification material, other construction, project AGENTS file, or tool/conversation history was inspected. No agent was delegated to or contacted during construction. The only final handoff is to the assigning root agent. Source and archive copies are made read-only at freeze. No claim of world novelty, hardware realization, fault tolerance, general transfer, economic compounding, or independent qualification follows from this development run.
