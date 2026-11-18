# Endpoint Lab

**Which measured configuration should MONTREAL.AI investigate for an interactive inference pilot?** Enter the model, benchmark workload, minimum user token rate and tolerable first-token latency. The instrument examines every recorded load point, reports the highest measured concurrency satisfying the requirements, explains excluded points and identifies a concrete next measurement. It uses published numerical observations offline. A user can change the contract and rerun the eligibility decision without submitting a request to an inference endpoint.

The primary illustrated contract permits a P90 time to first token of 500 ms and requires 100 reported output tokens per second per user. In the verified Google GPT-OSS 120B report this selects **140 concurrent queries**. Run 4 records **147.6 ms** and **294.4 tokens/s/user**. The throughput headline comes from 22,528 concurrent queries, whose **509.0 ms** and **42.1 tokens/s/user** miss both requirements. The next measured load to investigate on the same system is 272. Its first token took 610.9 ms at P90. A lab operating its own workload would have to remeasure it.

The separate Google DeepSeek report gives an explicitly online run at **128 concurrent queries, 165.1 ms and 106.9 reported tokens/s/user** under the same headline limits on its own agentic dataset. The benchmark’s native agentic end-to-end rate requires a different observation. The two models and workloads serve as separate test cases. A user asking for strict online evidence on the GPT report receives an abstention because its configuration type is the less specific `submission`.

The chosen metric can change the experiment to run next. On the DeepSeek sweep, with the same 500 ms latency limit, the highest qualifying measured load differed for **109 of 400** prespecified integer rate requirements. At 64 tokens/s, the displayed per-user field supported 512 concurrent queries; the inverse P90 token-time definition supported 256. At 100 tokens/s the two selected the same run. An independent SQL implementation agreed on all 800 selections. This describes sensitivity across the selected thresholds, not the frequency of errors in deployed systems.

## Run the recipient

Python 3 and its standard library are sufficient. In the downloaded instrument directory:

```sh
python3 -B decide.py --contract contracts.json --case interactive_gpt --output decision.json
```

In the repository, from `products/frontier-omega-ignition`:

```sh
python3 -B endpoint_lab/decide.py --contract endpoint_study/contracts.json --case interactive_gpt
python3 -B -m unittest discover -s endpoint_lab -p 'test*.py'
```

To test your own question, save a single contract as JSON and omit `--case`. For example:

```json
{
  "model": "GPT-OSS 120B",
  "dataset": "perf",
  "max_ttft_p90_ms": "500",
  "min_tps_per_user": "100",
  "min_concurrency": 1,
  "load_mode": "reported",
  "rate_metric": "reported_tps_per_user",
  "require_point_accuracy": false,
  "require_price": false,
  "require_access": false
}
```

```sh
python3 -B decide.py --contract my-workload.json --output my-receipt.json
```

The command writes to a fresh file or prints JSON by default. A valid decision to withhold has exit code zero and empty `selected`. Malformed contracts and changed evidence bytes fail with a nonzero exit. Use the receipt's `eligible` and `excluded` rows to reconstruct the decision. `source` is the official submission ID and `run` is the one-based published column. Every equal-highest supported observed load remains in the answer. The receipt includes SHA-256 identities for the logical contract, executing program and input pack.

## What the numbers mean

| Contract field | Interpretation |
| --- | --- |
| `max_ttft_p90_ms` | Inclusive ceiling for the published 90th-percentile time to first token, in milliseconds. Individual requests may take longer. |
| `min_tps_per_user` | Inclusive floor in output tokens per second, applied using the selected definition. Supply a plain decimal string or integer. |
| `reported_tps_per_user` | Uses the displayed *Tokens/Second per User* field literally at the report’s displayed precision. |
| `inverse_p90_tpot` | Uses 1,000 divided by the separately displayed P90 Time Per Output Token in milliseconds. The comparison uses exact rational arithmetic. The two published fields can imply different decisions. |
| `agentic_e2e` | Requires a separately qualified end-to-end turn interactivity measure. The compact reports do not supply that measure, so this request withholds. |
| `load_mode` | `online` requires an explicit online configuration. `reported` can also use a completed `submission` with published concurrency and first-token/rate fields. An explicitly offline point is ineligible. |
| Evidence requirements | A point-specific accuracy requirement asks for a measured score at that point. Submitted reports contain none in the retained fields. Price and MONTREAL.AI access rights are also unmeasured, so either corresponding requirement withholds. |
| `min_concurrency` | Sets the smallest acceptable observed load. A supported result describes the selected exact run. It does not certify untested intermediate loads. |

Only verified, standardized, available, client-on-premises reports of the requested version, model and dataset can contribute. Retained queries must have a completed state, issued queries, and zero reported failures. A report's *Available* category describes the published system category. A recommendation gives no endpoint entitlement, capacity reservation or production authority.

Published scalar values are rounded. Changing their representation or re-deriving a separately named metric may affect a borderline result. The scope is three complete published load sweeps and 28 points. The highest supported point in this finite inventory does not describe every possible system, or the highest physically attainable concurrency. This is a retrospective, benchmark-conditioned decision for a proposed pilot. The thresholds are illustrative research choices. Neither human time savings nor commercial demand has been measured.

## Evidence and complete alternatives

Compare the result directly with the official report's **Run** columns and its TTFT, token-rate, concurrency and query-failure rows. The source site is an immediately usable conventional alternative. The separate registered evaluator uses an independently captured projection and SQL to execute the same decision. The primary reference links are [Google GPT-OSS 120B](https://results.mlcommons.org/endpoints/report?source=phase2&submission=d6b88dff-6bbb-4107-8d2e-1090decd4d53), [Google DeepSeek](https://results.mlcommons.org/endpoints/report?source=phase2&submission=3fdca196-7298-4b65-832d-d455abd792eb), [NVIDIA provisional GPT-OSS 120B](https://results.mlcommons.org/endpoints/report?source=phase2&submission=053005da-b0ad-495d-9721-e39e9b144bd8), and the [MLCommons methodology](https://docs.mlcommons.org/endpoints-submission-docs/understand/what-is-mlperf-endpoints/).

The two Google reports were published November 4, 2026. The NVIDIA November 13 report was pending verification when retrieved November 17. Its eleven measurements remain visible as a status control and do not enter a supported selection. MLPerf is a trademark of MLCommons Association. The interpretation and workload thresholds here are MONTREAL.AI research choices.

The recipient preserves compact numerical facts. The source archive records the SHA-256 of each downloaded HTML report. For independent retracing, save the three links as complete HTML source. From the repository's product directory, with lxml installed:

```sh
python3 -B endpoint_lab/project_reports.py --output /tmp/mlperf-new google-gpt.html google-deepseek.html nvidia.html
cmp /tmp/mlperf-new/reports.json endpoint_lab/reports.json
```

The source pages are dynamically generated. A fresh page digest can change with the date or unrelated site content. A change to the retained report cells requires a fresh reviewed projection. The portable program refuses a modified pack. It uses no paid APIs, hosted model inference or shell execution. Developing the tool, acquiring and verifying sources, conducting any physical pilot, and operating the infrastructure all have costs. The complete monetary amounts remain unknown.
