# FRONTIER Ω — Living Opportunity Inventory

**The sensor and timing subsystem of the ALPHA Economic Engine.**

One persistent inventory of valuable blocked outcomes, their current technical barriers, proposed acceptance tests, evidence and next research action. This edition extends the canonical reservoir and release radar; it does not introduce a parallel prototype or financial ledger.

## Start

Python 3.10+ on POSIX. The supplied focused source kit needs no packages, paid API, credentials or network for its offline demonstration. Linux/Python 3.13.5 was exercised; other platforms are not independently qualified.

```sh
python3 -m frontier_omega.inventory demo --output ./frontier-demo
```

Use a fresh output directory. Open `frontier-demo/INVENTORY.html` in a browser. `INVENTORY.json` is the machine-readable research queue. The demonstration uses public research dossiers and reported capability observations, not actual customer orders. It creates 12 tasks; repeating the same refresh creates none.

To initialize an ongoing private inventory:

```sh
python3 -m frontier_omega.inventory --root ./frontier-private init
python3 -m frontier_omega.inventory --root ./frontier-private list --limit 5
python3 -m frontier_omega.inventory --root ./frontier-private watch --interval 30
```

The worker receives immutable problem, capability and trial JSON records through `frontier-private/inbox`. Use the canonical schemas in `core.py`; stage writes under a temporary non-JSON filename, then atomically rename to `.json`. No model or arbitrary code is executed by ingesting a record. Stop with Ctrl-C. No worker is installed or left running by the delivered demonstration.

## Optional release sensing, in the same worker

Without `--release-config` there are **zero network calls**. To opt in, save this JSON as `release-sources.json`:

```json
{
  "schema": "frontier-omega/github-release-sources/v1",
  "repositories": [
    {"repository":"ggml-org/llama.cpp","tags":["cost-reduction","long-horizon-agents"]}
  ]
}
```

```sh
python3 -m frontier_omega.inventory --root ./frontier-private watch \
  --interval 30 --release-config release-sources.json --release-every 3600
```

One worker owns inbox ingestion, optional allowlisted release polling, task updates and dashboard refresh. Do not run the older reservoir/release watch commands concurrently against the same root. Release metadata is a reported signal; configured tags are an operator hypothesis about relevance, not measured capability. No unrestricted web crawling or unsolicited outreach occurs. A source error is recorded without inventing a capability. Polling uses public GitHub metadata, not a paid AI API. This task did not establish a live network-polling deployment.

## The twelve problem dossiers

| Outcome | Value mechanism to investigate | Decisive acceptance work |
|---|---|---|
| Compiled cryptographic assurance | Reusable, independently checkable software assurance | Pin theorem, binary and compiler; reject faulty variants |
| Private inference provenance | Verify contracted model computation without disclosing weights | Check proof substitution attacks and full proving overhead |
| Enterprise software modernization | Remove migration cost, delay and operational risk | Frozen compatibility, deployment and rollback tests |
| Agent-operated business procedures | Reduce complete cost of correct repeated business outcomes | Hidden SOP exceptions, policy constraints and recovery |
| Cross-application computer work | Replace brittle integrations with verified application outcomes | State-based acceptance, idempotence and API/RPA comparison |
| Electronic design to bench | Shorten delivery of physically qualified subsystem prototypes | Independent bench tests, failure cases and full BOM costs |
| Verified GPU-kernel production | Reduce cost of accepted application workloads | Numerical parity, full-workload speed and strong library baseline |
| Research reproduction to service | Make research usable as reproducible systems | Frozen artifact reproduction and fresh cases |
| Engineering document to data | Reduce correction work in traceable specification extraction | Field accuracy, provenance and abstention on uncertainty |
| Accessible application workflows | Remove specific usability barriers and repeated repair work | Keyboard and assistive-technology workflow tests |
| Industrial-site screening | Reduce investigation effort for evidence-backed shortlists | Held-out geographic checks and independent domain review |
| Accepted complex software repair | Resolve buyer-relevant defects with outcome-based acceptance | Hidden regression, security and support tests |

All value mechanisms are hypotheses. No price, demand volume, customer, profit or independently verified frontier crossing is invented. Proposed numerical thresholds are example acceptance requirements to negotiate and freeze before an actual experiment, not observed results or universal standards. Physical, legal and production permissions remain separate.

## What makes this an inventory rather than a list

Original problem records remain immutable. `decision_briefs` and `research_queue` live inside the **same** canonical `frontier.sqlite`. Each brief binds an exact problem hash and adds the delivery unit, value driver, buyer question, successor asset, required access and measurable proposed criteria. To import a new version:

```sh
python3 -m frontier_omega.inventory --root ./frontier-private brief --file decision-brief.json
python3 -m frontier_omega.inventory --root ./frontier-private refresh
```

New brief IDs preserve older versions. The latest applicable assessed date is selected; future-dated evidence is not used. Use `list --as-of YYYY-MM-DD` for a read-only historical view. A live refresh cannot rewind its recorded clock. Watch timestamps use UTC.

The planning actions are `DEFINE_TEST`, `MONITOR`, `REPLAY_CANDIDATE`, `COMPARE_INCUMBENT`, `MEASURE_ECONOMICS`, `REVIEW_DEMAND` and `EXPIRED_DEMAND`. Ranking is explicit deterministic research triage, **not a globally optimal portfolio or a monetary ALPHA energy estimate**. Customer-reported requests receive attention but do not acquire verified consent by being ranked.

Every task carries problem/brief/frontier/trial hashes. Changed evidence creates a new task and supersedes an older pending one; identical refreshes/restarts do not duplicate it. An old monitoring task can reopen when a transient signal expires. Acknowledgment is a local workflow note, not proof of completed research:

```sh
python3 -m frontier_omega.inventory --root ./frontier-private ack \
  --task-id TASK_HASH --note "Reviewed; customer terms and full costs still needed."
```

## Five-week economic comparison

The comparison fixes acceptance, terms, protocol, price and reporting scope. It chooses the strongest eligible historical arm at or before the 35-day boundary and the latest matched current arm. Known successful historical alternatives can defeat a supposed new crossing; current alternatives can win on reported cost. Failure, unknown prices, mismatched terms, future trials, expired demand and unsupported evidence remain visible.

These calculations use exact integer modeled microUSD. Reported availability dates, prices, costs and test assertions are not independently established historical access or actual commerce. `REVIEW_DEMAND` is a request to verify the commercial case, not an execution authorization. Every packet has `execution_authorized=false`, `financial_authority=NONE` and unverified buyer consent. The existing ALPHA governor/treasury must perform its own authorization and accounting. This patch does not automatically submit orders to it.

The existing `frontier_omega.executable` module in the repository provides a separate bounded executable replay. The living queue does not claim to run models or those tests automatically. It schedules the **next test**, rather than converting an announcement into a passing benchmark.

## Reproduce and inspect

```sh
python3 -m unittest discover -s tests -p 'test_frontier_omega_inventory.py' -v
python3 -m frontier_omega.inventory demo --output ./another-fresh-demo
```

51 local regression tests pass. Cases include false-crossing defenses, competitor controls, changed price/acceptance/scope, future evidence, immutable brief bindings, duplicate/restart behavior, queue supersession and reactivation, HTML escaping, symlink refusal, one-writer locking, optional radar integration and offline defaults. A separate real-process test admitted an authored event after startup, created a new task and restarted without duplication. Synthetic event execution is not live release verification.

The dashboard was rendered in Chromium at desktop and 390-pixel mobile widths; search and absence of horizontal overflow were tested. This environment blocked direct file navigation, so DOM rendering used the exact generated bytes. Public-source citations are research starting points, not independent demand certification. The owner-controlled hash checks detect alteration but are not third-party attestation against an owner who can rewrite code and all data.

## Scope and preservation

This is an additive source extension stacked on the canonical PR #422/#424 reservoir. The focused source kit contains the exact inherited `core.py`, `releases.py`, initializer and original public seed plus the new inventory, catalog, tests and this guide. The repository retains its other replay/CLI modules; the focused kit does not claim to contain the full ALPHA economic engine.

No private databases, customer records, credentials, model weights or account recovery state belong in published artifacts. The package does not change licensing of inherited repository components or claim a new blanket license. Financial account sources and main-branch history are unchanged. Merge, deployment, actual purchases, paid APIs and customer outreach remain separate authorities.
