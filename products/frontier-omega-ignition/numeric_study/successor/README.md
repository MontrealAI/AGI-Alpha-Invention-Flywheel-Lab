# Delivering a repaired two-page table from retained or fresh model output

Both deliveries produced the same CSV. A separate parser verified all 25 cells and the temperature qualification on each page. Keeping the two earlier model outputs saved **58.216307 seconds** on this single repeat delivery. The two new calls also reproduced the earlier raw model outputs byte for byte.

| Measured Linux CPU run | Retained output | Fresh inference |
| --- | ---: | ---: |
| New model calls | 0 | 2 |
| Delivery wall time | 0.354181 s | 58.570488 s |
| CPU time summed across the delivery | 0.353831 s | 167.950352 s |
| Largest process peak RSS during delivery | 48,744 KiB | 3,022,092 KiB |
| Total wall time including the same crop preparation | 0.630989 s | 58.847296 s |
| Independently verified | 25/25 cells, 2/2 notes | 25/25 cells, 2/2 notes |

Crop preparation from original source took 0.276808 seconds and peaked at 52,272 KiB. Both arms used the same two registered crops, repaired decoder, acceptance criteria and CPU environment. Each fresh inference process independently loaded the provider weights. Its input was the corresponding registered image. Model and driver digest verification is included in the fresh arm. Both arms verified the identity of the recorded observations before releasing an artifact. Peak RSS is the largest individual process reported by Linux during each measurement. This was a single sequential pair, with retained delivery first and shared installed packages, model files and host caches. It measures redelivery for an already observed table. Performance on unseen papers and repeated-batch variability remain unmeasured. [Preregistered design at commit 4605b59](PROTOCOL.md) · [Measured comparison](COMPARISON.json) · [Two fresh model calls](fresh-observation.json).

## What the archive cost

Original acquisition took 68.2773 seconds for the full three-crop batch, including a separate published table. The two calibration model processes accounted for 51.8824 seconds of that time. The original receiver withheld the calibration, and its code and verdict remain available. The later repair accepted the retained observations. The two raw texts occupy 879 bytes combined, with another 1,621 bytes in their shared three-crop observation receipt. Both arms inherit the same prior design, decoder repair, installed model and evaluation work. Original data transfer, software installation, engineering, review and ongoing maintenance have no measured total cost. On this public synthetic source, direct HTML and native PDF extraction also produced the same accepted data. Their historical receiver windows were 0.000215 and 0.037301 seconds, respectively, excluding common preparation. [Original results and costs](../RESULTS.json) · [Original model receipt](../model_observation/observation.json) · [Repaired recipient](../RECOVERY.json).

## Reproduce the delivery

From the product directory, use the recipient dependencies in the [numeric study instructions](../README.md). This command independently decodes both observations, checks the source and all cells and footnotes, and writes a CSV plus its receipt per arm. Supply a new output directory.

```sh
python3 -B numeric_study/successor/replay.py --output /tmp/nd02-s-receive
```

The fresh observation receipt points at the same raw text digests as the retained files. The archive keeps a single copy of each text. Each output CSV must hash to `ee9cbc36b5836203a2ec84d4e5eeb81a5d4b3a5a4f663871fd8ceb5626ef659a`.

To repeat the measured pair with two actual local model calls, prepare the pinned local CPU checkpoint, official inference driver and model environment per the [original model instructions](../README.md). Run on Linux with an unused output path. The result also retains both generated texts and per-call error-stream logs.

```sh
python3 -B numeric_study/successor/run.py --model /path/to/pinned-model \
  --python /path/to/model-venv/bin/python --output /tmp/nd02-s-repeat
```
