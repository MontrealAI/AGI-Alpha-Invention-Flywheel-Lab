# Bounded logical-class mass decoder: first construction diagnostic

**Status: exploratory research, not a decoder performance claim.** This is original
correction-kernel code, not an implementation of a newly invented coset principle.
No hardware validation, commercial revenue, or progress toward a USD 3B profit
claim follows from these simulations.

## Missing capability and test
Low-overhead quantum LDPC computation needs accurate logical corrections under
strict classical compute budgets. The attempted missing capability is bounded
allocation of candidate-search work to logical-class probability mass instead of
choosing the single likeliest error configuration. Success could reduce classical
and physical error-correction overhead, but this first experiment neither proves
that benefit nor establishes a monetizable product.

The **same deduplicated error pool** is evaluated two ways: minimum log-odds cost
versus sum of exp(-cost) by observable class. Full correlations in each undecomposed
Stim DEM error instruction are retained. The shared all-zero probability factor
cancels. Scores are exact for the finite pool, NOT exact class partition functions.
A configuration is a set of independent normalized DEM mechanisms; this is not a
claim to enumerate all microscopic physical circuit faults. Equivalent detector
AND observable columns are normalized using Tesseract's exact independent XOR
probability merge. Distinct configurations are counted once, irrespective of the
number of search paths or orderings producing them.

## Construction
- Tesseract provides four detector-order candidate corrections (beam 10, queue cap
  10,000 each). Invalid candidate syndromes are detected, never scored as valid.
- A cost-ordered GF(2) basis supplies a valid non-oracle fallback when all capped
  searches fail. These shots remain in the denominator and are explicitly counted.
- Local pairs sharing a detector discover zero-syndrome triples; equal detector
  columns also supply moves. At most 200,000 unique pairs and 1,024 cheapest moves.
  No global nullspace enumeration is attempted. Catalogue construction is biased
  toward earlier detector indices; its adequacy is a limitation, not a theorem.
- Bounded nearest-neighbor expansion produces about 256 configurations, deduped
  across seeds. The actual corrections are formed and checked against the syndrome.
- Optional, separately labeled repair (`--diversify`): two logical parities selected
  from a syndrome-only hash are forced opposite the current predicted bit via an
  added detector constraint. Two capped searches attempt alternate classes. All
  12 constrained decoders are prepared and their cost/memory counted. This uses no
  simulated true error or observed logical label. It adds up to another 256 local
  candidates; it is NOT cost matched to the initial kernel.

### Important interface repair
Tesseract `decode_to_errors` returns original flattened DEM indices, whereas
`decoder.errors` contains retained/merged errors. The initial run raised an index
error rather than silently corrupting the result. `diagnostic.py` recompiles the
normalized DEM with merging disabled, aligning the two index spaces. The failure
is retained in compact form in `PROVENANCE.md` (original log hash included).

## Reproduce
The source is opt-in, independent of the financial runtime, and preserved byte-for-byte.
Use Python 3.12 on Linux with the versions in `requirements.txt` already installed.
No install is performed by these commands. Unit/oracle checks need no circuit files:

```sh
cd research/quantum_decoder_phase1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
python -m unittest discover -s . -v
python independent_semantics_oracle.py
```

To replay, create a disposable working directory outside the checkout. Copy this
folder there as `research/`; put the pinned official Tesseract checkout there as
`upstream/` (or a symlink to an existing checkout). Do not add upstream to this Git
repository. Check its revision and circuit SHA256 against `PROVENANCE.json` before
running. From that disposable directory, using the pinned installed dependencies:

```sh
export PYTHONPATH=research OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python research/diagnostic.py --noise 0.001 --shots 128 --seed 2026110101 --output initial-p001-replay.json
python research/diagnostic.py --noise 0.002 --shots 256 --seed 2026110102 --output initial-p002-replay.json
python research/diagnostic_repair_snapshot.py --diversify --noise 0.002 --shots 128 --seed 2026110103 --output repair-replay.json
python research/default_sanity.py
```

The default sanity script writes `research/default_sanity.json` in the disposable
copy. Never overwrite the historical evidence in this checkout. Current diagnostic
uses final kernel, not the post-run initial reconstruction: these commands do not
claim byte-identical initial execution. Source chronology is in `PROVENANCE.md`.
The scripts have between-shot time checks, not a hard process deadline; protect a
replay with the host's process controls. Do not continue tuning this closed phase.

Official repository: https://github.com/quantumlib/tesseract-decoder
Commit inspected: `838d4f64acc16b5c15adda01302a719400329d4b` (Apache-2.0).
Executed official registry wheel: `tesseract-decoder==0.1.1.dev20261021032048`;
`stim==1.16.0`, `numpy==2.5.4`. Source HEAD and wheel are not claimed identical.
Circuit: official Tesseract public testdata, [[72,12,6]], six rounds, Z memory,
SI1000 noise, 432 detectors and 12 observables. The script records circuit and DEM
SHA256, seed and batch size (Stim samples can depend on batch size). It does NOT
claim these are byte-identical to Bravyi's Nature-paper simulation circuits.
Original Nature source context: https://github.com/sbravyi/BivariateBicycleCodes,
https://doi.org/10.1038/s41586-024-07107-7.

## Prospective stopping and evaluation rules
Initial fixed diagnostics: 128 shots p=.001; 256 shots p=.002, each capped at 240 s
between shots. No rejected shots. No raw sample archives; seeds, hashes, aggregate
outcomes and at most eight compact disagreement witnesses only. Five exact/unit
tests check mathematics, moves, deduplication and API scoring; small exact tests
are not the headline circuit result. Optional one repair uses a separate seed and
128 shots /240 s. If there is still no class-mass decision signal, stop this bounded
construction attack and retain the negative result; do not keep sampling for a
positive outcome. This is an exploratory diagnostic, not a hypothesis-confirming
trial. No training is performed; repair choice is diagnostic-informed.

Only a promising diagnostic would justify a fresh, separately seeded confirmation:
20% lower failure at no worse p99.9 latency, paired 95% CI excluding no improvement,
at least two settings, against strongest executable cost-matched baselines.
Underpowered samples are inconclusive. Fixed expansion/queue caps are not a
hard-real-time wall-clock guarantee, especially on a shared CPU. Preparation,
all unsuccessful searches, fallback shots and memory must stay included.

## Comparator and prior-art boundary
Inspected current official Tesseract features: beam climbing, detector-order
ensembles, sparsification, multi-pass graph shattering, and GARI representations.
These are not all executed or tuned here. GARI must not be sampled; multipass
requires compatible tagged detector classification. A four-order capped decoder
is NOT the strongest global comparator. No SOTA claim is permissible.

Mandatory prior art read as context:
- https://arxiv.org/abs/2608.25545 : class partition functions and certified/region
  methods, including exact degenerate decoding of small BB instances.
- https://arxiv.org/abs/2609.26958 : confidence and postselection; here zero rejection.
- https://arxiv.org/abs/2609.10056 : BP-gated Tesseract complexity reduction.
- https://arxiv.org/abs/2610.40490 : neural triage and adaptive compute.
- https://arxiv.org/abs/2512.07057 : IonQ BP-guided beam search and latency tradeoffs.
  Its CC-BY-NC-SA code was NOT fetched, executed, derived from or distributed.

Deliverable scope is this small opt-in `research/` directory only. Do not publish
`deps/`, `upstream/`, caches or raw sample dumps. This publication is a research branch only, not runtime integration. No merge,
deployment, spending or external outreach is part of this work.

## Initial achieved evidence (2026-11-01)

| SI1000 p | shots | same-pool minimum failures | mass failures | disagreements | fallback shots |
|---|---:|---:|---:|---:|---:|
| .001 |128|1|1|0|1|
| .002 |256|66|66|0|65|

These fixed diagnostics expose **no decision-level benefit**. They do not establish
that the broader hypothesis is false. Mean distinct seed corrections were only
1.016 and 1.027; four order searches mostly found the same correction or exhausted
their caps. The high-noise failure count is largely dominated by fallback shots.
The first kernel therefore failed to expose adequate class competition. The one
parity-constrained repair is a targeted construction response to this bottleneck,
not a claim that any parameter sweep succeeded.

Initial total times were 22.52 s and 170.89 s (preparation 0.86 s and 1.26 s), with
about 150 MiB maxRSS as reported in KiB by Linux. Exploratory p99.9 kernel latency
was 1.20 s and 1.77 s; with these sample counts, tail estimates are essentially
sample maxima, not validated service-level guarantees. The first run's last few
seconds overlapped the second run's setup, so these are unsuitable controlled
latency comparisons. Subsequent repair pins one CPU and runs separately. No
prospective performance threshold has been reached.

`kernel_initial_reconstructed.py` is an explicitly **post-run reconstruction** of
the original kernel, not a falsely claimed contemporaneous source hash. The final
kernel adds zero-syndrome singleton moves and factors expansion into a reusable
method for parity repair. Initial JSON is preserved unchanged.

Independent semantic audit additionally enumerated the complete original and
normalized joint distributions in a six-mechanism correlated toy DEM: maximum
absolute difference 1.11e-16. Forced-invalid searches checked actual fallback
witnesses, and constrained alternatives checked syndrome plus parity. See
`independent_semantics_oracle.py` and `VALIDATION.md` (the archived oracle already had import paths relocated for
portability). This is mathematical validation, not performance evidence.

For a clean bounded environment, use a single core, constrain BLAS threads, and
apply a process address-space limit appropriate to the available machine (2 GiB
is the intended ceiling for this first experiment). Initial runs enforced bounded
candidate/queue/model counts but did not set an OS address-space rlimit; recorded
peak resident memory is the evidence, not a claimed hard memory guarantee.

## One parity-diversification repair: negative construction result
Fresh-seed p=.002,128 shots: both methods32 failures,zero disagreements. Mean
classes per pool **exactly1.0**: the repair did not expose competing logical classes.
All256 forced-parity attempts failed the bounded search/validation; total invalid
searches426 includes170 initial-order attempts. The33 initial fallback shots remain
included. Preparation7.55s,total204.64s,peak449660KiB (~439MiB),exploratory p99.9
3.42s. There is no mass-vs-minimum accuracy result to interpret when every pool
contains only one logical class. This closes this bounded construction branch;
it neither disproves degeneracy-aware decoding nor justifies further tuning here.

### Baseline competence boundary (critical)
The executed `decode_to_errors(syndrome, order, beam)` overload fixes one order and
beam per call. Although its configuration sets `beam_climbing=True`, **that overload
does not run the configured beam-climbing ensemble**. Actual initial work is four
fixed-order,beam10,queue10000 searches. Documented official defaults allow20 orders
and queue200000 (default beam5),and full decode can use beam climbing; official
examples also use queue1,000,000 and24 orders. Our queue cap is20x below the default
and100x below that example; four orders are one fifth of the default. A larger beam
is not a substitute for these search budgets. Sparsification,multipass and GARI
were inspected but not executed or cost-matched. **This deliberately small diagnostic
is not a competent strongest-baseline comparison.** Search starvation is an observed
limitation of this construction/configuration,not a general property of class mass.

Fallback incidence and failure count alone do not establish their overlap. A
same-seed/same-batch replay of the fixed p=.002 diagnostic records that cross-tab;
it is verification of the existing sample,not another independent trial or new
parameter selection. Initial JSON and repair JSON remain unmodified.
`diagnostic_repair_snapshot.py` preserves the source matching the prelaunch hash;
current `diagnostic.py` adds cross-tab instrumentation only.

### Attribution verified; bounded official-default sanity complete
The fixed-sample replay reproduced66 failures and zero disagreements exactly.
**65 of66 failures occurred on the65 fallback shots**; the diagnostic was therefore
fallback-dominated. Mean logical classes per pool was1.0. Runtime varied strongly
on the shared machine: replay p99.9 was10.44s versus1.77s initially,another reason
not to treat these tiny timing samples as an established latency frontier.

A final validity-only sanity check used fixed syndromes0,1,2 plus shot8,the first
syndrome for which all four capped searches were invalid (selection examined no
true logical label). Official defaults were verified at runtime:20 orders,queue
200000,beam5,beam-climbing false. All4 official-default calls produced valid
corrections,with no low-confidence flags and no45s worker timeouts. Decode times
were1.189,0.810,1.996,and3.134s; individual preparation0.53–0.67s. On shot8 the
capped search had0/4 valid candidates in0.856s,while official default produced a
valid correction. This supports insufficient capped-search effort as the immediate
bottleneck rather than a broad model/indexing failure. It does not establish true
logical correctness,average accuracy,tail latency superiority,or strongest-solver
performance. `default_sanity.py` and `default_sanity.json` records the exact bounded check.

**Stopping outcome:** an actual syndrome-preserving class-mass correction kernel
and parity-constrained discovery mechanism were built and validated; this capped
construction failed to produce competing classes on the tested circuit. No
positive frontier-performance result was achieved. A new algorithmic strategy
would require its own explicit hypothesis and protocol,not continued tuning of
this negative diagnostic. Hardware validation and economic value capture remain
unestablished.
