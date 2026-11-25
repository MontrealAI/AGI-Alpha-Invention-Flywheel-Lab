# Strategic protocol learning

**Build frontier AI LLM for Game Theory.** This experiment asks whether a local language model can extract who did what, in what order, who received a signal before acting, and which commitments could be revised. It compares bilingual private-signaling briefs with public posted-offer briefs. Standard extensive-form methods distinguish move order and information available to each actor. [OpenSpiel documentation](https://openspiel.readthedocs.io/en/latest/intro.html)

The learning environment presents a prose brief and accepts a four-field JSON action. It gives one point for exact agreement with separately reviewed facts and subtracts two for a false solver proposal. A missing or disputed fact withholds the corresponding policy. The private-signal test uses the retained two-state solver with a separately approved payoff matrix, calibrated signal, zero fee and publicly announced conditional policy. The exact value must agree with a separately implemented rational reference. The posted-offer test compares approved price and valuation with an exact surplus calculation. Both are finite synthetic games with explicit assumptions.

[Registration](REGISTRATION.json) fixes one CPU fit, separate training and development templates, the independently authored held input and reference hashes, all comparison arms and the decision to proceed. No held labels appear in the training file, prompt or retrieval examples. A preflight refused overlapping development prose before opening the base model. The recorded correction preceded all parameter updates. The assessor and constructor use separate conversations, with shared workspace administration.

The test uses the existing Apache-2.0 SmolLM2-135M-Instruct weights. The frozen base and adapted model receive the same direct prompt. The unchanged retrieval model receives two training examples chosen by language, family and lexical overlap. Predictions are greedy JSON completions with no post-generation correction. An approved semantic record has to match the proposed record before either mathematical instrument can run. [Exact base revision and license](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct/tree/12fd25f77366fa6b3b4b768ec3050bf629380bac)

## Held results

**GO for the experimental training artifact and reviewed exact policies. NO-GO for deploying the learned interpreter.** The one authorized 33-update fit used 44 training and 12 development briefs. The saved adapter changed all 122,880 trainable parameters across 32 tensors. A separate process reconstructed initialization from the registered seed and verified the change against the checkpoint. Development completion loss fell from 0.5131 to 0.1317. Training used 73.86 seconds wall time and 219.31 CPU seconds. The base weights remained frozen. [Training receipt](TRAINING-RESULT.json) · [Checkpoint verification](CHECKPOINT-VERIFICATION.json) · [Adapter](checkpoint/)

| Route | Exact records | Malformed completions | Certified cases | False solver proposals |
| --- | ---: | ---: | ---: | ---: |
| Unchanged model, direct prompt | 1/8 | 2 | 1/2 | 2 |
| Unchanged model, two retrieved examples | 1/8 | 3 | 1/2 | 3 |
| Adapted model, same direct prompt | 1/8 | 0 | 1/2 | 2 |
| Separate included Codex, assisted | 8/8 | 0 | 2/2 | 0 |

The adapted model matched event order on 6/8 briefs, actors on 7/8, information access on 3/8, and irrevocability on 6/8. Its only complete match was English. It tied both unchanged-base controls on complete records and missed the registered threshold. The runtime withheld every false solver proposal before the numerical calculation. The assisted route certified the private game at an exact worst-case value of `19/9` and the public offer at a surplus of `3/35`. The independently implemented rational and cross-product calculations agreed. The included Codex comparison was separately authored in a measured ten-second slice. Backend tokens, compute and cost were unobserved. A separate scorer reproduced all exact record counts and false proposal sets from the frozen predictions and reference. [Assessment](ASSESSMENT.json) · [Independent score](INDEPENDENT-SCORE.json) · [Local predictions](MODEL-PREDICTIONS.json) · [Assisted receipt](ASSISTED-RECEIPT.json) · [Freeze](CONFIRMATION-FREEZE.json)

Keep the reviewed protocol and exact policies for these scopes. One false proposal overlooked explicit revision rights in `external-04`. The other reversed the actors making the commitment and final choice in `external-06`. The next scientific comparison should score cited evidence for individual access, role and revision claims on a fresh independently controlled panel. This small study leaves broad extraction, unattended strategic reasoning, production integration and learned superiority unqualified.

## Reproduce locally

Use Python 3.12, PyTorch 2.8.0 CPU, Transformers 4.55.4 and Safetensors 0.8.0. The base directory must contain the exact five files identified by the accepted prior loader, which checks hashes and refuses remote code or downloads. Supply fresh output paths.

```sh
python -B curriculum.py /path/to/new/data
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -B fit.py train \
  --base /path/to/pinned-base --data /path/to/new/data \
  --registration REGISTRATION.json --output /path/to/new/checkpoint
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -B fit.py score \
  --base /path/to/pinned-base --data /path/to/new/data --cases HELD-INPUTS.json \
  --registration REGISTRATION.json --adapter /path/to/new/checkpoint/adapter_model.safetensors \
  --output /path/to/new/predictions.json
python -B assess.py --registration REGISTRATION.json --cases HELD-INPUTS.json \
  --reference HELD-REFERENCE.json --predictions /path/to/new/predictions.json \
  --training /path/to/new/checkpoint/TRAINING-RESULT.json --assisted ASSISTED-PREDICTIONS.json \
  --output /path/to/new/assessment.json
python -B score_independent.py HELD-INPUTS.json HELD-REFERENCE.json \
  MODEL-PREDICTIONS.json ASSISTED-PREDICTIONS.json
```

## Français

L’expérience évalue une formalisation locale de deux types de jeu. À partir d’un bref texte, le modèle propose l’ordre des événements, le rôle des acteurs, l’accès au signal avant la décision et la possibilité de réviser l’engagement. Un programme d’évaluation confronte cette proposition à des faits établis séparément. Il exécute le calcul exact uniquement dans le cadre admis. L’étude utilise des cas synthétiques bilingues et un seul ajustement de faible rang sur processeur.

L’entraînement a modifié 122 880 paramètres en 33 mises à jour. Le modèle adapté a produit une seule interprétation complète sur les huit cas, ce qui égale les deux comparateurs utilisant le modèle de base. Ses deux propositions d’utiliser un solveur hors du cadre admissible ont été bloquées. L’essai assisté séparé avec Codex a résolu les huit cas et validé les deux calculs exacts. Le déploiement du modèle adapté reste **non qualifié**. [Résultats détaillés](ASSESSMENT.json)
