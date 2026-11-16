# UNLOCK Ω — make a previously unaffordable computation run

**A single product, not an agent platform:** give us one expensive computation, its acceptance tests and the hardware/budget threshold it must meet. Receive a drop-in replacement (`candidate.py`) only if it reproduces the required behavior on held-out cases *and* crosses the preregistered performance gate. Otherwise the result is **HOLD**. Technical success is not a commercial sale.

## Try it

Requires Python 3.10+ and Docker. By default all customer-supplied code runs in a restricted Docker container; no hidden host-side execution or API billing is included.

```bash
python3 products/unlock-omega/unlock.py demo
python3 -m unittest discover -s products/unlock-omega/tests -v
```

The `demo` compares a deliberately slow quadratic implementation of counting nearby pairs with a known sorting/two-pointer implementation. Both use only the Python standard library. It demonstrates the *end-to-end acceptance gate*, **not** an original algorithm, previously unattainable mathematical result, an advantage over a competent specialist, or customer demand. `--unsafe-local` bypasses Docker only for trusted checked-in demonstration code on machines without Docker; never use it with customer/untrusted code.

## Bring a real problem

Create a project directory:

- `reference.py`: trusted baseline algorithm with `solve(payload)`, returning a JSON-serializable result.
- `examples.json`: public examples that the proposer may read.
- `heldout.json`: array of `{"id":"...","input":{...},"kind":"correctness"}` or `kind: "performance"`; at least one correctness and two performance cases. **The proposing agent never sees this file.** Store it outside the generation workspace; for real commercial acceptance, an independent evaluator should control fresh held-out cases.
- `acceptance.json`: `{"min_speedup":3.0,"max_perf_regression":1.10}`. Specify target hardware, business deadline and strong incumbent separately in a prospectively signed customer acceptance contract. These two threshold fields are for the bounded software check.

Then execute:

```bash
python3 products/unlock-omega/unlock.py verify /path/to/project /path/to/candidate.py
python3 products/unlock-omega/unlock.py invent /path/to/project
```

`invent` uses an **already installed, authenticated Codex CLI** (`codex exec`) to propose one implementation in a temporary workspace that contains only the reference, examples and acceptance. It does **not** automatically connect to ChatGPT Pro, create API keys or silently activate a paid API. Running it explicitly authorizes that local CLI session to process the provided material according to the operator's existing model-provider terms. It promotes no candidate without executing the same acceptance gate. If Codex is absent, it fails with an explicit error; there is no fake AI fallback. For code or data with confidentiality restrictions, get the source owner's permission before sending it to a model provider.

### Output

The JSON report pins SHA-256 hashes of the reference, candidate, held-out cases and acceptance fields; per-case functional comparison, per-case baseline/candidate latency, geometric-mean speedup and performance regression gate. Exact JSON result comparison is mandatory; this **does not prove full semantic equivalence on all possible inputs**. Reports produced on a single local machine are not independently audited. The Docker sandbox is a defense-in-depth baseline, not a certification for hostile multi-tenant use; production needs hardened dedicated workers, pinned container digests and customer security review.

### What buyers would pay for

The initial privately sold service is **one verified computational feasibility breakthrough** for an AI infrastructure or engineering customer that already spends materially on a bottleneck. Potential paid-pilot terms to test—not actual price acceptance—are a five-figure technical assessment and a larger success fee based on independently measured net savings or newly enabled workload. No government contracting. Run a buyer-controlled baseline against (a) current production code, (b) specialist alternatives / `torch.compile` / PyTorch KernelAgent or other strong incumbent methods when applicable, and (c) this system on **identical hardware and workload distributions** before claiming advantage. Include engineering, migration, inference, verification and maintenance costs.

The **frontier hypothesis** is that 2026 coding agents can now search over algorithms and implementation strategies well enough to cross previously unavailable business feasibility thresholds, sometimes beyond competent standard engineering routes. The recent Singularity-Bench and Evolving Agent Teams work justify testing that hypothesis, **not asserting automatic novelty or that a capability was literally impossible on November 15**. See:

- https://arxiv.org/abs/2611.16591 — Singularity-Bench (12 Nov 2026), constrained end-to-end AI-engineering tasks, not unrestricted invention.
- https://arxiv.org/abs/2610.36848 — Evolving Agent Teams (27 Oct 2026), reported production-kernel improvement against strong baselines.
- https://pytorch.org/blog/kernelagent-hardware-guided-gpu-kernel-optimization-via-multi-agent-orchestration/ — established incumbent for GPU kernel tuning.

### Stop/go for a commercial flagship

**Current state:** tested local sample; untested Docker isolation in this execution environment; Codex proposal not exercised here; no real customer workload, external acceptance, collected payment or evidence of original research. The next gate is one voluntarily supplied private-sector bottleneck, frozen independent acceptance and meaningful dollar-denominated feasibility threshold. A synthetic speedup over a deliberately slow reference must never be marketed as a frontier breakthrough.

