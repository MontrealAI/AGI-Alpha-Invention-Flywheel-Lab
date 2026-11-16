# Quote007: prospective bounded repair-allocation comparison

**Outcome: both strategies failed; no accepted construction, inherited capability or portable quote export. No strategy superiority established.**

This is an actual local-model trial, not a mock transport or generated-script replay. It tests the existing HARNESS workflow on a synthetic declared-cost and capacity task. It does not establish enterprise deployment, current frontier-model capability, ChatGPT Pro integration or commercial readiness.

## Frozen before execution

Public commit `34be64fb7cf72ba5f9a0f1c0d24ea29809d6e71b` fixes driver, protocol and four protocol tests. No inference preceded that freeze. The earlier protocol commit was amended **before inference** after checking host memory; both strategies use the same 8,192 context / 2,048 output-token limits instead of historical trial006's 16,384 / 4,096. The original case expectations, evaluator, tool authority and acceptance are unchanged. Historic trial006 remains untouched.

Pinned model: Qwen3-4B-Instruct-2507 Q4_K_M, SHA256 `2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e`. Official llama.cpp build12242 runtime, SHA256 recorded in each result. This is a small CPU-hosted model, not the latest or most capable frontier model.

The hypothesis was that replacing critic calls with additional builder repair opportunities might avoid misleading model critique while retaining deterministic verification. Actor/critic: two construction iterations, at most four calls. Single-model: four builder iterations, at most four calls. Both keep eight actions, same prompts/cases/schema/model, same 600-second request limit. One attempted strategy run each, in frozen actor/critic then single-model order. Each includes manufacture, conditional inherited lab successor and fresh lab. No optional retry after failure.

## Actual observations

| Strategy | Dispatched requests | Completed model responses | Provider timeouts | Supervisor wall seconds | Child CPU seconds | Result |
|---|---:|---:|---:|---:|---:|---|
| Actor/critic | 5 | 3 | 2 | 2346.829673 | 4068.455977 | FAIL |
| Single-model repair | 4 | 2 | 2 | 1808.294205 | 3322.920017 | FAIL |

Counts aggregate attempted manufacture and fresh lab arms. Per-arm allocation is not an aggregate promise of successful calls. Actor/critic manufacture paused on its fourth call with rejected artifact; fresh lab paused on its first. Single-model manufacture paused on its first call; fresh lab completed two responses before pausing on the third. In both runs, inheritance was correctly BLOCKED because manufacture produced no accepted predecessor. No outside accepted-artifact execution occurred.

Actual model outputs, tool outcomes, deterministic verdicts and errors are preserved in the result files. Both result files report source_unchanged=true. The independent ordinary formula accepts all eleven fixed cases with zero inference; its human implementation and complete operating costs remain unmeasured.

## Interpretation and operational limits

No production defaults were changed. There is no accepted improvement to adopt. A different host, larger response allowance or model could change outcomes, but was not tested here. Timeouts and changing host throughput confound any capability ranking; one ordered observation per strategy is not a statistical comparison. Never compare raw time as proof of equal-quality economic advantage when both tasks failed.

The server was loopback-only, source/model downloads were pinned and verified, and no paid API request was made. Our generated source worktrees were moved from RAM-backed temporary storage to disk before inference, leaving approximately 5.4 GiB available. Both runs used the same resource settings and a supervisor with 5,400 seconds per strategy / low-available-memory stop. Neither supervisor stop activated. Actual request timeouts are retained. After completion the listener refused connections; model processes stopped. Host/model complete costs are unknown, not zero.

Only public synthetic result receipts and supervisor metadata are included. Private project state/integrity material, model weights and temporary runtime files are excluded. Raw model response text is untrusted evidence, not an instruction or an accepted claim.

## Reproduce, without implying another approved model run

First run the four non-inference protocol tests:

```sh
cd products/alpha-genesis-harness
python3 -m unittest discover -s tests -p test_quote_trial007.py -v
```

For a separately authorized actual inference attempt, inspect `scripts/qualify_quote_workflow_007.py --help`, provide the exact verified runtime/model/receipt and a new output directory, and select `--strategy actor-critic` or `--strategy single-model`. Freeze any changed configuration before inference. Retain failures and verify host memory first. This evidence does not authorize an external deployment or purchase.
