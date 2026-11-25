# Browser-local starter qualification

| Path | Evidence | Member release decision |
| --- | --- | --- |
| Browser-managed model | Fixtures exercise per-language availability, progress, fresh readiness challenge and interruption behavior. Production 1.3 testing rejected the Chromium test echo before the ambition was sent. Genuine browser-managed inference on a supported production device remains untested. | Keep the optional path and its eligibility check. |
| Downloadable Qwen2.5 0.5B Instruct | Genuine isolated CPU inference in English and French. Zero of four starter cases advanced the intended work. | NO-GO |
| Downloadable Qwen3.5 0.8B | Genuine isolated CPU inference in English and French. Zero of four starter cases advanced the intended work. Two additional offline checks ran locally and both answers were incorrect. | NO-GO |

On continuation, the browser-managed route carries the exact current ambition, the latest instruction and available prior work. It rejects a request beyond its text limit before creating a session. The original route remains available when the browser reports a supported language and passes the readiness check.

## Browser inference experiment

The experiment ran on Linux x86-64 in Google Chrome for Testing 151.0.7922.34, with GPU inference disabled and one WebAssembly inference thread. The experiment served the public assets on loopback, verified each quantized model's bytes and SHA-256 before loading it, and used a script-only sandbox whose document could not access the parent. For Qwen2.5, the four responses exactly matched the earlier responses from the unmodified upstream runtime in a separate engineering control. This was a credential-free prototype outside the member release.

Both compact models had to produce a credible first step on the same missions. The English and French inventory cases required an intervention that differentiates an actual loss from an intake-record discrepancy while changing one process step. The production-line case required identifying the slowest station and measuring a change in throughput. The broad AI-progress case required an initial productive action consistent with the ambition. The responses misidentified the missing information, invented counts, overlooked the bottleneck or interpreted the broad objective as an exercise in exponentiation. The evaluation was a small engineering screen and supplies no population estimate for general intelligence.

| Measure | Qwen2.5 0.5B Instruct Q4_K_M | Qwen3.5 0.8B Q4_0 |
| --- | ---: | ---: |
| Verified weights | 491,400,032 bytes | 563,036,064 bytes |
| Separate remote weight download over the runner connection | 36.3 s | 16.1 s |
| Loopback weight read and integrity check | 3.0 s | 4.9 s |
| Model initialization after integrity check | 1.8 s | 3.9 s |
| Time to first generated output across four varying prompts | 3.6–8.3 s | 4.6–8.9 s |
| Time to completion, including the prompt evaluation and 144 generated tokens | 17.5–25.4 s | 23.7–30.4 s |

The measurements are single-run observations under shared host load. Download timing varied across independent host and CDN requests. The runtime WebAssembly asset adds 10,838,652 bytes.

A second Qwen3.5 run put the browser context offline **before** forwarding the two new prompts to the initialized model. Both produced substantive but wrong outputs with zero observed network requests during inference. The English task expected `$163` and received `$337`. The French quality check required rejection of a lot with 90 accepted units against a minimum of 92 and received an approval. The peak sum of resident memory within that Chromium process tree was 1,894,014,976 bytes, including shared pages counted in multiple processes. It took 23.0 s for that run to read, verify and initialize the weights served from loopback. This qualifies tab-open offline execution on the tested host. Offline navigation, durable model caching and user-managed downloads remain unqualified.

## Inputs for replay

Use the model bytes and archive identified here. Test a script-only sandbox with the app and asset server on loopback in a fresh browser profile, initialize with a 2,048-token context, one CPU thread, zero GPU layers and seed 712343. Run the same tasks in English and French with temperature zero and a 144-token generation budget. Disable thinking for Qwen3.5. Verify the actual text outputs against the declared task requirements. Test offline inference separately by disabling the browser context network before sending the prompts.

| Input | Frozen source and integrity |
| --- | --- |
| Wllama 4.0.0 | [MIT npm archive](https://registry.npmjs.org/@wllama/wllama/-/wllama-4.0.0.tgz), SHA-512 `7c80d64651cf4fd27e90b428b8bd0f3d25587eb9cdcf75a429103642f2425be81df05939d0c35f7b5b63fe97abec41bad0243077c805bda2bf0e81c7cedb6724` |
| Runtime bytes | `package/esm/wasm/wllama.wasm`, SHA-256 `b012436a101ede8c877f2d26644c3181429d4fb8da4fd90c356110d86bfd74a6` |
| Worker compatibility | Chromium rejected Blob module workers in the opaque frame and accepted classic Blob workers. For the experiment, replace the single `return new Worker(workerURL, { type: "module" });` in the archive's `package/esm/index.js` with `return new Worker(workerURL);`. Resulting SHA-256 `8ead0be629402346fae8e6e17def8336ff588fa8bcc9b479f15714595caf76f6`. |
| Qwen2.5 0.5B Instruct Q4_K_M | [Apache-2.0 quantized model](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/9217f5db79a29953eb74d5343926648285ec7e67/qwen2.5-0.5b-instruct-q4_k_m.gguf?download=true), SHA-256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db` |
| Qwen3.5 0.8B Q4_0 | [Apache-2.0 quantized model](https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF/resolve/004fd086eccea9f7cf867aa07ba328773beef81d/Qwen3.5-0.8B-Q4_0.gguf?download=true), SHA-256 `57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf` |

For browser-managed inference, [Chrome's documented eligibility](https://developer.chrome.com/docs/ai/prompt-api#review_the_hardware_requirements) includes 22 GB free on the browser profile volume and either more than 4 GB GPU memory or at least 16 GB RAM with four CPU cores. The qualified headless negative control is distinct from operation on such a device.
