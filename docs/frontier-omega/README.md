# 🌌♾️ FRONTIER Ω — Capturing the Exponential

**Working opportunity reservoir · implementation candidate v1 (16 November 2026)**

The first production dependency for the self-propelling ALPHA Economic Engine is **an inventory of valuable blocked outcomes that can be retested whenever the accessible AI frontier changes**. This package is an independently runnable, stdlib-only, nonfinancial sensor. It does not claim that a source announcement proves feasibility, that public need proves buyer consent, or that a modeled crossing produces cash.

## Use the inventory now

Requires Python 3.10+ on a POSIX system, from the repository root. No model API, purchased service, payment account or installation dependencies.

~~~sh
python3 -m frontier_omega --root ./frontier-omega-private seed \
  --file examples/frontier-omega/public-opportunities-20261116.json

python3 -m frontier_omega --root ./frontier-omega-private report
python3 -m frontier_omega --root ./frontier-omega-private dashboard
python3 -m frontier_omega --root ./frontier-omega-private list problems
python3 -m frontier_omega --root ./frontier-omega-private list triggers
python3 -m frontier_omega --root ./frontier-omega-private audit

python3 -m unittest discover -s tests -p 'test_frontier_omega.py' -v
~~~


The `dashboard` command writes an offline, responsive, searchable **FRONTIER-OMEGA.html** inside the private state folder. Open it locally in a browser to inspect blockers, test requirements, independent alternatives, source links, and pending capability matches. It loads no external fonts, scripts or assets. **Never publish a customer-populated dashboard.**

The seed contains **six original problem dossiers** and **five public capability observations**, linked to source publications. Every problem identifies a potential beneficiary, desired outcome, independently testable acceptance criterion, binding obstacle, capability tags, strongest plausible complete routes, no-purchase alternative, next discriminating experiment, and demand status. There are **zero verified customer purchase commitments or complete-cost valuations** in this seed.

The records are **hypotheses** supported by public technical publications and industry evidence, not claimed actual customer contracts or historical proofs that a particular commercial outcome was impossible five weeks ago.

## The six starting problems

| Problem | What must become independently deliverable? | Missing means to investigate |
| --- | --- | --- |
| Compiled cryptographic assurance | Scoped, machine-checked guarantees on a pinned real binary | Human-guided specification, prover construction and trusted-checker cost |
| Private inference provenance | Exact-model inference proofs with portable verification receipts | Proof throughput, model identity, verifier assurance and complete economics |
| Enterprise modernization | Regression-checked system migrations with rollback | Long-horizon dependency reasoning and recoverable construction |
| Real business SOPs | Independently checked agentic process outcomes | Reliable tool use under exceptions, policies and domain-specific criteria |
| Computer-use workcells | Correct end-to-end cross-application changes | State verification, replay safety, integration friction and delivery cost |
| Electronics design-to-bench | Independently measured electronic design output | Physical prototyping, fault handling, fabrication and bench verification |

**Public references:** [DeepMind / AlphaProof Code](https://deepmind.google/blog/introducing-alphaproof-code/), [Anthropic / FlashProve](https://www.anthropic.com/research/provable-inference), [Anthropic / Fable 5.2](https://www.anthropic.com/claude-fable-and-mythos-5-2), [OpenAI / model releases](https://help.openai.com/en/articles/9624314-model-release-notes), [Amazon / SOP-Bench](https://www.amazon.science/blog/sop-bench-a-new-benchmark-for-evaluating-ai-agents-on-real-business-procedures), and [McKinsey / 2026 State of AI](https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai). Source links document reported developments or known challenges only. The seed never asserts a buyer confirmed its willingness to pay.

## How it senses and times the wave

Every newly admitted capability observation is matched to the blocker's capability tags. The engine generates durable **INVESTIGATE_ONLY** retest signals, one per matching (problem, capability) pair. It does not create sales, payment intents, service commitments, jobs in other engines or speculative financial balances.

The durable inventory lives in a private SQLite file with immutable content-addressed records, deduplicated triggers, integrity audit and a single-writer watch lock. To provide a continuous *local* sensor:

~~~sh
python3 -m frontier_omega --root ./frontier-omega-private watch --interval 5
~~~

Add a new v1 JSON problem, capability or trial record to \`./frontier-omega-private/inbox/\` atomically (write under a temporary name and rename to \`*.json\`). The worker ingests it, schedules matching retests, and moves the original input into the private \`processed/\` or \`rejected/\` directory. Restarting after a crash is safe because existing records are immutable and idempotent. A finite smoke test is \`watch --cycles 1 --interval 0.05\`.

**The watch process monitors local incoming records; it does not independently crawl or scrape model releases.** Approved external source retrieval, customer onboarding and model benchmarking must supply signed/validated input through a separately qualified adapter. Existing HARNESS monitored-source capabilities may supply a future adapter, but that wiring is not claimed present.

## From a signal to a possible crossing

A test arm is JSON with an explicit \`frontier-omega/trial/v1\` schema. It names:

- problem and capability IDs, execution date, evidence SHA-256, author-reported check result;
- same exact SHA-256 terms, acceptance specification and measurement protocol in both arms;
- price, buyer-paid-acceptance probability, all ten declared complete-cost categories and additional expected loss in integer microUSD;
- competent alternative and its currently reported qualification;
- \`AUTHORED_SCENARIO\` or \`OPERATOR_REPORTED_UNVERIFIED\` evidence scope.

Run:

~~~sh
python3 -m frontier_omega --root ./frontier-omega-private add --file old-trial.json
python3 -m frontier_omega --root ./frontier-omega-private add --file new-trial.json
python3 -m frontier_omega --root ./frontier-omega-private compare \
  --problem compiled-crypto-assurance \
  --before capability-old \
  --after alphaproof-code-20261110
~~~

For each arm, \`M × 10,000 = price_microUSD × probability_basis_points − 10,000 × (complete_costs + extra_expected_loss)\`. A reported crossing requires the old margin to be nonpositive and the new margin positive, a reported passing new test, and an explicitly reported independent check. Different terms/acceptance/protocol, missing historical evidence and multiple matched comparisons do not qualify.

The current verdict can only be **REPORTED_CROSSING_UNVERIFIED**, never a customer-financed action. The reservoir cannot verify arbitrary customer assertions, model release claims, signed agreements, real provider costs or third-party test results by itself. A positive scenario is only an investigation priority.

## Precise interface with ALPHA

\`report\` emits a stable machine-readable inventory and retest signals, with \`execution_authorized: false\`, \`customer_payment_established: false\` and \`financial_authority: NONE\`. This is an **advisory sensor output**, not a payment/production command.

A qualified ALPHA integration must separately:

1. Attach independently reproducible old/new tests and current competitor comparisons.
2. Obtain a genuine customer request, acceptance terms and verified spending authority.
3. Construct and deliver under the existing economic engine's contract and independent checker.
4. Account for collections, complete costs, refunds and reservations exclusively through the canonical native enterprise account.
5. Retain only economically justified productive assets and check fresh successor value.

The connected ALPHA 0.2 economic-engine branch currently remains separate and unmerged; this work does not alter its accounting, source snapshots or customer interfaces. A future connector should translate **qualified** signals into a request through that engine's existing authenticated intake, not bypass its approval and cash gates.

## Reproduction, privacy and limitations

- Public seed data are original problem hypotheses with source URLs, no personal/customer content, credentials or agreements. Keep real customer dossiers under an owner-only local state directory and never commit them.
- An immutable SQLite hash detects accidental mutation, **not** an attacker able to modify the database and hashes; it is not a signature or independent attestation.
- A retrigger is driven by declared capability-tag matching, not by proof that the blocker was removed. Tags are coarse and can produce false positives or miss opportunities.
- Cost/probability values supplied as trials are authored or operator-reported; neither the service nor this document claims live customer profit, empirical crossing, model inference or comparative superiority.
- Strong alternatives must include competent specialist/human-plus-AI means and no purchase. A cheaper incumbent complete route can defeat a supposed frontier invention even when the modelled task passes.
- This is a source-bound engineering dependency serving the flagship, **not** evidence of an achieved one-person self-sustaining enterprise, general autonomous invention or a billion-dollar outcome.

**Next decisive executable milestone:** qualify one new arrival with exact historical/new model execution under identical customer outcome requirements, independently validate the full delivered artifact and strongest complete alternative, then connect a buyer-approved contract to the existing ALPHA workcell. No paid service or outreach is authorized by this package.
