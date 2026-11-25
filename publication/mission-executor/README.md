# MY FRONTIER Ω · Local mission execution

MY FRONTIER uses the existing Alpha Genesis HARNESS runner on your device. Once the member page is paired, **Activate FRONTIER Ω** submits the exact ambition under the scope selected by the local operator. The execution record shows provider requests, executed operations, refusals, recovery events and produced artifacts. Work that needs independent acceptance enters review.

[English member page](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/#my-frontier) · [Version française](#français) · [Acceptance ledger](GATES.md)

## Start a local workspace

1. Extract the local executor from **My Intelligence**. Use Python 3.12 or later. The qualified Endpoint replay also uses a local Node.js installation.
2. Start your configured llama.cpp or compatible local provider on numeric loopback. The example uses `127.0.0.1:38461`. In `local-model.example.json`, use the model identity and context capacity actually configured in that server.
3. From the extracted folder, start the existing HARNESS connector. Keep its workspace outside public files and use a directory controlled by the local operator.

```sh
python3 bridge/server.py --config local-model.example.json \
  --workspace "$HOME/.frontier/private-missions" --pages-missions \
  --mission-model qwen3-8b-q4_k_m --no-browser
```

4. Open **My Intelligence → Run missions with your local executor** in the member page. Enter the one-use code printed locally. Then activate your ambition. If your browser asks for local network permission, approve it for this page to connect. The same website origin covers multiple project paths, so pair a browser only when you trust that origin.
5. Open **My Results → Save or reopen a mission** to find existing runtime missions after pairing again. Use the runtime panel to pause, resume, cancel or download its execution record. Leave the local process running to continue permitted work after closing the browser.

The numeric loopback port for this mode is 38463. The command accepts `--mission-lease-minutes`, `--mission-turns`, `--mission-actions` and `--mission-output-tokens`. These bounds govern each operator’s authorization and remain independent of model text. A use-once code exchanges for a temporary, workspace-scoped browser session. The browser keeps it in memory and transmits it only to the enabled local connector. Each successful pairing prints a fresh code locally. Disconnect pauses running work and invalidates that browser session. Underlying provider execution already dispatched can take time to stop. The journal preserves settled work and records uncertain interruption and provider usage. Resuming a stored run checks the selected model, tools, budgets and expiry against the current connector. Activate its ambition again when a fresh authorization is needed. The linked run preserves its original ambition and history.

To restore a downloaded `frontier-execution.json`, start the connector with the same command and add `--mission-import /path/to/frontier-execution.json`. The historical artifacts reopen as a paused mission under the new local bounds. Inspect the mission in **My Results** and explicitly resume when ready. A portable checksum checks the archive contents. It supplies neither independent acceptance nor execution authority.

## What runs

| Boundary | Supported path |
| --- | --- |
| Mission intake | Exact natural-language ambition, bilingual member prompts, local executor or reviewed existing handoff |
| Construction | HARNESS arithmetic instruments, bounded read-only SQLite transformations and local documents |
| Dispatch | Model proposes structured actions. The runner validates them, records actual outcomes and can apply a later repair within its lease. |
| Applicability | Machine-readable, independently checked facts for qualified scoped capabilities. Missing verified facts and incompatible requirements prevent execution. |
| Evidence | A native operator can supply explicitly authorized, digest-bound input evidence. The Pages pairing surface accepts the ambition and locale under local policy. |
| Recovery | Original HARNESS checkpoint, immutable artifact contents, explicit resume, cancellation, expiry and revocation |
| Acceptance | Operator development checks stay separate from independent evaluation and capability promotion. |

The request body and resulting artifacts stay in the approved device boundary for this profile. The public site serves the interface and public research archives. Private publishing and external evaluation custody remain governed by [#550](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/550) and [#565](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/565).

[Scope and exact Endpoint replay](semantics/SCOPE.md) · [Game Theory extension](game/REPORT.md) · [Acquisition-fee transfer](transfer/REPORT.md) · [Opportunity Capture and scientific record](opportunity/REPORT.md)

## Français

MY FRONTIER utilise le moteur de missions de HARNESS sur votre appareil. Après le jumelage, **Activer FRONTIER Ω** transmet votre ambition intégrale dans le périmètre autorisé par l’opérateur local. Le journal affiche les demandes au modèle, les opérations réalisées, les refus, les reprises et les fichiers produits. Les résultats qui exigent une validation indépendante restent en attente d’évaluation.

1. Téléchargez l’exécuteur dans **Mon intelligence**, puis extrayez-le. Utilisez Python 3.12 ou une version ultérieure. Le rejeu Endpoint utilise aussi Node.js.
2. Démarrez le modèle local sur la boucle locale. Dans `local-model.example.json`, indiquez son nom exact et la taille de contexte réellement configurée.
3. Exécutez la commande ci-dessus en choisissant votre dossier privé et le nom du modèle. Dans **Mon intelligence → Exécuter des missions sur votre appareil**, saisissez le code à usage unique affiché dans votre terminal.
4. Activez votre ambition. Le module conserve son journal dans le dossier local pendant l’exécution. Pour rouvrir un dossier après une actualisation, jumelez le navigateur, puis ouvrez **Mes résultats → Enregistrer ou rouvrir une mission**.
5. Le panneau d’exécution permet de suspendre, reprendre, annuler ou télécharger le dossier. Fermer la page laisse le processus local poursuivre le travail autorisé dans les limites de son autorisation.

L’archive comprend le moteur de calcul HARNESS et un exécuteur SQLite en lecture seule. Le modèle propose des actions et le moteur les contrôle. Les faits nécessaires à l’emploi d’une capacité qualifiée doivent être établis avant son exécution. Les autorisations expirées, les exigences incompatibles et les renseignements indispensables manquants donnent un statut explicite.

Pour rouvrir un dossier d’exécution téléchargé, ajoutez `--mission-import /chemin/vers/frontier-execution.json` à la commande de démarrage. Le dossier est restauré en pause sous l’autorisation locale actuelle. Examinez l’historique dans **Mes résultats**, puis reprenez la mission si son périmètre convient. Si les limites d’un dossier sauvegardé ont changé, activez de nouveau son ambition pour créer un dossier lié sous l’autorisation actuelle.

[Étude sur les observations bruitées et coûteuses](game/START.md) · [Registre de qualification](GATES.md)
