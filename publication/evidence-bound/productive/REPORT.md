# Local model preflight and scientific clock reconciliation

## Productive decision

The next scoped owner-computer experiment compares stronger local models on the existing dual-TITAN RTX system. Operators can inspect both publisher files and choose how to stage that run using a small download. The first preflight checked 579 tensor descriptors. A different architecture required a larger capture and then checked 459 more. The official decoder independently reproduced both layouts. Coalesced downloading was the main source of the observed speed difference. [First result](PREFLIGHT-FIRST.json) · [Repeat and recovery](PREFLIGHT-RECOVERY.json)

| MONTREAL.AI decision | Evidence and next threshold | Disposition |
| --- | --- | --- |
| Which local model should lead the already scoped dual-TITAN RTX run? | Two publisher checkpoints already selected. GPT-OSS has the lower declared weight span and dense KV estimate. Start its load probe first if the approved build can run this exact MXFP4 file, with Qwen as the comparison or fallback. | Public preflight executed. Await owner-host telemetry. |
| Which site monitoring intervention should follow the NISAR catalog studies? | Public catalog and site shortlist exist. A real observation-driven decision requires actual approved imagery, decision owner, intervention and accepted outcome. Another ranking would reuse the same metadata. | Preserve studies. Await approved pilot inputs. |
| Is an additional strategic observation worth acquiring in a real MONTREAL.AI decision? | The existing strategic instrument compared generic payoff regimes. A consequential choice still requires measured or independently elicited signal accuracy, admissible actions and costs for the actual decision. | Reuse instrument when those inputs have been authorized. |
| Is the earlier host-to-device optimization worth operation? | A qualifying advantage needs the actual production job, a CPU-only control, GPU trace and operator consent. Repeating a synthetic transfer would leave the operating question open. | Keep previous findings at their measured scope. |

[Previous value assessment](../../mission-executor/opportunity/REPORT.md) · [Original preflight registration](REGISTRATION.json)

## Exact model evidence

| Quantity | Qwen3-30B-A3B Q4_K_M | GPT-OSS-20B MXFP4 |
| --- | ---: | ---: |
| Declared publisher file bytes | 18,556,685,824 | 12,109,566,624 |
| Tensor descriptors agreed across both implementations | 579 | 459 |
| First tensor byte offset | 5,969,408 | 13,008,288 |
| GGUF block count | 48 | 24 |
| Declared native context tokens | 40,960 | 131,072 |
| Dense float16 KV scenario, one 4,096-token sequence | 402,653,184 bytes | 201,326,592 bytes |
| Dense float16 KV scenario, one 32,768-token sequence | 3,221,225,472 bytes | 1,610,612,736 bytes |

Each acquisition checked the publisher commit, reported whole-object digest and length, and the exact HTTP `206` body range. Responses have their own measured SHA-256. The default tool used serial 2 MB reads to the same exact publisher object. The coalesced control ran that same unchanged decoder on the actual acquired prefix. Agreement covers tensor names, shapes, types and offsets and the selected metadata. Full digest verification still requires the entire file. A small incidental payload tail is inside each retrieved prefix. [Qwen publisher](https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF/tree/e4d4bafdfb96a411a163846265362aceb0b9c63a) · [GPT-OSS publisher](https://huggingface.co/ggml-org/gpt-oss-20b-GGUF/tree/41e8a94d15d62070b36cf4553a0250717ecf46b8) · [Independent parser](https://www.npmjs.com/package/@huggingface/gguf/v/0.4.6)

The cache scenario uses two bytes per element for both K and V. The exact arithmetic multiplies sequence length, layers, KV heads and the combined key and value widths. GPT-OSS also declares a sliding window of 128 tokens. Backend-specific cache layout and memory allocation, GPU compatibility, resident weights, throughput and mission quality still require a measured host run. [GGUF format](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md) · [Qwen case](PREFLIGHT-FIRST.json) · [GPT-OSS case](PREFLIGHT-RECOVERY.json)

## First use, fresh transfer and conventional alternatives

| Observation | Coalesced fetch and retained parser | Official default fetch and decoder | Official decoder with exact same prefix already acquired |
| --- | --- | --- | --- |
| Qwen first | 7.123 s wall, 0.220 s CPU, 1 range, 8 MB | 29.247 s wall, 1.395 s CPU, 4 ranges, 8 MB | 1.028 s wall, 0.942 s CPU, 0 new bytes |
| GPT-OSS first repeat under original cap | 10 MB received, incomplete index | Requested a sixth range and reached the 10 MB cap | Incomplete index |
| GPT-OSS registered recovery | 12.385 s wall, 0.402 s CPU, 1 range, 14 MB | 60.499 s wall, 3.911 s CPU, 7 ranges, 14 MB | 2.796 s wall, 2.682 s CPU, 0 new bytes |

The initial two-case speed gate failed at its original cap. The separately registered recovery used the same object and symmetric 20 MB ceiling and stopped at 14 MB per arm. Candidate ran first on Qwen and the official default ran first on GPT-OSS. A single capture took 6.813 seconds and 11.975 seconds respectively. Adding separately measured unchanged-decoder time to the corresponding acquisition gives a 7.84-second and 14.77-second conventional coalesced estimate for those exact captures. This is an estimate from shared measured inputs, with one run per arm and unmeasured network variance. [Recovery registration](RECOVERY-REGISTRATION.json) · [First result](PREFLIGHT-FIRST.json) · [Repeat result](PREFLIGHT-RECOVERY.json)

Transfer consisted of reusing the Qwen acquisition and applicability controls on a second model family, observing failure at 10 MB, and adapting the acquisition ceiling. The official decoder matched all admitted results when given the same bytes. Its default serial fetch was the bounded withdrawal of coalescing. Four negative controls refused a truncated index, bad magic, impossible file size and a different publisher object with the same size. The retained method qualifies as a developer planning tool that can be carried forward to another exact model. The ordinary coalesced route is a practical incumbent. The experiment cannot attribute an advantage to the invention system, establish improving invention rates or justify dedicated maintenance of a second decoder. [Parser](gguf_preflight.py) · [Source binding](fetch_gguf_range.py) · [Ordinary comparison](ordinary_gguf.mjs)

The two completed comparisons read a combined **44 MB** of publisher response bodies across four arms, excluding discovery, registry responses and the initial unsuccessful attempt on each repeat arm. Development, setup, analyst attention, later maintenance, network and energy charges, distribution and recurring use frequency were unmeasured. The timed operation used zero model requests, paid-provider requests and GPU execution. Its deliverables are verified layouts and an operator planning calculation. Realized operating savings, financial return, transactions, predictive acceptance and independently controlled productive advantage remain unestablished. Keep the input/provenance guard, favor the supported decoder with coalesced input for ordinary operations and keep the separate parser as a cross-check. [Measured run](PREFLIGHT-RECOVERY.json)

## Native mission and admission

An operator-authored local action exercised the universal executor on the exact observed publisher metadata. It constructed a bounded calculator and produced both registered cache sizes from the recorded source input and two matching arithmetic references. The service returned `ABSTAIN` for the requested actual GPU value because its required telemetry field was missing. A fresh service instance reopened the workspace and found the same original ambition, execution artifacts and evidence. The portable archive retains the public source metadata and authored action journal. Provider transport was fixture-authored and there was no live inference in this mission. [Bound execution and archive](BOUND-PREFLIGHT-MISSION.json) · [Native replay](replay_bound_preflight.py)

| Asset | Operating contract | Admission |
| --- | --- | --- |
| Acquisition and exact layout check | Anonymous HTTPS to a pinned public GGUF publisher release. Requires Python 3.11+, curl, an exact commit, linked digest and size, and explicit per-arm byte caps. The comparison uses unchanged `@huggingface/gguf` v0.4.6 on Node 20+. Files remain local. | **GO** for developer replay and reviewable layout planning. Quarantine observations after a publisher identity change, completeness failure or parser disagreement. |
| Portable dense KV calculator | Exact recorded block, KV head and K/V width metadata. One dense float16 sequence with explicit length. Published result is the bounded estimate for the observed input. | **GO** for the stated arithmetic scenario. **NO-GO** for hardware fit, model selection based on run quality, telemetry or production capability approval. |
| Productive or causal promotion | Actual accepted owner output, recurring use, complete cost, independently retained new objectives and equivalent strong alternatives. | **NO-GO** for realized value, commercial demand, causal inventor improvement or reinvestment. Actual owner-host build and model ingestion remain separate. |

The exact hashes and observed inputs are in the JSON receipts. The retained calculation can be disabled by omitting its authorized action and by checking the source, version and scenario before each reuse. No active service or admission changed. The smallest pending hardware receipt is the existing single owner-host loopback run, including exact runtime build, model digest, per-card placement and peak memory, rates and tested mission outcomes. [Package lock and licenses](ordinary-package-lock.json) · [Owner authorization packet](../../cascade/OWNER.md) · [Owner machine procedure](../../../products/frontier-member-tools/activation/SUBSTRATE.md#owner-controlled-ubuntu-host-with-two-titan-rtx-cards)

## Scientific continuation

All 72 published July 2020 SAAO samples for TOI-216 have zero barycentric timestamps. Astropy reconstructed the clock from the recorded UTC times and the published site. Its topocentric result and an independent JPL Horizons DE441 geocenter projection differed by at most 0.019 seconds, within the expected site displacement. The separate 408-point November 2023 real observation reproduced its recorded BJD within 0.026 seconds. The reconstructed July visit starts 3.873 hours after the nominal TESS Sector 27 event ends. It starts 3.595 hours after adding the historical 1,000-second margin. This closes the specific same-event timing question for those July samples. April planet attribution, forecasting, and physical confirmation remain abstentions. [Registered test](CLOCK-REGISTRATION.json) · [Exact result](CLOCK-RECONCILIATION.json) · [Raw Horizons results](astronomy/) · [Previous ground-evidence investigation](../../mission-executor/opportunity/SCIENCE.md)

## Reproduce

Run from this directory. Choose a fresh `study` directory per acquisition. Assay output includes elapsed seconds and source response digests.

```sh
study=$(mktemp -d)
mkdir "$study/ordinary"
cp ordinary-package-lock.json "$study/ordinary/package-lock.json"
printf '%s\n' '{"private":true,"dependencies":{"@huggingface/gguf":"0.4.6"}}' > "$study/ordinary/package.json"
npm ci --prefix "$study/ordinary" --ignore-scripts --no-audit --no-fund
decoder="$study/ordinary/node_modules/@huggingface/gguf/dist/index.mjs"
python3 run_preflight.py "$decoder" "$study/first" --case first
python3 run_preflight.py "$decoder" "$study/recovery" --recover-repeat
python3 replay_bound_preflight.py "$study/local" "$study/bound.json"
```

The original repeat at its 10 MB cap can be reproduced with `--case repeat`. It stops on the incomplete index. The increased cap requires the separate recovery switch.

```sh
science=$(mktemp -d)
python3 -m pip install --target "$science/deps" astropy==7.2.0 numpy==2.5.5
cp astronomy/*.json "$science"
curl --fail --silent --show-error --location 'https://exofop.ipac.caltech.edu/tess/get_file.php?id=74164' --output "$science/2020.tbl"
curl --fail --silent --show-error --location 'https://exofop.ipac.caltech.edu/tess/get_file.php?id=948869' --output "$science/2023.tbl"
PYTHONPATH="$science/deps" OPENBLAS_NUM_THREADS=1 python3 clock_reconcile.py "$science"
```
