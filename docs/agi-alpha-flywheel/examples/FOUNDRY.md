# Instrument foundry results

**Scope:** authored finite exact-arithmetic program construction; no business accounts, market evidence or physical qualification.

Protocol: [FOUNDRY_PROTOCOL.md](FOUNDRY_PROTOCOL.md). Source: [instrument_foundry.py](instrument_foundry.py). Exact records: [foundry-results.json](foundry-results.json).

## All registered requests

| Arm | Accepted | Certified nonidentifiable | Exhausted | Rejected | Scalar arithmetic operations |
| --- | ---: | ---: | ---: | ---: | ---: |
| fresh | 30 | 6 | 0 | 0 | 51633 |
| frozen_first | 30 | 6 | 0 | 0 | 49041 |
| accumulating | 30 | 6 | 0 | 0 | 48141 |
| conventional | 30 | 6 | 0 | 0 | 13566 |

## Whole-episode cost by family

| Family | Fresh | Frozen first generation | Accumulating | Conventional |
| --- | ---: | ---: | ---: | ---: |
| shared | 8082 | 5202 | 4158 | 3819 |
| disjoint | 3321 | 3609 | 3753 | 2661 |
| changed | 8082 | 8082 | 8082 | 5094 |
| rank_deficient | 32148 | 32148 | 32148 | 1992 |

Counts include executed construction, failed search, certificate checking and expanded runtime arithmetic. They are unit scalar rational-operation counts, not calibrated compute cost, money or profit. Bit lengths, serialization traffic, node visits, invalidations and descriptive timing are in the JSON.

Fresh and frozen-first-generation policies are mechanism ablations. Conventional rank-aware reuse is the competitive comparator and may win. A positive accumulation difference does not establish an improved discovery policy: all supplied compilers remain fixed.

Every accepted program remains in the supplied observation span. No retained program creates an unobserved distinction. Full-rank program fixtures, invalid-identity/type controls, a false-nullspace control and explicit exhaustion are checked separately from the 36 requests per arm.

## Reproduce

```sh
python3 examples/check_foundry.py
python3 examples/instrument_foundry.py --run --output /absolute/new/foundry-results.json
```

Run from `docs/agi-alpha-flywheel`. The preferred [portable checker](check_foundry.py) reports both recorded and replay Python versions and excludes only Python-version metadata and measured timing from equality. All scientific, source, protocol, workload, artifact and cost fields must match exactly. This is a deterministic replay of public, exposed tasks, not new independent confirmation. A new output path preserves the original registered record.

Run status: **COMPLETE**. Public protocol commit: `fa7a1117b91340afb27288ec09adbc33926d9ba4`.

## Interpretation and accounting supplement

This section interprets the preserved initial registered execution. It does not change the source, workload, protocol or recorded results. The source-bound deterministic replay passed. The primary run completed all 144 requests, with no implementation error, rejection or exhaustion; its seven separate adverse controls all passed. Search attempts that did not produce an answer remain included in construction costs. The controls are not additional successful workload instances.

**Use the conventional rank-aware compiler for this exact linear domain.** It achieved the same 30 accepted programs and six certified nonidentifiable requests per arm while using 13,566 declared arithmetic operations. The accumulating expression constructor used 48,141. Conventional compilation had the lowest whole-episode arithmetic total in each of the four families. This is a comparison of these supplied implementations on this authored suite, not an optimality theorem about every compiler.

Retained programs did become executable ingredients of later, different programs. On shared-substructure episodes, accumulating retention reduced total arithmetic from 8,082 for fresh construction to 4,158; freezing the archive after generation 1 cost 5,202. Thus later artifacts contributed beyond repeatedly reusing the first one. On disjoint requests, accumulation increased arithmetic from 3,321 to 3,753. Operator/type changes removed the measured retention advantage. These adverse cases matter to the interpretation of the shared family.

### Where the arithmetic changed

| Arm | Construction | Independent verification | Expanded execution | Total |
| --- | ---: | ---: | ---: | ---: |
| Fresh | 47,466 | 4,026 | 141 | 51,633 |
| Frozen first generation | 44,442 | 4,458 | 141 | 49,041 |
| Accumulating | 43,326 | 4,674 | 141 | 48,141 |
| Conventional | 8,751 | 4,674 | 141 | 13,566 |

**Expanded runtime arithmetic is identical across all four arms: 141 operations.** The observed gain from retention is in construction search, partly offset by extra certificate verification. For the shared family alone, fresh construction costs 6,948 operations, verification 1,080 and execution 54; accumulating construction costs 2,376, verification 1,728 and execution the same 54. Retaining a qualified program does not make its arithmetic free, and this experiment does not demonstrate a faster executed measurement.

Each expression arm constructed all 30 accepted programs through its bounded expression search. The six rank-aware fallbacks per expression arm supplied the six independently checked nonidentifiability witnesses. Conventional compilation used its rank-aware path for all 36 requests. Expression search proposals totaled 4,964 for fresh, 4,565 for frozen first generation and 4,382 for accumulating retention. Those proposal totals include unsuccessful and duplicate proposals; proposal counts are distinct from scalar arithmetic counts.

### Signed comparisons, including losses

Each entry below is **accumulating cost minus comparator cost**, using complete three-generation episode totals. Negative values favor accumulation; positive values favor the comparator. Every family contains nine requests per arm.

| Family | Minus fresh | Minus frozen first generation | Minus conventional |
| --- | ---: | ---: | ---: |
| Shared substructure | −3,924 | −1,044 | +339 |
| Disjoint targets | +432 | +144 | +1,092 |
| Changed identity/type | 0 | 0 | +2,988 |
| Rank deficiency | 0 | 0 | +30,156 |
| All registered requests | −3,492 | −900 | +34,575 |

The large conventional advantage on rank-deficient requests comes from using exact linear algebra without first spending the expression-search allowance. All arms correctly preserve the information boundary. There is no difference in accepted-request coverage under the registered allowance, no improvement to a discovery policy, and no evidence here about the prevalence of shared structure in naturally occurring work.

### A concrete three-generation lineage

In episode 1, both accumulating and conventional construction produce the same following executable lineage. `read(i)` accesses the current observation `y_i`; calls expand recursively on each new input.

| Generation | Constructed expression | Retained-call depth | Expanded arithmetic per input | Artifact ID |
| --- | --- | ---: | ---: | --- |
| 1 | `p1 = read(0) + read(1)` | 0 | 1 addition | `26ce347303454c14ee25cfb3c2954cebe146772f07d44c31b0a07e7ab1251fcb` |
| 2 | `p2 = call(p1) + read(2)` | 1 | 2 additions | `96c34d77e688a25cab1e34d8e12de30ddf528b738d0944e1aaf70a2cd2ce58ba` |
| 3 | `p3 = call(p2) + read(3)` | 2 | 3 additions | `422d62f096b032a6f081182fe968f04478d2368f287071ba9e3ab30a2737a611` |

The JSON contains the complete typed ASTs, operator identities, coefficient certificates and fresh latent inputs. The independent verifier derives coefficients from each AST and verifies every referenced artifact before checking the requested quantity. These three programs illustrate a compositional lineage; they provide no evidence of new information outside the supplied observation operator. The frozen archive reaches a maximum retained-call depth of one; accumulating and conventional archives reach two on the shared family.

### Serialization, time and limits of the cost model

| Arm | Artifact bytes written | Of those, retained archive bytes | Archive bytes read | Bytes screened for identity/type | Invalidated archive entries |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fresh | 14,001 | 0 | 72 | 0 | 0 |
| Frozen first generation | 13,425 | 4,897 | 9,866 | 9,794 | 6 |
| Accumulating | 13,155 | 13,155 | 13,870 | 13,789 | 9 |
| Conventional | 13,155 | 13,155 | 13,870 | 13,789 | 9 |

`archive_bytes_written` is a retained subset of `artifact_bytes_written`; these columns must not be added as disjoint write costs. `archive_bytes_validated` records initial identity/type screening volume. Full recursive certificate checking is charged to verification when an artifact is used. Archive reads include JSON container syntax; an empty archive serializes to two bytes. Invalidations count rejected entries at each screen, so the same stale entry may be counted on more than one request. Factorization-cache traffic is recorded separately in the JSON.

Arithmetic counts expand every executed rational addition, subtraction, multiplication and division in the declared phases. They do not price hashing, serialization, allocation, control flow, arbitrary-precision integer internals, software development or observation acquisition. The maximum observed numerator/denominator bit length was six for each expression arm and seven for conventional compilation. Runtime AST visits, primitive reads and retained calls are separately recorded. Common-subexpression reuse is limited to one latent-input execution.

Descriptive CPU totals in the preserved run were approximately 0.128 seconds for fresh, 0.132 for frozen first generation, 0.131 for accumulating and 0.041 for conventional. Such short single-run timings depend on the environment and are not a speed benchmark or significance test. In particular, the lower arithmetic count for accumulating retention did not translate into a lower measured CPU total than fresh construction in this run. Timings are excluded from exact replay equality.

Workload generation and direct formation of the common supplied observations are evaluation setup. Executed decoding and independent target checks are charged. The accepted programs operate only on their observation values; constructors do not receive the fresh latent inputs or target-generation recipe. Implementation and workload-authoring effort are supplied and unmeasured. A prospective measurement service would additionally need calibrated semantics, provenance, lawful access, external validation, uncertainty treatment, demand and complete business costs.

### Preserved provenance and replay environment

| Item | Recorded value |
| --- | --- |
| Public protocol commit | `fa7a1117b91340afb27288ec09adbc33926d9ba4` |
| Protocol SHA-256 | `6ca5081308beaf3805e7e53d2532edcf2380b91b4568bdc5a381003b80bbf8f7` |
| Source SHA-256 | `a71d0623d537e06c9facbd1efeded205b485f9204305a2f9d5a072913637e77a` |
| Workload SHA-256 | `4edb3aff1aaaf854d8f0d0d5d74c6d93fbb93917e25409bdcc1c3656aeae6d2e` |
| Python | `3.12.14` |

The frozen executable's strict `python3 examples/instrument_foundry.py --check` compares Python-version metadata as well as source, protocol, workload, artifacts and non-timing records. Use Python 3.12.14 for that original exact-environment check. The separate portable checker above preserves the source and initial record while permitting a different Python-version label; it still rejects any scientific-field difference, including a changed generated workload. A reproduction can also be written to a new output path for explicit comparison without replacing this record. The original run was not amended, tuned or selectively replaced after its outcomes were observed.
