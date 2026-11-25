# Choose your intelligence / Choisir votre intelligence

The three automated access categories share one workspace but have different authorization, privacy, accounting and qualification requirements. Manual exchange remains available when no automated connection is configured.

| Mode | What you supply | Where inference runs | Qualification boundary |
|---|---|---|---|
| Local LLM | Installed server/model, approved loopback endpoint | Your selected local server | A scripted fixture does not count as local inference |
| Provider API | Authorized account, private key, exact model, declared rates and budget | Explicitly selected provider | Protocol tests do not count as authenticated live completion |
| ChatGPT plan | Eligible account consent through official OAuth, applicable distribution eligibility | Official permitted OpenAI route | Paid-edition use requires applicable commercial approval and live verification |
| Codex construction | Official installed Codex, authorized HARNESS ChatGPT connection and permitted sandbox | Codex's configured execution path | Distinct from general model inference; usage/account limits remain separate |
| Manual | Your own chat account or authored response | Service you independently choose | No automatic sign-in or account integration is implied |

## Local models without cloud credentials

### MY FRONTIER Ω

Start the connector with `Launch-FRONTIER.sh` on Linux, `Launch-FRONTIER.command` on macOS or `Launch-FRONTIER.cmd` on Windows. Pair the member page, open **Intelligence**, and select **Find local models**. Choose a model reported by your running runtime and authorize the connection test. The connector checks standard numeric loopback endpoints and eligible endpoints from the private HARNESS configuration. For compatible runtimes that report a local file path, the member page shows the model filename and the connector uses the exact runtime identifier privately.

| Runtime | Default connector inventory | Official setup |
| --- | --- | --- |
| Ollama | `127.0.0.1:11434/api/tags` | [Install Ollama](https://ollama.com/download) |
| LM Studio | `127.0.0.1:1234/v1/models` | [Install LM Studio](https://lmstudio.ai/download) |
| llama.cpp | `127.0.0.1:8080/v1/models` | [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases) |
| vLLM | `127.0.0.1:8000/v1/models` | [Install vLLM](https://docs.vllm.ai/en/latest/getting_started/installation/) |

If the list is empty, start your already installed runtime. If you need a runtime or model, use its official installation instructions. Check the exact weight and runtime downloads, license, context size, storage and working memory on the model and runtime release pages. The discovery response reports operating system, CPU and supported memory and storage measurements for comparison. Verify published checksums when available, and start the runtime on numeric loopback. Choose an installation and model download yourself before returning to the same mission in **Intelligence**.

The connector validates an actual response to a short arithmetic request before enabling the selected route. It records the observed format, response time and token counts when reported. Schema-mode testing includes a random value supplied only in the schema. If the automatic route cannot demonstrate schema output, it can test JSON mode or prompt-constrained JSON. This checks the connection and observed format. Suitability for a particular mission depends on its own evidence and evaluation.

The private HARNESS workspace remembers the selected route and local or hybrid preference. After restarting the connector, use **Reconnect my model** to check the same route again. Hybrid mode available through this connection combines local inference and permitted local capabilities. Separately authorize any external model access. Discovery and the readiness request carry no mission text.

### Advanced HARNESS configuration

In the standalone HARNESS, use **Local** in the Intelligence workspace to discover and connect an installed server and model. Declare the exact model ID and demonstrated capabilities. Advanced operators can instead use a private copy of `bridge/config.local-only.example.json`. The supported compatibility configurations cover Ollama, LM Studio, llama.cpp, vLLM and MLX servers. Follow [provider protocols](PROVIDER-PROTOCOLS.md) for supported fields and the difference between compatibility and live verification.

Local-only configuration denies remote provider access. Public-source retrieval must also remain disabled for a fully local workflow. The HARNESS cannot certify another local program's network behavior; use OS-level isolation if your use requires that separate guarantee. Local token rates of zero mean no declared API token charge, not free hardware or electricity.

For an independently qualified local compatible-chat or Ollama model, explicitly enable the separate `json_schema` capability to constrain response structure. See [local structured output](STRUCTURED-OUTPUT.md) for the supported subset, exact wire fields and fail-closed validation. Ordinary JSON mode does not imply this capability.

## Historical source-scoped local observations

The [historical equality-corrected `0398ea31` source receipt](../evidence/live-local-workflows-v0.3-equality-fixed.json) records actual Linux CPU Qwen3-1.7B inference through llama.cpp. The single builder exhausted three calls with invalid input-field artifacts; the aggregate run is **FAIL**. The builder–critic path passed in three calls: malformed builder JSON was rejected, the next builder response repaired the artifact, and a separate critic completed. The independently checked export returned 34 for x=17 and reuse returned 82 for x=41. This is a bounded observed repair, not reliable success across policies or validation of the merged runtime. Only the recorded source snapshot was executed; a final-source claim requires evidence matching the packaged code. [Earlier attempts](../evidence/LIVE-LOCAL-REPLAY-NOTES.md) retain their original source identities and failures. Each receipt records model/runtime/source hashes and actual attempts.

This qualifies those recorded local executions. It does not verify every local server, frontier API, ChatGPT plan, scientific novelty or improved invention. The retained instrument tied the ordinary direct control; no compounding advantage is established.

## Frontier APIs

Use a private copy of `bridge/config.example.json`. Configure only model IDs you can access and explicit capabilities. OpenAI Responses and compatible chat protocols, Anthropic Messages, Gemini, xAI/Mistral compatible endpoints and other supported endpoints retain their protocol differences. Do not infer tool support from a model's name.

Supply credentials through the named local environment variable, never a project, screenshot or command committed to source control. Explicitly authorize external requests and a request/session budget. No key or paid call is needed for offline tests. The release evidence identifies actual live models; an adapter's existence is not a promise of universal provider support.

## ChatGPT subscriptions

Use **Continue with ChatGPT** only when the installed configuration is eligible for the official flow. The HARNESS must receive consent and discover the selected account's available models. Account identity, plan requests and separately billed API usage are distinct. A ChatGPT Pro subscription is not an unlimited API key.

The open-source/local pathway and a paid commercial distribution have different eligibility requirements. Do not configure a paid application as open-source/local to evade commercial approval. The current candidate cannot claim operational paid-edition plan inference without applicable approval and a completed live test. See the [dedicated ChatGPT guide](CHATGPT-PLAN.md) and the [qualification matrix](../evidence/QUALIFICATION-MATRIX.md).

Official references inspected for this implementation: [quickstart](https://developers.openai.com/siwc/quickstart), [open-source token sharing](https://developers.openai.com/siwc/token-sharing-open-source), [inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference), [preview limits](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations). Eligibility and limits may change; inspect the current official guidance for your deployment.

## Codex and manual operation

Codex is a separate supported engineering route, not a substitute credential for arbitrary model APIs. Install the official CLI and authorize the HARNESS ChatGPT connection; review its sandbox and approval settings. This adapter isolates its Codex home and does not reuse an existing CLI login. Do not extract consumer session cookies or automate the ChatGPT interface.

For manual use, create a prompt in the HARNESS, copy it to your independently operated chat service, then import the response with its provider/model/role identity. You decide what leaves the device.

## Français

Les trois catégories automatisées — modèles locaux, API et forfait ChatGPT — ont des autorisations, lieux de traitement et règles de coût distincts. Le parcours manuel reste disponible sans connexion automatique.

**Local dans MY FRONTIER Ω.** Démarrez le connecteur avec le lanceur correspondant à votre système, associez la page membre et choisissez **Détecter les modèles locaux** dans **Intelligence**. Sélectionnez un modèle trouvé et autorisez le test. Si la liste est vide, démarrez un serveur local installé ou suivez le guide officiel du tableau ci-dessus. Vérifiez la licence, la taille du téléchargement, l'empreinte publiée et les besoins en mémoire et en espace disque avant d'installer le modèle. Revenez dans **Intelligence** pour reprendre la même mission. Le test valide une réponse réelle et le format utilisé. Après un redémarrage, choisissez **Reconnecter mon modèle** pour revérifier la sélection conservée dans l'espace privé HARNESS. Le mode hybride utilise l'inférence et les capacités locales autorisées. Autorisez séparément tout accès à un modèle externe.

**Configuration avancée dans HARNESS.** Utilisez une copie privée de `bridge/config.local-only.example.json`, installez le serveur et le modèle séparément, puis indiquez le modèle exact. Désactivez la recherche externe pour un fonctionnement entièrement local. Vérifiez les paramètres réseau du serveur choisi pour éviter le relais vers un service distant.

**API :** configurez le fournisseur, le modèle, ses capacités démontrées, les tarifs et le budget. Les clés restent dans l'environnement privé. Un adaptateur de protocole testé n'est pas une connexion de compte vérifiée.

**ChatGPT :** le bouton de connexion utilise le parcours officiel admissible avec consentement. L'accès au forfait, les quotas et la facturation API sont distincts. Une édition payante exige son autorisation commerciale applicable; ne détournez pas l'admissibilité open source. Consultez la matrice pour savoir ce qui a réellement été vérifié.

**Codex :** installez et authentifiez l'outil officiel et vérifiez son isolation. Ce parcours d'ingénierie est distinct de l'inférence générale. Le parcours manuel n'automatise jamais votre compte.
