# Test a successor on a new task

Use this workflow when you have a verified scalar HARNESS instrument and a different task that can reuse its outputs. The two missions must share the earlier inputs and their types. Narrower integer bounds are supported. An evaluator prepares the new cases and a competent incumbent before any construction. Run with a member-controlled loopback model. The study sends no case rows or case answers. The hosted workbench never connects to the model.

1. Give the evaluator the preceding capability file, its original cases, the new mission and a candidate for the conventional incumbent. Write `spec.json` with exactly `task` (the new mission object), `hypothesis` (what reuse might improve), `model` (a configured local model ID) and `output_tokens` (the same response cap for each arm).
2. Register the comparison. Give the constructor `plan.json` only. Keep the new cases under evaluator control until construction ends.
3. Review the three prompts and the model configuration. Run the plan in an empty workspace you control. Use `--step` for one request at a time. Repeat with the same workspace to resume. Ctrl+C stops the local run. After an interruption, a reserved arm is recorded as interrupted and cannot be sent again from that workspace.
4. Give the attempts file to the evaluator. Grade the candidate instruments and incumbent against the same original cases. Reopen the report and cases in **My results**, or replay in the companion. Quality comparisons cover those cases. Measure setup, labor, usage, review, energy and maintenance before making a cost claim.

```sh
node study-cli.mjs register spec.json previous.json previous-cases.json incumbent.json cases.json > plan.json
node study-cli.mjs plan plan.json
python3 study.py --config local.json --provider localhost-inference --plan plan.json --workspace ./my-study > attempts.json
node study-cli.mjs grade plan.json cases.json attempts.json > report.json
node study-cli.mjs replay report.json cases.json
```

The direct arm gets the new mission. The ordinary and retained arms get the same earlier instrument. The retained arm can use named earlier outputs and the compiler inserts their data-only expressions. The existing HARNESS evaluator runs every sealed candidate. Physical file and process access, arbitrary executable source, automatic paid requests and automatic promotion are outside this path. Store exports on a device you control. The report contains private mission and candidate data if your study used it. The digests bind bytes within this workflow. Evaluator custody and provenance require separate evidence.

## Tester une capacité sur une nouvelle tâche

Partez d’un instrument HARNESS qui a réussi ses vérifications et d’une nouvelle tâche pouvant exploiter ses sorties. Les deux missions partagent les entrées de l’instrument précédent et leurs types. Des bornes entières plus étroites sont permises. Une personne chargée de l’évaluation prépare les nouveaux cas et un comparateur de référence avant la construction. Utilisez un modèle local accessible sur l’adresse de boucle locale.

1. Créez `spec.json` avec la nouvelle mission (`task`), l’hypothèse à vérifier (`hypothesis`), le nom du modèle (`model`) et la limite de jetons de sortie par démarche (`output_tokens`). Rassemblez l’instrument précédent, sa grille originale, le comparateur et la nouvelle grille.
2. Figez le protocole avec `register`. Transmettez seulement `plan.json` à la personne ou au processus qui construit les instruments. Conservez la nouvelle grille à part jusqu’à la fin de la construction.
3. Relisez les trois consignes avec `plan`. Lancez `study.py` dans un dossier que vous contrôlez. Ajoutez `--step` pour faire un seul appel à la fois. Reprenez ensuite dans le même dossier. Si un appel a pu partir lors d’une interruption, la démarche est marquée comme interrompue et l’appel demeure consommé.
4. Utilisez `grade` avec la grille originale. Ouvrez le rapport et la grille dans **Mes résultats** ou utilisez `replay` dans l’utilitaire local. L’accord porte sur les cas vérifiés. Mesurez les coûts complets avant de conclure à un avantage.

La démarche directe reçoit la nouvelle mission. Les deux démarches de réemploi reçoivent le même instrument antérieur. L’une d’elles peut aussi appeler ses sorties par leur nom. Le compilateur les insère comme expressions inertes. Le rapport peut contenir des données de mission. Gardez-le sur un appareil que vous contrôlez. L’identité de l’évaluateur et la provenance des cas s’établissent séparément.
