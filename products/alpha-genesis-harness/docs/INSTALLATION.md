# Installation / Installation

## Start with what you already have

The download contains a browser application and an optional Python connector. It does not install a model, create a cloud account, activate billing or contact Squarespace. No Docker is required.

1. Keep the original ZIP. Compare its SHA-256 with the exact release's published checksum.
2. Extract the **whole** ZIP into a folder you can keep, not inside a temporary archive viewer.
3. Open `START-HERE.html`. Choose **Open the HARNESS** for the offline demonstration and manual model workflow.
4. To connect models or run persistent agentic work, install Python 3.10 or later if you do not already have it, then start the appropriate launcher below. Python is supplied separately under its own licence.
5. Keep the connector terminal open. The application opens at the printed `http://127.0.0.1:8765` address. Stop it with Ctrl+C when finished.

| System | Local connector launcher | Equivalent command in the product folder | Verification scope |
|---|---|---|---|
| Linux | `Launch-HARNESS.sh` | `python3 launch.py` | Linux automation is recorded in the exact release evidence |
| macOS | `Launch-HARNESS.command` | `python3 launch.py` | See this exact release’s macOS source-launcher/Chromium receipt; Finder/Safari are separate |
| Windows | `Launch-HARNESS.cmd` | `py -3 launch.py` | See this exact release’s Windows source-launcher/Chromium receipt; Explorer double-click is separate |

The separate native evidence supplement records each tested OS, exact archive hash, source launcher, headless Chromium workflows, screenshots and exported output. Only a matching PASS receipt establishes that scope; the included static matrix describes the source-freeze state before hosted execution. Finder/Explorer double-click, Safari, signed installers and notarization need separate evidence.

These are source launchers, not signed installers or notarized applications. If your operating system blocks an untrusted download, first verify its origin and checksum. Do not disable system protections globally. The terminal command is an explicit alternative after you trust the source. If a ZIP extractor loses the macOS/Linux execute bit, the terminal command still works.

Use another available port with `python3 launch.py --port 8766`. Suppress browser opening with `--no-browser`. Use `--config /absolute/private-config.json` to load your private model configuration. Keep that file outside this download and outside source control. Persistent workflow storage is separate from the application; select a private directory with `--workspace /absolute/private-workspace`.

### Model prerequisites

- **Local:** install and start your selected inference server and a model permitted by its licence. Use the installed model's exact ID. RAM/VRAM, storage, speed and context capacity depend on the model and quantization; follow that model/server's measured requirements. The HARNESS does not bundle model weights.
- **API:** use an account and credential you control, exact model IDs, explicit network permission and a deliberate budget. An existing chat subscription does not supply a conventional API key.
- **ChatGPT plan:** use the documented eligible sign-in path and required optional dependencies. Commercial use remains gated by OpenAI approval. Install the optional identity-verification dependencies with `python3 -m pip install -r requirements-chatgpt.txt` in your private Python environment. See [ChatGPT setup](CHATGPT-PLAN.md), [model connections](MODEL-CONNECTIONS.md) and the release matrix before relying on it.
- **Codex:** install the official supported CLI separately and authorize the HARNESS’s official ChatGPT connection. The isolated app-server uses that authorized connection, not an existing CLI login. This construction pathway is distinct from general model inference.

For an already running local server, choose **Local** in the Intelligence workspace. Select Ollama, LM Studio, llama.cpp, vLLM, MLX or the compatible preset, confirm its loopback port, and choose **Discover installed models**. Enter/select the exact model ID, declare only capabilities the server actually supports, then choose **Connect local model**. Non-secret connection settings persist privately; no source-code or JSON edit is needed. Discovery is not an inference test: run a workflow to establish that the selected model works. A local proxy could itself forward requests elsewhere, so verify your server's own offline configuration.

### Update safely

Keep your old version and exports. Extract a new version into a new directory, read its release notes, start it with the intended workspace and inspect saved work before continuing. A project replay checks stored evidence; it does not reproduce a nondeterministic model response. Never copy credentials into the product to make an upgrade easier.

## Français

Le téléchargement contient une application de navigateur et un connecteur Python facultatif. Aucun modèle, compte infonuagique ni service payant n'est installé automatiquement. Docker n'est pas nécessaire.

1. Conservez le ZIP original et comparez son empreinte SHA-256 à celle de la publication exacte.
2. Décompressez **tous** les fichiers dans un dossier permanent.
3. Ouvrez `START-HERE.html`, puis l'application. La démonstration et le parcours manuel fonctionnent sans clé API.
4. Pour connecter des modèles et conserver des exécutions agentiques, utilisez Python 3.10 ou ultérieur avec le lanceur de votre système indiqué dans le tableau.
5. Gardez le terminal ouvert. Utilisez l'adresse locale affichée. Ctrl+C arrête le connecteur.

Les lanceurs sont des scripts source, sans signature native ni notarisation. Consultez les reçus macOS et Windows du supplément de preuves correspondant à l’empreinte exacte du ZIP. Une réussite y couvre le lanceur source et Chromium sans interface système; elle ne couvre pas le double clic Finder/Explorer, Safari ou une installation native signée. La matrice incluse décrit l’état au gel du code, avant ces exécutions hébergées. Vérifiez l'origine du téléchargement; ne désactivez pas globalement les protections du système. Si le droit d'exécution n'est pas conservé par l'extracteur, utilisez la commande du tableau.

La configuration privée et l'espace de travail doivent rester hors du téléchargement et du dépôt. Un modèle local exige son propre serveur, ses poids et les ressources indiquées par son éditeur. Un compte API exige une autorisation explicite et un budget; un abonnement ChatGPT utilise un parcours d'autorisation distinct. L'accès commercial au forfait ChatGPT reste soumis à l'approbation applicable.

Pour un serveur local déjà lancé, choisissez **Local** dans l'espace Intelligence, son moteur et son port, puis **Découvrir les modèles installés**. Sélectionnez l'identifiant exact, déclarez uniquement les capacités prises en charge et utilisez **Connecter le modèle local**. Les paramètres non secrets sont conservés sans modification de code ou de JSON. Exécutez ensuite une procédure : une liste de modèles n'est pas un test d'inférence. Vérifiez aussi que votre serveur ne relaie pas les requêtes vers un service distant.

Pour une mise à jour, gardez la version précédente et vos exports, extrayez la nouvelle édition dans un autre dossier et lisez ses notes. Une relecture de preuves enregistrées n'est pas un nouveau calcul de modèle.
