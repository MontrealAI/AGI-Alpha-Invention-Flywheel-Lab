# INVENT Ω — algorithm invention with a serious incumbent gate

**A high-cost computation in; one faster, tested substitute out—if and only if it actually wins against the fastest supplied working alternative.** Otherwise the result is **HOLD**, with evidence of what stopped admission.

This product **extends UNLOCK Ω** in `../unlock-omega` (existing [PR #406](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/406)). It adds a separate comparator, prevents synthetic strawman speedups from being called frontier inventions, and optionally models a buyer's year-one value. It is an initial verifiable deliverable, **not** proof of a new algorithm, superior state of the art, live customer demand, or autonomous production-scale profitability.

## Run locally

Python 3.11+; Docker required for default evaluation. On first use Docker may retrieve `python:3.12-alpine`; pin by digest and harden the worker for commercial multitenancy. **No paid model APIs or keys**.

```bash
python3 -m unittest discover -s products/invent-omega/tests -v
python3 products/invent-omega/invent.py demo

# Real buyer-supplied project and independently generated candidate:
python3 products/invent-omega/invent.py verify /path/to/buyer-project /path/to/candidate.py

# Generate one proposal using an already installed/authenticated Codex CLI,
# then independently subject it to the same best-incumbent gate:
python3 products/invent-omega/invent.py invent /path/to/buyer-project
```

For the sample *only*, `--unsafe-local` runs trusted checked-in Python programs without Docker, **never** customer or third-party code. Production requires customer-authorized execution, isolation, pinned images, time and resource limits, no outbound networking, independent evaluation, and data rights. This should be deployed in a dedicated tenant worker, not used as an internet-facing arbitrary-code runner.

## A buyer project

Use the underlying [UNLOCK Ω input contract](../unlock-omega/README.md):
```text
buyer-project/
  reference.py          # reference solve(payload) -> JSON-serializable output
  examples.json         # visible to the proposal agent
  heldout.json          # independent evaluator controls fresh unseen cases
  acceptance.json       # minimum base speedup and maximal regression
  frontier.json         # strongest-incumbent thresholds, optional economics
  incumbents/
    production.py       # strong existing working alternatives; 1–8 required
    specialist.py
```

`frontier.json` example:
```json
{
  "min_best_speedup": 1.2,
  "max_worst_regression": 1.05,
  "economics": {
    "annual_invocations": 2000000,
    "compute_cost_per_hour": 4,
    "year_one_integration_cost": 50000,
    "annual_maintenance_cost": 15000
  }
}
```
The economics fields are a **customer-input scenario**, not a sale or observed cost; the runner uses equal weights for the two-plus performance cases, not an inferred production distribution. A buyer should substitute representative workload frequencies, resource prices and complete incremental costs before making a commercial decision.

## What is *actually* tested?

1. The preexisting UNLOCK verifier checks hidden correctness, reference performance, material regressions and optional large-domain oracle/deadline cases.
2. This verifier runs reference, candidate and **all** supplied incumbents under the same execution mode, case IDs and functional responses. An invalid competitor produces HOLD, never selective removal.
3. On each hidden performance case it compares the candidate against the **fastest** correct incumbent, not an average or conveniently slow reference.
4. Admission requires geometric-mean best-incumbent speedup >= the buyer's preregistered threshold, no material per-case regression, and the base acceptance PASS.
5. The report hashes reference, candidate, heldout input, thresholds and all competitor files. It labels a passed local gate `PASS_LAB`, explicitly **not** external acceptance. A buyer-controlled repeat using the exact source and real hardware is the next gate.

The `demo` intentionally shows the same candidate passing against a weak incumbent and being **rejected when a strong equivalent incumbent is supplied**. Its known sorting/two-pointer algorithm is not novel; benchmark noise near close thresholds needs repeated measured runs and preregistered confidence bounds. Cross-interpreter, compiler, GPU, input-distribution and maintenance effects require their own controlled measurement.

## Commercial hypothesis, not booked business

Start with private AI inference operators, cloud/database providers or specialist computing teams facing a specific expensive bottleneck. Freeze a written buyer-owned acceptance standard before generation; require consent to share protected code with any model provider. Charge for an independently accepted result, perhaps assessment fee plus success fee tied to *realized net* infrastructure savings. Competent specialist optimization, tuned compiler/kernel tools, competing AI systems, human-plus-AI suppliers, no purchase, and in-house alternatives are mandatory commercial comparators. Sales, price willingness, customer authorization, deployments and profit have **not** been established.

Frontier motivation: November 2026's multi-agent algorithm discovery and rigorous falsifier workflows suggest a more efficient proposal–test–refine production route, but this version implements only a **single optional Codex proposal**, not unattended recursive autonomous scaling, and does not claim anything literally impossible in late October.
