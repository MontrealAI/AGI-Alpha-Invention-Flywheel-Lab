# Invent a capability

This companion builds inspectable SQL instruments and runs a registered comparison of ways to select development evidence. Unzip it on a device you control. It uses Python 3.11+ with standard-library SQLite 3.37+ and a selected local model for construction. The research release includes the actual checked public experiment and its reproducible artifacts. Start with model-free replay.

```sh
python3 reproduce.py
python3 reproduce.py --diagnostic
python3 reproduce.py --larger
```

The replay verifies report hashes and runs each submitted query against the originally committed confirmation data. The separate `study/reproduction.json` contains the mission definitions, conventional alternatives and case sheets. Requalify and run a recorded passing instrument on a fresh tables object with `python3 reproduce.py --apply ARM input.json`. Use a name from `comparisons` in the replay output and an input matching that mission's tables. Keep the companion and original evidence together. Values and tables remain within the declared input limits. Cases are drawn from controlled examples and public source replays. Operational adoption needs evidence on the intended workload.

## Run a new local investigation

Use the public research registration and `run_pilot.py` as a worked example. Authorize only source material you can share with the selected local server. Have the evaluator write and retain the confirmation cases privately, freeze their digests before construction and provide only the mission and development cases to the constructor. For separate custody use a distinct authorized evaluator on an independently controlled host. The bundled public experiment already contains its published cases. Use fresh material to evaluate a new invention claim.

Configure a numeric loopback server such as llama.cpp or a compatible member-controlled runtime. Adapt `local.example.json` to its model, port and context window. Keep `local_only` enabled and the budget for paid requests at zero. The runner supplies only the mission, allowed development examples, and optional prior artifacts. It has no shell or external actions. Its SQL engine operates over in-memory, typed input tables, with a read-only authorizer and bounded execution. Keep the local model port private and use a runtime you trust.

```sh
python3 inventor.py choose --input opportunities.json --config local.json --provider localhost-inference \
  --model qwen3-8b-q4-k-m --budget 256 --workspace ./research/choice
python3 inventor.py construct --input mission.json --development development.json --config local.json \
  --provider localhost-inference --model qwen3-8b-q4-k-m --budget 640 --workspace ./research/first
python3 inventor.py learn --input research/first/run.json --development development.json --config local.json \
  --provider localhost-inference --model qwen3-8b-q4-k-m --budget 512 --workspace ./research/method
```

An opportunity file is an array of objects with unique `id`, `goal`, `evidence` and `incumbent`. A mission has `id`, `goal`, `contract`, `tables` and `output`. Each development case has `id`, `family`, `input` (table name to row objects) and expected output rows. Use distinct development case IDs. The model sees at most two detailed examples at a time. To compare a new mission, export the completed learning run's `result` object as a prior file. Run `construct` in separate workspaces using `--arm original` alone and `--arm ordinary|augmented|withdrawn --prior prior.json` for the three retained-information arms. Use the same model and budgets. `inventor_verify.py REGISTRATION MISSION CASES RUN ARM` checks the sealed run against the separately committed confirmation data.

Use `--observations` to show the model the rows its previous query actually produced on its development examples. Register the same `development_feedback` setting (`observations`) in the evaluator's protocol. Use `--diagnostic` with `reproduce.py` to open the separately registered repair trial.

Interrupt with Ctrl+C. Resume with the same inputs, model configuration and workspace. The checkpoint charges an uncertain dispatch against its budget. GitHub Pages provides the public project interface, download and evidence. It holds no member model configuration or study state. The program has no production promotion permission. Running the withdrawn arm removes the executable policy from that comparison.

## Inventer une capacité

Décompressez l’utilitaire sur un appareil que vous contrôlez. Il utilise Python 3.11 ou plus récent et SQLite 3.37 ou plus récent. La commande `python3 reproduce.py` reproduit l’étude publique hors ligne. Le fichier `study/reproduction.json` contient les missions, les références conventionnelles et les grilles d’origine. La commande `python3 reproduce.py --apply ARM input.json` vérifie et exécute un instrument ayant réussi ses cas. Choisissez une démarche dans le résultat du rejeu. Utilisez des données d’entrée qui respectent ses tables.

Pour une nouvelle étude, configurez votre modèle à l’adresse de boucle locale dans `local.example.json` en gardant `local_only` actif. Fixez la mission, le budget et les critères avant de commencer. Confiez les cas de confirmation à un évaluateur autorisé. Réservez des cas distincts au développement. Lancez `choose`, `construct` ou `learn` avec les options ci-dessus. Arrêtez avec Ctrl+C et reprenez avec les mêmes fichiers et le même dossier. Un appel interrompu qui a pu partir compte dans le budget.

Pour comparer les démarches, utilisez le même modèle, des ressources comparables et une grille commune. L’utilitaire consigne les essais, les cas choisis et les coûts observables. La qualification technique porte sur le périmètre évalué. L’usage réel, les coûts complets et les gains d’invention demandent des mesures distinctes.
