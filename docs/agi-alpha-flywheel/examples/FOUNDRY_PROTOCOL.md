# Instrument foundry finite construction protocol

Protocol ID: `agi-alpha-instrument-foundry/1`  
Status at registration: prospective; no substantive benchmark executed.  
Scope: exact, authored computational experiment for the second AGI ALPHA FLYWHEEL research edition.

## Question and permissible conclusions

Can a program constructed for one measurement request become an executable ingredient of a different request, and does retaining later programs reduce the measured burden beyond repeatedly using the first program? Does a conventional rank-aware compiler already provide an equally good or better route?

The intended application is on-demand retrospective measurement: construct a requested quantity from existing traces when those traces contain the necessary information, or expose the missing distinction. This experiment studies its exact computational core. It is not physical calibration, autonomous discovery of a new industry, a commercial simulation, or evidence of profitable demand. It does not create or mutate enterprise accounts.

The code is a developer-authored **linear-expression/straight-line program synthesizer**, not a linear-programming optimization study. No paid model calls, network requests or private data are involved. The public workload is a mechanism test, not protected statistical confirmation. Reuse cannot create information outside the available observation span.

## Observation model and executable products

Each request has six latent rational coordinates `z`, six primitive observations `y = A z`, one exact linear target `q z`, an observation-operator identity and a quantity type. Constructors receive `A`, `q`, the type, permitted primitives and their eligible archives. They do not receive the latent execution inputs, target-construction recipe, family name or generation number as synthesis inputs.

The language consists of typed primitive reads, exact rational scaling, addition, subtraction and calls to qualified retained programs. Each artifact is a serialized AST plus an exact flattened coefficient certificate `w`. Independent acceptance expands the AST without invoking the synthesis or elimination routines, verifies compatible types and identities, and checks `w A = q`. It also executes the program on three fresh latent inputs and compares with direct target evaluation. Every retained call expands into its actual arithmetic; a call is not a one-operation replacement for its contents. Exact common subexpressions may be evaluated once per execution, equally for all arms.

A nonidentifiability claim must supply `h` such that `A h = 0` and `q h != 0`, checked independently by direct exact products. Failure to find a program within a search budget is `EXHAUSTED`, not `NONIDENTIFIABLE`. A malformed program, failed certificate or wrong output is `REJECTED`, never successful completion.

All intermediate quantities in an operator have its declared type. Generation-specific identity or type changes invalidate earlier executable qualifications. A changed identity does not imply information loss; it requires a fresh construction or valid requalification.

## Frozen workload: twelve episodes, three requests each

The primary denominator is **12 episodes x 3 generations = 36 requests per arm**. There are four arms. Failed, exhausted and nonidentifiable requests remain in that denominator. Each episode starts with an empty generated-program archive and a fresh compiler state. No episode inherits artifacts from another.

Three variants use seeds `17`, `29`, and `43` in each family. Each starts with the six-dimensional identity matrix. Using a local `random.Random(seed)`, perform six row-shear operations: choose two distinct row indices with `sample(range(6), 2)`, choose a multiplier from `(-1, 1)` with `choice`, and add that multiple of the second row to the first. Then use `sample(range(6), 6)` to permute observation rows. These are exact invertible operations. Use seeds in the declared order and do not select a favorable permutation after execution. Python version is recorded.

Write the resulting rows as `a0` through `a5`. Constructors receive only the resulting target coefficients, not the following recipes.

| Episodes | Family | Generation 1 | Generation 2 | Generation 3 |
| --- | --- | --- | --- | --- |
| 1-3 | Shared substructure | `a0+a1` | `a0+a1+a2` | `a0+a1+a2+a3` |
| 4-6 | Disjoint targets | `a0+a1` | `a2+a3` | `a4+a5` |
| 7-9 | Changed identity/type | First two current rows | First three current rows | First four current rows |
| 10-12 | Rank deficiency | `a0+a1` | last coordinate vector `e5` | `a2+e5` |

For episodes 7-9, generation 1 uses the seed-generated operator and type `u`. Episode 7 changes operator identity each generation by adding `generation_index` times row 1 to row 0 of the original operator (`generation_index` is 0, 1, 2); type remains `u`. Episode 8 keeps the numeric operator but changes its type to `u`, `v`, `w`. Episode 9 makes both changes. Identity includes the full operator and type, not just a supplied label.

For episodes 10-12, set the last column of every generated observation row to zero. This gives a rank-five operator. Define targets from these modified rows, with `e5=(0,0,0,0,0,1)`. The two later requests are intended information-boundary controls; an independently checked witness must establish their status.

For every request, execute on three new six-dimensional integer latent vectors. Replicate `r` uses local seed `10000 + 100 * episode_index + 10 * generation_index + r`, with zero-based indices and `r=0,1,2`; each coordinate is `randint(-11,11)`. Workload generation and direct construction of observations are common evaluation inputs, not charged as a fictional acquisition process. Runtime decoding and independent target checks are charged.

## Arms and permitted construction

1. **Fresh:** the generic expression synthesizer receives no retained target programs on each request. Its previous targets, observations and operation receipts remain available as data; only executable target-program retention is removed.
2. **Frozen first generation:** the same synthesizer retains only qualified generation-1 target programs. Later programs are checked and executed but are not eligible synthesis atoms in later generations.
3. **Accumulating:** the same synthesizer may retain every qualified target program from earlier generations.
4. **Conventional rank-aware reuse:** exact row reduction produces a decoder or nullspace witness. This arm may cache its operator factorization, compile ordinary exact expressions, perform common-subexpression reuse, and retain qualified target programs. It has the same primitives, types, observations, data history and construction permissions as the other arms.

Every arm may retain operator-calibration/elimination metadata under the same operator identity. The archive intervention concerns generated target programs, not a ban on generic implementation caching. The conventional arm is not forced to mimic expensive expression search, and may tie or beat it. The three expression arms use identical code except for the eligible archive policy.

The expression constructor searches deterministic atoms consisting of current primitive reads and compatible retained programs, most recent retained programs first and primitive indices ascending. It considers exact atom matches, scaling by `-1`, `1/2`, and `2`, and sums/differences of atoms. It can construct intermediate expressions and search again, with at most three expansion rounds, 96 distinct semantic atoms, and 512 proposed arithmetic transformations per request. A proposal that duplicates an existing semantic vector is still charged. A fixed deterministic traversal is used and recorded in source; it cannot use family or generation recipes.

The constructor may use exact rank-aware compilation as a fallback after its bounded expression search. All preceding unsuccessful search remains charged. If its total arithmetic allowance is exhausted, it must return `EXHAUSTED` instead of silently resetting the allowance. A fallback that supplies a valid impossibility witness earns the appropriate nonidentifiability result, not a successful measurement.

## Fixed endpoints and stopping rules

Execute all registered requests once in each arm, in episode, generation and arm order. Each request permits at most **100,000 exact rational scalar arithmetic operations** across construction, certificate checking and runtime acceptance. Separately record search proposals and archive traffic. The expression-search caps above apply before fallback. No time-to-success retry, changed seed, replacement task, enlarged budget or omitted failed arm is allowed after the first substantive run.

A program exceeding its allowance receives `EXHAUSTED`; its incurred operation counts remain reported. An implementation fault invalidates the affected run. Preserve its compact failure and source identity, repair only the fault, and label a new full execution as a corrected reproduction of this protocol rather than silently retaining favorable cells. Any change to workload, arms, costs or limits requires a separately identified protocol amendment before rerunning.

## Exact operation accounting

Count every executed rational addition, subtraction, multiplication and division in construction, failed search, elimination, certificate generation, independent verification and decoding. Each vector/matrix operation is expanded into its actually executed scalar operations. Count all executed operations, including operations with zero operands; algebraically avoided operations are not charged. Fraction internals such as integer gcd operations are not represented by a single known runtime cost: disclose maximum numerator/denominator bit length and record CPU/wall time separately.

Maintain per-phase scalar counts for `construction`, `verification` and `execution`; the sum is a declared **unit arithmetic-operation count**, not FLOPs, dollars, calibrated energy or complete business cost. Report additions/subtractions and multiplications/divisions separately as well. Do not turn CPU seconds or counts into monetary profit.

Measure serialized archive bytes written, read and validated, retained artifact counts, dependency depth and invalidations. Actual serialization/deserialization and identity checks occur; report their byte volume and elapsed CPU/wall time rather than inventing a currency tariff. Record typed AST node visits and primitive reads at runtime. Repeated valid calls can share an exact common subexpression within one execution, but not an answer from a different latent input. No cross-request answer cache is allowed.

Compiler implementation/development and public workload-authoring effort are common supplied software and are not measured by the runtime counter. This limitation is explicit; execution costs do not establish autonomous invention economics. Failed trials, fallback costs and qualification work inside the registered execution are included.

## Registered comparisons and result fields

Primary outcomes are accepted executable programs, independently certified nonidentifiability, rejection and exhaustion, each reported separately. For every request retain compact identities, target, status, certificate or witness, produced AST, inheritance references, actual costs, and fresh-input checks. Report all four arms and all four workload families, including unfavorable cases.

The comparison of accumulating with fresh measures retained-program contribution in this constructor. The comparison of accumulating with frozen first generation tests whether later inherited means add a benefit beyond the first artifact. Compare entire episode costs, including generation 1. Compare with the conventional arm separately; a favorable ablation does not establish superiority to conventional compilation.

Report signed differences, not only wins. Runtime/compiler timing is descriptive and not a significance test. Results provide no estimate of task prevalence or market demand. No claim of an improved discovery policy follows from these fixed supplied algorithms.

## Adverse acceptance controls

After the primary campaign, independently check these bounded mutations using a small separate full-rank fixture and hold its original target fixed. Coefficient and AST/read mutations must change semantics; equivalent rewrites are not expected to fail. Their results are controls, not extra successful workload instances:

- change a nonzero decoder coefficient while retaining the original target;
- mutate an AST read or arithmetic operation;
- present a retained artifact under a changed numeric operator;
- present one under an incompatible type;
- provide a purported nullspace witness with a nonzero observation product;
- request a target with the search/operation allowance exhausted, preserving `EXHAUSTED` rather than claiming impossibility.

A control not rejected as specified invalidates the corresponding acceptance claim. Also reconcile full runtime call expansion with a directly expanded expression on the same input, so retained calls cannot receive a free-operation discount.

## Alternative explanations and falsification

Accumulation may merely retain one repeatedly useful tool, may cost more than it saves, or may be matched by ordinary incremental compilation. The frozen archive, disjoint requests, identity changes and conventional arm expose these alternatives. Shared-substructure episodes are constructed to permit inheritance; their results do not establish that naturally occurring work has the same structure.

An increase in attainable answers would be invalid if it relied on an unrecorded new observation, leaked latent state, mismatched units or relaxed acceptance. Every accepted decoder is constrained to the original observation span. A cost improvement is relative to the tested algorithms and declared accounting, not a proof that all conventional routes were previously infeasible.

The computational connection to a prospective industry is qualified construction of previously unrequested measurements from existing traces. A real offering still requires source provenance, calibrated observation semantics, rights, independent external truth where applicable, accepted uncertainty, actual demand and complete business costs. This study does not provide those missing commercial or physical facts.
