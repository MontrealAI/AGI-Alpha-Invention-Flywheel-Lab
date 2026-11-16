# INVENT Ω
## One expensive computation in. One independently testable replacement out.

**Implemented research prototype, not demonstrated autonomous profit or novel invention.**

This builds on [UNLOCK Ω](../unlock-omega/README.md) rather than starting a competing
optimizer. It keeps the same `solve(payload)` interface and reuses its known
sorting/two-pointer algorithm **as the incumbent**, not as a discovery. The
improvements here are acceptance integrity, strong-baseline discipline, adaptive
model-backed proposal search, and an independently controlled final evaluation.

### What it does

1. An existing authenticated ChatGPT/Codex CLI proposes executable Python code.
2. A bounded, registered development search evaluates proposals and returns actual
   feedback to the model, retaining the best correct candidate. No mock fallback.
3. A **separate evaluator** runs the frozen candidate against fresh buyer-controlled
   cases, supplied exact expected outputs and the buyer's strong incumbent.
4. It emits `PASS_SCOPED` only if every tested answer agrees, weighted end-to-end
   speed improves, no case materially regresses, and the explicitly supplied
   full-cost economic **scenario** clears the threshold. Otherwise `HOLD`.

No deployment, payments, outreach, production data access or autonomous purchases.
A finite-case pass is not a proof of equivalence, a state-of-the-art result,
a customer acceptance, a bill saving, a sale or a profit claim.

## Quick start

Python 3.10+, Linux amd64 Docker and the official Codex CLI are prerequisites.
The evaluator runs no candidate on the host. Docker absence fails closed. Pull
this public pinned runtime explicitly; this is not paid GPU capacity:

```sh
docker pull python@sha256:a61cbd76a882645de7f91423329fe43a67eed60d7da24f9e5331414bb3618b20
python3 -m unittest discover -s products/invent_omega/tests -v
python3 products/invent_omega/make_demo.py /tmp/invent-demo
python3 products/invent_omega/invent.py verify /tmp/invent-demo \
  /tmp/invent-demo/candidate.py --output /tmp/invent-report.json
```

The demonstration is a **known-algorithm equality control**, not an artificially
slow incumbent. It should not earn a durable speedup. Exit 2 means `HOLD`, not a
crash. An additional `wrong.py` control must fail correctness. The authored test
inputs use independently enumerated exact answers. They are public fixtures,
not genuinely unseen model-discovery evidence.

## Use your own computation

Adapt it into a Python standard-library module with `solve(payload)` returning
one JSON value. The current product supports deterministic, stateless,
JSON-in/JSON-out CPU workloads, not arbitrary services, GPUs, filesystem-heavy
applications, stochastic models or persistent state. Strings, integer versus
boolean values and numeric representations are compared strictly; encode
numerical tolerances explicitly in your independently validated adapter rather
than silently accepting approximate answers.

### Generation machine: development project

- `incumbent.py`: strongest practical available implementation, not a deliberately
  weak baseline. Explain specialist/competent-expert alternatives not included.
- `examples.json`: public examples for the proposing model.
- `brief.txt`: meaningful task, supported domain, desired constraints.
- `heldout.json`: **development cases only in search mode**. Despite the shared
  filename, these are adaptively exposed through feedback and cannot qualify the
  final claim. Format below.
- `contract.json`: prospectively frozen thresholds and economic assumptions.

On your own already-authenticated official CLI, run `codex login status` first.
The product requires a status identifying ChatGPT; it creates no account, copies
no credentials, configures no API key and activates no paid API. Included plan
usage still has limits and economic resource cost. Ambient provider configuration
is ignored, ChatGPT login is forced, known API-key environment variables are
removed, and unsupported configurations fail closed. Provide only source you are
allowed to send to that model provider. Pick a model your account actually has;
the product does not silently impersonate an unavailable frontier model.

```sh
python3 products/invent_omega/invent.py search ./development ./search-output \
  --rounds 3 --model YOUR_AVAILABLE_CODEX_MODEL
# Or generate just one proposal, without running it:
python3 products/invent_omega/invent.py propose ./public-inputs ./proposal
```

`search` uses actual Codex outputs and actual isolated execution; it never
substitutes a developer fixture for a failed model call. A selected candidate is
`SELECTED_NOT_QUALIFIED`. A provider/setup failure is recorded, not retried with
weaker permissions. `--provider-timeout` sets the per-call safety deadline
(default 1,800 seconds, adjustable up to the six-hour platform window); output
is bounded and the process group is terminated on interruption. This is not a
business scale or whole-mission budget. The model identity field records only the requested model
and explicitly leaves actual identity unverified unless independently checked.

**Confidentiality:** exclusion from the prompt is not an OS isolation guarantee.
The adapter reuses the HARNESS exact-root/no-network permission profile and
requires its no-inference OS boundary probe before a model turn. This is still
not a guarantee against every same-account host process or provider-side leak. Keep final evaluation data on a separate machine/account unavailable
to the generator, and transfer only the selected code to the evaluator. Do not
place secrets or private final tests on the generation machine.

### Evaluator machine: independently frozen project

Use the same schema, but supply genuinely fresh `heldout.json` maintained by the
buyer/evaluator, never fed back during development. Freeze the candidate hash
before unveiling these cases. One final qualification attempt per frozen set;
a repair needs fresh cases and a separately disclosed trial.

```json
[
  {"id":"case-a","input":{"values":[1,3,4],"distance":2},"expected":2,"weight":0.5},
  {"id":"case-b","input":{"values":[],"distance":0},"expected":0,"weight":0.25},
  {"id":"case-c","input":{"values":[9,9],"distance":0},"expected":1,"weight":0.25}
]
```

```json
{
  "incumbent_description":"Actual strongest supplied implementation and comparison limits",
  "min_speedup":1.5,
  "max_regression":1.1,
  "repeats":5,
  "case_timeout_seconds":30,
  "annual_jobs":1000000,
  "compute_usd_per_hour":1,
  "annual_other_cost_usd":10000,
  "minimum_annual_net_usd":1000
}
```

The sample dollars are **illustrative user assumptions**, not a price, market
measurement or expected profit. `annual_other_cost_usd` must include generation,
failed attempts, verification, development/amortization, acquisition,
integration, support, maintenance and other relevant incremental obligations.
Compute cost uses parent-measured wall-time only as the stated rate model;
it does not measure CPU/GPU billing, parallel infrastructure utilization,
taxes or customer financial results. Use a representative weighted workload
and sensitivity analysis. Short small-fixture results cannot establish annual
scale or demand.

```sh
python3 products/invent_omega/invent.py verify ./independent-evaluation \
  ./search-output/candidate.py --output ./qualification-new.json
```

The verifier snapshots input bytes before execution. Only one input payload at a
time reaches a disposable worker; expected results, other cases, weights and
thresholds remain in the parent. The parent checks exact answers and measures
elapsed time, including process startup and serialization. Neither a candidate
nor its returned JSON can dictate the timer. Median repeated results are
counterbalanced by alternating which implementation runs first. Startup costs
can dominate short workloads; the report must not be sold as kernel timing.

Containers have no network, no host secrets, a read-only filesystem, unprivileged
UID, dropped capabilities, process/memory/CPU limits, a bounded temporary disk,
bounded output, and an explicit per-case safety deadline. Timeouts force-remove
the container as well as terminating the client. This is defense in depth,
**not certified hostile multi-tenant isolation**: use dedicated hardened evaluator
machines for adversarial workloads. The trusted host, Docker engine, kernel,
pinned image and supplied oracle remain assumptions. A SHA-256 report is not a
signature; independently rerun rather than trusting an unsigned JSON document.

## Qualification and limits

- Unit tests exercise failure paths with clearly labeled controlled runners.
- Hosted workflow runs real Docker equality and wrong-answer controls.
- Real model generation is a separate qualification: a test stub is not inference.
- The present cloud's actual proposal attempt failed the native sandbox
  probe at protocol initialization, before inference; no paid API or sandbox bypass was attempted.
- No customer workload, cash collections, autonomous profitable operation,
  novel algorithm, or superiority over a strong external specialist is established.

The commercially testable offer is a candidate replacement plus independently
replayable evidence, conditional on the buyer's actual feasibility threshold.
The buyer may prefer its existing implementation, expert engineering,
AlphaEvolve/KernelAgent/other agents, or no purchase. Retain `HOLD` when they win.

**Why now:** recent frontier research motivates this experiment; it does not
prove this pipeline was impossible two weeks ago. The mechanism here is
executable proposal → criticism through independent measurements → revision →
fresh acceptance. It implements an enabling product boundary, not an achieved
Goal Genesis frontier expansion. Relevant repository foundations:
[developer mechanisms](../../docs/harness/DEVELOPER_GUIDE.md),
[OUT-EXECUTE / OUT-EVOLVE map](../../docs/harness/OUT_PAPERS.md).
