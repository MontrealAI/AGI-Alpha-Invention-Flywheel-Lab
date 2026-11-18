# Public-release investigation with a pinned local model

On November 18, 2026, IGNITION opened a research mission from three published llama.cpp releases and one earlier revision. A separate direct call to the same local Qwen3-4B model returned the same five hypotheses and the same initial favourite. The first ordinary mission stopped when the challenge reached the server's 6,144-token context limit. Reobserving the same releases produced zero additional children. No technical effect on a beneficiary, accepted delivery or payment was measured.

| Registered primary arm | Completed calls | Outcome | Wall seconds | CPU seconds |
| --- | ---: | --- | ---: | ---: |
| Direct discovery | 1 of 1 | Five proposals | 245.845 | 978.960 |
| Ordinary mission | 1 of 2 | Discovery completed, challenge stream failed | 333.116 | 1,313.445 |

Each discovery processed 3,439 input tokens and generated 1,951 output tokens. The canonical output SHA-256 begins `f7d66a31` for both. The Q4_K_M weights and llama.cpp b12242 archive added 2,520,439,371 bytes of downloads, 370.284 seconds wall and 7.125 seconds CPU before inference. Model calls used a loopback CPU server. Electricity, shared infrastructure billing and attributable revenue were unmeasured.

The primary source revision was `bd0ddc3dddb643856edcb8aa81cfb978713cc73a`. The source-bound budget, exactly repeated prompt, negative result and source access conditions are recorded in `observation.json`. The GitHub connector acquired the publisher objects. The workspace's direct public-source transport separately recorded a DNS-policy refusal. The connector copies were imported into the ordinary observer interface. The receipt includes the direct transport failure and the two independently observed response identities.

A fresh ordinary mission on `a44aa8535e7899aa197d6e17f567e86547792536` used a 12,288-token context. Its discovery reached the 2,048-token output ceiling and the controller declined the incomplete answer in 231.591 seconds. An unchanged observation again produced zero duplicate calls or children. A final registered experiment gives each model call the provider's usual 4,096-token output allowance. All four cited publisher excerpts also matched separate reads of their original public objects.

## Inspect or repeat

Run the offline consistency check from the repository root.

```sh
python -IB products/frontier-omega-ignition/evidence/source-observer-20261118/verify.py
```

To reconstruct the attributed public source arrays, use a new output directory on a host that can reach the four pinned GitHub objects. The command checks the original excerpt digests. Public metadata such as download counts can change. On a later day, the explicit replay timestamp restores the original source evaluation day. Model inference still runs at the actual current time. The fresh run can produce different outputs and timings.

```sh
cd products/frontier-omega-ignition
python -B evidence/source-observer-20261118/verify.py --capture /tmp/observer-public-inputs
python -B field_trials/prepare_cache.py --assets /tmp/observer-model-cache --receipt /tmp/observer-model-acquisition.json
PYTHONPATH=. timeout 600 python -B evidence/source-observer-20261118/recovery.py \
  --work /tmp/observer-new-trial --assets /tmp/observer-model-cache \
  --observations /tmp/observer-public-inputs --replay-at 2026-11-18T18:08:00+00:00
```

Cache preparation can download the two public pinned assets. The model run requires a supported Linux x86-64 CPU environment. For the final experiment use a new work directory, `--output-tokens 4096` and a 900-second time limit. The registration documents, complete model-output digests, original source links, parser receipts and resource measurements are included. The local-model answers are hypotheses.
