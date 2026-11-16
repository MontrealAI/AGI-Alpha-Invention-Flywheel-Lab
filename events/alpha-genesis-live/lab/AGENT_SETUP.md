# Technical demo modes and execution contract

## The modes (never confuse them)

**Browser mode:** Double-click `proof_lab.html`, run the exact-text comparison, paste model response if available, and export a check record. The browser never calls a model. It does not need internet, a GitHub account, wallet, personal data or API key. It uses original, event-specific code, separate from the existing MONTREAL.AI Alpha Agent comparator. Browser security controls differ, so direct file-open needs a real-device preflight before paid delivery.

**Manual live AI mode:** In the browser lab, copy the prompt containing the synthetic CSVs into a provider account you are authorized to use; the provider may bill or log the prompt according to your own account settings. Paste the unedited JSON result; the independent checker examines the result. This illustrates AI-assisted analysis, but the browser itself is not an autonomous tool-using agent.

**Actual tool-using local agent mode (optional):** A locally installed Ollama model selects the allowed `compare_catalogs` tool; Node executes the read-only deterministic tool; the model receives the returned evidence and produces its structured findings; the verifier checks them and a JSON receipt is saved. This is bounded model-mediated tool use, not general autonomy. Requires *existing* local Ollama running at `http://127.0.0.1:11434` and Node.js 22+. Install/pull and qualify your own appropriate local model before announcing this route. No new software is installed by the script.

```
node 03_DEMO/agent_runner.mjs --mode ollama --model YOUR_ALREADY_INSTALLED_MODEL --output 06_QA/live_model_receipt.json
```

This command may fail (bad model output, unavailable server, timeout or policy refusal). It makes exactly two local model requests: tool-choice JSON and evidence-grounded synthesis JSON. An incorrect final claim produces `CHECKS_FAIL` rather than silent acceptance. A malformed tool choice or model output **fails closed**.

**Scripted rehearsals (NO AI model):**

```
node 03_DEMO/agent_runner.mjs --mode fixture-wrong --output 06_QA/rehearsal_wrong_receipt.json
node 03_DEMO/agent_runner.mjs --mode fixture-reference --output 06_QA/rehearsal_reference_receipt.json
```

These verify plumbing and falsification. **Do not use them as evidence that a live model worked.**

## Security and input limits

- Only read-only local CSV analysis; no filesystem modifications except an explicitly named output receipt.
- The local agent connector targets **127.0.0.1**; it does not read shell/model credentials or contact arbitrary URLs. It is a simple educational runner, not a sandbox for malicious local models.
- Browser checker input limit: 300,000 characters, 1,500 rows, 32 columns and 4,096 characters per cell; identifiers compared as exact case-sensitive text.
- **Duplicate SKU identifiers cause `BLOCKED`** in this supplementary tool. The separately developed original Alpha Agent engine has different multi-pair duplicate semantics; do not claim equivalence.
- Different headers are explicitly reported as unexamined. No inferred normalization or authoritative source selection is performed.
- CSV/JSON receipts may contain source text; use only synthetic/approved content and protect downloaded files if using non-synthetic data privately.
- The model's free-text summary is not mechanically verified; only `unmatchedLeft`, `unmatchedRight`, and `conflicts[{sku,field}]` are checked. Human authority stays `null`.

## Authoritative external project links

- Existing AGI Alpha Agent tool: https://montrealai.github.io/AGI-Alpha-Agent-v0/try/
- Existing source documentation: https://github.com/MontrealAI/AGI-Alpha-Agent-v0/tree/main/examples/ti-guide
- Proof/acceptance architecture: https://github.com/MontrealAI/proof-gradient
- Bounded signed analytical work: https://github.com/MontrealAI/AGI-Alpha-Node-v0

The external sites may be updated or unavailable and were **not** bundled. The workshop's core exercise works without them.
