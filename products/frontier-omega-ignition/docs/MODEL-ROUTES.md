# Model execution and qualification

The default installation opens the workbench without making model calls. Configure a route on the machine running IGNITION. Each mission must independently grant permission for that route. The application shares the HARNESS transport and sends no model tools. A model can return JSON proposals. Only explicit operations recognized by the local interpreter can run.

## Local inference

Use a trusted, locally provisioned inference server under your control. A loopback URL binds our client to the local machine. It does not certify the behavior of another program listening there. For llama.cpp use a local weight file and an explicit server alias matching the configured ID. For Ollama use a fully qualified, locally installed tag such as `qwen3:4b`. The adapter rejects cloud-tagged models and checks local model metadata before sending mission data.

| Host setting | Meaning |
| --- | --- |
| `IGNITION_MODEL_PROVIDER` | `llama-cpp` or `ollama`. An unset value selects the unavailable state. |
| `IGNITION_MODEL_ID` | Exact model name returned by the server on completed generation. |
| `IGNITION_MODEL_PORT` | Loopback TCP port. Defaults to 8080 for llama.cpp, 11434 for Ollama. |
| `IGNITION_MODEL_SHA256` | Optional immutable model digest independently obtained by the operator. Receipts label this declaration. The hosted driver measures the downloaded weights. |
| `IGNITION_MODEL_OUTPUT_TOKENS` | Output-token limit for each generation. Default 4096. |
| `IGNITION_MODEL_SCHEMA` | Set to `1` only for a provisioned server/model supporting native JSON schema. Default is `0`. Stores the exact grammar digest per call. |
| `IGNITION_MODEL_STREAM` | Set to `1` to request incremental SSE from a local llama.cpp server. The default `0` uses the existing buffered route. |
| `IGNITION_MODEL_TIMEOUT` | Connection and socket-read timeout in seconds, from 1 through 600. Default 300. A streaming generation can run longer while its connection continues to deliver bytes. |

A mission changing providers requires a new revision. A stopped, incomplete, differently identified or invalid response fails the stage. Receipts preserve the declared and returned model IDs, request and response hashes, elapsed time and token counts if reported. An interrupted request can have used resources. CPU, electricity, maintenance and operator time have real costs even when no billable service is contacted.

## Assisted model exchange

Choose the assisted mode explicitly. Review each pending prompt before transferring it to a separately authorized service. Supply the model and provider label you actually used and send the reviewed JSON answer with the displayed request SHA-256. The identity binds the exact stage, prompt, mission revision and selected route. The software records operator-declared attribution and zero application-dispatched model calls. A supplied reply establishes neither the identity of an underlying checkpoint nor externally verified model usage. Retained responses used in demonstrations are historical evidence.

IGNITION does not read existing account credentials or automate the host's signed-in CLI. The separate HARNESS eligibility and consent gates for its ChatGPT and Codex integrations still apply. Account-integrated plan inference is outside the implemented IGNITION routes.

## Reproduce the hosted CPU trial

From a clean repository checkout on Linux x86-64 with Python 3.12+, download access to the existing HARNESS-pinned llama.cpp release and Hugging Face weights, and at least 2.5 GB for the model plus runtime and working space, run:

```sh
python3 -B products/frontier-omega-ignition/qualify_live.py \
    --work /tmp/fresh-ignition-qualification \
    --output /tmp/fresh-ignition-model-receipt.json
```

Use fresh output paths outside the checkout. The trial loads Qwen3-4B-Instruct-2507 Q4_K_M on CPU, records the measured runtime and model digests, and attempts the predeclared public candidate-register migration using fixed source excerpts and the normal mission controller. The model sees development examples. Its constructor cannot see the confirmation rows. The worker retains private local state and publishes only allowlisted measurements and hashes. The portable verifier and sample invocation run in a separate process after their executable bytes have been matched to the checkout.

The exit status is 0 for a complete verified run, 1 for failed qualification or 2 for an unavailable prerequisite. Passing requires completed calls for discovery, challenge and construction, the selected model returning its exact alias, independently checked frozen cases, and successful operation of the exported program. A deferred recommendation may be reasonable and still fails the experiment's construction endpoint. This trial does not measure current live-feed retrieval, original historical impossibility, financial returns or superiority to a human team.

### Comparison and live-feed arms

The original registered migration trial remains the primary result. Two separate arms run on the same loaded model after it. The direct arm receives the same declared task, public source excerpts, grammar, development examples and output-token allowance in one construction request. Its frozen confirmation cases, conventional comparator and portable verification are identical. The evidence reports both acceptance outcomes, per-arm wall time and reported tokens. Model startup and downloads are shared. Warmth, order effects and unmeasured operating costs limit inference from a single timing comparison.

In the third arm, the same public mission separately permits live release-feed retrieval. The standard controller researches, challenges, selects and, if warranted, builds and verifies. Its receipt preserves current and approximately 35-day earlier observations, exact feed URLs, source response digests, model calls, and the candidate IDs that actually cited an eligible retrieved source. A valid decision to defer remains a research result. It establishes no construction. An empty source response or unused live evidence cannot qualify this integrated investigation.

### Streaming the prospective live-source arm

The earlier buffered live-source trial stopped with a provider connection error at its 600-second socket wait. The original observation still stands. Protocol `ignition/hosted-local/2` registers a separate arm, `live-sources-streaming-sse-v1`, on the same model, weights, schemas, output allowance and loopback server. Primary and direct controls retain their buffered transport. A new hosted run is necessary to determine the Qwen mission outcome under the streaming arm.

Each JSON event must identify the configured model. Only a single text answer that finishes with `stop` and the SSE end marker can proceed to JSON and native-schema validation. The adapter counts output bytes and fragments, discards partial replies, and sends one model request. The socket idle limit, 512 KiB text limit, 4 MiB wire limit and output-token allowance still apply. A stalled request can consume local compute even when the provider supplies no final usage record.

A pinned SmolLM2-135M CPU run exercised both terminal paths. The discovery generation consumed its 96-token allowance and produced no accepted response. A separate routing request with no eligible candidates completed in 0.272 seconds, using 154 input and 16 output tokens. Its validated answer was `{"choice":"abstain"}`. The receipt includes the inputs, expected results, model and runtime digests, per-call provenance and both outcomes. [Actual local streaming measurements](../evidence/local-stream-transport.json)

To repeat those two transport checks, use the runtime and model linked in the receipt. Start `llama-server` on loopback with alias `SmolLM2-135M-Instruct-Q4_K_M`, two CPU threads, context 2048, seed 6144 and temperature 0. From the product directory, pass each observation's `call.stage` and `input` to `LocalProvider("llama-cpp", "SmolLM2-135M-Instruct-Q4_K_M", port, weights_sha256, output_tokens=96, timeout=30, schema_output=True, streaming=True).propose(stage, payload)`. Each original observation used a fresh server. The local unit suite also exercises fragmented HTTP replies that span several socket-read intervals and rejects idle, truncated, oversized and mixed-identity streams.


### First observed local-model failure

On 17 November 2026 the original source `0cbf2757dfbb575561fd486d410c22312888b003` ran actual Qwen3-4B CPU inference. Discovery returned a JSON object after 2,051 input and 1,512 output tokens. Challenge returned an object after 3,772 input and 638 output tokens. Its objection failed the check for a declared candidate ID and a recognized scope. The original receipt stores the digest of that rejection, so the failing field within the pair is unknown. The trial stopped before construction in 926.018 seconds. [GitHub Actions receipt archive](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44151148461/artifacts/14360935462)

Schema-enabled local inference uses the existing HARNESS native grammar and validates the completed JSON separately. The challenge grammar restricts structural IDs and scope values. A new candidate becomes referable only when the response supplies that challenger. The model still determines the substantive objection, proposed solution and selection. Declining and deferring remain valid. Both direct and full construction use the same visible grammar. New source revisions require fresh qualification.
