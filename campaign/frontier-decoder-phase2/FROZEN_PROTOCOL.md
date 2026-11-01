# Phase 2 proposal — single-frontier bounded terminal-list construction

Status: source feasibility inspected; NO patch, build, or new experiment executed.
Phase-one package and research directory remain unchanged.

## Hypothesis and narrow novelty boundary
Phase one mostly exposed one class because each bounded search returned one goal
or no goal. Hypothesis: retaining the already-built priority frontier after a first
syndrome-consistent goal, while avoiding residual-only merging of alternative
histories, can obtain multiple valid error configurations/classes more cheaply than
independent constrained searches. A finite candidate list can then support a real
same-pool class-mass decision. This is a new construction relative to phase one,
NOT a claim to invent list decoding, multi-goal search, or degenerate ML decoding.

Prior art: Tesseract https://arxiv.org/abs/2503.10988 and official Apache-2.0 code;
class partition methods https://arxiv.org/abs/2608.25545; IonQ paper
https://arxiv.org/html/2512.07057v2 Appendix B explicitly already maintains valid
results and a num_results stopping condition. Its noncommercial implementation
was NOT accessed or used. This proposal derives only from official Tesseract code
and generic error-set/probability identities, not IonQ implementation details.
BP-gated Tesseract, neural triage, and soft postselection remain comparator/prior-art
boundaries, not claimed innovations here. No exhaustive novelty review is claimed.

## Feasibility findings at pinned source
quantumlib/tesseract-decoder commit838d4f64acc16b5c15adda01302a719400329d4b.
- src/tesseract.cc decode_to_errors_with_graph (~504–751) owns the queue, error-chain
  arena, pushed-count cap, and reconstructable goal chains. No restart is necessary.
- Goal handler (~566–604) reconstructs original flattened DEM error IDs then returns.
  It can safely retain the goal and continue popping the same frontier.
- Residual-only visited checks (~606,~691) can discard histories with different
  logical action. Merely changing return to continue is inadequate. For the minimal
  list mode, disable BOTH checks using the existing no_revisit_dets=false option.
  A residual+logical key is NOT an exact-state fix: blocked-error history differs
  even when residual and logical labels agree. Do not claim it preserves mass.
- Goal handling must continue before the residual-beam update: do not set
  min_num_dets=0 and accidentally collapse the remaining beam to an altered policy.
- Queue cap counts pushes, not current queue length. Existing behavior may create
  P+1 pushed nodes before stopping. Preserve/report that convention rather than
  silently advertise an exact P bound; arena allocation is correspondingly bounded.
- Detector-driven search does not enumerate disconnected zero-syndrome cycles or
  expand zero-syndrome roots. Returned list remains a partial pool, NOT all errors,
  global top-K errors, certified mass bounds, or unbiased class evidence.

## Exact minimal proposed patch
1. `src/tesseract.h`: add opt-in `CandidateListResult` with deduplicated candidates
   (original DEM IDs), true likelihood costs, logical labels, pushed/popped/expanded
   counts, maximum queue/arena sizes, raw and duplicate goal counts, and stop reason.
   Add `decode_to_error_candidates(detections, order, beam, max_unique_goals=64)`.
   No default configuration behavior changes.
2. `src/tesseract.cc`: factor the existing search helper to accept an optional list
   collector. Legacy null-collector path retains original first-goal behavior.
   List method requires no_revisit_dets=false (reject incompatible configuration
   rather than silently alter it). At a goal, reconstruct RETAINED error indices,
   XOR-canonicalize repetitions into a sorted set, independently verify syndrome,
   dedupe by that retained set, calculate cost and logical XOR, then map to original
   representative IDs for the public API. Store each unique configuration once.
   Continue the current queue until64 unique goals, existing P+1 pushed cap, or
   exhaustion. Do NOT stop simply because two classes appeared; that would change
   the sampling/selection rule after seeing interesting output.
   Preserve first valid goal as the prediction. On cap/exhaustion after any goals,
   return valid candidates with `truncated=true`; do not discard them or imply no
   valid correction. Distinguish no-goal from incomplete-list status explicitly.
   All goal processing/canonicalization/dedup costs count in measured runtime.
3. `src/tesseract.pybind.h`: expose opt-in method/result only; document original-ID
   contract and partial-pool semantics. Python class-mass reduction can use stable
   log-sum-exp on returned true costs, with every unique candidate exactly once.
4. `src/tesseract.test.cc` / binding tests: deterministic small DEMs with multiple
   classes, multiple same-class configurations, duplicates, correlated separators,
   merged/original IDs, empty syndrome, cap reached before/after first goal, queue
   exhaustion, and zero-goal fallback. Compare every returned witness against H/L.
   max_goals=1 with no_revisit=false must reproduce pristine first-goal correction
   and cost under identical order/beam/cap on deterministic cases.

No per-class quota in this minimal patch: quotas would distort finite-pool mass
and confound whether retaining the frontier itself exposes class competition.
Class-aware prioritization is a possible DIFFERENT future hypothesis, not part of
this diagnostic. This first list mechanism is deliberately simpler and falsifiable.

## Matched build and unchanged controls
Bazel/Bazelisk is absent; g++14.2.0 is present. Official AGENTS.md mandates Bazel,
--jobs=1. Before any benchmark, obtain a pinned official Bazel/Bazelisk toolchain
through the approved vendor/registry route; record version and binary hash. No
unrecognized executable/source installation. If toolchain retrieval is blocked,
report the build blocker, not a decoder result.

Create two local worktrees at the SAME commit: pristine and modified. Use identical
Bazel version, C++ compiler, .bazelrc, architecture flags, dependency revisions,
Python/Stim toolchain, optimization mode, and one-core affinity. Preserve resolved
module lock, complete commands, compiler/version, and executable/wheel hashes.
Build both with `bazel build --jobs=1 --config=wheel ...` (matching portable flags),
run upstream relevant tests on both, and new tests on modified. Do not compare the
phase-one installed wheel with the newly compiled extension for speed.

Primary controls at fixed beam5/order0/queue200000:
A. Pristine single-goal API, no_revisit_dets=true.
B. Pristine single-goal API, no_revisit_dets=false (isolates pruning change).
C. Modified single-search list, no_revisit_dets=false,max_unique_goals64.
Also check modified max_goals1 against B on mathematical/regression cases.
The list may consume more of the SAME push ceiling after the first result; this is
not equal actual work. Report actual counts/time. Existing pristine verbose trace
can supply pushed counts in a SEPARATE deterministic telemetry replay; do not time
verbose output as baseline. No speed advantage claim merely from equal caps.
An official20-order configured decode on four fixed syndromes is a competence
anchor only, not cost-matched to single-frontier variants.

## Finite diagnostic, conditional on reviewed patch/build
First mathematical and regression tests; stop on any syndrome/ID/dedup failure.
Then the same published [[72,12,6]],6-round SI1000 p=.002 fixture/hash as phase one.
Four fixed development syndromes0,1,2,8 from seed2026110102 (chosen before this phase;
shot8 was selected by capped validity, not true label). Plus16 fresh stream shots,
seed2026110201,batch1. No parameter tuning or seed substitution. No rejected shots.
The no-goal fallback remains deterministic and all failures/timeouts count.

Single CPU;2GiB process address-space ceiling; each decoder call subprocess timeout
45s; entire diagnostic15min ceiling after builds. Build preparation separately capped
at30min,one core,with setup time/storage/memory recorded. These are resource bounds,
not hard-real-time guarantees. A timeout yields a scored fallback and explicit count.
Do not claim timeout selection establishes intrinsic solver performance.

Record first-goal and final-list cost/time, unique configurations and logical classes,
validity, raw/duplicate goals, all search counts, truncation/cap/timeout, fallback,
prep/peak RSS, finite-pool minimum versus sum decisions, paired truth scoring only
AFTER decisions. Store seeds/hashes/aggregates and <=8 compact witnesses; no sample
archive. Tail statistics from20shots are descriptive maxima only.

Go/no-go: this stage establishes candidate-generation feasibility, not accuracy
superiority. Continue no further if zero valid multilogical pools appear, search is
mostly no-goal/timeout, invariants fail, or build cannot be matched. If multilogical
pools appear but no decision changes, retain the mechanistic result without claiming
accuracy. Only a meaningful candidate pool could justify a separately registered,
larger diagnostic/confirmation; no automatic cap sweep or positive-result fishing.

Hardware utility, strict latency benefit, and commercial profit remain unproved.
