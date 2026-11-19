# 🌌♾️ FRONTIER Ω — Machine Asset 001
## A bounded, machine-consumable transformation with reproducible acceptance

**Beneficiary and intended economic owner:** MONTREAL.AI.
**Status:** offline prototype with a disabled-by-default dual-chain checkout shell / commercial hypothesis. **Not** a production service, proven new invention, external security attestation, customer-validated product or money-earning deployment.
**Priority:** retain a capability MONTREAL.AI can operate. Sell verified outcomes or usage if genuine demand exists; do not sell the discovery engine by default.

### The first executable kernel

An authorized AI-agent caller submits a JSON dataset and an explicit transformation contract. The kernel produces output rows and checks every row against the contract using a separately written local verification routine. It returns a canonical SHA-256 binding of the input, contract, delivered output and receipt. Source data are not fetched; input provenance, external truth and authority are **not** independently attested.

This simple starting kernel deliberately tests the entire **machine-consumable artifact + acceptance record** interface without buying APIs, handling credentials, charging a customer or exposing a public endpoint. Its operations (copy/strip/upper/lower) are mundane and available in free tools. **It has no demonstrated discovery advantage or pricing power** and cannot be called a Blue Sky invention or the flagship in the 064 research charter. Its admission to a paid portfolio depends on identifying a genuinely underprovided, higher-value verification obligation and outperforming strong free alternatives.

### Reproduce locally

Standard-library Python 3.10+; no external services, packages, accounts or keys.

From this directory:

~~~sh
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 gate.py < example.json
python3 gate.py --verify < audit-example.json  # check an independent candidate
python3 gate.py --serve --port 8788
# POST JSON to http://127.0.0.1:8788/v0/transform
# GET http://127.0.0.1:8788/healthz
python3 market.py --state /tmp/frontier-local-market.sqlite3
python3 market.py --state /tmp/frontier-local-market.sqlite3 --serve
python3 portfolio_metrics.py --state /tmp/frontier-local-market.sqlite3
# Machine commerce API is local-only and charges are disabled by default
~~~

Never expose the prototype beyond loopback. The transformer is unauthenticated, and the separate market shell is also research-only. Live token collection is **disabled** unless an operator deliberately provisions mainnet RPC, treasury addresses, token amounts and an explicit activation flag. No such activation is authorized by this PR; no external payment or settlement has been attempted.

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

The optional independent-delivery route accepts the same contract and source rows plus a candidate_delivery list, and returns a local acceptance verdict without constructing a new answer. This supports machine-agent verification experiments, but is still no substitute for external certification or evidence provenance.

Only source fields explicitly required by the rules are emitted. All source identifiers must be unique; fields, operations, rows and request bytes are capped. Unknown operations, duplicate JSON keys, nested values, malformed records and nonfinite numbers are refused. Output and receipt SHA-256 digests protect local replay comparisons but are **not** signatures or proofs of source authenticity.

### Commercial qualification: required, not presumed

The first **valuable FRONTIER Ω product** is not predetermined by this repository: the engine must search actual machine-agent workflows and compare missing acceptance/verification capabilities with existing, free and paid alternatives. A candidate enters the paid-asset portfolio only after:

1. An identified machine-consumable outcome that a buyer cannot already obtain at similar quality and total cost from a strong alternative.
2. Preregistered fresh, independently checked acceptance tests on authentic authorized sources; clear licensing and data rights.
3. Reliable execution and fully costed delivery under meaningful operating-load and abuse tests.
4. An authorized demand test: an independent buyer willingly pays for the exact capability and receives the accepted output.
5. A second successful purchase or deployment and a measured positive contribution margin net of platform fees, retries, fraud/refunds, infrastructure and necessary support.

**No positive conclusions on 1–5 have been established in this kernel.**

### Machine-payment rail strategy — two valid $AGIALPHA mainnets

The supporting payment shell now includes read-only token-transfer verification, private orders, atomic anti-replay checks, and paid-only delivery gates, with all live collection **disabled by default**.

- **Ethereum mainnet:** $AGIALPHA at 0xA61a3B3a130a9c20768EEBF97E21515A6046a1fA (chain ID 1, 18 decimals), verified by ERC-20 Transfer log, exact one-time quote amount and finalized block.
- **Solana mainnet-beta:** $AGIALPHA at tWKHzXd5PRmxTF5cMfJkm2Ua3TcjwNNoSRUqx6Apump (confirmed valid by the owner), verified by finalized transferChecked, authentic mint/treasury token account, original payer, exact order memo and credited balance. Solana decimals are inspected on chain rather than assumed.

Stripe/Tempo MPP can be evaluated as a future primary rail, and token settlement can serve as an independent fallback. The shell does not claim to implement MPP or accept live payments yet. Cloudflare Monetization Gateway is currently closed beta and may not support Canadian merchants.

All merchant receiving wallets, Solana treasury token account, pricing, RPC endpoints and required compliance approvals remain to be supplied and validated. For exact procedures see [OPERATIONS.md](OPERATIONS.md); for economic admission see [ADMISSION.md](ADMISSION.md). [portfolio_metrics.py](portfolio_metrics.py) deliberately keeps chain transfer observations separate from recognized revenue, profitability and company valuation.

### Scientific admission

This is a **supporting instrument**. To demonstrate the Ω ALPHA discovery-and-economic-capture thesis, the engine must prospectively select the valuable opportunity, construct it, outperform strong frontier agents or conventional methods on the same complete acceptance and cost envelope, and show later independent improvement. No portion of this simple mapping kernel should be represented as that result.

### Evidence / status

Local unit tests and a public CI workflow test adversarial input and acceptance logic. They do not independently verify a third-party customer outcome or commercial demand. All no-sale and no-deploy cases remain legitimate stopping decisions.
