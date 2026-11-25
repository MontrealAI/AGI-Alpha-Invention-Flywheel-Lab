# Game Theory LLM · cited observation and strategic verification

**Owner mission — Build frontier AI LLM for Game Theory.**

**GO for the reviewed information partition and exact strategy check in the declared scope. NO-GO for promoting the learned interpreter.** The experiment moves from a source-language decision rule to a testable question about who can use which information when choosing an action. It tests whether a trained language model can propose both the access judgment and its decisive source rule on new game structures. It uses the existing rational normal-form reference for the mathematical check. [Independent exact reference](../../member-workspace/strategic-information/independent_reference.py)

## What can be used now

`partition.py` turns separately reviewed observation judgments and finite possible histories into groups a player cannot distinguish at a named choice. A missing known signal fails validation. An unresolved access judgment withholds the affected decision. Histories must have the same available actions for each named choice. The reviewed observation record must cover everything the actor could use to distinguish histories, including relevant prior actions.

In a synthetic sealed-bid game, the replay recovers a value of **1/2** when the planner sees the reserve signal before bidding and **1/4** when the signal arrives after both bids are final. Separate pure-policy enumeration and exact bounds agree. A conditional release with missing approval evidence withholds the planner's partition. The payoff gain of **1/4** applies to this registered game. [Executable partition](partition.py) · [Replay and exact results](PARTITION-REPLAY.json)

## What actually learned

The fit updates a compact Apache-2.0 SmolLM2-135M-Instruct adapter. The base is pinned and frozen. One 60-update CPU AdamW run processed 66,684 forward tokens on 120 synthetic lessons. It changed 122,880 of 122,880 trainable parameters. A separate process reconstructed the initial tensors and confirmed the change against the saved weights. The fit took **94.60 seconds wall** and **280.50 CPU seconds** with peak memory of 1.34 GB. Witness loss on the 24 disjoint development texts went from 1.828 to 1.718. Access judgment loss went from 1.477 to 1.543. [Registration](REGISTRATION.json) · [Training receipt](checkpoint/TRAINING-RECEIPT.json) · [Tensor check](CHECKPOINT-VERIFICATION.json) · [Base source and license](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct/tree/12fd25f77366fa6b3b4b768ec3050bf629380bac)

The held briefs include logical reconstruction, asymmetric roles, conditional forwarding, aggregate information and changes between preliminary and final choices. The same-base arms share weights and allowed output tokens. One baseline receives two retrieved demonstrations. A second receives a candidate rule-number hint from a word lookup. The learned route uses the same direct prompt as the frozen base. The evaluator counts a cited claim only when both the access decision and an admissible source-rule number agree.

## Independent primary panel

| Route | Complete cases | Cited claims | False claims of access |
| --- | ---: | ---: | ---: |
| SmolLM2 direct | 0/10 | 4/26 | 0 |
| SmolLM2 with two retrieved examples | 0/10 | 0/26 | 6 |
| SmolLM2 with word lookup | 0/10 | 8/26 | 5 |
| SmolLM2 with the trained adapter | 0/10 | 6/26 | 13 |
| Qwen3 4B direct, schema-constrained | 2/10 | 16/26 | 2 |
| Included Codex direct, separate comparison | 8/10 | 24/26 | 0 |

The five English and five French cases were independently authored. The oracle was committed by digest before inference and released after all primary predictions froze. Two rules about a partial signal admitted a defensible alternative reading of access. An alternate evaluation permits `hidden` as well as `unclear` for those two queries. Included Codex reaches 10/10 and 26/26 on that sensitivity check. Every other complete-case count stays the same. The frozen scoring remains the primary result. Case author and constructor operated under shared administration. [Held briefs](PRIMARY-BRIEFS.json) · [Freeze](HELD-FREEZE.json) · [Frozen adjudication](PRIMARY-ADJUDICATION.json) · [Ambiguity check](PRIMARY-SENSITIVITY.json) · [4B adjudication](QWEN-ADJUDICATION.json)

Qwen3 4B completed ten actual CPU requests through a loopback-only llama.cpp process. It used 3,112 reported input and output tokens and 341.66 seconds across the ten requests. This stronger local model used different compute. The included Codex control received the same raw briefs and decision rules, without the oracle. Its backend compute was unobserved. Owner effort, energy and complete cost were unmeasured. [4B prediction and resource receipt](QWEN-4B-CONTROL.json) · [Included Codex predictions](INCLUDED-CODEX.json)

## Independent confirmation

A second author froze eight further briefs with 24 claims, half English and half French. Every same-model route completed 0/8 cases. The adapter matched two cited claims and asserted access falsely ten times. The direct base matched zero cited claims and made zero false claims of access. Retrieval matched zero with two false claims of access. Word lookup matched zero with no false claims of access. Across both panels, the candidate completed **0/18** cases with **8/50** exact cited claims and **23** false claims of access. This misses the registered quality, gain and reliability gates. [Confirmation briefs](CONFIRMATION-BRIEFS.json) · [Frozen confirmation](CONFIRMATION-FREEZE.json) · [Independent evaluator](CONFIRMATION-INDEPENDENT-EVALUATION.json)

The first confirmation attempt aborted before producing predictions. Four retrieval transcripts exceeded the 768-token tool limit, with a maximum of 781 tokens. The pinned model supports 8,192. A recorded inference-only correction increased the tool limit to 1,024 before any oracle was opened. It preserved the full briefs, prompts, adapter, comparison arms and acceptance. The corrected run produced the results above. [Context correction](CONTEXT-CORRECTION.json) · [Replayed adjudication](CONFIRMATION-ADJUDICATION.json)

## Reproduce

From the repository root, use Python 3.12 and SciPy for the verified mathematical path.

```sh
study=publication/prove-advantage/game-theory
python -B "$study/replay.py" /tmp/frontier-reviewed-partition.json
python -B "$study/adjudicate.py" --registration "$study/REGISTRATION.json" \
  --held-freeze "$study/HELD-FREEZE.json" --cases "$study/PRIMARY-BRIEFS.json" \
  --oracle "$study/PRIMARY-ORACLE.json" --predictions "$study/PRIMARY-PREDICTIONS.json" \
  --assisted "$study/INCLUDED-CODEX.json" --output /tmp/frontier-primary-observations.json
python -B "$study/adjudicate.py" --registration "$study/REGISTRATION.json" \
  --held-freeze "$study/CONFIRMATION-FREEZE.json" --cases "$study/CONFIRMATION-BRIEFS.json" \
  --oracle "$study/CONFIRMATION-ORACLE.json" --predictions "$study/CONFIRMATION-PREDICTIONS.json" \
  --output /tmp/frontier-confirmation-observations.json
```

To reproduce learning, use PyTorch 2.8.0 CPU, Transformers 4.55.4 and Safetensors 0.8.0. Place the five pinned files listed in the training receipt in a local base directory. The existing model loader validates them and disables remote custom code. Choose fresh dataset and output paths.

```sh
python -B "$study/curriculum.py" /tmp/frontier-observation-lessons
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -B "$study/fit.py" train \
  --base /path/to/pinned-base --data /tmp/frontier-observation-lessons \
  --registration "$study/REGISTRATION.json" --output /tmp/frontier-observation-adapter
```

## Français

**L’outil de vérification est utilisable avec des observations validées. Le modèle entraîné demeure expérimental.** Le calcul indépendant confirme une valeur de 1/2 lorsque le signal est reçu avant la décision et de 1/4 lorsqu’il arrive après. Un signal conditionnel sans preuve d’autorisation suspend le calcul du joueur concerné. Le modèle entraîné n’a réussi aucun des 18 cas complets des deux évaluations et a attribué à tort 23 accès. L’utilisation directe de Codex a réussi huit des dix cas de l’évaluation principale selon le barème figé. [Résultats détaillés](PRIMARY-ADJUDICATION.json) · [Confirmation](CONFIRMATION-ADJUDICATION.json)
