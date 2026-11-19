# 🌌♾️ FRONTIER Ω — Machine Asset 001
## A bounded, machine-consumable transformation with reproducible acceptance

**Beneficiary and intended economic owner:** MONTREAL.AI.
**Status:** offline prototype / commercial hypothesis. **Not** a production service, proven new invention, external security attestation, customer-validated product or money-earning deployment.
**Priority:** retain a capability MONTREAL.AI can operate. Sell verified outcomes or usage if genuine demand exists; do not sell the discovery engine by default.

### The first executable kernel

An authorized AI-agent caller submits a JSON dataset and an explicit transformation contract. The kernel produces output rows and checks every row against the contract using a separately written local verification routine. It returns a canonical SHA-256 binding of the input, contract, delivered output and receipt. Source data are not fetched; input provenance, external truth and authority are **not** independently attested.

This simple starting kernel deliberately tests the entire **machine-consumable artifact + acceptance record** interface without buying APIs, handling credentials, charging a customer or exposing a public endpoint. Its operations (copy/strip/upper/lower) are mundane and available in free tools. **It has no demonstrated discovery advantage or pricing power** and cannot be called a Blue Sky invention or the flagship in the 064 research charter. Its admission to a paid portfolio depends on identifying a genuinely underprovided, higher-value verification obligation and outperforming strong free alternatives.

### Reproduce locally

Standard-library Python 3.10+; no external services, packages, accounts or keys.

From this directory:

~~~sh
python3 -m unittest discover -s . -p 'test_gate.py' -v
python3 gate.py < example.json
python3 gate.py --serve --port 8788
# POST JSON to http://127.0.0.1:8788/v0/transform
# GET http://127.0.0.1:8788/healthz
~~~

Never expose this unauthenticated prototype beyond loopback; it has neither production authentication, contractual safeguards, audit-service independence nor payment integration. It never calls a payment gateway and never reports a settled charge.

Input object:

~~~json
{
  "contract": {
    "id_field": "id",
    "rules": [
      {"from": "name", "to": "customer", "op": "strip"},
      {"from": "country", "to": "region", "op": "upper"},
      {"from": "quantity", "to": "amount", "op": "copy"}
    ]
  },
  "source_rows": [
    {"id": "a", "name": "  Ana  ", "country": "ca", "quantity": 2}
  ]
}
~~~

Only source fields explicitly required by the rules are emitted. All source identifiers must be unique; fields, operations, rows and request bytes are capped. Unknown operations, duplicate JSON keys, nested values, malformed records and nonfinite numbers are refused. Output and receipt SHA-256 digests protect local replay comparisons but are **not** signatures or proofs of source authenticity.

### Commercial qualification: required, not presumed

The first **valuable FRONTIER Ω product** is not predetermined by this repository: the engine must search actual machine-agent workflows and compare missing acceptance/verification capabilities with existing, free and paid alternatives. A candidate enters the paid-asset portfolio only after:

1. An identified machine-consumable outcome that a buyer cannot already obtain at similar quality and total cost from a strong alternative.
2. Preregistered fresh, independently checked acceptance tests on authentic authorized sources; clear licensing and data rights.
3. Reliable execution and fully costed delivery under meaningful operating-load and abuse tests.
4. An authorized demand test: an independent buyer willingly pays for the exact capability and receives the accepted output.
5. A second successful purchase or deployment and a measured positive contribution margin net of platform fees, retries, fraud/refunds, infrastructure and necessary support.

**No positive conclusions on 1–5 have been established in this kernel.**

### Machine-payment rail strategy

Payments are a separate, explicitly authorized adapter, not part of this prototype. Stripe/Tempo MPP (HTTP 402) is an available open agent-payment mechanism; merchant approval and actual supported payout methods for a Canadian seller must be verified. Cloudflare Monetization Gateway is currently closed beta and requires U.S.-based buyers and sellers; do not assume MONTREAL.AI is eligible.

If future authority and eligibility are confirmed, use a well-maintained, provider-supported adapter with payment verification, idempotency, receipts, refunds and accounting. A caller-supplied "paid" flag must never unlock a paid result. Keep public publishing, signing credentials and actual collection disabled until separately qualified.

### Scientific admission

This is a **supporting instrument**. To demonstrate the Ω ALPHA discovery-and-economic-capture thesis, the engine must prospectively select the valuable opportunity, construct it, outperform strong frontier agents or conventional methods on the same complete acceptance and cost envelope, and show later independent improvement. No portion of this simple mapping kernel should be represented as that result.

### Evidence / status

Local unit tests and a public CI workflow test adversarial input and acceptance logic. They do not independently verify a third-party customer outcome or commercial demand. All no-sale and no-deploy cases remain legitimate stopping decisions.
