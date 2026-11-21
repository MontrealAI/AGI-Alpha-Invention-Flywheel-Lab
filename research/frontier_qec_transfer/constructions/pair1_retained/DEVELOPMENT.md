# Nondestructive noise experiment: public development record

## Outcome and scope

The initial implementation passed the supplied public example and the additional public-contract checks described below. There were **zero implementation repairs** and **zero scientific-development failures**. One measurement-wrapper launch failed because `/usr/bin/time` is unavailable; its stderr and correction are preserved under `attempts/`. No scientific code ran during that failed launch. A standard-library subprocess/resource wrapper then measured the actual development execution.

These results are development evidence only. The artifact has not received independent second-stage qualification. The retained first-stage recovery asset does not qualify the new objective by itself.

## Reusable interface

`NoiseExperiment(n, codewords, hypotheses)` implements all four required methods:

- `measurement_operators()` returns explicit one-Kraus physical-to-logical outcome operators as two sparse direct-coefficient row dictionaries per outcome.
- `response_matrix()` returns the physical observation model, excluding the zero-supported-probability erasure outcome.
- `identifiability()` returns rank, uniqueness, and the orthogonal projector onto the response row space.
- `estimate(observed)` explicitly normalizes classical counts or probabilities, rejects zero total mass, and returns a feasible simplex representative, identifiable coordinates, and fitted observations.

Additional methods `outcome_labels()`, `erasure_effect()`, and `measure(branches)` expose outcome ordering, the complementary erasure effect, and execution of the complete instrument on arbitrary sums of sparse pure-state outer products. Quantum input mass remains raw; subnormalized inputs are supported. Solver method, convergence status, and fit residual are returned with estimates.

The module imports the supplied, unchanged `recovery.py`. Both exact files are included in the frozen archive. NumPy and SciPy are the only other nonstandard runtime dependencies. There is no runtime network access or package acquisition.

## Mathematical construction and certificate

Let the retained recovery operators be R_s, with syndrome index s from 1 to r. On the complete correctable error span, every error E has R_s E V = c_s(E) I on the logical input, and sum_s R_s† R_s = P_S. The retained construction supports degeneracy and nonorthogonal complex error images.

Construct a syndrome POVM from the vectors e_i and, for every i<j, (e_i+e_j)/sqrt(2), (e_i-e_j)/sqrt(2), (e_i+i e_j)/sqrt(2), and (e_i-i e_j)/sqrt(2). The sum of their projectors is (2r-1) I. Divide each bra by sqrt(2r-1) to obtain rows f_o and form M_o = sum_s f_os R_s. There are L=2r²-r logical outcomes.

Because sum_o f_o† f_o=I, sum_o M_o† M_o=P_S. The complementary classical erasure map is rho -> Tr((I-P_S)rho)|erasure><erasure|. Thus the logical outcomes together with erasure form a trace-preserving instrument on the entire physical space, including subnormalized inputs. Each supported branch satisfies M_o E V=(sum_s f_os c_s(E)) I, so every branch preserves the arbitrary unknown logical state; there is no postselection.

For channel h with Kraus operators K_hk, define the syndrome density sigma_h=sum_k c(K_hk)c(K_hk)†. The response is A_oh=f_o sigma_h f_o†. Computational-basis outcomes determine every diagonal entry; differences of real and imaginary pair outcomes determine both parts of each off-diagonal entry. The POVM is therefore injective on all Hermitian syndrome matrices. Its response rank equals the rank of the physical channel-output densities on any fixed encoded pure logical state. A full information-complete measurement is used; no shot-efficiency or optimal-design claim is made.

The SVD of A supplies the row-space projector. Column normalization places the normalization functional in that row space. For exactly consistent observations, inversion on the identifiable quotient gives the minimum-norm representative; if this representative is not nonnegative, a feasibility linear program returns another representative with the same identifiable coordinates. No nonunique representative is claimed to reveal the true underlying mixture. Noisy frequencies are fitted with constrained least squares on the simplex, with solver status exposed.

## Public development design

The development script independently applies local matrices by physical bit coordinates and derives an orthonormal basis from all I/X/Y/Z error images. It checks:

1. Completeness against the independent full correctable-space projector, using a spectral residual.
2. Scalar logical action of every exported branch on every Pauli error and both logical basis columns, establishing the full-span nondisturbance identity rather than testing only one logical state.
3. Agreement of the response with the exported physical operators.
4. Equality of the reported row-space projector and the row-space projector of independently constructed physical output density coordinates.
5. Feasible ideal estimates for interior, boundary, and uniform mixtures; count scaling; exact identifiable coordinates; unique weights where appropriate.
6. Subnormalized noisy mixtures, arbitrary physical branches with off-span mass, zero input, and raw erasure/mass conservation.
7. Invalid classical observations, a one-hypothesis model, impossible observations, and large finite count scaling.

The additional families use only the public codes, transformed by seeded local unitary operations and a logical basis unitary. The mixed libraries include coherent rotations, amplitude damping, dephasing, depolarization, random multi-Kraus CPTP channels, duplicates, and explicit convex dependencies. These choices exercise complex coherence and feasible inversion beyond the public Pauli example. All test construction and seeds are preserved in `run_development.py`.

| Public development family | Hypotheses | Available/reported rank | Unique | Outcomes |
|---|---:|---:|---|---:|
| Pollatsek–Ruskai Pauli library | 22 | 22 | yes | 946 |
| Shor Pauli library | 28 | 22 | no | 946 |
| Complex rotated Pollatsek–Ruskai mixed library | 24 | 19 | no | 946 |
| Complex rotated Shor mixed library | 32 | 27 | no | 946 |

All four families passed. The largest recorded physical/operator/response/certificate residual was 4.107825191113079e-15. Across 40 fresh ideal-mixture trials the largest identifiable-coordinate error was 3.3306690738754696e-15 and the largest prediction error was 4.7271214720367993e-17. The supplied public example also passed. Feasibility-program inversion was exercised on both mixed families.

## Finite-count observations

Each family had three fresh seeded multinomial trials, at 2,000, 20,000, and 200,000 shots. Every fit reported convergence and returned a feasible normalized representative. These are descriptive observations, not a universal error guarantee; different shot levels also use different fresh mixtures.

| Family | Coordinate error, 2,000 shots | 20,000 shots | 200,000 shots |
|---|---:|---:|---:|
| Pollatsek–Ruskai Pauli | 0.04160 | 0.01561 | 0.00691 |
| Shor Pauli | 0.02149 | 0.00831 | 0.00106 |
| Rotated Pollatsek–Ruskai mixed | 0.11047 | 0.02266 | 0.02470 |
| Rotated Shor mixed | 0.17823 | 0.03134 | 0.01440 |

Errors are the maximum absolute identifiable-coordinate difference. Complete true mixtures, observed count vectors, fitted probabilities, representatives, fit statuses, and prediction errors are in `development_results.json`.

## Measurements, provenance, and limitations

The independent numerical subprocess took 3.3374689770025725 seconds wall time and 3.37349 seconds CPU time, with peak resident memory 180032 KiB (about 175.81 MiB). These measurements include interpreter/import overhead. The in-script scientific execution interval was 2.8061189530017145 seconds. Per-family constructor and sparse-export timings are preserved separately. This is one measured run, not a benchmark distribution, cost comparison, or inference-compute measurement.

Every scientific Python command used `CODEX_PRIMARY_RUNTIME_PYTHON` with `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, and `MKL_NUM_THREADS=1`. No timing targets or discretionary engineering timeouts were used. The source contains 357 lines and 17702 bytes; the retained dependency contains 260 lines and 11778 bytes.

Sources used were the assigned `TASK.txt`, `SECOND_CONTRACT.json`, `PRIOR_ASSET.txt`, unchanged `recovery.py`, and the two public fixture modules. No outside workspace, private qualification material, other constructor result, agent history, paid service, extra package, or downloaded source was used. The mathematical claims above follow from the displayed construction and the checked identities; no claim of world novelty is made.

The domain is the stated finite, exact, well-conditioned code family with separated numerical rank. The implementation constructs up to 2r²-r outcomes, which is convenient and complete but can be statistically inefficient. Finite-count estimation uses constrained least squares, not a claim of likelihood optimality. Near-unidentifiable noise combinations can have large sampling error even with accurate predicted observations. Floating-point rank choices are numerical and are not a theorem about arbitrarily ill-conditioned families outside the contract. No physical-hardware or fault-tolerance claim is made.

Model inference calls, tokens, host compute cost, and monetary cost are unknown because no receipt exposes them. Included-agent execution is not zero economic cost. The acquisition and qualification cost of the retained asset must remain in the parent experiment's cumulative accounting; it is not treated as free here.

## Reproduction

Run from the artifact directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 "$CODEX_PRIMARY_RUNTIME_PYTHON" measure_process.py
```

The frozen evidence records the original execution. A fresh rerun should write its outputs to a separate writable copy to preserve that evidence.
