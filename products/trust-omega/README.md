# 🌌 TRUST Ω — Independent Inference Evidence (experimental)

**Objective:** Make precise claims about third-party AI computation independently checkable—without confusing a signed receipt, hardware attestation, a partial proof, or a weak inference-policy check with a proof of an exact response.

This package is an **experimental assurance adapter**, not a novel zero-knowledge prover, a cryptographically signed receipt, an audit-certified service, or an achieved commercial product.

## Evidence and real limits (16 November 2026)

Anthropic released [FlashProve](https://www.anthropic.com/research/provable-inference) on 2 November 2026, with a 400B-parameter MoE demonstration. The study's reported batch yielded 110 checked token positions/s, ~18.78 MB proofs in its single-token evaluation, and roughly 70–95× GPU-time overhead relative to native inference. The [released repository](https://github.com/anthropics/FlashProve), which has a proof covering 1,001 token positions in a synthetic full-size example, supports other scopes. Neither metric can be extrapolated into a universal per-token serving cost.

The released implementation is marked **not maintained**, describes important [known limits](https://github.com/anthropics/FlashProve/blob/main/guide/known-limits.md), and reports no independent security audit. Its Lean proofs do not automatically establish security of its C++/CUDA executables. A clipped-gap acceptance is strictly weaker than an exact match. A valid proof does not establish which real model a provider committed, whether its language output is correct, or whether every output token was covered.

## Implemented (scope and limitations)

- [verify.py](verify.py) invokes **upstream** FlashProve's check_proof.py, which invokes the real cp_verify binary. This project does not roll its own cryptography.
- Client must independently pre-pin the model commitment ID, exact-match policy, end token IDs, allowed proof-of-work accounting, SHA-256 hashes for the checking script, compiled verifier and configuration files. The **reviewer v2** anchor also pins all public verification-key file names and bytes. The string naming the independent source does **not** itself authenticate its publisher. Earlier v1 anchors remain compatible but do **not** bind the key directory and must not be represented as complete verifier-input assurance.
- The checker receives a client-constructed request file, a response proof and next-token file, and checks the exact token range, end token and policy. UPSTREAM_EXACT_ACCEPTED means only that the pinned upstream implementation accepted that specific claim under its own documented limitations.
- Failed, malformed, missing, clipped-gap or inconclusive outputs **do not** pass as exact proof. The record is unsigned JSON with evidence hashes and warnings, and is **not a proof in isolation**.
- [Unit tests](../../tests/test_trust_omega.py) test strict classification and the anchor schema locally. The [GitHub Actions job](../../.github/workflows/trust-omega.yml) is intended to compile the pinned upstream verifier and check its *stored synthetic* accepted proof and an incorrect commitment ID. It is not real-model proof generation and does not demonstrate production capability.

## Requirements and usage

Obtain the model commitment and its identity **from outside the untrusted inference endpoint**, ahead of the request. Review [FlashProve's verification manual](https://github.com/anthropics/FlashProve/blob/main/docs/verifying.md). Build its verifier from separately pinned sources as an ordinary (non-root) user. The model provider must cooperate: arbitrary closed API responses cannot be proved by merely passing them through this adapter.

Create a client-controlled JSON anchor, using real independently checked values instead of the placeholders:

~~~json
{
  "schema": "trust-omega-anchor-v2",
  "model_label": "Independently identified quantized integer model",
  "independent_source": "An independently checked, pre-request public commitment",
  "commitment_id": "<64 lowercase hex characters>",
  "policy": "exact-match",
  "end_token_ids": [2],
  "allow_proof_of_work": false,
  "trusted_sha256": {
    "checker_source": "<64 lowercase hex characters>",
    "verifier_binary": "<64 lowercase hex characters>",
    "parameter_file": "<64 lowercase hex characters>",
    "scales_file": "<64 lowercase hex characters>",
    "layout_file": "<64 lowercase hex characters>",
    "public_key_tree": "<64 lowercase hex characters>"
  }
}
~~~

For v2, independently pin `public_key_tree` **before** seeing the provider response. Compute it from the complete verification-key directory: recursively enumerate regular files; reject symlinks; sort each relative POSIX path; make a JSON array of `[relative_path, sha256_file]` pairs serialized with `ensure_ascii=True, separators=(",", ":")`; then SHA-256 the UTF-8 serialized bytes. Missing, extra, renamed or modified key files cause v2 refusal before upstream execution. This commits local verifier inputs, **not** independent model identity, the soundness of the underlying checker, or immunity to concurrent filesystem changes. V1 remains a legacy compatibility mode and cannot support the stronger v2 claim. The v2 engineering correction is in the dependent reviewer PR #416 and remains subject to current exact-head qualification and product-owner integration.

Create the binary request from your **own tokenized prompt and received reply**; require the correct end token. The provider sends proof material under response/proof.bin and response/y.bin. Keep every file required for independent replay.

~~~sh
python3 products/trust-omega/verify.py \
  --anchor anchor.json \
  --checker /trusted/FlashProve/integrations/check_proof.py \
  --verifier /trusted/FlashProve/bin/cp_verify \
  --response /private/response --request /private/request.req \
  --public-key-dir /private/ivk \
  --parameter-file /trusted/config/policy.txt \
  --scales-file /trusted/config/KL.bin \
  --layout-file /trusted/config/layout.txt \
  --prompt-tokens 120 --reply-tokens 40 \
  --next-token 2 --out evidence.json
~~~

This example is syntax, not an independently verified model response. The evidence JSON is an unsigned local observation, not proof of the claimed publisher or time unless third parties establish those facts independently.

## First consequential external acceptance

For a cooperating real inference supplier, prospectively select 1,000 fresh independent challenges, with public/precommitted model identity and reproducible exact-model semantics. Compare the verifier's honest acceptance and refusal under token mutation, wrong commitments, replay and model substitution, measuring **complete** GPU, CPU, memory, bandwidth, verification, engineering, failure and support costs. Compare strongest alternatives: hardware attestation, independent recomputation, and other provable-inference suppliers. Count only precisely covered and individually accepted claims; report all refusals and failures. Then obtain an external customer's independent evaluation and willingness-to-pay evidence.

This experiment **has not been executed**. The project currently does not provide a working inference server, a real provenance registry, audited proof generation, live customer traffic, measured demand or observed revenue. It is an early engineering component for testing whether a defensible commercial trust layer is possible.
