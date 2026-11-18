# Which measured load merits a field trial?

MONTREAL.AI needs an operating point it can justify before seeking infrastructure access. The headline for a verified Google GPT-OSS 120B endpoint reports **948,368.9 system tokens/s**. A user at that point would see a reported **42.1 tokens/s** and a **509 ms P90** time to first token. Both miss the illustrative interactive contract of 100 tokens/s per user and no more than 500 ms P90 to first token. Testing all published points selects run 4 at a recorded concurrency of **140**. The corresponding request counts are benchmark measurements. They do not represent a fleet, account or allocation belonging to the lab.

[Prescored comparison](REGISTRATION.md) · [Nine contracts](contracts.json) · [Fixed sensitivity sweep](SENSITIVITY.md) · [Independent results and timings](OBSERVATION.json)

| Registered workload | Maximal qualifying reported concurrency | P90 first token | Reported tokens/s per user | Highest-throughput alternative |
| --- | ---: | ---: | ---: | --- |
| Google GPT-OSS 120B, perf, reported mode | 140, run 4 | 147.6 ms | 294.4 | 22,528 concurrent, 509.0 ms, 42.1 tokens/s per user |
| Google DeepSeek, agentic inference dataset, explicit online mode | 128, run 5 | 165.1 ms | 106.9 | 2,048 concurrent, 20,722.4 ms, 26.5 tokens/s per user |

Both verified reports were published on November 4, 2026. The separate NVIDIA report was still pending review in the November 17 snapshot and is excluded from every supported decision. Full source URLs and the observed HTML/table hashes accompany each report. The two models, dataset distributions, hardware configurations and serving stacks differ. No cross-model speedup is inferred. [Official GPT-OSS report](https://results.mlcommons.org/endpoints/report?source=phase2&submission=d6b88dff-6bbb-4107-8d2e-1090decd4d53) · [Official DeepSeek report](https://results.mlcommons.org/endpoints/report?source=phase2&submission=3fdca196-7298-4b65-832d-d455abd792eb) · [Provisional report](https://results.mlcommons.org/endpoints/report?source=phase2&submission=053005da-b0ad-495d-9721-e39e9b144bd8) · [Benchmark method](https://docs.mlcommons.org/endpoints-submission-docs/understand/what-is-mlperf-endpoints/)

## Two meanings of a token-rate requirement

The displayed per-user rate and the reciprocal of the P90 time per output token are separate measures. The fresh DeepSeek report admits concurrency 128 under either definition at 100 tokens/s. At 110, the displayed-rate constraint selects 64 while the reciprocal-P90 constraint selects 128. At 200, the first must abstain and the second selects 24. Across all 400 registered integer thresholds with fixed 500 ms first-token constraint, the selected outcomes differed on **109**. The full table of intervals is in the receipt. These are sensitivities on the same nine published points, not 400 independent workloads, per-user guarantees, or measurements of total agent turn latency.

## Independent comparator and adoption decision

A conventional SQLite query reads the complete displayed run tables directly. It uses fractions for exact decimal comparisons, honors report status, workload/mode and every requirement, and returns all equally optimal measured load points. The separately authored Endpoint Lab reaches identical results on **all nine primary contracts and 800 sensitivity decisions**. Six primary contracts correctly withheld a recommendation. Seven corrupted decision-receipt checks were rejected, including altered latency, source/witness, scope and operating authority. A separate synthetic tie regression checks that two equally good points are retained. The independent checker covers the contract, operating authority, source population, eligibility decision and all selected numerical coordinates. Further interpretations in a producer's narrative require separate verification.

For these published reports, a direct full-report query is a sufficient strong implementation. The delivered instrument adds repeatable decision receipts, visible exclusions and an independently replayable field-test proposal. A unique institutional advantage and a newly attainable productive activity remain unestablished. A field decision requires permission to test actual infrastructure, a representative MONTREAL.AI input/output distribution, an independent quality/accuracy requirement, measured tail latency under that workload, and complete acquisition, serving and support costs. Keep non-entry available until these exist. The two benchmark-derived pilot points qualify only for preparing that next experiment.

One registered scorer run took **0.468880 wall seconds** and **0.469385 cumulative process and child CPU seconds**. It includes nine separate candidate processes, repeated full-table checking and an in-process 800-decision sensitivity sweep. Individual SQL timings exclude source loading and process startup; they are unsuitable as measured end-to-end speedups. The role of AI here was in researching and building the instrument; the 28 operating points are the original submitters' measurements. No new endpoint traffic or paid model calls were made. Acquisition, source verification, development, unsuccessful search, review, maintenance, field infrastructure, labor and monetary costs remain unmeasured.

## Reproduce from a clean checkout

From `products/frontier-omega-ignition`, using standard Python 3.11+ and its SQLite module:

```sh
python3 -B endpoint_study/score.py --output /tmp/ep01-new.json
python3 -B -m unittest discover -s endpoint_study -v
python3 -c 'import json; print(json.dumps(json.load(open("endpoint_study/contracts.json"))["interactive_gpt"]))' > /tmp/ep01-gpt.json
python3 -B endpoint_study/reference.py --contract /tmp/ep01-gpt.json
python3 -B endpoint_lab/decide.py --contract /tmp/ep01-gpt.json --output /tmp/ep01-candidate.json
python3 -B endpoint_study/reference.py --contract /tmp/ep01-gpt.json --receipt /tmp/ep01-candidate.json
```

The output locations for new observations and candidate receipts must be fresh. The direct SQL recipient only needs `reference.py` and `sources/`. It has no candidate imports, answer key or network dependency. `sources/` contains the three compact complete factual tables as displayed, including source strings at their original precision. To regenerate the source capture, save all three official complete reports and run `python3 -B endpoint_study/capture.py NEW_DIRECTORY report-1.html report-2.html report-3.html` with lxml available. Compare the table hashes and review state for each public submission. Dynamic HTML may change independently of numerical tables; a new source revision requires its own qualification before adoption.
