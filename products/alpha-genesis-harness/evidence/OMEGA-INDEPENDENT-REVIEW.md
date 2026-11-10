# Ω GENESIS NEXT — independent engineering review

Reviewer scope: the product's exact-evidence cache, isolated fixed-source
constructor, current-input acceptance, changed-dependency refusal and distinct
successor comparison. This review is independent of the candidate source
recipe; it is not an external commercial audit or an autonomous-discovery
evaluation.

## Baseline and frozen criteria

The inherited PR #324 product passed **170 Python tests and 60 JavaScript tests**
before this work. The original Ω protocol was published before candidate
outcomes at `0cf4d8444a4a7ba930d75937ee1dfa235389a53f`, with file SHA-256
`5d4b2141e8bf02f398e6a9a8508417d53105f6927b186ca49a92b1a42ddf12d5`.
The fresh-successor protocol and initial generator were published at
`67e03d3933dd73b5a82add380e2a6b84dcb21b99`, before any fresh nonce.

The fixed C01–C12 conditions are executed in
`tests/test_genesis_next_independent.py`. They test the original interpreter's
actual answers rather than copying the candidate's acceptance claims.
Fresh-instance receipts separately bind their executed source identities.

## Findings retained as lessons

1. **Input mutation during verification: FAILED, then repaired.** The original
   index computed a key before invoking the verifier but did not check that the
   caller-owned specification remained unchanged. A verifier that changed input
   23 to 24 and expected output 42 to 43 could retain the new successful result
   under the old key. The independently executed regression failed on the
   original implementation: a later request for the original case incorrectly
   reported reuse. The repaired implementation refuses a changed payload or
   dependency key before retention. The regression now passes. This does not
   retroactively turn the observed original failure into a pass.
2. **Artifact metadata belongs to the acceptance identity.** An instrument and a
   source record can have identical JSON bytes while the original checker treats
   their kinds differently. Candidate keys now include the artifact metadata;
   the independent regression verifies accepted instrument → rejected source
   record with identical content.
3. **Loaded-code identity must match source evidence.** Hashing newly edited
   disk files while continuing to execute already imported code misattributes
   evidence. The implementation pins loaded dependencies and refuses drift until
   restart. The separate security-review suite covers this boundary.
4. **Withdrawn inheritance retains acquisition costs.** Pre-execution review of
   the fresh-instance generator found that its ablation skipped the initial 24
   checks. Before generating any nonce, the implementation was corrected to run
   all initial checks and then invalidate their entries. The frozen protocol,
   case generator and acceptance thresholds were unchanged. All arms report
   actual acquisition plus successor calls.

The independent 20-test C01–C12 suite passed after the source-binding repairs.
The exact release archive must rerun it; this working-source result does not
qualify later changes automatically.

## Fresh generated successor — executed result

Source and final evaluator were publicly frozen at
`cabc418dde9c127f49a3999566102cab76c13410` before sampling the single retained
nonce. `OMEGA-FRESH-SOURCE-FREEZE.json` binds the candidate, evaluator, both
protocols, original interpreter and imported helper modules. The resulting
`OMEGA-FRESH-RESULTS.json` passed all predeclared correctness and allowance
conditions. Its SHA-256 is
`f318d3d6c2ac6785912d9030d7e8846320881b1b20a08bcd07f01dee267f9290`.
The C01–C12 suite was rerun on those candidate bytes: **20/20 passed**.

| Arm | Initial evaluator calls | Successor evaluator calls | Correctly adjudicated successor cases | Errors |
|---|---:|---:|---:|---:|
| Uncached baseline | 24 | 20 | 20/32 | 0 |
| Inherited candidate | 24 | 20 | 32/32 | 0 |
| Strong ordinary memoization | 24 | 20 | 32/32 | 0 |
| Inheritance withdrawn after acquisition | 24 | 20 | 20/32 | 0 |

The retained mechanism safely reused 12 unchanged observations and devoted 20
new evaluations to the remaining cases. It rejected stale transfer by identity.
The ordinary control achieved the same result. Candidate wall time in this
single tiny run was approximately 3.53 ms versus 0.88 ms for conventional
memoization; this is telemetry, not a statistically established speed estimate.
Initial construction plus this successor used 44 evaluator calls, while simply
evaluating the entire successor without prior construction would use 32. The
experiment therefore establishes useful reuse under its declared **successor**
allowance, **not** a complete-cost or strong-control superiority claim.

No fresh seed was discarded or regenerated. The receipt includes the sampled
seed and all generated cases, allowing exact reproduction of this first attempt.
Cases were sampled after the source freeze; they are fresh instances of the
specified internal task, not a new external task family.

## Interpretation

The constructor emits and executes an isolated, inspectable HARNESS subclass.
Its recipe is developer authored and deliberately bounded; it cannot edit the
external evaluator, import arbitrary changed source, access model credentials,
or promote itself into the running product. This establishes a useful tested
mechanism and a controlled self-modification experiment. It does **not** show
that GENESIS autonomously discovered an arbitrary new software improvement.

Conventional exact-content memoization is a capable equal-information control.
Matching its performance is a valid negative superiority result. Any saving
relative to repeated recomputation or an ablation must be stated with that
comparison. Unknown engineering, verification, maintenance and operating costs
prevent a complete-cost advantage claim. Public authored cases and post-freeze
fresh generated instances remain separate from new external task families.

No review outcome supplies live ChatGPT Pro consent, commercial OpenAI approval,
authenticated cloud inference, native macOS/Windows qualification, actual
customer demand or profit. Squarespace actions remain excluded.
