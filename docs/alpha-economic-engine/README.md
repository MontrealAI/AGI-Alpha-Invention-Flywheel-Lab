# ALPHA Economic Engine · Connected operating edition 0.2.0

**A persistent, end-to-end operating-loop implementation candidate—not a demonstrated autonomous profitable company.**

This edition connects opportunity intake, model-driven bounded instrument construction, independent acceptance, customer delivery, settlement, protected obligations, earned-funded retention and successor work. It extends the repository's canonical `JournalAccount` / adaptive `Account`; it does not create another money ledger. First Ignition remains available without changes.

## Start with an actual run

Python 3.10+ on a POSIX host. Linux is qualified by the executed receipts. No pip packages, model API key or purchase is needed for the authored-fixture demonstration.

```sh
python3 -m connected_enterprise.alpha_economic demo --output ./alpha-demo
python3 -m unittest discover -s tests -p 'test_alpha_economic*.py' -v
```

Use a new demo directory. One continuous controller receives successive signed synthetic buyer requests on the **same native account**. The first attempt deliberately fails; its cost remains. The controller constructs a valid instrument, tests it, delivers a runnable customer ZIP, receives synthetic buyer acceptance, settles on the native simulated rail, preserves obligations, funds retention from modeled earnings, handles a fresh successor using the retained instrument and declines a buyer whose outside option wins. The daemon is stopped after the demo.

Outputs: `REPORT.json`, `RESULTS.json`, `outbox/<contract-id>/solution.zip`, package receipts, `native-export.json`, and immutable source/contract/acceptance records. The private `account*` files and signing/recovery material must **never** be published. The public report/export is key-free; customer contracts and inputs may still be private.

The delivered ZIP can be extracted independently and run with:

```sh
python3 instruments.py instrument.json input-example.json --max-operations 1000
```

## Continuous operation and control

```sh
python3 -m connected_enterprise.alpha_economic example-config > alpha-config.json
# Set ALPHA_BUYER_DEMO_KEY locally to an operator-chosen secret of at least 32 characters.
python3 -m connected_enterprise.alpha_economic --config alpha-config.json doctor
python3 -m connected_enterprise.alpha_economic --config alpha-config.json --root ./alpha-machine run --watch
```

The example configuration explicitly selects an authored fixture, not an AI model. Use `submit --envelope signed-request.json` to submit an authenticated request while the worker runs. A buyer's request is not quote acceptance: the controller separately checks price-bound consent and artifact/package-bound delivery acceptance. HMAC keys identify registered buyers; they do not prove economic independence or external certification.

`serve` starts the worker and a loopback control plane (default port 8765). Supply `ALPHA_CONTROL_TOKEN` with at least 32 characters. The server requires a bearer token, rejects browser Origin headers and unexpected Host headers, bounds bodies and never serves credentials or account exports. Endpoints: `POST /v1/requests`, `GET /v1/status`, `GET /v1/orders/<id>`, `POST /v1/pause`, `POST /v1/resume`. Stop the worker before the standalone `audit` command obtains its writer lock. SIGINT/SIGTERM finish bounded current work and stop; OS process death leaves recoverable state.

This HTTP server is **not** a qualified internet-facing multi-tenant deployment. An owner-provided authenticated HTTPS reverse proxy, customer onboarding, authorization and operational hardening are required. Stripe webhook forwarding must pass through that trusted proxy because the loopback endpoint additionally requires its control token.

## Model-backed construction

The engine uses the existing HARNESS adapters instead of automating browser cookies or scraping a ChatGPT subscription. Explicit `harness`, official `chatgpt-plan`, and `codex` configurations preserve the existing authorization boundaries. Remote paid requests are disabled unless separately configured and authorized; this project execution used no paid model APIs.

Example local-compatible adapter configuration:

```json
{
  "kind": "harness",
  "max_output_tokens": 768,
  "routes": {"construct": {"provider": "local", "model": "YOUR_INSTALLED_MODEL"}},
  "runtime": {
    "local_only": true,
    "allow_paid_requests": false,
    "timeout_seconds": 600,
    "providers": {
      "local": {
        "kind": "openai",
        "base_url": "http://127.0.0.1:8080/v1",
        "output_limit_field": "max_tokens",
        "models": {
          "YOUR_INSTALLED_MODEL": {
            "input_per_million": 0,
            "output_per_million": 0,
            "json_mode": true,
            "max_output_tokens": 768
          }
        }
      }
    }
  }
}
```

Zero local token rates mean no provider per-token API fee; they do **not** mean zero compute, electricity, development or maintenance cost. Complete actual costs remain unmeasured. `scripts/alpha_economic_local_model.py` executes a separate pinned Qwen/llama.cpp CPU qualification; its receipt, not the existence of this script, determines whether actual inference and a model-produced accepted artifact were demonstrated.

Models propose inert JSON instruments. They cannot modify customer confirmation cases, the financial account, source allowlists, consent, payment observations or execution policy. Construction receives training cases but not confirmation cases. A competent ordinary instrument is checked as a first-class alternative and can win. Failures consume their prepaid modeled resource envelopes; conventional fallback is explicitly labeled.

## Discovery, adaptation and capital allocation

Authenticated demand can arrive continuously; content-addressed contracts are admitted without reseeding capital or replacing historical accounts. The controller prioritizes declared price less the full declared failure-inclusive cost envelope. This ranking is not a global optimum or proof of willingness to pay.

Configured exact-host public sources can be monitored with the HARNESS DNS-pinned HTTPS retriever. Source changes are evidence for investigation, not verified improvements. A configured discovery model may produce evidence-bound hypotheses only after a native earned-funds research allocation. A hypothesis does not become a purchase, permit unsolicited outreach, or authorize spending. Fresh capabilities are revalidated against each successor. Identical already-retained instruments do not receive a redundant reinvestment: holding cash wins.

The implemented production domain is **bounded JSON instruments with finite declared acceptance cases**. It is not arbitrary code execution, unrestricted company creation, generalized autonomous scientific invention, automatic retraining or an independently demonstrated expansion of humanity's productive frontier. Extending the domain requires an approved constructor/checker and source-qualified deployment; models cannot self-authorize that change.

## Economics: precise scope

The executable native loop uses `SIMULATED` microUSD. It records buyer choice, funded orders, actual produced artifact hashes, separate delivery acceptance, collections, costs, reserves and earned-only reinvestment. Its source-bound public audit replays financial conservation and all prepared artifacts. Seed capital, restricted customer funds and predicted profits are not relabeled earned cash.

The declared model includes acquisition, research, construction failures/retries, verification, delivery, support, maintenance and a tax provision, plus separately expensed startup and discretionary retention. These values are illustrative assumptions, not a real supplier quotation, tax calculation or audited complete-cost business margin. Time in this demonstration is explicitly simulated integer hours. Default capital is only a demonstration parameter, not a universal funding requirement or business-scale ceiling.

Original account histories, old source snapshots and account ownership remain untouched. There is no migration, top-up or reset of an existing enterprise.

## External commerce interfaces and the unfinished production dependency

`commerce.Stripe` implements explicitly authorized test/live Checkout, authenticated webhooks, server-side PaymentIntent/charge/balance-transaction reconciliation, fees, partial refunds/disputes and idempotent refunds. A Checkout redirect, notification, invoice or successful HTTP response is not booked as profit. Notifications are durable/deduplicated; their ordering is not trusted. Provider state is read afresh before recognition.

`HTTPBuyer` supports registered opt-in buyer endpoints for quote consent, payment notices and delivered packages. This is not automatic unsolicited lead generation. `LiveEngine` connects these paths to the same construction and acceptance machinery, uses real wall-clock hours for obligations, and never provisions native simulated wallets. It refuses fixture agents/synthetic counterparties in external modes. Live write uncertainty beyond the provider's idempotency window stops for reconciliation rather than blindly repeating a charge.

**A real authoritative treasury/accounting gateway is NOT bundled or deployed.** `gateway.TreasuryGateway` is a strict authenticated client protocol, not a bank account or an implementation of the remote accounting service. A compatible operator-side implementation must supply independently reconciled balances, actual resource prepayments, costs, obligations, settlement recognition and atomic earned-only investment authority. The client cannot create those facts by signing its own local test receipts. Its interface is tested with explicit fixtures only.

Consequently this edition is **not live-commerce complete**. Real gateway implementation/integration, actual model-account qualification, buyer onboarding, payment-account authorization, deployment, actual billing and real customer acceptance remain outstanding. No real customer, real collection, live treasury, actual profit or self-financing company is established by the simulated run or by protocol tests. Offline `doctor` exposes that boundary rather than claiming readiness.

## Recovery and safety

One process owns the financial writer. Immutable input contracts, output hashes and source closure bind execution. Durable effect intents precede financial operations; retry uses the same operation, payload and financial time. Pending effects are reconciled before advancing the clock. Computation is at-least-once after a kill; committed financial operations are idempotent. A terminated model attempt is not a free attempt.

Accepted outputs are stored before delivery. Repeated deterministic packaging verifies rather than overwrites changed bytes. Public event hashes detect local accidental alteration but are not independent signatures or cryptographic inference proofs. The native private journal retains its existing owner-authenticated recovery boundary. An owner controlling code, keys and all files is not an independent verifier.

Pausing halts new work. The external path reconciles provider notifications and pauses investment when its authoritative gateway reports uncovered obligations. Unknown actual costs, disputed receipts, expired authorization, source drift, malformed data and mismatched scopes do not create spendable money.

## Reproduce qualification

```sh
python3 -m unittest discover -s tests -p 'test_alpha_economic*.py' -v
python3 -m unittest discover -s tests -p 'test_connected_finance.py' -v
python3 -m unittest discover -s tests -p 'test_alpha_runtime_ignition.py' -v
python3 -m connected_enterprise.alpha_economic demo --output /absolute/new/demo
python3 scripts/alpha_economic_package.py --output /absolute/new/source-kit.zip
```

Qualification must match the final source hashes. The test suite includes complete modeled cycles, actual HTTP ingress, separately checked delivery, buyer refusal/refund, failed attempts, interrupted accounting acknowledgments, duplicate submissions, model protocol authorization, provider reconciliation, webhook tampering/replay, source/output changes, existing native finance and original ignition regressions. Protocol fixtures are explicitly not real model or payment-provider execution.

References used for the payment interface:
- https://docs.stripe.com/api/checkout/sessions/retrieve
- https://docs.stripe.com/api/balance_transactions/object
- https://docs.stripe.com/webhooks
- https://docs.stripe.com/api/idempotent_requests

The HARNESS evaluator keeps its Apache-2.0 license. Other repository components retain their existing rights; this source kit does not relicense the surrounding repository or models.
