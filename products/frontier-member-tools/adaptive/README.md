# FRONTIER Ω · Learn from real work

This companion observes public MONTREAL.AI release work. It can produce a timing forecast, train a small residual model on completed runs, and retain challenges and alternative monitoring policies. The existing Pages verifier controls release acceptance. Active watches run in this local process. The member page displays exported local evidence.

## Reproduce the public research

Use Python 3.11 or newer. A model and internet connection are unnecessary for forecast replay.

```sh
python3 reproduce.py
```

The companion contains time-separated, normalized Actions records, source digests, the trained model, and sealed receipts. Install the pinned Wasmtime wheel in a separate environment to replay generated tools and their comparisons. The included requirements hashes cover Linux x86-64.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-linux.txt
.venv/bin/python reproduce.py --full
```

## Observe and improve work

```sh
python3 operate.py --workspace ./local-learning init
python3 operate.py --workspace ./local-learning seed study/cohort/fit.json
python3 operate.py --workspace ./local-learning advance
python3 operate.py --workspace ./local-learning watch --cycles 12 --interval 30
```

Use `--run` with an Actions run ID to watch one run through completion. Stop with Ctrl+C and resume with the same workspace. The watcher reads the fixed public Actions and Pages origins and has an hourly read budget. It requires no account or model credentials. The workspace records interruptions and charges uncertain reads against the budget. Save `learning-status.json` and open it under **My results → My gains and evolving intelligence**. A saved view records the export time and contains no connection to the watcher.

`advance` operates on local history. It trains a candidate when enough records are available. With a running loopback model, pass `watch --research-config LOCAL.json --research-model MODEL` with a registered local model. A measured development loss may queue a bounded construction attempt. Candidate policies use typed Wasm inputs and cannot invoke host interfaces. Full code isolation beyond this Wasm contract requires a separate evaluation.

An operator may initialize a separate authorized workspace with the SHA-256 of a separately held evaluator's public key. `admit RECEIPT PUBLIC_KEY` requires that pinned key and a signed decision for an exact local candidate and scope. The decision expires. `rollback` reverts to the conventional forecast. A measured degradation on five live forecasts can suspend an adopted model. The bundled research is advisory. Use a separately authorized evaluator and fresh cases for a new adoption decision.

To run the published construction protocol with your own local model, use `PYTHONPATH=. python3 study/run_study.py study/cohort ./new-study ./local.json MODEL`. It opens the fit and development files. The separate confirmation program is `python3 check.py verify study/cohort --training study/training.json --runs new-study/runs.json`. Keep confirmation files outside the constructor's account for a separately administered trial.

## Apprendre du travail réel

L’utilitaire observe les publications publiques de MONTREAL.AI. Il entraîne un petit modèle de prévision sur l’historique des exécutions terminées. Le vérificateur Pages conserve l’autorité d’accepter une publication. Le suivi s’exécute dans le processus local.

Avec Python 3.11 ou plus récent, lancez `python3 reproduce.py` pour refaire la comparaison de prévisions hors ligne. Installez la version de Wasmtime indiquée ci-dessus pour vérifier aussi les outils construits dans l’expérience. Les fichiers de l’étude contiennent les données normalisées, les reçus et le modèle entraîné.

Les commandes `init`, `seed`, `advance` et `watch` démarrent le suivi à partir d’un historique public. Interrompez le processus par Ctrl+C. Reprenez avec le même dossier. Dans **Mes résultats → Mes gains et l’évolution de mes capacités**, ouvrez le fichier `learning-status.json` exporté. La date affichée correspond à l’export.

Une évaluation distincte est nécessaire avant l’adoption d’un modèle. Le dossier peut être initialisé avec l’empreinte de la clé publique de l’évaluateur. `admit` vérifie la décision signée, sa portée, son échéance et l’identité du modèle. `rollback` rétablit la prévision conventionnelle.
