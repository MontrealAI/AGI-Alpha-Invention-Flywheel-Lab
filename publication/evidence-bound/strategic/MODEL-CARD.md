# Strategic measurement adapter

**Experimental checkpoint.** This low-rank adapter changes a public causal language model for a single purchase decision in a finite noisy-observation game. The direct evaluation restricts the next-token choice to ` A` and ` B`, corresponding to `BUY` and `SKIP`. It returns a score conditional on that choice set. The output has no operational authority. The exact solver supplies an independently checkable decision and its payoff certificate.

| Field | Observed value |
|---|---|
| Base | `HuggingFaceTB/SmolLM2-135M-Instruct` at `12fd25f77366fa6b3b4b768ec3050bf629380bac` |
| Base weights SHA-256 | `5af571cbf074e6d21a03528d2330792e532ca608f24ac70a143f6b369968ab8c` |
| Adapter SHA-256 | `f278bd65102ef04e060ccade71fde2a92a7438064af3e95be53e7b744e6c64a3` |
| Changes | All 122,880 trainable parameters changed across `q_proj` and `v_proj` in the final eight transformer layers |
| Training | 80 AdamW updates, rank 8, alpha 16, seed 710162, batch size 8, two epochs |
| Labeled data | 320 exact synthetic training cases, 64 structurally disjoint development cases, and 48 separately authored confirmation inputs withheld until freeze |
| Hardware | Linux on AMD EPYC 9V74, four process threads and CPU bfloat16 forward computation |
| Fit measurement | 123.377 seconds wall time, 399.011 CPU seconds, 960,073,728 bytes peak process memory |
| Training cross-entropy | Mean 0.705223 in epoch 1 and 0.708007 in epoch 2 across 93,362 total input tokens |
| Artifact | 495,672 bytes of Safetensors plus a local configuration and an Apache-2.0 license copy |

The fit timer begins after model loading and verified data preparation. Actual energy, host charges, human effort and commercial costs are unmeasured. There were no paid inference calls. The model has no network tools, credentials or access to independent evaluation cases during fitting. Its supervision comes from the exact mathematical instrument and a separate retained-verifier replay for each label.

The input scope has 2–5 ordered payoff rows, exactly two hidden opponent columns, two integer signal probabilities, and a single integer fee charged once. The confirmation distribution deliberately changes structural assumptions within the supported input scope. Cases outside the verified game semantics require different evidence. The training loss stayed near the uniform-choice loss of log(2). The independent results determine what, if anything, qualifies. [Training record](TRAINING-RESULT.json) · [Dataset record](DATA.json) · [Frozen identities](MODEL-IDENTITY.json) · [Setup and replay](README.md)

## Independent decision

**NO-GO for specialist admission.** The 48 targets were independently authored and withheld from model construction through the checkpoint and prompt freeze. A separate evaluator conducted the scored comparison within shared administration. Separately administered custody and evaluator signing remain outstanding.

| Input available to the model | Unchanged base | Adapted model |
|---|---:|---:|
| Direct decision question | 26/48 | 28/48 |
| Decision question and competent method instructions | 20/48 | 27/48 |
| Method instructions and retrieved verified examples | 40/48 | 40/48 |
| Method instructions and exact instrument output on this case | 21/48 | 27/48 |

The exact independent primal and dual solver passed **48/48**. The adapter's primary no-tool arm missed the preregistered acceptance gate. Retrieval gave equal accepted outcomes at 40/48. Supplying verified payoffs as text still allowed wrong model decisions. Reserve a verified purchase recommendation for deterministic comparison of the two exact values. The checkpoint is retained for research. [Independent registration, thresholds and results](../evaluation/strategic/RESULT.json)

Known development performance gives the same practical decision. Both retrieval arms passed 46/64. A fee-only rule selected on the training split passed 37/64, and the exact solver passed 64/64. In a separate diagnostic on the first eight development pairs, using the base model's native chat template still gave equal retrieval results at 12/16. Both direct and exact-value prompt comparisons tied at 8/16. The results support using the exact instrument when its assumptions apply. [Development controls](DEVELOPMENT-EVALUATION.json) · [Native chat diagnostic](CHAT-FORMAT-DEVELOPMENT.json)
