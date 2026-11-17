# 🌌♾️ FRONTIER Ω — Living Opportunity Inventory

**Capture the exponential by tracking valuable unsolved buyer problems, not model releases.**

As of **16 November 2026**, this seed contains **56 distinct buyer-problem hypotheses**, six candidate engine families (including DISCOVER Ω) and **12 dated primary-source signals**. Established at this stage: **zero independently verified five-week threshold crossings, zero customer-accepted paid outcomes and zero proven autonomously operating companies**.

This is a supporting operational discovery instrument for the existing AGI ALPHA flagship—not a new Blue Sky breakthrough, model leaderboard, market-size estimate or revenue system.

Interactive viewer: https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega.html (available after PR merge and GitHub Pages publication).

## Five proposed new-frontier engines, plus a recurring-operations wedge

| Engine | Buyer-valued outcome | Recent trigger | Critical obstacle |
| --- | --- | --- | --- |
| MIGRATE Ω | Verified replacement or upgrade of critical software | Fable 5.2 on 9 Nov | Complete parity, code access, expert alternatives |
| PROVE Ω | Machine-checkable software property assurance | AlphaProof Code on 10 Nov | Specification assurance, research-only methodology |
| OPERATE Ω | Completed and reconciled enterprise administrative work | Terra on 26 Oct; Hydrogen on 12 Nov | Permissions, independent acceptance, entrenched competitors |
| TRUST Ω | Cryptographic receipts for covered inference | FlashProve on 2 Nov | 70–95x inference cost, narrow support, unproven buyer demand |
| ENGINEER Ω | Qualified CAD, simulation and engineering deliverables | Physical engineering updates on 3 Nov | Physical validity, professional approvals and expensive failures |
| DISCOVER Ω | Reproducible scientific algorithms, research instruments and licensed computational methods | Fable 5.2 theoretical-physics and mathematical formalization demonstrations on 9 Nov | Genuine novelty, independent replication, buyer demand and rights |

A new model release is not proof that the complete business was impossible on October 12. The testable event is a **matched task-specific technical and economic crossing** with a documented historical baseline. A new result without a pre-period baseline can establish present feasibility but cannot establish a five-week newly feasible crossing.

## Inventory contents

The canonical data files are **frontier_omega/opportunities.json** (56 cases) and **frontier_omega/signals.json** (12 dated signals). Every opportunity records the buyer, blocked outcome, required deliverable, independent acceptance test, strongest complete alternative, first executable probe, frontier signal and explicit price/test threshold hypotheses. Price tests are **not** actual price quotes, orders, market observations or profits. Initial scores are ordinal editorial priors, not probabilities or valuation models.

The Python standard-library-only module **frontier_omega/__main__.py** validates joins and evidence gates, ranks experiments, exports the 56 opportunities as CSV, assesses reported historical/current crossings, and watches a bounded set of public official release indexes. **tests/test_frontier_omega.py** contains deterministic negative tests against false promotion and incomplete cost accounting. **.github/workflows/frontier-omega.yml** runs those tests for PRs and, after merge, schedules a read-only daily watch. The repository's existing local [Frontier Monitor](../products/alpha-genesis-harness/docs/FRONTIER-MONITOR.md) remains available for authorization-gated monitoring and replay.

## Reproduce without paid model APIs

From the repository root (Python 3.10+, no third-party packages):

~~~sh
python3 -m frontier_omega validate
python3 -m frontier_omega rank --limit 15
python3 -m frontier_omega rank --json --limit 48
python3 -m frontier_omega export-csv > /tmp/frontier-omega.csv
python3 -m unittest discover -s tests -p test_frontier_omega.py -v
~~~

Assess separately obtained benchmark evidence with:

~~~sh
python3 -m frontier_omega assess --evidence /path/to/matched-evaluations.json
~~~

The evidence JSON must be an array. Each record needs an opportunity_id, explicit synthetic flag, frozen 64-character task-suite SHA256, same_frozen_suite=true, baseline (before 2026-10-12) and current (2026-10-12 or later) runs. Both runs require equal case counts, acceptance numerators, p95 elapsed hours and **all 12 full-lifecycle cost categories**, including model, software, human labor, verification, retries, acquisition, onboarding, maintenance, overhead, financing, refunds/disputes and obligations. The thresholds are stated in each opportunity record. Synthetic fixtures cannot promote any stage.

An event may also report an independent-verifier URL and payment/acceptance fields. **The CLI does not authenticate these URLs, signatures, buyer identities, actual payment, permission or residual liabilities.** Even passing reports remain labeled **AUDIT_REQUIRED** and **UNVERIFIED_EXTERNALLY**; independent receipts and existing native enterprise accounting are mandatory for any stronger public commercial claim.

Manually run the official-source fingerprint watcher:

~~~sh
python3 -m frontier_omega watch --state /tmp/frontier-last.json --out /tmp/frontier-observations.json
~~~

The watcher fetches only fixed HTTPS provider indexes (OpenAI, Anthropic, Google DeepMind), within a bounded response size and timeout, without secrets or billable model calls. Failure preserves the previous known hash. A changed HTML digest triggers **SOURCE_CHANGE_ONLY** review, not automatic evidence upgrade. Scheduled monitoring begins only after merge and depends on GitHub Actions permissions, network availability and official page access. This does **not** claim comprehensive discovery of every new model or frontier paper.

## First three materially different experiments

| ID | Opportunity | Decisive experiment | Competent alternatives |
| --- | --- | --- | --- |
| O002 | Python-to-Rust critical-service migration | Preserve behavior on a frozen test corpus, compare total costs and p95 elapsed time | Experienced Rust team, established migration tools and AI-assisted coding |
| O019 | Freight overbilling recovery | Independently confirm recoverable discrepancies in a consented historical invoice corpus | Freight-audit firm, incumbent audit software and existing AP staff |
| O010 | Formal assurance of an auth library | Produce an approved spec and reproducible machine proof, reject seeded mutants | Formal-methods specialist, mature scanners and external security audit |

First commercial recommendation: **build the scoped O002 delivery artifact with an executable acceptance contract**. If a credible pre-October-12 baseline is not available, report newly measured feasibility—not false historical impossibility. Then compare demand and complete cost against a competent complete alternative. Actual outreach, customer access, pricing commitments, financial transactions or paid tools require their own authority.

## Gates required for a company rather than a catalogue

**Observe → Measure → Verify → Sell → Deliver → Collect → Reinvest → Retest.**

A source signal reopens a problem. Measured matched tests can show a technical crossing. Real buyer choice, accepted scope, complete costs and actual collections establish commerce. Strict 100% autonomy needs actual unattended execution of production, recovery, checking and customer delivery; human help remains labeled and costed. A compounding claim requires a fresh successor that demonstrably benefits from an acquired asset over a strong equal-resource comparator.

Revenue, ARR, profit, unrestricted cash, valuation and frontier-expanding capability are different measures. For illustration only, $100 million ARR at a 10x revenue multiple equals $1 billion enterprise value; neither input is an achieved result or forecast.

**Current result:** a source-bound and inspectable 48-opportunity inventory, ranking tool, technical-crossing assessment logic, regression suite and conditional daily source monitor; no paid autonomous outcome is claimed.
