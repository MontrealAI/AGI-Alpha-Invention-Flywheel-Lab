# Provider protocols and local inference

The connector implements API protocols; a working fixture is not a live-provider qualification. No cloud model credentials or paid inference were used in these protocol tests. The llama.cpp-compatible local path also completed actual SmolLM2-135M-Instruct CPU inference in both buffered and streamed modes; see [the exact receipt](../evidence/LOCAL-MODEL-VERIFICATION.json). The preserved model output includes an inaccurate answer, so this is connection-operation evidence, not answer-quality qualification. No model ID is hardcoded as available. Discover the models on the selected service, then explicitly configure the model you are entitled to use.

| Connection | Configuration `kind` | Requests | Scope |
|---|---|---|---|
| OpenAI API | `responses` | `/models`, `/responses` | Native Responses, text and declared function calls; `store:false` |
| OpenAI-compatible, xAI, Mistral | `openai` | `/models`, `/chat/completions` | Compatible Chat Completions subset; model/provider fields still differ |
| Anthropic | `anthropic` | `/models`, `/messages` | Text and declared tool use; Messages SSE |
| Google Gemini | `gemini` | `/models`, `:generateContent`, `:streamGenerateContent?alt=sse` | Generate Content protocol; text and function declarations |
| Ollama | `ollama` | `/api/tags`, `/api/chat` | Loopback only; native NDJSON streaming |
| LM Studio | `openai` | `/models`, `/chat/completions` | Loopback compatible server, typically port 1234 |
| llama.cpp | `openai` | `/models`, `/chat/completions` | Loopback compatible server; configured local model |
| vLLM | `openai` | `/models`, `/chat/completions` | Local compatible server; model needs suitable chat/template/tool configuration |
| MLX LM | `openai` | `/models`, `/chat/completions` | Local Apple-silicon server; feature availability depends on its installed version/model |

ChatGPT-plan and Codex access are separate integrations and usage classes. This API configuration never substitutes API billing for a ChatGPT subscription.

## Configure only demonstrated model features

Copy `bridge/config.local-only.example.json` outside the release directory. Keep the provider you actually run. Discover installed IDs using Intelligence Center, and add the exact model name to that provider's `models` map:

```json
{
  "YOUR_INSTALLED_MODEL_ID": {
    "input_per_million": 0,
    "output_per_million": 0,
    "max_output_tokens": 2048,
    "input_token_overhead": 4096,
    "context_window": 32768,
    "json_mode": false,
    "streaming": true,
    "tool_calling": false
  }
}
```

The numeric values above are example configuration, not hardware/model specifications. Use the actual context and generation limits of your installed model. Set `json_mode` and `tool_calling` true only when the selected server/model supports them and a completed request has exercised them. A provider's model list does not establish these capabilities.

`local_only:true` rejects configurations containing remote providers, disables source retrieval, and never falls back to a cloud provider. The connector accesses loopback servers; the separately installed inference server is responsible for its own network behavior. Pre-download model weights and disable external access/firewall egress for an offline inference environment. The HARNESS does not download weights, contact a model hub during generation, or require Docker. Local zero token rates mean no API token charge, not free hardware/electricity/maintenance.

For remote API use, explicitly authorize `allow_paid_requests`, configure a deliberate spending budget and current maximum applicable input/output rates, and use a private environment variable for the credential. `config.example.json` contains empty, disabled model maps and endpoint presets; it enables no paid request by itself. xAI/Mistral presets use their compatible Chat Completions interfaces and `max_tokens`; native Responses is separately configurable. Never infer a universal feature set from the shared protocol.

## Requests, streaming and tools

`Runtime.generate(data, on_event=None)`, `/api/generate` and `/api/generate-stream` accept the existing text fields plus `stream`, `tools` and `required_capabilities`. Function declarations use `name`, `description`, and an object JSON schema under `parameters`. The adapter converts these to each provider's native shape and returns normalized `tool_calls` with decoded object arguments. Returned calls are untrusted requests, never execution permission. Unknown/undeclared functions and invalid argument JSON are refused. The workflow/tool layer must validate arguments and the applicable action permission before execution.

Streaming reads SSE or Ollama NDJSON incrementally; callback events carry `text_delta`. The `/api/generate-stream` endpoint emits NDJSON progress and a final result/error; `/api/generate` retains its buffered HTTP contract. A terminal success event is required. Truncation, malformed output, provider error and incomplete streams are not accepted as completed results. Reasoning/thinking blocks are not exposed as user text. Partial progress is not verification. Streamed tool arguments are accumulated and parsed only after completion. Stream transport bounds total response bytes, honors timeouts, and checks cancellation between reads. A stalled socket may remain until the configured read timeout; stopping the local stream cannot recall already incurred provider usage.

Ordinary buffered requests remain available. Missing usage retains the conservative reservation. Schemas as well as prompt bytes are included in the input estimate. Provider-reported usage is priced at the customer-supplied rates; an overrun locks further generation. Each retry reserves another attempt; no provider change or model fallback occurs. A local progress-observer failure after complete usage does not charge the same request twice.

`stage_routes` maps a stage to exactly `{ "provider": "id", "model": "id" }`. `Runtime.route(stage, required_capabilities)` rejects unconfigured or unsupported assignments; it does not pick an unapproved provider. Models have independent capability maps. Context overflow fails before dispatch using a conservative UTF-8-byte estimate plus declared overhead; automatic silent truncation is not performed.

## Français

Le fichier `bridge/config.local-only.example.json` permet de connecter un serveur local déjà installé, sans clé d'API externe. Indiquez le nom exact du modèle disponible et ses limites réelles. `local_only:true` refuse les fournisseurs distants et désactive la récupération de sources externes. Le serveur d'inférence installé séparément doit aussi être configuré pour fonctionner hors ligne.

Les capacités JSON, diffusion progressive et appels de fonctions sont déclarées pour chaque modèle. Une liste de modèles ne prouve pas leur fonctionnement. Les appels de fonctions retournés sont des propositions à contrôler; ils ne donnent aucune autorisation d'exécuter du code. Les flux incomplets échouent. Les coûts des requêtes envoyées restent comptabilisés même après une interruption. Aucun changement silencieux de fournisseur ou basculement vers un service payant n'est permis.

## Official protocol references consulted

Checked during this implementation. Documentation is not an authenticated integration test.

- https://developers.openai.com/api/docs/guides/migrate-to-responses
- https://developers.openai.com/api/docs/guides/streaming-responses
- https://platform.claude.com/docs/en/build-with-claude/streaming
- https://ai.google.dev/api/generate-content?hl=en
- https://docs.ollama.com/api/streaming
- https://lmstudio.ai/docs/developer/openai-compat
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://docs.vllm.ai/en/stable/serving/online_serving/openai_compatible_server/
- https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/SERVER.md
- https://docs.x.ai/developers/rest-api-reference/inference/chat-completions
- https://docs.mistral.ai/api
