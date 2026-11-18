# A qualification choice hidden by a leaderboard tie

MONTREAL.AI’s internal engineering evaluation has one question. If every represented repository matters equally, which published coding-agent configuration should enter the next qualification first? The two mini-SWE-agent 2.0.0 submissions both resolved **364 of 500** SWE-bench Verified cases. On the independently recovered 12-repository roster, GPT-5.2-Codex scored **65.6268%** per repository and GPT-5.2 (high) scored **64.6249%**. The executable evaluation input puts GPT-5.2-Codex first. Internal task performance, model access and beneficiary adoption await separate qualification. [Frozen mission](REGISTRATION.md) · [Qualification input](qualification_input.json)

| Measure | GPT-5.2 (high), A | GPT-5.2-Codex, B |
| --- | ---: | ---: |
| Historical resolutions | 364 / 500 | 364 / 500 |
| Mean of 12 repository resolution rates | 231449063 / 358142400 | 5341759 / 8139600 |
| Cases only that submission resolved | 22 | 22 |
| Reported submission cost field, dollars | 236.78350885 | 224.71194935 |
| Reported mean calls per case | 35.046 | 28.072 |

Both submissions resolved 342 of the same cases and both failed to resolve 114. Each repository gets one twelfth of the weight, so the same number of discordant resolutions can yield different scores. B resolved two more of eight Requests cases, while A resolved three more of 44 Sphinx cases. A post hoc sensitivity check found that dropping Requests alone would put A ahead by 1.1797 points. The registered decision includes Requests. Django accounts for 231 instances, and the submissions both resolved 181 there. The exact B advantage is 170873 / 17054400 of the possible score, or **1.00193 percentage points**. This is a finite-population comparison of two complete historical submissions. The paired counts describe reported harness outcomes. A source that records successful patch application still needs a separate resolution result. [All repositories and exact calculations](result.json) · [Publisher leaderboard](https://www.swebench.com/)

## What had to be constructed

The official leaderboard publishes all 500 A resolution flags. Its B entry publishes the same aggregate rate and identifies an evaluator archive, but omits per-instance flags. The acquisition client reads the first 115 bytes of each necessary original B evaluation report. Four complete Boolean fields establish the recorded resolution and patch-application status. Individual code changes, issue descriptions, tests, model conversations and full logs are outside the recipient.

A second source supplies the denominator. The first two columns of the pinned Princeton Parquet file contain 500 official repository and instance IDs. The receiver reads four compressed pages and intervening metadata from an original 4,490-byte prefix. Its strict standard-library reader checks the file layout, value counts, uniqueness and correspondence between the two columns. The original pages travel with the recipient. Matching IDs from two submissions do not establish the official population on their own. [Princeton publication](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/tree/c104f840cc67f8b6eec6f759ebc8b2693d585d4a) · [Range receipts](sources/roster-receipt.json)

Each disclosure subtracts measured resolutions from the pooled totals. The inherited facility-calibration routine gives sharp bounds for all remaining allocations, with one vote per repository. The instrument stops opening repository files once every feasible allocation gives the same ordering. A separately implemented SQLite route orders individual remaining case weights and obtains the same bounds at every one of 13 disclosure levels. Full conventional SQL also obtains the final rates and paired totals with a single grouped census, without adaptive bounds. [Inherited calculation](../../discovery_field/decision_study/calibration_bounds.py) · [Independent SQL](direct.py) · [Original submission catalogue](https://github.com/SWE-bench/experiments/tree/40f164d5b8f1d249bf95a6df8b74b577fd8e519d/evaluation/verified)

The order was fixed before opening the outcomes. At ten repositories, A minus B can still range from −305831 / 4775232 to 2443477 / 51163200. The eleventh disclosure, SymPy, settles the ordering after 269 original B outcomes. The two pooled totals determine the last repository’s counts. Testing all 4,096 subsets after the fact shows this is the unique decisive subset with only 269 individual reports. If a source supplies a whole repository total for the price of one request, a different cost applies. Four ten-repository subsets suffice, and the least expensive of those in original reports still requires 434. These minima apply to this snapshot and whole-repository disclosure contract. [All bounds and certificates](result.json)

## Reproduce or challenge

From this directory with the product tree or portable instrument available, use Python 3.10 or later. No packages, accounts or model calls are required for the offline commands.

```sh
python verify.py
python direct.py
python direct.py --stop
python verify.py --profile
```

The first command independently checks all stored conclusions and the fresh qualification input. It exercises source withdrawal, source replacement, duplicated and foreign IDs, unknown outcomes, contradictory pooled totals, exact ties, an actual pairing mutation at fixed margins and a weighting reversal. An additional control preserves the entire population contingency table while moving a paired resolution between repositories. A hash binds the frozen bytes. Independently decoding the population, verifying the original statuses and checking the estimand test different claims.

The same client can reobserve the public sources in new directories. The second command below physically stops network requests once the evidence suffices. The third validates new response prefixes, entity tags, source identifiers and byte ranges against the archived records while allowing retrieval times to advance. Omit the stopping option to recapture all 500 original B evaluations.

```sh
python roster.py /tmp/ignition-new-roster
python acquire.py /tmp/ignition-new-status --until-decision /tmp/ignition-new-roster
python prepare.py /tmp/ignition-new-status --compare sources
```

The source manifest supplies immutable Git and dataset revisions. Each B row supplies the S3 object path through its original ID, byte interval, entity tag, object modification time and retrieval time. Entity tags are opaque identifiers. The raw prefix is the portion of a checked evaluator report obtained here. Publication and ingestion times for individual decisions are unreported. No historical live-availability decision follows from this retrieval. The harness has not been rerun on these 500 tasks. [Source manifest](sources/pool.json) · [A submission](https://github.com/SWE-bench/experiments/tree/40f164d5b8f1d249bf95a6df8b74b577fd8e519d/evaluation/verified/20260217_mini-v2.0.0_gpt-5-2-high) · [B submission](https://github.com/SWE-bench/experiments/tree/40f164d5b8f1d249bf95a6df8b74b577fd8e519d/evaluation/verified/20260219_mini-v2.0.0_gpt-5-2-codex)

## What the successor establishes

Retaining an executable bound helped deliver a different decision on real, independently identified data. Replaying the two-facility example gives no decision for these repositories. A competent direct SQL workflow can reach the same decision and stop at the same 269 statuses. Ordinary grouped SQL is sufficient when all labels are local. A second physical acquisition stopped after 269 reports in 117.993 seconds. The full acquisition took 201.353 seconds. Including the four shared metadata responses, the two runs read 4,185,866 and 4,212,431 response-body bytes respectively. A single 4.09 MB leaderboard dominates both transfers. The separate Princeton roster used 23 successful ranges and a schema request. The clocks include network conditions at different times. The comparative economics also depend on checking, implementation, maintenance and beneficiary benefit. The historic submission dollar fields describe the publishers’ runs. Our actual bill, labour, opportunity cost, future model price, value on internal work and cost per adopted decision remain unknown. [Measured scope and costs](economics.json)

Benchmark leakage and imperfect task specifications limit transfer. OpenAI’s February 2026 audit of a subset of frequently failed tasks documented test problems and evidence of training-data contamination. Weighting repositories differently leaves both issues unresolved. The next decision requires fresh internal tasks with independently reviewed acceptance, equal rights and resource ceilings for both candidates, and a capable human or direct specialist baseline. The delivered input records those missing conditions. [Publisher audit](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/) · [Next qualification input](qualification_input.json)
