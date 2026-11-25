# MY FRONTIER Ω · Universal mission workbench

[MONTREAL.AI × QUÉBEC.AI · English](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/#my-frontier) · [Français](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/fr.html#my-frontier)

## Run an ambition

Enter an ambition in My Frontier and activate FRONTIER Ω. The browser opens a mission, preserves the original wording and looks for optional Atlas evidence. Choose a local model, prepare a reviewed assistant prompt, or open an applicable deterministic capability. A model or reviewer can choose a direct answer, capability, composition, adaptation, research, invention, continuing investigation or clarification. Inspect the result and its assumptions, then revise or continue from the same record.

Use **My Results → Mission files** to download a local checkpoint and reopen it later. A waiting assisted request keeps its exact identifier and prompt. A running local request restores in a paused state so the member decides whether to dispatch again. Locking clears in-memory mission data. The exported JSON contains the mission text and work, so keep it in storage you control. Its hash detects changed bytes and supplies no signature or independent acceptance.

### Local intelligence

Choose **My Intelligence → Connect a model for this mission** and enter the model name shown by your runtime. The actual browser request requires selecting **Run with my local model**. Only the following loopback endpoints are allowed:

| Runtime | Address | Product qualification |
| --- | --- | --- |
| llama.cpp | `http://127.0.0.1:38461/v1/chat/completions` | Real Qwen3-4B inference and structured outcomes |
| Ollama | `http://127.0.0.1:11434/api/chat` | Protocol fixtures |

For the tested llama.cpp build, start a local service with a model you already have. Use its registered alias as the model name.

```sh
llama-server --host 127.0.0.1 --port 38461 --model /path/to/model.gguf \
  --alias my-model --ctx-size 8192 --no-ui \
  --cors-origins https://montrealai.github.io --cors-methods POST,OPTIONS \
  --cors-headers Content-Type --no-cors-credentials
```

Scope the allowed origin to the Pages origin if you choose to connect your browser. Other pages at the same origin share its browser permissions. Your browser may prompt for local-network access. If the runtime or browser declines the request, the mission remains available for assisted continuation. The module bounds response size, accepts a single response on each dispatch and aborts when the member pauses, cancels, locks or revises.

[llama.cpp server configuration](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) · [Ollama origin configuration](https://docs.ollama.com/faq)

### Reviewed assistant or provider

In **Prepare an assisted mission**, review the complete prompt, opt in to copying or downloading it, and use your approved ChatGPT or Codex workflow. Paste the resulting structured message into the same mission. Use the same prompt with the optional local HARNESS provider tool, or with the local provider route you control. Credentials remain in the existing local provider configuration. For a remote provider, use its existing exact-plan approval and budget guard. Paste the returned object or the tool's JSON response envelope. HARNESS currently accepts prompt files up to 24 KiB. The mission itself accepts up to 24 KiB before context and instructions are added, so use the reviewed copy workflow if your full prepared prompt exceeds the HARNESS input contract. These replies are recorded as assisted work.

[Existing HARNESS connection and approval guide](../../products/frontier-member-tools/foundry/README.md)

## Research and integration evidence

| Path | Execution and decision |
| --- | --- |
| Universal browser intake | General text is the mission identity. Related Atlas evidence is optional. Direct routes and research routes share the same request contract. |
| Deterministic reuse and construction | The router receives exact operating limits for qualified tools. Their scope remains visible alongside a model suggestion. The mission can carry the interpreted objective to bounded HARNESS authoring and make an independently accepted portable solver available for later missions. |
| Living Atlas and Opportunity Capture | Published primary lead and evidence can inform the mission. The existing independent Atlas and NISAR/Sentinel checks remain in the previous release. |
| Scientific Truth Engine and Productive Intelligence Factory | Published scope, attribution and evidence-lineage checks remain callable from their current workbench and portable releases. |
| Substrate, Scientific Discovery and Cascade | Existing experiments are accessible in Capabilities and Activation packages; their published qualification scopes apply. |
| Capability Switch and Successor research | Retention is portable. Prior bounded studies and library requalification are available. The Game Theory follow-on exercised solver reuse to design a one-bit disclosure. |
| Ω ALPHA and RSI RESEARCHER | The local assisted construction and evaluation context can undertake new research. Standing autonomous operation, native profit and recursive intelligence improvement require separate evidence. |

The exact owner ambition **Build Frontier AI for Game Theory.** was run using Qwen3-4B through llama.cpp and by an included Codex construction context. Qwen returned a preliminary research route. Codex constructed the executable solver and the independent evaluator applied a different exact arithmetic method to six held games. The downloaded certificate checker needs only Python's standard library. The model route, mathematical result and evaluator authority have separate receipts. The browser opens the exact ambition and discloses the already completed public assisted run.

- [Executed research and comparator results](game-theory/REPORT.md)
- [Portable research inputs and commands](game-theory/START.md)
- [Local inference for the exact ambition](intelligence/game-theory-local.json)
- [English direct calculation diagnostic](intelligence/volumes-local.json)
- [French invention diagnostic](intelligence/traversiers-local.json)
- [Independent six-game evaluator](evaluator/game-run-v1/INDEPENDENT-REPORT.json)
- [Opportunity Capture qualification](../opportunity/REPORT.md)

External experiments, deployment, publication and spending continue to require their respective authorization. Pages serves public application assets. It holds no remote inference credentials or server-side mission storage. [Confidential delivery issue #550](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/550) and [independent evaluator custody issue #565](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/565) cover the separate administrator-controlled work.

## Version française

Saisissez votre ambition dans **Ma frontière**, puis cliquez sur **Activer FRONTIER Ω**. La mission garde vos mots d’origine. Les dossiers de l’Atlas peuvent orienter la suite. Vous pouvez lancer un modèle local, préparer une mission assistée ou ouvrir un outil pertinent. Le résultat indique la voie choisie, l’objectif interprété, les hypothèses et la prochaine action. Vous pouvez réviser et poursuivre la même mission.

Ouvrez **Mes résultats → Fichiers de mission** pour enregistrer votre travail dans un fichier local et le reprendre plus tard. Une demande assistée conserve sa consigne et son identifiant. Une demande locale ouverte au moment de l’exportation reprend en pause. Le verrouillage efface la mission de la mémoire de la page. Conservez vos fichiers exportés dans un emplacement que vous contrôlez.

La configuration d’un modèle local se trouve dans **Mon intelligence → Connecter un modèle à cette mission**. Sélectionnez votre environnement, indiquez le nom du modèle et revenez à la mission pour lancer la requête. Le navigateur peut demander l’accès à la boucle locale. Pour un assistant ou un fournisseur autorisé, relisez la consigne, emportez-la dans votre environnement approuvé et importez la réponse. Un modèle connecté demeure une source de propositions, et les résultats reçus restent à vérifier.

La mission exacte **Build Frontier AI for Game Theory.** a livré un solveur local d’allocation stratégique à scénarios cachés et un vérificateur indépendant du solveur. Les six jeux d’essai conçus indépendamment ont été acceptés, dont un comportant 211 775 256 paires d’actions possibles. Le modèle local a amorcé la recherche. Le travail de construction assisté par Codex a produit les certificats. La vérification d’un certificat demande seulement la bibliothèque standard de Python. [Démarrage et commandes](game-theory/START.md) · [Résultats détaillés](game-theory/REPORT.md).
