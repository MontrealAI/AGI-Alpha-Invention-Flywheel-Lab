# Strategic formalization from a bilingual brief

**Build frontier AI LLM for Game Theory.** This study tests a learned step that the retained solver does not perform. A local language model interprets the timing and privacy of a paid, noisy observation, the compatibility of fee and payoff units, and the required numerical information. The runtime compiles a compatible proposal into a game only after agreement with an independently approved interpretation.

The decision maker publicly announces the purchase and commits to a conditional policy. The opponent fixes a hidden payoff state. Only the decision maker sees the noisy reading before choosing the binding row. The opponent cannot revise its state. Late readings, opponent response to a realized signal or row, incompatible units, and missing data leave an explicit disposition. This builds on the existing two-state zero-sum solver and exact primal and dual checks. [Prior strategic model](../../evidence-bound/strategic/README.md) · [Independent exact reference](../../evidence-bound/evaluation/strategic_reference.py)

## Experimental design

- The benchmark asks for three semantic fields and a complete outcome. Compatible cases require an actual solver input and exact policy certificate. Other cases require all relevant reasons to withhold the result. The environment shows the brief, hides its reference, accepts one structured interpretation, and penalizes false admission.
- The generator produces 128 training briefs and 32 separate development briefs in English and French. Development uses separate phrase templates. Numeric facts are sampled with documented seeds. The teacher checks authorized input completeness and verifies both exact bounds on each compatible example. The model learns structural declarations from prose. It receives neither solver values nor BUY/SKIP labels.
- The independent assessor authored confirmation prose and kept its references separate before the checkpoint was frozen. Evaluation uses frozen authorized facts and an independent exact rational reference. Administration is shared. The comparison outputs are three constrained native model tokens with identical choices for the baseline and adapted model.
- The primary adapted route uses a competent instruction and exact field-presence inspection on authorized numerical data. Comparators include unchanged base with direct instructions, a method prompt, two retrieved training examples, and exact field-presence inspection. A standalone conservative phrase checker with exact field inspection supplies the ordinary software control. Field accuracy and complete outcomes are both reported.

The [registration](PRE-REGISTRATION.json) fixes the one 48-update training attempt, model setup, data hashes, admission thresholds, and stopping rule.

## Results on the independent panel

**NO-GO for specialist deployment.** The adapted model improved exact agreement over the strongest registered baseline on this panel. Its whole-outcome score and false solver proposals failed the minimum admission gates. Independent evidence withheld all six incorrect proposals.

| Route | Complete outcomes | Certified games | False solver proposals |
| --- | ---: | ---: | ---: |
| Unchanged base, strongest registered route with inspection | 3/16 | 1/2 | 4 |
| Adapted model with method prompt and exact field inspection | 5/16 | 2/2 | 6 |
| Conservative explicit rules with exact field inspection | 1/16 | 0/2 | 0 |
| Separate included-Codex assisted interpretation | 16/16 | 2/2 | 0 |

The adapted primary route read all missing fields correctly with the inspection tool and recognized **11/16** unit conventions. It assigned the private, pre-action timing label to all 16 briefs, giving it **6/16** correct timelines. The strongest registered unchanged-base route recognized **7/16** unit conventions and **7/16** timelines. The adapted route delivered complete outcomes on 2/8 English briefs and 3/8 French briefs. A new study should compare a representation that explicitly models event order and access to information with a stronger authorized model on fresh prose.

On the separately templated development briefs, the adapted route completed **12/32** outcomes against **8/32** from the strongest registered base route. Its three false proposals give similar grounds to withhold deployment. Development examples share the training generator's structure and serve as a diagnostic. [Development replay](DEVELOPMENT-DIAGNOSTIC.json)

The included-Codex result is a separately frozen exploratory control on exactly the same input-only briefs with unknown inference resources. It required an observed 26-second authoring slice that included handoff. The registered local comparison stayed unchanged. Each compatible result also matched the separate rational solver's values. [Independent assessment](CONFIRMATION-RESULT.json) · [Assisted assessment](ASSISTED-RESULT.json) · [Assisted predictions and timing](../productive/comparators/strategic-included/)

The autonomous product did not run this learning experiment. The model, compiler and reproducible fit remain experimental artifacts. The prior mathematical solver and the independently tested exact earthquake-catalog specialist retain their scoped conclusions. [Model card](MODEL-CARD.md) · [Exact geospatial control](../../evidence-bound/specialization-evaluation/README.md)

## Reproduce on a local CPU

Use Python 3.12, PyTorch `2.8.0+cpu`, Transformers `4.55.4`, and Safetensors `0.8.0` in an isolated environment. Use all five files from the exact released `SmolLM2-135M-Instruct` revision. The loader validates the source bytes and disables remote code. This study used the already available Apache-2.0 model files. The full Qwen3-8B GGUF is available for inference separately. No compatible larger trainable base was present for this fit. [Pinned base and license](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct/tree/12fd25f77366fa6b3b4b768ec3050bf629380bac)

Run from `publication/outcome-driven/strategic` in a repository checkout. Choose new output paths.

```sh
python -B -m unittest test_formalize
python -B cases.py /path/to/new/data
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -B fit.py train \
  --base /path/to/pinned-base --data /path/to/new/data \
  --registration PRE-REGISTRATION.json --threads 3 --output /path/to/new/fit
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -B fit.py score \
  --base /path/to/pinned-base --cases CONFIRMATION-INPUTS.jsonl \
  --training /path/to/new/data/train.jsonl --adapter checkpoint/adapter_model.safetensors \
  --threads 3 --output /path/to/new/predictions.json
python -B grade.py --train-registration PRE-REGISTRATION.json \
  --training-result TRAINING-RESULT.json --cases CONFIRMATION-INPUTS.jsonl \
  --oracle CONFIRMATION-ORACLE.jsonl --confirmation-registration CONFIRMATION-LINKAGE.json \
  --predictions /path/to/new/predictions.json --output /path/to/new/assessment.json
python -B grade_assisted.py --cases CONFIRMATION-INPUTS.jsonl \
  --oracle CONFIRMATION-ORACLE.jsonl --linkage CONFIRMATION-LINKAGE.json \
  --observed ../productive/comparators/strategic-included/AUTHORING.json \
  --predictions ../productive/comparators/strategic-included/PREDICTIONS.jsonl \
  --output /path/to/new/assisted-assessment.json
```

`replay.py` independently verifies approved interpretation and proposal files, then prints each exact result. Each file contains one record per specified case. A proposal has `id`, `timing`, `units`, and `missing`. The approved interpretation must come from an authorized separate review.

## Français

L'étude porte sur la formalisation d'un problème de décision à deux états. Le modèle propose l'ordre des engagements et la confidentialité du signal, la compatibilité des unités et les données manquantes. Une interprétation conforme à l'évaluation indépendante permet au programme exact de produire des certificats de gain. Un signal tardif, une réponse adverse après l'observation, des unités incompatibles ou une donnée absente entraînent un refus motivé.

L'entraînement a effectué 48 mises à jour et modifié 122 880 paramètres. Sur 16 cas rédigés séparément, l'adaptateur assisté par l'outil d'inspection a résolu 5 cas complets, et le meilleur modèle de base en a résolu 3. Les six propositions erronées ont été bloquées. Un essai assisté distinct avec Codex a résolu les 16 cas. Le déploiement du modèle spécialisé reste **non qualifié**. [Configuration et critères](PRE-REGISTRATION.json) · [Résultats](CONFIRMATION-RESULT.json)
