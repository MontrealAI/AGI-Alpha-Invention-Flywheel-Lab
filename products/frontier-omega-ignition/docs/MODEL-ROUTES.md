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
| `IGNITION_MODEL_TIMEOUT` | Per-request transport timeout in seconds, from 1 through 600. Default 300. |

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
