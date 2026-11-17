# 🌌♾️ FRONTIER Ω → ALPHA: From a qualified crossing to a paying customer

**Dependent integration candidate:** built on ALPHA Engine 0.2 (PR #419) plus FRONTIER Ω Reservoir (PR #422), both unmerged. Public source observations are hypotheses, not qualified buyer demand, executed frontier crossings, or real revenue.

## One-command ignition of the three continuous loops

Run from an integration-branch checkout with Python 3.10+ on POSIX:

~~~sh
python3 -m frontier_omega --root ./frontier-private seed \
  --file examples/frontier-omega/public-opportunities-20261116.json

# Deliberate simulation sample: no model access, no buyers, no real money.
python3 -m connected_enterprise.alpha_economic example-config > alpha-config.json

# Set ALPHA_BUYER_DEMO_KEY privately, to a secret of at least 32 characters.

python3 -m connected_enterprise.alpha_economic.frontier_conversion_cli \
  --reservoir-root ./frontier-private \
  --engine-root ./alpha-private \
  --config ./alpha-config.json \
  ignite --poll 5
~~~

The supervisor runs a private frontier capability-event inbox, a buyer-signed qualified-order inbox, and the existing ALPHA economic worker. These loops share no fabricated financial account. The source-event watcher reads locally supplied records: it does **not** currently crawl the frontier automatically. To review the inventory, run:

~~~sh
python3 -m frontier_omega --root ./frontier-private dashboard
~~~

For a prospective qualified order, freeze an exact machine-checkable bounded JSON outcome contract, including buyer-visible price, terms, separate training/confirmation cases, a qualified conventional control, and a fixed acceptance protocol. Historical and current replay receipts are constructed with the host-owned frontier_bridge.make_trial checker and inserted into the Reservoir. **All cost and acceptance-probability numbers remain estimates until independently substantiated.** No currently seeded problem qualifies automatically.

A buyer who is already registered through ALPHA's key boundary must independently sign the exact ALPHA request envelope. A private conversion bundle contains that original signed request, problem ID, historical/current capability IDs, and both instruments.

Inspect without financial effects:

~~~sh
python3 -m connected_enterprise.alpha_economic.frontier_conversion_cli \
  --reservoir-root ./frontier-private --engine-root ./alpha-private \
  --config ./alpha-config.json \
  preflight --bundle ./private-customer-request.json
~~~

Or submit the same bundle using the submit subcommand, or place it (owner-only mode 0600) in the private folder alpha-private/frontier-intake/inbox. The worker repeatedly checks deferred requests after new evidence arrives; invalid signatures are rejected, and committed submissions are idempotent.

## Commercial gates enforced by this implementation

**Host replay:** The system re-executes the supplied historical and current bounded instruments against identical acceptance tests. Trial evidence is bound to exact instrument hashes, buyer contract, evaluator and checker source hashes. A prior instrument may fail the declared cases, or pass at an operator-reported economically negative cost. The current instrument must pass. Unchanged competent ordinary alternatives remain qualified controls. **This does not prove that the broader customer outcome was previously impossible or that current reported costs are real.**

**Buyer:** The registered buyer's signed, unexpired request must match the exact blocked outcome. The price must satisfy the declared budget and outside option; the reported buyer ceiling and deadline, if any, are enforced. Public-source claims alone can never create a payment or buyer consent. ALPHA subsequently requires separate price-bound quote consent, accepted delivery, and collection.

**Economic execution:** Only the existing ALPHA engine receives the work order. It handles model construction, verification, buyer choice, Stripe Checkout, receipts, refunds, reserve/obligation accounting and earned-funded successor decisions through its own independent configured interfaces. The FRONTIER bridge creates no ledger and cannot bypass those checks.

A successful handoff means **SIGNED ORDER ADMITTED**, not money earned. The existing external production path refuses authored fixture agents and synthetic buyers, and the bridge separately refuses authored-scenario frontier trials in external mode.

## Real commercial readiness

The current ALPHA external code contains opt-in customer delivery interfaces, explicit Stripe test/live checkout and provider reconciliation, and a strict real-treasury **client**. A compatible, independently reconciled authoritative live treasury gateway is **not bundled or deployed**. Live buyer/Stripe/model credentials and owner permissions have not been provided. This branch has performed no real payment, customer acceptance, or funded production. Simulation remains simulation.

A live pilot must first qualify:
1. An actual customer-controlled purchase request, verified prior/current task evidence and strong complete alternatives;
2. A real configured buyer endpoint and independently accepted production outcome;
3. An active, authorized payment provider plus a separately deployed authoritative financial backend that protects refund/claim/support obligations;
4. Complete actual costs, fees, taxes and unrestricted available earnings;
5. A fresh successor commercially accepted on its own merits and causally enabled by a retained asset or real unrestricted earnings.

The initial supported delivery is a bounded JSON instrument. No arbitrary enterprise migration, compiled crypto proof or physical design can be claimed deliverable through that narrow instrument checker.

## Reproducible tests

~~~sh
python3 -m unittest discover -s tests -p 'test_alpha_frontier_conversion.py' -v
python3 -m unittest discover -s tests -p 'test_frontier_omega.py' -v
python3 -m unittest discover -s tests -p 'test_alpha_economic*.py' -v
python3 -m unittest discover -s tests -p 'test_connected_finance.py' -v
~~~

The new tests execute real host checkers, financial simulation through the existing native account, receipt durability, signed-buyer enforcement, negative controls, deferred intake and the three-loop ignition. Authored evidence must never be represented as independent historical frontier proof or actual commerce.

**Ultimate acceptance:** a previously blocked valuable customer outcome is independently qualified, built, accepted and paid for; complete costs and obligations are covered; and the engine uses real available earnings or proven reusable capability to advance a new accepted opportunity with minimal founder intervention. This remains to be earned.
