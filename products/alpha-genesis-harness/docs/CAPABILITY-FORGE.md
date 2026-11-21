# CAPABILITY FORGE Ω

CAPABILITY FORGE extends the private HARNESS workflow with a new experimental capability. A local model diagnoses a scientific task, proposes an executable instrument and repairs it against exposed checks. A separate exact verifier then judges the frozen source on sealed qualification and transfer cases. A successful tool can be run again without a model.

This candidate implements one task family, **exact rational telemetry with sparse faulty readings**. It reports an exact value, ambiguity, or inconsistency. The measurements in the registered trial are synthetic. The instrument does not model measurement noise or qualify physical equipment. The experiment and its A–F comparisons are specified in [the preregistration](CAPABILITY-FORGE-PROTOCOL.md).

## Start in the HARNESS

1. Open the local HARNESS connector on Linux with Python 3.10 or newer and libseccomp.so.2. Connect a model in the Intelligence Center using Ollama or a compatible local chat server.
2. Open **CAPABILITY FORGE Ω**. Describe the measurement you want to establish and select the local model. **Start investigation** approves this local mission and its technical attempts.
3. Observe the diagnosis, candidate generation, refusal or repair, and exact test findings. The model receives the objective and development evidence. The verifier alone receives the sealed qualification inputs during construction.
4. Download a qualified tool or export the full terminal run, including rejects and costs. From **Qualified tools**, paste a new input to run the selected artifact and independently verify its result.

The engine tries a compatible retained artifact first when requested. Verification never transfers automatically. A failed retained development check can trigger fresh construction. A failed sealed qualification stops that candidate. Pause and resume preserve committed artifacts, evidence and consumed allowances. An interrupted model request may have consumed resources before its response was saved.

## CLI and authenticated API

Run from the HARNESS directory. A CLI process and the connector cannot simultaneously own the same workspace.

    python3 -m bridge.forge create --config /path/to/local-config.json --input examples/forge-mission.json
    python3 -m bridge.forge run --config /path/to/local-config.json --run-id PRINTED_RUN_ID
    python3 -m bridge.forge inspect --run-id PRINTED_RUN_ID
    python3 -m bridge.forge export --run-id PRINTED_RUN_ID --output forge-telemetry.zip
    python3 -m bridge.forge reuse --run-id PRINTED_RUN_ID --input examples/forge-telemetry.json
    python3 -m bridge.forge registry

Use the same config with 'resume' if you interrupted a run before it finished. Select a fresh workspace with '--workspace'. Export to a '.json' filename to retain a terminal run's full event record. The 'retire' command removes a particular qualified run from active registry lookup while preserving its historical receipt. The most recent remaining compatible run can be selected by the next investigation.

The private connector uses its standard same-origin session token. GET '/api/forge/status' reports the sandbox and contract. POST '/api/forge/create' takes the example mission schema. POST '/api/forge/start', '/get', '/pause', '/resume', '/cancel', '/export', '/bundle' and '/retire' under '/api/forge' take 'run_id'. The '/reuse' endpoint also takes 'input'. The '/list' and '/registry' endpoints take an empty object. The binary bundle omits the objective text and credentials.

In an extracted tool bundle:

    python3 forge_sandbox.py candidate.txt input.json
    python3 forge_telemetry.py candidate.txt evidence.json

The sandbox runs each tool invocation in a clean child process with a Linux seccomp allowlist, bounded input and output, memory and CPU limits, no shell, no network and no filesystem access from generated code. macOS and Windows can browse HARNESS; this generated-Python route needs a compatible Linux environment, such as a Linux VM. Host support is checked before construction.

## Reproduce the pinned CPU experiment

Use Python 3.12 and install python-flint 0.8.0 in a separate environment for the independent conventional arm. Keep the weights outside the repository and have enough storage for about 7.2 GB of weights plus the runtime. The trial runs the models sequentially. The verified receipts report measured host usage.

Use the public upstream files at their pinned content identities. The trial driver hashes the downloads before launching them. The model license is Apache-2.0. llama.cpp uses the MIT license.

| File in the assets directory | Source |
| --- | --- |
| llama-b12242.tar.gz | [llama.cpp b12242 Linux x86-64 runtime](https://github.com/ggml-org/llama.cpp/releases/download/b12242/llama-b12242-bin-ubuntu-x64.tar.gz) |
| qwen3-4b.gguf | [Qwen3-4B-Instruct-2507 Q4_K_M](https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF/resolve/ae44f08e1392f39c0e474af10c3ff8355c8b6688/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf) |
| qwen-coder-7b.gguf | [Qwen2.5-Coder-7B-Instruct Q4_K_M](https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/1f629da0c8bed16b9e50cee91c70693650e66c35/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf) |

    python3 scripts/qualify_capability_forge.py --assets /path/to/assets --output /path/to/new-study

The '--first' option runs the conventional and development controls and Forge construction before the remaining model arms. Append '--resume' with the same source and output to continue. The run records any unfinished arm. A restricted reference requires an independently authorized comparable session.

## Français

CAPABILITY FORGE prolonge le connecteur privé HARNESS. Un modèle local diagnostique une difficulté scientifique, construit un outil exécutable et peut le corriger d’après des essais de développement. Un vérificateur rationnel indépendant contrôle ensuite l’artefact scellé. L’outil qualifié peut être réutilisé sans refaire l’inférence.

Ce candidat couvre la télémétrie rationnelle à lectures erronées peu nombreuses. Il établit une valeur exacte, une ambiguïté ou une incompatibilité. Les essais sont synthétiques et reposent sur un modèle linéaire exact.

1. Ouvrez HARNESS sous Linux avec Python 3.10 ou ultérieur et libseccomp.so.2. Connectez un modèle local dans le Centre d’intelligence.
2. Ouvrez **CAPABILITY FORGE Ω**, décrivez la grandeur recherchée, choisissez le modèle et lancez l’enquête.
3. Consultez les essais, les erreurs et l’utilisation du modèle. Seul le vérificateur accède aux cas de qualification pendant la construction.
4. Téléchargez l’outil qualifié. Dans **Outils qualifiés**, choisissez un artefact et collez de nouvelles mesures pour en vérifier le résultat.

Le fichier [forge-mission.json](../examples/forge-mission.json) sert d’entrée à la commande 'create'. Adaptez les champs 'provider', 'model', 'objective' et 'language', puis exécutez 'run'. Les autres commandes ci-dessus permettent d’inspecter, de reprendre, d’exporter et de réutiliser l’outil. L’archive contient le programme isolé, un exemple, les preuves et les deux commandes de reproduction.

Le modèle est local et son nom déclaré ne certifie pas ses poids. Le pilote de l’expérience vérifie les octets des poids et de llama.cpp, consigne les routes réellement utilisées et mesure le temps de calcul. Installez Python 3.12 et python-flint 0.8.0 pour ce pilote. Les liens du tableau désignent les poids publics verrouillés. Aucun gain économique ou niveau d’équivalence avec un modèle de pointe ne découle d’une qualification sur les cas synthétiques.
