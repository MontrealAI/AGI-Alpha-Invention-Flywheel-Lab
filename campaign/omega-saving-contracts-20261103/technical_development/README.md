# Numerical construction: development evidence and decisive failure

The constructor produces independently accepted numerical outputs and a usable
standalone program. It does **not** demonstrate a faster complete workflow or
avoidable buyer compute spending. The strongest equal-content conventional
policy and ordinary reuse tie its method choices and declared work counts. A
bounded attempt to remove the verification bottleneck produced a useful optional
checker, but the complete candidate workflow remained slower than NumPy with
the same checker in every measured workload group. Stop this improvement
iteration and keep the direct alternative for these measured cases.

This is development evidence, not the held-out confirmation experiment, a demand
forecast, revenue, an autonomous invention of numerical algebra, or an externally
certified engineering model. All inputs are generated synthetic linear systems.

## What works, and what is not established

`omega_savings/kernel.py` accepts a typed local goal and explicit matrices and
right-hand sides. It checks whether repeated matrices, genuine supplied low-rank
updates, or neither hypothesis applies. It selects direct factorization, shared
factorization, or the established Woodbury identity, constructs complete Python
source, executes that source, and binds the result to the input and program.
Unknown goals, malformed numbers, inapplicable methods and unsafe conditioning
are rejected. The standalone example below needs NumPy/SciPy and no repository
imports, network, API, account or outside action.

`omega_savings/verify.py` independently checks exact rational residuals and a
strict row diagonal-dominance inverse-norm bound. For
`alpha = min_i(|a_ii| - sum_{j != i}|a_ij|) > 0`, the forward-error bound is
`||b-A*x||_infinity / alpha`. It accepts only the declared absolute/relative
tolerance and condition limit. It never calls the producer or trusts its method
claim. This is procedural independence on the same host. It does not establish
that a buyer's supplied equations describe a physical system. One-time NumPy
direct-solve and SVD qualification is separately executed and costed; recurring
production checks do not silently refactorize every matrix.

The methods are established capabilities. Relevant primary documentation includes
[SciPy LU factorization](https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.lu_factor.html),
[factor reuse](https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.lu_solve.html),
[LinearSolve's low-rank-update implementation](https://docs.sciml.ai/LinearSolve/stable/tutorials/low_rank_updates/),
and [Higham's diagonal-dominance bounds](https://nhigham.com/2021/04/08/what-is-a-diagonally-dominant-matrix/).
The prospective product's possible utility is finite packaging, setup and
checkable delivery. No buyer willingness to pay for those benefits, reduced
installation effort, actual service spending or incremental benefit over a
competent incumbent was measured here.

## Initial development: all 60 rows retained

The initial seed-11 run covers eight families by six policies, plus two fresh
successor families crossed with old/new method content and three policies.
`initial/results.json` retains all 60 rows: 44 accepted and qualified, 16
refusals, and zero exceptions. Adaptive, conventional and equal-content ordinary
reuse tie in all eight paired family comparisons. The weak analogy accepts only
two of eight main cells; invalid analogies are refused rather than passed off as
useful completion. Ill-conditioned and singular inputs remain failures of
applicability.

At dimension 32, eight cases, the declared complete per-batch scalar proxies are
237,776 for the installed repeated-direct route, 104,864 for shared RHS work and
198,600 for low-rank work. Dense changes and noisy update descriptions add
inspection cost without removing direct work. Dimension 16 low-rank development
selected direct work and lost 8,192 proxy units; the choice of dimension 32 was
made before confirmation. Neither dimension is a market limit.

These counts combine different kinds of work and are **not measured FLOPs,
equivalent processor cycles or dollars**. Exact rational arithmetic's bit
complexity, parsing, hashing, generated-program compilation, Python overhead and
optimized library execution can dominate. The actual repeated-use comparison
exposed that difference:

| Seed-11 diagnostic | Accepted repeated batches | Candidate complete seconds | Additional first qualification seconds | NumPy direct plus same checker seconds | Outcome |
|---|---:|---:|---:|---:|---|
| Repeated RHS | 10 | 1.210529 | 0.077697 | 0.685741 | Candidate slower |
| Low-rank updates | 33 | 3.813414 | 0.071804 | 2.022644 | Candidate slower |

The batch counts are the first integers that repay the separate 1,261,520-unit
qualification charge **within the declared scalar proxy**. They are not measured
cash break-even points. No persistent numerical-factor cache is claimed across
separate program executions. There is no incremental proxy saving over a strong
incumbent with the same methods. `initial/diagnostics.json` preserves both these
losses and the known-method connector replay; installing an already available
Woodbury template is not evidence of a new discovery method.

## One bounded checker improvement: all 108 rows retained

The optional `interval.py` / `interval.c` instrument uses directed IEEE binary64
rounding to bound residuals and diagonal margins conservatively. It compiles
reviewed source with fixed conservative flags into a private temporary directory.
Source, compiler, flags and binary identity are recorded; no binary is committed.
Unsupported compilation, unavailable bounds, overflow or inconclusive tolerance
checks fall back to the exact Fraction checker or explicitly refuse.

An immutable prepared boundary avoids copying the same input again inside a
single workflow. Each genuinely new request is validated and hashed afresh.
Prepared boundaries carry no financial authority and are not an authenticated
external-input format. Native service acceptance continues to receive raw
requests and to use **exact Fraction by default**.

The fixed development grid uses seeds 11/12, dimensions 32/64/128, RHS and
low-rank families, adaptive/conventional/NumPy-direct arms, and three rotated
execution orders. Every arm receives the same fast checker. Complete timing
includes fresh boundary preparation, construction when used, execution and
production verification. All 108 outputs were accepted by both fast and exact
checks; there were zero observed false positives. This finite result is not a
general proof of platform correctness.

| Dimension | Family | Adaptive median complete seconds | Conventional median complete seconds | NumPy median complete seconds | Adaptive wins? |
|---:|---|---:|---:|---:|---|
| 32 | RHS | 0.060817 | 0.058171 | 0.008151 | No |
| 32 | Low rank | 0.071435 | 0.072324 | 0.009294 | No |
| 64 | RHS | 0.207797 | 0.203332 | 0.028931 | No |
| 64 | Low rank | 0.204051 | 0.214131 | 0.029187 | No |
| 128 | RHS | 0.752158 | 0.715095 | 0.101095 | No |
| 128 | Low rank | 0.874462 | 0.904231 | 0.116881 | No |

Across the 36 complete runs per arm, adaptive took 13.133849 seconds,
conventional 12.945945 seconds and NumPy direct 1.744596 seconds. Cold compilation
cost another 0.134900 seconds once per process. Actual independent Fraction
qualification took 7.603993 seconds across 18 distinct input/output byte pairs;
it was reused only for identical bytes. Those one-time costs are disclosed
separately, not erased by the table. `interval/results.json` records every row,
including preparation/check timings and exact-qualification reuse.

The measured host uses Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, one OpenBLAS
thread and Ubuntu cc 13.3.0. CPU scheduling remains uncontrolled. The C runtime
checks directed rounding and gradual subnormals at compilation/load and restores
the floating-point environment around each calculation. A later unrelated native
extension changing flush-to-zero behavior was not qualified in this iteration;
the instrument remains optional. Its arithmetic bounds, extreme values,
ill-conditioning, forged outputs and unavailable-compiler fallback were tested
against exact Fraction. The broader platform/compiler set is unresolved.

## Cost, acceptance and next-action boundary

No real payments or paid API calls occurred in this numerical experiment.
Included host/subscription resources still have an economic cost; their actual
bill, buyer input preparation, installation and administrative labor are
unmeasured. Computer elapsed time is not human labor. The commercial simulation
must label any monetization of work-unit reductions as a conditional assumption,
and separately test zero cash avoidability. It cannot use these timing results
as support for actual compute savings.

The working buyer interface in `omega_savings/buyer.py` investigates alternatives,
constructs and checks a program, compares complete executions with the same
independent checker, and records the next action. On a valid measured slowdown,
the appropriate action is `USE_STRONG_DIRECT_ALTERNATIVE`. All measured candidate
and baseline outputs must pass acceptance before timing guides that choice.
Certification/packaging utility remains a hypothesis to test on its own terms;
it does not turn a slower route into a proven compute-savings offer. No further
tuning on this development grid or on confirmation was performed by this agent.

## Evidence identity and reproducibility

`SOURCE.json` records all executed source digests and distinguishes the initial
source from the optional instrument. `SHA256SUMS.json` binds the compact evidence.
All initial receipts and the single standalone example are copied byte-for-byte;
all 108 instrument rows are retained. `REGRESSIONS.json` records the local
18-test pass plus the subsequent metadata-only reproduction-role check. Hosted
CI, a merge, a release and downloaded-release execution are separate statuses.

The historical kernel and exact verifier are byte-identical to the current
ones. To reconstruct the exact initial experiment runner, reverse-apply
`initial-source.patch` in an isolated copy and check its SHA-256 against
`initial/registration.json`. Do not mutate an active frozen account's source.

From the repository root, use fresh output directories:

```sh
OPENBLAS_NUM_THREADS=1 python -m unittest tests.test_omega_savings_kernel -v

OPENBLAS_NUM_THREADS=1 python -m omega_savings.experiment \
  --output /tmp/omega-technical-development --seeds 11 --role development

OPENBLAS_NUM_THREADS=1 python -m omega_savings.interval \
  --benchmark /tmp/omega-interval-development

OPENBLAS_NUM_THREADS=1 python \
  campaign/omega-saving-contracts-20261103/technical_development/initial/standalone_example/plan.py \
  campaign/omega-saving-contracts-20261103/technical_development/initial/standalone_example/request.json
```

After the registered confirmation is complete, a later replay must use
`--role reproduction`; it is not fresh independent confirmation. Timing values
can vary by host and scheduling. Outputs, applicability, declared count formulas,
source binding and complete denominators are the reproducible claims.

## Compact correction ledger

| Tried or corrected | Observed outcome | Retained decision |
|---|---|---|
| Small low-rank work at n16 | Inspection erased arithmetic saving | Select n32 development fixture before confirmation; disclose n16 loss |
| Reused LU / Woodbury versus direct count model | Lower declared work on matching structure | Keep established methods, count qualification and inspect costs |
| Equal-content conventional and ordinary reuse | Complete method/count tie | No special discovery or inheritance advantage claim |
| Repeated-use exact-check workflow | Slower despite proxy break-even | Record actual loss; do not convert counts into measured cash |
| Directed-rounding checker and immutable input boundary | 108 accepted, zero observed false accepts; all six complete timing groups still lose | Keep optional checker; exact verifier stays default; stop tuning |
| CLI replay documentation | Reproduction role was missing | Add explicit reproduction label without weakening confirmation seed guards |
| Buyer timing acceptance gate | Every timed delivery must be checked | Parent applied all-row acceptance gate before source freeze |

