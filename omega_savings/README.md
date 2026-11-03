# Ω: verified local numerical work and a native commercial experiment

This is a working, deliberately narrow example of the requested buyer/seller
flywheels. It constructs local Python programs for finite linear-response
requests, independently checks results, compares existing means, then recommends
an evidence-backed next action. Its commercial environment models voluntary
purchase, paid expiring acquisition, execution, correction, collection, claims,
tax, cash-constrained expansion and a full365day operating history using the
repository's existing native accounts.

**Current limitation:** development produced correct results but the full
workflow lost to NumPy direct with the same checker. The optional faster interval
instrument also lost. The conditional economic grid assumes equal-work-unit
monetization; it is not measured cloud savings, customer demand or a ready offer.
No novel LU/Woodbury algorithm, special invention advantage or global strategic
optimum is claimed. This is not the general Genesis product described in the
assignment.

## Local installation and a buyer's first useful run

Use Python3.12 or later and a local isolated environment. No OpenAI account,
provider key, model API or network action is needed by the program. Install the
exact declared dependencies through your usual package process:

```bash
python -m pip install -r requirements-commercial010.txt -r requirements-omega-savings.txt
```

The request is JSON with a finite supported outcome, input matrices, right-hand
sides, acceptance tolerances and both external-action permissions set to false.
For a reproducible synthetic example:

```bash
python -c 'import json; from omega_savings.kernel import build_request; print(json.dumps(build_request(11, "rhs", n=32, cases=8)))' > /tmp/omega-request.json
OPENBLAS_NUM_THREADS=1 python -m omega_savings.buyer --request /tmp/omega-request.json --output /tmp/omega-buyer-example
```

Use a fresh output directory. Inspect `REPORT.json`: hypotheses include same
matrix, low-rank updates and neither. The workflow constructs `worker.py`,
executes it locally, validates every output, compares NumPy direct using the same
acceptance, and may recommend declining or using the existing direct solution.
`request.json`, `plan.json` and `result.json` make the decision reviewable. Run
the generated exact-request worker separately:

```bash
python /tmp/omega-buyer-example/worker.py /tmp/omega-buyer-example/request.json
```

The worker refuses a changed request. For another request, construct and check a
new worker. Keep customer data local; the experiment's public examples contain
only authored synthetic data. No natural-language goal interpreter or general
project construction interface is implemented. No automatic account access,
purchase, deployment or outbound communication occurs.

The generated worker takes the request filename as its positional argument;
redirecting JSON to standard input alone is not its CLI contract.

Acceptance uses exact rational residuals and a strict row diagonal-dominance
bound. Matrices outside that verifiable region are declined rather than silently
given a weaker contract. One-time qualification also runs independent NumPy and
SVD diagnostics and records their cost. The optional `interval.py` instrument
requires a supported compiler and directed-rounding binary64 platform; failures
fall back to the exact checker. It is not the native service default.

## Reproduce the registered commercial experiment

Read the experiment's `PREREGISTRATION.md`, `PAPERS.md`, `OPPORTUNITIES.md` and
the exact source receipts before interpreting money. All amounts in machine
records are integer microUSD (USD1 =1,000,000). Time is integer hours.

```bash
OPENBLAS_NUM_THREADS=1 python -m omega_savings.runner register --output /tmp/omega-reproduction --role reproduction
cd /tmp/omega-reproduction/source
OPENBLAS_NUM_THREADS=1 python -m omega_savings.runner operate --output /tmp/omega-reproduction --case positive-adaptive-701 --max-events 6
OPENBLAS_NUM_THREADS=1 python -m omega_savings.runner operate --output /tmp/omega-reproduction --case positive-adaptive-701
OPENBLAS_NUM_THREADS=1 python -m omega_savings.runner audit --output /tmp/omega-reproduction --case positive-adaptive-701
python -m omega_savings.runner summary --output /tmp/omega-reproduction
```

The first operation intentionally pauses. The next command resumes the same
authenticated account; it does not replace initial capital. Running summary
after just this account correctly reports the other59 registered comparisons as
missing. Execute every `cases[].id` from `REGISTRATION.json` for the complete grid.
Use `--cadence-days 7 --variant cadence7` or30 for timing sensitivity, and
`--cost-surcharge 50000000 --variant cost50` or200000000 for additional per-buyer
cost. The published sensitivity grid uses only positive/adverse, adaptive,
seeds701/702. Register each into a fresh output before running any confirmation.

For the complete76-account registered grid, including the four sensitivity
variants, use the checked orchestration scripts. The second command uses each
account's frozen source and independently replays it after completion. A later
invocation resumes unfinished authenticated accounts; it never reseeds them.

```bash
python campaign/omega-saving-contracts-20261103/prepare_comparison.py --output /tmp/omega-complete-reproduction --role reproduction
python campaign/omega-saving-contracts-20261103/execute_comparison.py --output /tmp/omega-complete-reproduction --workers 4
```

Workers are an execution-concurrency choice. Each account keeps its own funds,
history and observations; no account learns from another. Logs retain failed
attempts and `ALL_COMPARISONS.json` identifies every missing or unaudited case.

Run the separate technical comparison from the exact frozen source, labeling
known-input repetitions as reproduction:

```bash
OPENBLAS_NUM_THREADS=1 python -m omega_savings.experiment --output /tmp/omega-technical-reproduction --seeds 701,702,703 --role reproduction
```

`ACCOUNT.json.gz` is a public, independently replayable native export.
`OPERATING.json` is checked against paid rights, policy observations, selection
order, artifacts and every financial effect. `RESULT.json` separates the year
from settlement; cash from profit; tax assessment from payment; and protected
obligations from available capital. Native account files and signed restart
authority under `private/` must never be put in public evidence or a PR.

## Self-support and limits

* `EXECUTE_FROM_FROZEN_SOURCE_REQUIRED`: change directory to the generated source
  directory and use that interpreter module. Do not edit frozen runtime files.
* `FRESH_REGISTERED_OUTPUT_REQUIRED`: choose a fresh directory for a new account;
  use `operate` on the existing directory for recovery.
* `FROZEN_SOURCE_CHANGED` or manifest/artifact mismatch: stop and preserve the
  evidence. A new source needs a separately named experiment; do not erase the
  account or reconstruct private authority from a public export.
* A declined mathematical contract is a result. Inspect the independent reasons,
  select an appropriate existing solver/verification method, or propose a new
  separately tested contract. Do not loosen tolerance solely to obtain a sale.
* Native durable tape/journal limits (64MB) and operating-checkpoint limit (32MB)
  are engineering safeguards, not market ceilings. Very large executions need
  qualified streaming/segmented state before any extrapolated scale claim.

The finite package has no promised continuing updates, personal support or
hidden subscription. Buyer installation/effort and actual host costs are not
proven away. No customer workload or real commercial outcome has been tested.
