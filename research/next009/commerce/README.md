# Source-bound commercial lane

This adapter closes one practical evidence gap: an actually accepted observation-plan artifact can be delivered through the **existing** pinned Alpha exchange while production economics are examined against human service. It introduces no competing financial ledger, live merchant account, payment API, customer message, or paid model call.

## Two deliberately distinct executions

1. `NATIVE_EXCHANGE.json` records actual execution of the inherited `ProtectedExchange`: source-bound acceptance, payment-gated artifact download, forged observations, nonpayment, modeled buyer rejection, duplicate settlement/refund, transaction interruption/reopen, custody loss, and correlated reversals. Its provider is an **idealized local nonrecourse simulation**, its unit remains **simulated-microUSD**, and no real provider cost is known. The CAD250 quote is converted using the dated CAD/USD reference before entering that ledger. The native reversible-card route is explicitly refused. These tests do not repair the historical unrelated SIGINT-startup defect.
2. `CARD_SCENARIOS.json` performs **read-only aggregate CAD cashflow arithmetic**, using the published Canadian domestic-card fee schedule and explicit scenario assumptions. It is neither a payment ledger nor a production escrow implementation. Card captures are reversible; the full remaining principal plus one received-dispute fee is reserved. There is no automatic release at day120, no reserve release booked as revenue, and no invented capital after the declared start.

Both paths preserve the same artifact identity. The receipt binds original raw bytes; the native payload uses canonical JSON and separately reports that identity. Twenty illustrative buyer opportunities do not create twenty independent technical confirmations or twenty real customers.

## Frozen authority and command

The separate verifier supplies a receipt with schema `agi-alpha/next009-delivery-acceptance/v1`, `accepted: true`, the raw `artifact_sha256`, `verifier_source_sha256`, `protocol_sha256`, and scope `model-based-water-observation-plan`. Extra descriptive evidence is permitted. Four expected hashes must come from the integration/verifier freeze; they are not inferred as authority from the receipt itself. Actual source/protocol files are checked against those hashes. The adapter does not execute an arbitrary verifier file.

From the repository root:

```bash
python research/next009/commerce/run.py \
  --artifact DELIVERY.json --receipt ACCEPTANCE.json \
  --verifier-source verification/next009/verify.py --protocol verification/next009/protocol.json \
  --expected-artifact-sha256 ARTIFACT_SHA256 \
  --expected-receipt-sha256 RECEIPT_SHA256 \
  --expected-verifier-sha256 VERIFIER_SHA256 \
  --expected-protocol-sha256 PROTOCOL_SHA256 \
  --output evidence/next009/commerce-001
python -m unittest research.next009.commerce.test_commerce -v
```

Optional `--price-cad` and `--cohort-size` create a separately recorded scenario policy. They never overwrite prior results. Price 250 and cohort 20 are illustrative, not observed demand. `FROZEN_POLICY.json` is written before execution, and its hash is attached to all reported results. Production must be prefunded under the declared scenario; no borrowing or new capital is silently introduced.

## Economic interpretation

All admitted attempts, failures, unsold work, setup, research recovery, verification, monitoring, maintenance, acquisition, and repair allowances are charged. Current official model and tool rates support cost sensitivities. The total model-token envelope is authored across all orchestration roles and retries; actual session usage is unknown. There is no fictitious human charge for autonomous computation.

The primary card scenario yields **CAD2,057.81 modeled accounting profit** and **CAD1,557.81 conditional earned cash** after delayed payouts and protection, while **CAD3,710 remains reserved** against the remaining principal and dispute fees. These numbers are outputs under authored cost and participation assumptions, not measured business results. Joint lower uptake, overstated useful benefit/refunds, increased inference, and warranty stress yields a **CAD2,388.61 loss**, funded only from the explicitly declared simulated equity. Zero demand also loses money. Separate payout and liquidity cases preserve positive accounting profit while deferring cash-funded investment.

Matched competent-human task duration and full overhead are unmeasured. The program therefore returns human-time break-even frontiers, not invented person-hours, and recognizes that competent humans can use the same EPANET/optimization tools. The posted wage, service rates, and broader procurement evidence do not establish buyers for this package. Technical parity with a conventional algorithm does not discard a positive conditional service scenario.

The prespecified policy would assign 30% of **qualified** unrestricted earnings to a successor, requiring at least CAD250, grounded participation, a complete-cost bound, and available earned cash. Those gates are not established. **Qualified simulated earned funds and successor allocation remain CAD0.00**, even when ideal-provider balances or conditional card projections are positive. Research-funded technical successors must retain their actual funding label. Actual NPV and investment attractiveness remain unknown because collection timing, protection duration, capital opportunity cost and competitive AI-native alternatives are not established.

`source_docket.json` gives primary references and limits. Source hashes prove byte identity at the trusted caller boundary; they do not turn an authored receipt into independent external certification, provider clearance, demand validation, or actual commerce.
