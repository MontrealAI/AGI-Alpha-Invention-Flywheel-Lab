# FRONTIER Ω · Activate the inventor

The companion restores public research evidence and tests candidate acquisition policies. It links observed failures to bounded objectives, retains a versioned research record, and separates candidate comparison from source-matched policy adoption. The member application displays the map and exported checkpoints. Runs require an authorized local server and an operator-selected workspace.

## Replay the public evidence

Use Python 3.11 or later and the included hash-pinned Wasmtime wheel requirements for Linux x86-64.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-linux.txt
.venv/bin/python reproduce_activation.py
```

To reproduce the live conventional reconstruction, use `python3 verify_activation.py live study/corpus study/live-case.json ./restored`. The replay checks the committed identities, downloads only approved public URLs, reassembles the eight exact files in a fresh directory and runs the already qualified timing verifier. Use `--parallel 8` to compare bounded concurrent reads. The public archives and direct Git object paths must be reachable. The frozen replay and the timing comparison use different evidence paths.

## Continue an authorized investigation

The `study/corpus` package includes published confirmation cases for challenge and audit. For a new study, the independent evaluator should hold those cases outside the constructor's account. Give the constructor only commitments, catalogue and development files. Use the frozen example to reproduce the research process. A separately selected mission needs fresh protected outcomes.

Configure the existing local HARNESS route and allow the selected model at least 512 output tokens per request. Use `--inventory` to select an objective automatically or `--selection study/selection.json` to reuse the exact registered choice. Record the model, configuration, input commitments and lease before starting. Reuse the same workspace and expiry to resume.

```sh
python3 activate.py --workspace ./investigation --data ./constructor-data \
  --inventory study/inventory.json --config ./local.json --model MODEL --until LEASE_UNIX_SECONDS
```

Open `activation-status.json` under **My results → Living bottleneck map**. Press Ctrl+C or send SIGTERM to pause. Pending model reservations are conservatively accounted on restart. A completed candidate carries experimental status until separately qualified. Code proposals run with supplied integer rows in Wasm, without host interfaces. The candidate cannot change its case sheets or deploy an improvement.

For live phase shadowing, use `python3 phase.py watch --history study/phase-history.json --events study/phase-events.json --workspace ./phases --run ACTIONS_RUN_ID --until LEASE_UNIX_SECONDS`. Start while the authorized Pages workflow is still running. Outputs contain observation times, historical support, shadow predictions and the terminal record. Runs have a bounded number of public reads and can resume from the same checkpoint. Public API or Pages availability can limit a run.

## Activer l’inventeur

L’utilitaire reconstitue les preuves publiques et évalue des méthodes candidates. Il relie les blocages observés à des objectifs précis, conserve les étapes et protège les cas de confirmation. La commande `python3 reproduce_activation.py` reproduit les comparaisons avec Wasmtime installé selon les exigences ci-dessus. Le rejeu en ligne vérifie les sources publiques exactes avant d’exécuter le vérificateur déjà qualifié.

La commande `activate.py` poursuit une recherche autorisée dans un dossier local. Gardez les cas de confirmation hors de ce dossier pour une nouvelle étude. Reprenez après interruption avec la même configuration et la même échéance. Ouvrez `activation-status.json` dans **Mes résultats → Carte des blocages en invention**. La commande `phase.py watch` consigne les observations publiques d’une exécution Pages en cours et compare les prévisions après sa fin.
