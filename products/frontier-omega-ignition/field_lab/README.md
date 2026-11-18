# Endpoint Field Lab Ω

MONTREAL.AI needs to know whether an endpoint completes a useful bilingual task under load. This instrument submits service briefs, times the visible response, checks the resulting machine-readable contract and withholds an operating recommendation when the evidence is incomplete. Both a field client and a conventional curl client can run it. A separate SQLite evaluator replays the observed wire events.

## What happened

Six public English and French briefs ask for exact latency and delivery-rate requirements. Four have enough information to produce a typed contract. Two require abstention. The authored mix includes seconds, milliseconds, French decimals, per-user versus aggregate rates, and the wrong latency percentile. It represents a technical use case for internal intake. The distribution of incoming MONTREAL.AI briefs is unknown.

| Local service | Requested and observed concurrency | Complete on first attempt | Complete by end of turn | Correct usable outcome | Verdict for the six briefs |
|---|---:|---:|---:|---:|---|
| Nominal grammar fixture | 1 and 3 | 6/6 | 6/6 | 6/6 | Accepted at both observed loads |
| Adverse grammar fixture | 1 and 3 | 2/6 | 3/6 | 2/6 | Withheld at both loads |

Both the HTTP and curl clients obtained those counts. The adverse profile introduced one wrong answer, a retryable 503, an interrupted response, an empty response, and an unexpected model identity. It took seven attempts to deliver six logical turns. Fast, wrong and partial responses remained in the denominator. The nominal fixture also supplies a simple conventional grammar that solves this frozen population. This is a serious outside option for strictly structured intake. Natural production briefs need fresh references.

These observations qualify replay and rejection on scripted public traffic. The [recorded projection](PUBLIC.json) binds the clocks, percentiles, source and receipt digests to the four [capture files](evidence/). The [pinned-CPU adapter](../field_trials/observe.py) can exercise an actual local model. Physical availability, representative traffic quality, complete cost and the production operating decision require separate evidence.

## Reproduce from the product directory

Ordinary Python 3.10+ with SQLite suffices for offline verification. Fresh dual-client measurement also requires curl on PATH.

```sh
python3 -B field_lab/verify.py --public field_lab/PUBLIC.json
python3 -B field_lab/verify.py --receipt field_lab/evidence/adverse-conventional.json
python3 -B -m unittest discover -s field_lab -p test_field.py -v
python3 -B field_lab/field.py fixture --output /tmp/frontier-field-fresh
python3 -B field_lab/verify.py --public /tmp/frontier-field-fresh/PUBLIC.json
```

Choose a new output directory. A fresh run measures new clocks. The frozen answers, injected faults and independent decision rules reproduce. All four historical capture files remain inspectable. A source mismatch requires using the recorded revision or qualifying a new capture.

## Field protocol

| Decision input | Exact interpretation |
|---|---|
| Frozen work and demand | Equal weights over six public briefs, once per configured concurrency. A closed-loop worker starts the next case when one finishes. Requests have distinct corpus IDs. The measured peak counts overlapping client attempt intervals. This captures a finite closed-loop run, including client overhead. An arrival-rate population needs a separately registered driver. |
| Task quality | Strict JSON object equality to the beneficiary reference, including required keys, exact numbers, booleans, and abstention. Formatting differences are allowed. Duplicate keys, extra fields and prose fail. |
| First visible output | Client monotonic microseconds from initial attempt dispatch to the first nonempty visible text frame in the final attempt. A frame may contain multiple tokens. TTFT here describes first client-visible output. Transport, queueing at the local service and any admitted retry are included. |
| Complete user turn | Dispatch to observed end of the final attempt. Require matching model identity, a visible payload, a normal stop, and the terminal SSE event. Tool calls, content refusals, length stops, truncated streams, empty responses and wrong identities fail. |
| Output tokens and delivery rate | Tokenize the joined visible output with the pinned GGUF through llama.cpp after the timed runs. Disable special-token insertion and parsing. Preserve the resulting token IDs and separate provider-reported usage. Divide visible tokens by **complete turn duration**, including first-token wait and retries. Compute thousandths of a token/s by rounding down. A fixture token is explicitly one UTF-8 byte. These metrics differ from published MLPerf per-user throughput, reciprocal P90 token gap, and generated tokens including invisible reasoning. |
| Load-specific decision | Nearest-rank P90 first-visible ≤500 ms, P90 complete turn ≤2,500 ms, P10 delivered rate ≥5 tokens/turn-second, and observed peak equals requested load. All turns need usable timing and token evidence to pass interaction. Quality and first-attempt completion each require 100% in the registered trial. A displayed percentile can describe a measured subset when the decision withholds. |
| Failure and retry | At most one retry, solely after a 429/503 with no accepted stream payload or client error. Record all attempts. A later successful request cannot erase a first-attempt failure. |
| Revalidation | Change to prompt population, outputs, model, tokenizer, server settings, concurrency, hardware, or authority requires a fresh run. The offline checker independently parses wire data and computes SQL ranks and overlap. On the authorized running model, it can also repeat tokenization and compare all native token IDs. Hashes identify the captured files. Physical source authentication requires trusted capture and separately verified target identity. |

The [frozen registration](REGISTRATION.md) and [exact workload](workload.json) specify the tested operating scope. The apparatus applies the source-boundary and fresh-work principle from [OUT-EXECUTE, pp. 4–10 and 11–18](../../../docs/harness/OUT_PAPERS.md). A previously observed benchmark row provides a reason to choose the next test. New service traces provide the service verdict. The tokenizer parameters and response contract follow the [pinned llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/b12242/tools/server/README.md).

## A privately authorized service run

The private operator supplies an already running, locally owned, non-forwarding llama.cpp server. This CLI takes a literal loopback origin. It accepts no API key, remote address, proxy, custom path or redirect. A loopback address alone cannot establish ownership. The process owner verifies the weights and executable digests, serving arguments and resource scope before issuing authority. The public exhibition cannot invoke this command.

The authority document contains schema 1, scope `authorized-workload-pilot` for approved private traffic or `public-synthetic-pilot` for the frozen public workload, target label, `base_url` shaped like `http://127.0.0.1:PORT`, model alias, `model_sha256`, `runtime_sha256`, hardware, configuration, the exact `workload_sha256`, `max_concurrency`, `max_attempts` per invocation, `tokenizer` set to `llama.cpp-/tokenize-add_special=false-parse_special=false`, and `locally_owned_no_forwarding` set to true. The included trial adapter constructs the permit from verified artifacts. Each client invocation can send at most the permitted number of inference requests. Retokenization uses at most one local tokenizer call per distinct nonempty observed text. Verification with the explicit option below repeats those tokenizer calls.

```sh
python3 -B field_lab/field.py run --route field --workload field_lab/workload.json \
  --authority /private/permit.json --output /private/new-field.json
python3 -B field_lab/verify.py --workload field_lab/workload.json \
  --receipt /private/new-field.json --retokenize-authority /private/permit.json
python3 -B field_lab/field.py run --route conventional --workload field_lab/workload.json \
  --authority /private/permit.json --output /private/new-conventional.json
```

New capture files are created owner-readable only and can contain complete response text. Keep private captures in the approved workspace. Only the frozen public briefs are eligible for a public fixture package. No test runs customer traffic, changes a deployment, or secures provider capacity.

## The blocked operating experiment

The source-matched GPT-OSS 120B report on Google's GB300-NVL72 system with TRT-LLM supplies two concrete observations. At 140 concurrent queries it reports 147.6 ms P90 TTFT and 294.4 tokens/s per user. At 272 it reports 610.9 ms and 264.3, crossing the illustrative 500 ms latency limit. The primary source, original scalar values and specific report hash are retained in the [Endpoint Study](../endpoint_study/sources/manifest.json). DeepSeek has a different model and workload.

The mandate supplies no matching cluster allocation, administered listener or representative private request distribution. The physical 140/272 comparison therefore remains unresolved. The decisive field test needs the matching configuration, permitted load neighbourhood, hardware entitlement, frozen representative task mix and reference answers. Compare the intended deployment with its actual incumbent and a serious alternative under the same requirements. A local CPU trial of a different model can establish evidence about that CPU model only.

| Operating obligation | Evidence from FA01 | Next decision |
|---|---|---|
| Technical function and task quality | Complete stream, exact quality, retries and actual observed load per row | Use the appliance for the approved pilot scope and investigate each failure before widening it. |
| Availability and maintenance | One short run per case/load gives first-attempt outcomes. Long-run uptime, recovery, patching and on-call work remain unmeasured. | Specify the beneficiary's observation period, availability requirement and service owner. Measure outages under agreed conditions. |
| Resource fit | Client process CPU, curl child CPU where available, wall-clock duration, tokenization, output size and clean reference verification. The live adapter can record server resources separately. | Capture hardware allocation, energy and serving obligations on the intended hardware. |
| Economics | Complete supplier prices, labor, setup, prior engineering, verification/rework, maintenance, support, incident cost and voluntary demand are unknown. | Compare cost per correctly delivered contract against the conventional grammar, direct benchmarking/SQL, incumbent and no adoption. |
| Adoption | Both fixture clients reached identical finite verdicts. A short synthetic replay cannot establish a deployment scope. | Defer the production decision. Claim acceptance only for the observed registered replay. |

The measured public fixture runs include the retry and both incomplete and incorrect outputs. Each receipt separates process CPU, child CPU, per-client wall and retokenization. The public projection also records independent verification time. The fixture server runs in the capture process, and its CPU is included there. Source acquisition, historic construction, electricity and continued support have no audited monetary total. The [historical Endpoint Lab](../endpoint_lab/README.md) and the earlier failed model investigations remain separate evidence.
