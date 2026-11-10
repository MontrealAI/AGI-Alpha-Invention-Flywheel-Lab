# Ω fresh successor instances — predeclared supplement

Version **omega-fresh-successor/1**, 2026-11-10. This supplements the fixed
`OMEGA-PROTOCOL.md` without changing any original case, expected result or arm.
It is frozen with its generator before candidate execution. The candidate
source is then frozen by SHA-256 **before** a new 256-bit nonce is sampled.
The nonce and exact generated instances are recorded for reproduction.

The independent generator/evaluator is
`scripts/qualify_genesis_successor.py`. Its source is outside the candidate
construction artifact and cannot be rewritten by that artifact. Public
generator logic is not secret; the post-freeze instance values are fresh.

## Fixed task and generator

Initial task: verify 24 exact bounded affine arithmetic instruments. Each has
random integers `x` in [-10000,10000] and `offset` in [-1000,1000], with exact
expected result `x + offset`, distinct source-dependency SHA-256 and the
original `bridge/instruments.py` source identity. These are correct by
construction; no candidate tunes itself on their generated values.

Distinct successor task: choose which capability checks require the next
validation effort under **20 evaluator calls**. The 32 successor records are:

- 12 unchanged observations sampled from the initial 24;
- 8 observations with changed source identity and changed input, sampled from
  the other initial records (half have deliberately incorrect expected values);
- 12 new observations with independent source identities (one third have
  deliberately incorrect expected values).

The generator shuffles these 32 records using the post-freeze nonce. This order
is the fixed priority order seen by every arm. All arms receive identical
information and may use the same complete content/dependency identities.
No extra hidden observation or free verification is supplied to the candidate.

## Fixed arms

1. **Fresh uncached baseline:** use the priority order and re-evaluate each
   check until its 20-call allowance is exhausted.
2. **Inherited candidate:** reuse only valid unchanged evidence, then allocate
   its 20 calls to remaining observations in the same priority order.
3. **Strong ordinary memoization:** independently implemented exact-content
   cache over full payload, checker identity and dependencies, with the same
   initial observations and allowance.
4. **Ablation:** candidate with initial evidence withdrawn, same allowance.

Report complete adjudication count, correct decisions, errors, refused stale
hits, actual evaluator-call count, elapsed time and CPU time for each arm.
All four initial constructions, including conventional cache construction,
count their initial evaluator calls. Separately compare total inherited
construction-plus-successor calls against a direct unbudgeted 32-check
successor; this prevents presenting a one-use cache as a net cost win.

## Fixed acceptance and claim limits

No stale or incorrect acceptance is permitted. Every decision actually emitted
must match a separate arithmetic oracle. The inherited and ordinary arms must
fully adjudicate the 32 cases within 20 successor evaluator calls. Any protocol
or source mutation aborts qualification. Candidate/evaluator hashes and seed
appear in the receipt; every arm is reported, including failures.

The superiority gate requires improvement over the strong conventional arm
after complete costs. The expected tied ordinary comparator is an admissible
negative result, not a failure to implement the experiment. Unknown engineering,
maintenance, host/electricity and financial costs prevent a complete-cost
superiority claim. A measured reduction against the uncached ablation does not
establish improved discovery over capable conventional reuse.

These are **fresh generated instances after a source freeze** of a distinct
internal task, not new external task families, a double-blind study, autonomous
open-ended discovery, actual market validation or general recursive intelligence.
