# Advanced operator guide / Guide d'exploitation avancée

[Instrument workshop operation and replay · Exploitation et reproduction](WORKSHOP.md#operator-interface)

## Define acceptance before generation

Specify the desired artifact, permitted inputs, input/output meaning, independent checks, material constraints and a competent conventional alternative. Separate factual evidence from assumptions. The same model may perform multiple roles, but role names do not establish independent verification. Programmatic acceptance checks are distinct from a critic's opinion.

## Choose the smallest adequate team

Local model connections can be created through the Intelligence workspace after the customer's inference server is running. Presets address `127.0.0.1` on the selected port. Model catalog discovery, context/output settings and JSON/streaming/tool-use declarations are separate from successful inference. **Remove saved connection** removes the HARNESS connection settings; it does not stop or uninstall the external model server. No API key, model download or cloud activation is part of this local setup.

Use one model when it can perform the task and independent checks can establish correctness. Add a critic to challenge assumptions; a researcher to gather evidence; a builder to construct an artifact; or an economist to inspect complete costs and participation. Assign exact provider/model identities and keep each provider authorization explicit. Never infer permission to send private context to a fallback provider.

The executable workflow implements bounded propose → act → observe → critique → revise. Its permitted tools construct constrained, inspectable artifacts. It does not grant model text shell access or authority to send messages, spend money or sign contracts. A trusted local executor and its input grammar are part of the security boundary; review that grammar before relying on a new artifact type.

## Budgets and accounting

API token estimates, ChatGPT-plan request allowances, Codex usage and local compute are different resources. Provider prices are customer declarations, not live quotes. Missing usage after an uncertain failure remains unknown, never zero. A per-process request budget is not a guaranteed vendor billing cap. A cancelled upstream request can still consume quota or incur charges.

Include search, failed attempts, construction, validation, maintenance, human intervention, electricity/hardware and financing when comparing complete costs. Modeled revenue is not a transaction, anticipated funding is not cash and retained capability is not automatically productive advantage. The HARNESS does not create a second financial account or move money.

## Recovery and portability

Keep private workflow storage separate from the installation. Checkpoints record progress and attributable outcomes. After interruption, inspect the recorded state, then resume the same run where supported. Do not silently dispatch a paid step again under a new identity. Export the completed evidence and artifacts; inspect exported content before sharing it.

A saved record can be inspected or replayed without making the same model prediction again. Nondeterministic inference cannot be promised byte-identical. Integrity hashes detect byte changes only relative to a trustworthy reference; they do not prove that a claim was true.

## Retain and test transfer

Retain an instrument only with its implementation identity, assumptions, accepted tests, provenance and limits. On a different successor objective, recheck those limits. Compare inherited execution with a capable fresh or ordinary reuse route using the same acceptance and full costs. Count acquisition, adaptation and validation. Preserve a tie or loss. More saved files are not evidence of compounding intelligence.

## Evidence terminology

| Label | Meaning |
|---|---|
| Implemented | Code exists and its callable interface is identified |
| Tested | Named tests executed with recorded results |
| Verified | A specific claim survived its declared checks |
| Demonstrated | Observations support the stated, bounded outcome |
| Commercially validated | Actual users, transactions or external acceptance support the claim |

The release matrix uses **PASS, FAIL, BLOCKED, NOT TESTED** for individual requirements. Passing protocol fixtures does not pass a live-account requirement.

## Français

Définissez le livrable, les entrées permises, la signification des résultats, les tests indépendants et l'alternative conventionnelle avant la génération. Un critique qui approuve une réponse n'est pas une preuve indépendante. Une équipe doit apporter des fonctions distinctes et identifiables, pas seulement des noms de rôles.

Le cycle agentique propose, agit avec des outils limités, observe, critique et révise. Le texte d'un modèle n'obtient pas un accès libre au terminal, aux paiements, aux contrats ou au démarchage. Chaque transmission à un fournisseur doit être autorisée; aucun changement silencieux de fournisseur n'est permis.

Distinguez le budget API, les quotas ChatGPT, l'usage Codex et le calcul local. Les coûts inconnus restent inconnus. Une annulation ne garantit pas l'arrêt de la facturation distante. Incluez recherche, essais échoués, construction, vérification, entretien et intervention humaine dans toute comparaison.

Conservez l'espace de travail privé hors de l'installation. Après une interruption, inspectez puis reprenez la même exécution. Exportez les preuves et les livrables. Une relecture n'est pas une nouvelle prédiction du modèle.

Un instrument conservé transmet un moyen utilisable avec ses limites, pas une autorité ni une preuve pour toute situation future. Réévaluez-le sur une nouvelle mission et comparez ses coûts complets avec une méthode compétente. Une égalité ou une perte demeure un résultat valable.

## Export a run, reopen it and use its artifact

In the connected workspace, select the run after its active request has stopped. Export its **JSON project** to preserve the mission, evidence, state and artifact contents. Use **Import workflow** to reopen that JSON into a new run. The imported status is paused and its old verification is historical; execute its current acceptance checks before treating it as verified.

Choose **Download artifacts** for the actual ZIP of constructed files. Extract the bundle, inspect `instrument.json` and the supplied `RUN_INSTRUMENT.py` evaluator, then follow the generated artifact instructions. These files can be used outside the HARNESS. The JSON project and artifact ZIP have different purposes; retain both when you need portable continuation and usable output. Neither export contains provider credentials or the workspace integrity key.

CLI equivalents from the product directory:

```sh
python3 -m bridge.workflows list --workspace /absolute/private-workspace
python3 -m bridge.workflows inspect --workspace /absolute/private-workspace --run-id RUN_ID
python3 -m bridge.workflows export --workspace /absolute/private-workspace --run-id RUN_ID --output /absolute/project.json
python3 -m bridge.workflows import --workspace /absolute/another-private-workspace --spec /absolute/project.json
```

### Français

Après l’arrêt de la demande active, exportez le **projet JSON** pour conserver mission, état, preuves et contenus. L’importation crée une nouvelle exécution en pause. Les anciennes preuves restent historiques : refaites les vérifications avant d’accepter le nouveau résultat.

Utilisez **Télécharger les livrables** pour obtenir le ZIP des fichiers construits. Décompressez-le et inspectez l’instrument et son évaluateur fourni. Le JSON sert à poursuivre le travail; le ZIP fournit les fichiers utilisables ailleurs. Conservez les deux si nécessaire. Les clés des fournisseurs et la clé d’intégrité de l’espace ne sont pas exportées.

## Retrieve current evidence only when authorized

The `retrieve_source` action is excluded from the default workflow tools. To use it, explicitly include it in the mission's `tool_permissions` and configure the exact public hostname in `source_hosts`. It accepts HTTPS URLs on that allowlist, rejects private addresses and redirects, bounds the returned bytes, and records the actual URL, retrieval time and content hash. It is refused in `local_only` mode.

A retrieved document is untrusted evidence. Its text cannot add tools, change permissions or override acceptance. The retrieval timestamp is not a publication date, and a content hash is not proof that the source's claims are true.

### Français

L'action `retrieve_source` n'est pas activée par défaut. Ajoutez-la explicitement aux permissions de la mission et autorisez le nom d'hôte public exact dans `source_hosts`. Elle utilise HTTPS, refuse les adresses privées et redirections, limite la taille et consigne l'URL, l'heure de récupération et l'empreinte. Elle est interdite en mode `local_only`. Le texte récupéré reste une preuve non fiable, jamais une nouvelle instruction ou permission.
