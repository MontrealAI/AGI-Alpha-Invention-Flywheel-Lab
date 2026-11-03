# Independent verification
All seven implemented methods pass the narrow registered recovery contract. This establishes neither a new activity nor Super Alpha.
## Final verification
- Independent carryless-polynomial GF(256), modulus 0x11d: all 65,536 products and 255 nonzero inverses cross-checked against the codec.
- All 16,384 survivor subsets per method enumerated independently, proving exact whole-shard helper minima and the complete erasure failure profile. Every 469 ordinary failure sets plus three rack losses passes.
- 420 independent encoder comparisons, 198,240 actual full-source decoder byte cases, 5,880 independently derived minimum-helper byte cases, and 5,880 actual supplementary minimum-read repairs pass.
- 9,440 binary matrix-vector successor recovery cases pass against integer bit-parity reference outputs. This is reuse of linearity, not independent market validation.
- Five unit tests pass, including seven corrupted-input rejection probes. Python -O is refused so assertions cannot be disabled. Source and preregistration fingerprints are checked before importing the codec.
## Outcomes
| Method | Mean helpers | Worst helpers | Minimum distance | Fresh rack layouts passing /20 |
|---|---:|---:|---:|---:|
| synthesized_xor | 3.0714 | 4 | 4 | 12 |
| reed_solomon | 8.0000 | 8 | 7 | 20 |
| conventional_lrc | 4.2143 | 7 | 5 | 19 |
| extended_hamming | 3.7143 | 4 | 4 | 18 |
| unscaled_lrc | 4.2857 | 5 | 6 | 20 |
| uniform_cauchy_lrc | 6.0000 | 6 | 6 | 20 |
| pair_local_lrc | 2.4286 | 5 | 4 | 16 |

The candidate loses 37 of 1,001 four-shard erasure patterns, versus 26 for pair-local LRC and zero for RS, unscaled LRC and uniform-Cauchy LRC. Ordinary pair-local LRC reads fewer shards on average; the candidate has the smaller worst-case helper count. These are tradeoffs, not dominance. Ordinary controls already meet the entire recovery contract.
## Limits and preregistration gaps
Original recovery timings measure eight-shard full-source decoding, not optimal single-shard repair. The explicitly post-original supplement separately executes minimum-read plans. None of these local timings establishes production cost, all-in economics, demand, novelty, frontier superiority, or annual profit.
The original search saves 24 final states, not a full proposal/failure/incumbent trace. Tie-breaking is lexicographic without a separate complexity proxy. Candidate joint proposals allocate roughly 35% to placement, while controls receive 9,600 dedicated placement trials. These gaps are disclosed, not retroactively repaired.
## Review history and reproduction
The first review recorded provenance matches without making mismatches fatal. Before publication the verifier was hardened to reject mismatches and deliberately tested against corrupt generators, helper claims, witnesses, coefficients, source fingerprints, preregistration fingerprints and modified source files. The final receipts are a new exact-source qualification; prior matching-source V1 evidence is retained locally. Original experimental source and RESULT.json remain unchanged.
Run `python -m unittest -v test_independent_review.py`, then `python independent_review.py --supplement`. The final evidence is INDEPENDENT_REVIEW.json and INDEPENDENT_SUPPLEMENT_REVIEW.json.
Runtime epochs are recorded as their source; filesystem modification timestamps are not treated as UTC or proof of registration order. No claim of independently verified public registration chronology is made by the verifier.
