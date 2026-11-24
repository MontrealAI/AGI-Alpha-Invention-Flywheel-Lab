# FRONTIER Ω · Intelligence amplification

Activation 1.1 adds a local research environment for comparing the same model with and without an experimental instrument. The package also contains the previously published activation, Wasm construction and phase observation tools. Read `README.md` for the earlier workflows and their requirements.

## Reproduce the public comparison

With Python 3.11 or later and SQLite, open a clean extraction and run:

```sh
python3 reproduce_amplification.py
python3 route_environment.py study/amplification/trial.json
python3 calibration_environment.py study/amplification/calibration-trial.json
```

The first command recomputes exact controls and checks the recorded candidate outputs against the same case contracts. The second finds the highest capacity floor supported by individually qualifying measurements from the requested number of distinct system configurations for one workload. Each witness retains its own measured concurrency. `study/amplification/provenance.json` maps the result aliases to exact public MLCommons records. Operational adoption is **ABSTAIN**. Hardware configuration names cannot establish real failover, reliability, quality or operating costs. The calibration command returns the minimum relative allowance, as an exact fraction, and the two measurement rows certifying it. It applies to the numerical boxes in the original measurement fixture.

To rerun candidate code and boundary checks, run `python3 reproduce_amplification.py --native` on a compatible Linux x86-64 host with a system Python, Bubblewrap, util-linux `unshare`, `libseccomp.so.2` and authorized user namespaces. The worker mounts the system interpreter, Python library and runtime libraries read-only. The kernel policy blocks sockets, child processes and further program execution. File output, virtual address space, CPU and supervised wall time are bounded. Candidate code sees one input after isolation setup completes. The command refuses unsupported hosts. Candidate execution and actual model requests are separate from the portable record replay.

## Reopen or continue a local experiment

Configure an authorized loopback model through the existing HARNESS adapter. Give your constructor the registered contract and development cases only. The public historical confirmation examples demonstrate replay. For a fresh claim, the evaluator should author and retain separate confirmation cases outside the constructor's account.

```sh
python3 amplify.py design --registration registration.json --development development.json \
  --workspace ./instrument --config ./local.json --model MODEL --until LEASE_UNIX_SECONDS
python3 amplify.py construct --registration registration.json --development development.json \
  --workspace ./experiment --config ./local.json --model MODEL --until LEASE_UNIX_SECONDS \
  --arm amplified --instrument ./instrument/instrument.json
python3 amplify.py evaluate --registration registration.json --confirmation confirmation.json \
  ./experiment/amplification-status.json
```

Run matched `direct` and `harness` controls in different workspaces. Each receives the task, development cases and the outputs of its development executions. Use the identical model, output budget and authorized information. Stop with Ctrl+C or SIGTERM. Resume using the same configuration, workspace, instrument and lease. A pending inference reservation is charged conservatively on restart. The workflow records development progress and stops when registered conditions are met. Keep promotion and confirmation outside the constructor's authority.

Use `amplify.py compare` with the same inputs to drain all registered arms in one resumable local queue. It organizes checkpoints in `PREFIX-ARM` directories and leaves a `PREFIX-comparison.json` status when they are ready for independent evaluation. Use `--prefix` to name a new run. Resume the same prefix and lease to recover an interrupted queue.

For a fresh transfer, run `amplify.py transfer --registration new-registration.json --development new-development.json --instrument old-instrument.json --output transfer.json`. This binds the original artifact's exact bytes and source registration to the new study. Pass `transfer.json` as the amplified arm's instrument. A change to the original bytes or target registration causes refusal.

Open `amplification-status.json` in **My Results → Intelligence amplification** to inspect development attempts locally. Keep that file on a device you control. Use the compiled report for the comparison against separated confirmation cases and the exact reference. Importing a checkpoint carries no authority to adopt a model or artifact.

## Français

Activation 1.1 ajoute un environnement de recherche local pour comparer un même modèle avec et sans instrument expérimental. Les outils antérieurs de construction WebAssembly, d’observation des publications et de rejeu restent disponibles dans le même utilitaire.

`python3 reproduce_amplification.py` recalcule les références exactes et vérifie les résultats consignés. `python3 route_environment.py study/amplification/trial.json` calcule le plus grand seuil que les mesures individuelles admissibles atteignent sur le nombre demandé de configurations distinctes. Chaque preuve conserve sa propre charge mesurée. Les identifiants renvoient aux résultats publics dans `study/amplification/provenance.json`. L’adoption opérationnelle demeure en **ABSTENTION**. Les mesures publiques ne démontrent pas la disponibilité en production ni le basculement entre systèmes.

L’option `--native` rejoue les programmes en isolation sous Linux x86-64. Elle requiert Python système, Bubblewrap, `unshare`, `libseccomp.so.2` et l’autorisation d’utiliser les espaces de noms. L’exécution échoue si l’isolation requise n’est pas disponible. Pour une nouvelle étude, confiez les cas de confirmation à l’évaluateur et fournissez au constructeur les seuls cas de développement.

Utilisez la commande `amplify.py` avec la configuration locale de HARNESS. Pour reprendre après une interruption, réutilisez le même dossier, la même configuration et la même échéance. Ouvrez le fichier `amplification-status.json` dans **Mes résultats → Amplification de l’intelligence** pour voir les essais de développement. Conservez l’évaluation et l’autorisation d’adoption sous contrôle distinct.
