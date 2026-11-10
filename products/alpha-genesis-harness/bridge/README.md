# Optional private model connector

The application’s offline/manual workflow opens by double-clicking
`app/index.html`. It needs no Python, installation, account or API key.
This optional connector is for customers who want their own local model or
authorized API access. It requires Python 3.10+ with its standard library for API/local protocols. ChatGPT authorization additionally requires the pinned cryptography package; see the separate ChatGPT guide.
It does not install models, create accounts, activate billing, purchase access
or perform any enterprise transaction.

## Start without a model connection

From the product directory:

```sh
python3 bridge/server.py
```

The connector opens `http://127.0.0.1:8765`. Keep its window open while working.
Close it with Ctrl+C. An occupied port can be changed with `--port 8766`.
`--no-browser` suppresses automatic browser opening. No model is configured and
no remote inference is authorized by this command.

## Configure a model you are authorized to use

Copy `bridge/config.example.json` to a **private location outside the release
directory and source repository**. Never add credentials to this JSON file.
It contains environment variable names, exact model IDs, service endpoints,
limits and user-declared USD token rates.

To connect an already installed local Ollama model, add its exact name to the
Ollama `models` object. For example, replace the placeholder key below with a
name actually installed on your computer:

```json
{
  "YOUR_INSTALLED_MODEL": {
    "input_per_million": 0,
    "output_per_million": 0,
    "json_mode": true,
    "max_output_tokens": 4096,
    "input_token_overhead": 4096
  }
}
```

Zero token rates declare no API token charge for that local configuration.
They do **not** measure or eliminate electricity, hardware, time, maintenance
or other complete costs. Ollama must already be running locally. This package
does not download models or accept their licences on your behalf.

For a remote API, put the exact authorized model ID and **current applicable
maximum input/output rates** in the chosen provider’s `models` object. The
values are USD per million tokens, not cents or prices per token. Include
applicable cache/thinking premiums in the chosen conservative rates; this
connector does not estimate vendor-specific discounts. Then set a deliberate
`session_budget_usd`, change `allow_paid_requests` to `true`, and supply the
credential through the named environment variable using your operating
system’s private process/environment mechanism. Do not paste it into the app,
project, command history, source repository or report. ChatGPT subscriptions are separate from API credentials and billing; use the dedicated authorized ChatGPT connection, not an API preset, for plan access.

Start using that private configuration:

```sh
python3 bridge/server.py --config /absolute/private-config.json
```

The default names are `HARNESS_OPENAI_API_KEY`, `HARNESS_ANTHROPIC_API_KEY`, and
`HARNESS_GEMINI_API_KEY`. They are configurable. They are read only by the local
Python process and are never returned to the browser. Keep your computer and
local user account trusted; a process running as your user can access your
environment. Close the connector when finished.

## Implemented adapters and qualification

| Adapter | Request | Current scope |
|---|---|---|
| OpenAI Responses | `/responses`, `/models` | Native Responses text and declared function calls; no server storage requested |
| OpenAI-compatible | `/chat/completions`, `/models` | Text and declared function calls; compatible local, xAI and Mistral presets |
| Anthropic | `/messages`, `/models` | Messages text and declared tool use; configured API version |
| Google Gemini | `:generateContent`, `:streamGenerateContent`, `/models` | Generate Content text and declared function calls |
| Ollama | `/api/chat`, `/api/tags` | Native loopback text and declared function calls, installed models only |

These adapters have protocol and actual loopback HTTP boundary tests. The
llama.cpp compatible path was additionally exercised with real local CPU
inference using SmolLM2-135M-Instruct Q4_K_M in buffered and streamed modes:
[evidence](../evidence/LOCAL-MODEL-VERIFICATION.json). This tiny model produced
an inaccurate answer in the preserved output. The result qualifies that
connection operation, not answer accuracy or frontier reasoning. No
cloud API provider has authenticated live qualification in this release.

A model list reports availability, not generation entitlement or features.
Only explicitly configured IDs may generate. Each model declares JSON,
streaming and tool-calling capabilities independently. Local validation still
applies to every returned function call or JSON artifact.

Streaming is implemented incrementally as SSE for supported cloud/compatible
protocols and NDJSON for Ollama, with mandatory terminal-success evidence.
`Runtime.generate(data, on_event)` emits text progress. `/api/generate-stream`
returns actual NDJSON progress to an operator/client; ordinary `/api/generate`
remains a buffered compatibility endpoint. Workflow jobs retain phase progress. Tool calls are returned as untrusted structured requests
and never executed by the provider adapter. Unsupported modalities, hosted
tools and vendor-specific extensions are refused rather than assumed.

`max_concurrent_requests` defaults to 2. Models, output/context limits and
stage assignments remain configurable; no silent provider/model fallback or
paid-service activation occurs. The
[provider guide](../docs/PROVIDER-PROTOCOLS.md) describes the precise contracts,
local-only presets, capability declarations and current primary references.

## Cost, retry and cancellation behavior

Before dispatch, a lock atomically reserves the configured attempt count times
the conservative token estimate: one input token per UTF-8 prompt/schema byte plus
the declared input overhead, together with the requested output-token limit.
No concurrent request may consume that reservation. Successful reported
usage is priced at the user-declared rates. Missing usage, malformed replies,
connection failures and failed attempts keep their full attempt reservation
as **unknown actual cost**; they are never treated as free.

`max_attempts` defaults to 1. An explicit setting of 2 or 3 permits retries
after connection/HTTP failures; every attempt is pre-reserved, including
possibly duplicated upstream work. Retries can still incur charges. A used
run ID cannot be dispatched again, including after failure. Cancellation
prevents retries and local result acceptance. It cannot guarantee that an
already sent provider request stops or avoids charges. A completed response
discarded after cancellation still has its reported cost accounted.

This is a **process-session spending guard**, not a vendor billing limit,
financial ledger, complete-cost calculation or guarantee against incorrect
prices/token assumptions. It resets when the connector closes. Provider bills
do not reset. Use provider-side spending controls as well. An observed usage
overrun locks future generation in this process. Unknown complete operating
costs remain unknown. No native enterprise account or journal is created.

## Privacy and network boundary

- The server binds only `127.0.0.1`. Requests must use its exact printed Host.
- API access requires a private random session token; bootstrap needs a custom
  same-origin request header. Foreign Origin/fetch-site values, CORS preflight,
  browser credential forms and arbitrary filesystem paths are rejected.
- Only the four packaged app assets are served. No directory listing, private
  configuration or environment access is exposed.
- Model output and retrieved content are untrusted data. Provider adapters never
  execute returned function calls. The separate workflow engine enforces its
  own bounded artifact tools and permissions; no financial action or unrestricted
  shell is authorized by a model response.
- API/local provider transport uses no telemetry, prompt logs, cookies, proxies or
  redirect following. Known configured credentials are redacted from responses
  and buffered across streaming fragments to prevent split-secret leakage.
  Workflow progress and artifact evidence are recorded within their project.
- Request/response byte limits and HTTP timeouts bound transport resources.

## Attributable current sources

`POST /api/source` retrieves text/HTML/Markdown/JSON from an exact configured
public-host allowlist, with HTTPS only, public DNS address checks and a pinned
TLS connection to the checked address. Private addresses, credentials in URLs,
nonstandard ports, redirects and compressed/oversized responses are rejected.
It returns the exact URL, retrieval timestamp and SHA-256 of the received
bytes. A supplied previous hash produces a byte-change flag. Retrieval time is
not publication time; changed bytes are not automatically a meaningful
capability advance or evidence that a claim is true. Source text is displayed
and carried as data, never instructions.

The source transport was verified with pinned-address fixtures. A real
`https://docs.ollama.com/api/chat` retrieval attempt in the release execution
environment was refused at public-address validation, before HTTP dispatch;
that environment does not provide a qualified direct public route for this
connector. **Live connector retrieval remains unverified.** Official API
documentation was inspected separately through available read-only browsing.

## Original repository integration

When launched from the complete source repository, `/api/mechanism` can invoke
the existing `mechanism_harness/core.py` finite symbolic composer, then its
independent replay checker. The adapter returns that original source hash,
plan, check and candidate capsule; it does not copy or relicense this code.
It has no native financial mutation and no real-world dispatch. This existing
research code and its original limits remain authoritative. The standalone
customer archive intentionally lacks the original research modules; this
optional endpoint then reports `NATIVE_UNAVAILABLE`, while the packaged
browser workflow remains available.

## Reproduce the tests

From the product directory:

```sh
python3 -m unittest discover -s tests -p 'test_bridge.py' -v
```

Automated protocol tests send no external inference requests. They include all five wire formats,
usage accounting, missing credentials, permission refusal, atomic reservations,
retries, malformed responses, duplicate dispatch, cancellation, credential
redaction, Host/Origin/token/CSRF boundaries, source provenance, and private-IP
refusal. The canonical-source adapter test is explicitly skipped when that
source is absent from the standalone archive.

## Primary API references checked for this implementation

Documentation inspection is not authenticated integration testing.

- [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- [OpenAI Models](https://developers.openai.com/api/reference/resources/models/methods/list)
- [Anthropic Messages](https://platform.claude.com/docs/en/api/messages/create)
- [Anthropic API versioning](https://platform.claude.com/docs/en/api/versioning)
- [Anthropic Models](https://platform.claude.com/docs/en/api/models/list)
- [Gemini generateContent](https://ai.google.dev/api/generate-content?hl=en)
- [Ollama Chat](https://docs.ollama.com/api/chat)
- [Ollama model list](https://docs.ollama.com/api/tags)
