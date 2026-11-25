# Strategic measurement decisions

This is a local learning experiment for the ambition **Build frontier AI LLM for Game Theory.** A pretrained causal language model was fitted to decide whether to pay for a noisy signal in a restricted class of zero-sum games. The solver establishes the decision target and exact payoff bounds. The learned checkpoint changes internal language-model parameters and can score a game without calling the solver during that prediction.

The adapted model completed 80 optimizer updates and scored 28/48 in the independent direct-decision test. The best retrieval arm tied the unchanged base at 40/48. The exact solver passed 48/48. The learned checkpoint remains experimental. The exact solver is the preferred operating method. [Model card and decision](MODEL-CARD.md) · [Independent held evaluation](../evaluation/strategic/RESULT.json)

## Playable scope

The observation contains the payoff matrix, the two signal-accuracy percentages, and the fee. The opponent sees the public purchase decision and the declared mixed policy before choosing one hidden column. When the player buys, the next observation is a binary signal about that column. The policy can condition on the signal. Skipping selects a row without a signal. The information cost is paid once. Private random draws and the hidden column are absent from the model input.

The action is either `BUY` or `SKIP`. `PurchaseEnvironment.step` terminates the purchase decision and scores its exact worst-case regret. `game.play` samples a realized episode under a declared policy against a worst-case column. Finite geometric enumeration supplies a feasible policy and an adversary probability. The two verified bounds must coincide as exact fractions. The rule selects `SKIP` when values are equal. Scenarios model decisions under declared game rules and carry no claim about real fees, signal accuracy, or demand.

The training generator uses paired fees on structurally disjoint training and development splits. It embeds each own action as one occupied lane and each hidden column as a zero-budget opponent in the previously released costly-observation instrument. This yields a second exact check for both the buy and skip label. All development and independent confirmation cases are excluded from fitting. The generated training labels are exact mathematical results, with no external-model output used for distillation. [Retained verifier](../../mission-executor/game/observation.py) · [Dataset identity](DATA.json)

## Reproduce on a local CPU

The exact recorded environment used Linux, Python 3.12, PyTorch `2.8.0+cpu`, Transformers `4.55.4`, and Safetensors `0.8.0`. A fresh Python environment avoids changing an existing installation. Other execution platforms have their own qualification requirements.

```bash
python -m pip install 'torch==2.8.0+cpu' --index-url https://download.pytorch.org/whl/cpu
python -m pip install 'transformers==4.55.4' 'safetensors==0.8.0'

# Run in publication/evidence-bound/strategic from a repository checkout.
python -m unittest test_game -v
python replay.py examples.jsonl --retained --sample-seed 781
python generate.py /path/to/new/learning-data
```

With explicit local download consent, save `model.safetensors`, `config.json`, `tokenizer.json`, `tokenizer_config.json`, and `special_tokens_map.json` from the pinned base revision to a directory you control. The base weights are about 269 MB. The loader checks the SHA-256 of each file, uses local Safetensors, and keeps remote code disabled. [Pinned Apache-2.0 base model](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct/tree/12fd25f77366fa6b3b4b768ec3050bf629380bac)

```bash
python learn.py train --base /path/to/base --data /path/to/learning-data \
  --output /path/to/new/training-run --threads 4 --batch-size 8 --epochs 2

python learn.py score --base /path/to/base --cases examples.jsonl \
  --adapter checkpoint/adapter_model.safetensors \
  --training /path/to/learning-data/train.jsonl --verified-tools \
  --output /path/to/replay.json --threads 3
```

To apply the retained artifact, keep `adapter_config.json` and `adapter_model.safetensors` together. The replay loads the frozen base and scores both with and without the adapter under the same prompts. `--verified-tools` provides both models with the instrument's checked values. The exact solver is available directly through `replay.py`. Where an exact solver covers the proposed action and its assumptions, it remains the preferred scientific reference.

`DEVELOPMENT-INPUTS.jsonl` is the public input-only copy of the development split. The grading tool checks prediction-to-input identity and compares both models with an exact solver and a fee-only rule calibrated on the training split.

```bash
python learn.py score --base /path/to/base --cases DEVELOPMENT-INPUTS.jsonl \
  --adapter checkpoint/adapter_model.safetensors \
  --training /path/to/learning-data/train.jsonl --verified-tools \
  --output /path/to/development-scores.json --threads 2
python grade_development.py /path/to/learning-data/train.jsonl \
  /path/to/learning-data/development.jsonl /path/to/development-scores.json
```

The evidence applies to bounded two-column games and forced-choice next-token scoring. Free-form explanation, general Game Theory expertise, commercial performance, frontier-model superiority, autonomous runtime training, and inventor improvement require separate evidence.

## Mode d’emploi en français

Le problème consiste à déterminer s’il vaut la peine de payer pour un signal imparfait dans un jeu à somme nulle. L’adversaire choisit une colonne cachée après avoir vu la décision d’acheter le signal et la stratégie annoncée. Le vérificateur calcule exactement le gain garanti pour les deux décisions. Lorsque les gains sont égaux, on choisit de ne pas acheter.

Pour rejouer les cas publics, exécutez `python replay.py examples.jsonl --retained --sample-seed 781` dans ce dossier. Cette commande utilise la bibliothèque standard de Python et le vérificateur du dépôt. Les commandes d’installation ci-dessus permettent aussi d’exécuter l’adaptateur sur processeur avec les fichiers du modèle de base à la révision indiquée.

Après 80 mises à jour, l’adaptateur a obtenu 28 bonnes décisions sur 48 en réponse directe. Avec des exemples vérifiés, les deux modèles ont obtenu 40 bonnes décisions sur 48. Le solveur exact a obtenu 48 sur 48. L’adaptateur demeure un résultat de recherche. On privilégie le solveur pour une décision opérationnelle dans le périmètre vérifié. [Fiche du modèle](MODEL-CARD.md) · [Évaluation indépendante](../evaluation/strategic/RESULT.json)
