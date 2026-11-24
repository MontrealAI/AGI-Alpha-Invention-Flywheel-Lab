# My Frontier Ω · Capability Foundry

Start in **My intelligence**. The archive replay runs without AI, an installation or a provider account. To create a tool, freeze one clearly specified input and output contract, choose how to obtain the instrument, and check it against cases from a separate reviewer. The browser supports named scalar inputs, exact safe integers, individual bounds in a mission file, text, booleans, and the limited HARNESS expression language. A missing field, wrong type, out-of-bounds input or invalid calculation stops the run. Limit files to 128 KiB, 12 fields per contract, and 64 verification cases. Use the existing HARNESS workshop if you need longer experiments or a different runtime.

## Offline quick start

Unzip the companion in a directory you control. Use Node.js 22 or later. The release qualification records the exact tested versions. Model connections additionally use Python 3.11 or later and a runtime you already control.

```sh
node foundry-cli.mjs demo
node foundry-cli.mjs prompt mission.json > prompt.txt
node foundry-cli.mjs seal mission.json candidate.json
node foundry-cli.mjs check mission.json candidate.json cases.json
node foundry-cli.mjs retain mission.json candidate.json cases.json > capability.json
node foundry-cli.mjs recheck capability.json cases.json
node foundry-cli.mjs run capability.json cases.json input.json
```

Use the browser's case template or take the mission fingerprint from `seal`. The case sheet requires `reference` (describe the independent method and its exact source) and `cases` containing `input` and `expected` objects. Keep the sheet away from the constructor and use the original sheet to requalify a reopened file. The digest detects changes to a file with an independently trusted fingerprint. A self-generated or recomputed hash confers zero authority. The sample archive check is a historical technical replay. It gives no operating or economic approval.

## Choose intelligence

- **No model.** Author the finite expression or use the archive sample. No internet is needed in the CLI. Public-file member access is an interface gate and does not provide confidential hosting.
- **My ChatGPT.** Review the prompt. Copy or download it, submit it in your own conversation and paste or import the JSON reply. Keep verification answers outside the conversation. Account access and terms apply. There is no automatic subscription connection in the Pages experience.
- **Local model.** Install the desired runtime from its official source and select a model compatible with the resources you control. Prefer a numeric loopback bind and a locally authorized runtime. Copy `local.example.json` to your own configuration. For llama.cpp or LM Studio, replace the URL and model ID with the selected OpenAI-compatible endpoint. For Ollama, use kind `ollama` and change the base URL to `http://127.0.0.1:11434` without `/v1`. Use the platform's recommended local access controls. Keep `local_only` true. The Pages process cannot talk to your runtime. `discover` lists model identifiers. Actual inference and the separate verification cases qualify an instrument.
- **Provider API.** Start from [HARNESS provider configuration](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/39e76570c851b3527d78a526053a9ea2a611a993/products/alpha-genesis-harness/docs/MODEL-CONNECTIONS.md). Remote calls require `local_only: false`, `allow_paid_requests: true`, explicit model rates and a budget covering the declared reservation. Keep keys in named local environment variables. Inspect the precise prompt, model, destination and conservative local reservation with `plan`. Append `--approve HASH` using that plan for one dispatch. The reservation is a local accounting estimate and a vendor bill may differ. Record the reported tokens, a separate provider invoice if available, and your actual complete costs.
- **Hybrid.** Generate with a manually reviewed reply or a selected local or remote connection. Import an instrument and execute it deterministically with the shared HARNESS evaluator. Reuse needs no further inference. A model contributes a candidate. It receives no operator permission, evaluator trust or deployment rights.

```sh
python3 provider.py --config local.json status
python3 provider.py --config local.json discover --provider localhost-inference
python3 provider.py --config local.json plan --provider localhost-inference --model YOUR_MODEL --prompt prompt.txt
python3 provider.py --config local.json generate --provider localhost-inference --model YOUR_MODEL --prompt prompt.txt --candidate-file candidate.json
```

The archive checks found a reliable result with the pinned Qwen3-4B model using compact formulas. For your own mission, the companion also supports this input form:

```sh
node foundry-cli.mjs formula-prompt mission.json > formula.txt
python3 provider.py --config local.json generate --provider localhost-inference --model YOUR_MODEL --prompt formula.txt --formula-mission mission.json --candidate-file candidate.json
node foundry-cli.mjs check mission.json candidate.json cases.json
```

The formula compiler translates a finite list of expressions into data. The Foundry still checks the complete instrument and original cases before evaluation or reuse. To replay the exact retained Qwen3-4B instrument without the model:

```sh
node foundry-cli.mjs recheck retained/noaa-window.json retained/noaa-cases.json
node foundry-cli.mjs run retained/noaa-window.json retained/noaa-cases.json retained/noaa-reuse-input.json
```

The archive receipt reports the two 0.5B failures and the failed successor comparison. See the [bilingual report](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/publication/frontier-foundry/REPORT.md). The HARNESS native project export also works with the [standalone HARNESS](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/39e76570c851b3527d78a526053a9ea2a611a993/products/alpha-genesis-harness). Reopen a native project with an instrument under the same mission objective. Importing a project carries only its data-only instrument. It leaves qualification undecided.

Use `--stream` only if streaming is explicitly configured for the model. Ctrl+C cancels locally. A dispatched provider can continue to work or bill independently of the local process. The companion makes one attempt. Keep its request receipt beside the instrument if provider provenance or usage matters. Neither is uploaded. Store local exports somewhere you control. Rerun a stopped mission from the saved mission, candidate or asset, and original case sheet. The companion cannot grant itself access, execute generated code, run continued background evolution or promote a result.

The bundled HARNESS code retains its Apache-2.0 license and notice. The download contains no models or customer data. Public evidence and existing products retain their own rights. Use the registered scope and strongest alternatives before relying on a result. See [the experiment registration](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/publication/frontier-foundry/REGISTRATION.md).

## Français

Dans **Mon intelligence**, choisissez le rejeu de l’archive ou ouvrez une mission. Décrivez une opération qu’une autre personne peut vérifier. Figez les champs, la méthode de référence et les critères. Écrivez l’instrument vous-même, importez la réponse JSON de votre conversation ou passez par l’utilitaire local. Demandez à une autre personne de conserver les réponses attendues hors de la construction. Téléchargez ensuite la grille et importez les cas. Une concordance atteste ces cas seulement. Gardez la grille d’origine pour requalifier le fichier exporté.

Après avoir décompressé l’utilitaire, lancez `node foundry-cli.mjs demo` pour un essai hors ligne. Les commandes ci-dessus permettent de produire la consigne, de sceller l’instrument et d’exécuter les contrôles. Pour un modèle local, copiez `local.example.json`, indiquez l’adresse de boucle locale et le nom du modèle, et gardez `local_only` à `true`. Le mode `formula-prompt` prépare des formules scalaires pour le compilateur HARNESS. Les fichiers sous `retained/` permettent de rejouer l’instrument Qwen3 sans charger le modèle. La commande `discover` liste les modèles. `plan` affiche l’opération prévue. `generate` lance un seul appel. Relisez la consigne avant une transmission. En mode distant, vérifiez le tarif, la destination et l’empreinte du plan. Le coût complet et les frais réels doivent être établis séparément. Ctrl+C interrompt l’attente locale. Le fournisseur peut poursuivre une requête entamée.

Le navigateur et l’utilitaire partagent le même langage restreint. Un modèle peut proposer un instrument, mais la grille séparée en contrôle les résultats. Aucune clé de fournisseur, donnée de membre ou sortie privée ne doit être déposée dans une publication. Les fichiers fournis par GitHub Pages sont publics. Les fichiers locaux restent sous votre contrôle et peuvent contenir des renseignements sur votre mission. Une activation confidentielle relève toujours de l’autorisation distincte dans le dossier #550.
