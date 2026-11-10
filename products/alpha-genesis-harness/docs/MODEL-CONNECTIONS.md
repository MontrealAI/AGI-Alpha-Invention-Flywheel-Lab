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

Start the optional connector, then use **Local** in the Intelligence workspace to discover and connect an installed server/model. Declare the exact model ID and demonstrated capabilities. Advanced operators can instead use a private copy of `bridge/config.local-only.example.json`. The supported compatibility configurations cover Ollama, LM Studio, llama.cpp, vLLM and MLX servers. They do not install the servers or model weights. Follow [provider protocols](PROVIDER-PROTOCOLS.md) for supported fields and the difference between compatibility and live verification.

Local-only configuration denies remote provider access. Public-source retrieval must also remain disabled for a fully local workflow. The HARNESS cannot certify another local program's network behavior; use OS-level isolation if your use requires that separate guarantee. Local token rates of zero mean no declared API token charge, not free hardware or electricity.

## Executed local qualification in this candidate

The [final 0.3 source receipt](../evidence/live-local-workflows-v0.3.json) records actual Linux CPU Qwen3-1.7B inference through llama.cpp. The single builder exhausted three calls with invalid input-field artifacts; the aggregate run is **FAIL**. The builder–critic path passed in two calls, exported an independently checked instrument returning 34 for x=17 and reused it to return 82 for x=41. The [earlier 0.3 both-policy success](../evidence/live-local-workflows-v0.3-before-final-integration.json) and [0.2 live receipt](../evidence/live-local-workflows.json) retain their original source identities. Each receipt records model/runtime/source hashes and the actual attempts.

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

**Local :** utilisez une copie privée de `bridge/config.local-only.example.json`, installez le serveur et le modèle séparément, puis indiquez le modèle exact. Le mode local doit également désactiver la recherche externe. Un test avec réponses préparées n'est pas une inférence locale réelle.

**API :** configurez le fournisseur, le modèle, ses capacités démontrées, les tarifs et le budget. Les clés restent dans l'environnement privé. Un adaptateur de protocole testé n'est pas une connexion de compte vérifiée.

**ChatGPT :** le bouton de connexion utilise le parcours officiel admissible avec consentement. L'accès au forfait, les quotas et la facturation API sont distincts. Une édition payante exige son autorisation commerciale applicable; ne détournez pas l'admissibilité open source. Consultez la matrice pour savoir ce qui a réellement été vérifié.

**Codex :** installez et authentifiez l'outil officiel et vérifiez son isolation. Ce parcours d'ingénierie est distinct de l'inférence générale. Le parcours manuel n'automatise jamais votre compte.
