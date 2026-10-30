# Operating guide for the bounded reconciliation workflow

This guide covers the implemented public synthetic-input service. It is not an instruction to connect customer accounts or move funds.

## Input and output contract

Use explicit USD integer cents, unique invoice/payment IDs and customer identities. Include invoice references when known. A strict-completeness order rejects unresolved rows; an exception-schedule order preserves ambiguity for follow-up. Delivery contains reconciliation.json and exceptions.csv.

## Tested worked example

The accompanying minimal-input.json supplies one invoice and one exactly referenced payment for 12345 cents. The actual produced worked-example/reconciliation.json was independently checked; all rows are conserved.

## Run source-bound engineering checks

```sh
python -m unittest discover -s tests -p "test_service*010.py" -v
python -m unittest discover -s tests -p "test_onboarding010.py" -v
```

The release reproduction guide provides the frozen CLI and clean-package commands. Use a new output directory; preserve original failures and source identities.

## Operational limits

Authored public synthetic records only. No account attestation, tax filing, fraud certification or real payment execution. Exact host inference billing and customer attention costs are unmeasured. The independently checked example does not establish quality on all future customer records.

## Source-backed capability answers

# Technical response and evidence packet

Scope: public source-backed engineering evidence; customer behavior and commercial payments remain simulated.

## What input data are qualified?

Authored public synthetic USD receivables and payment records only; this qualification does not represent live customer records.

Evidence: `campaign/commercial-010/service/executed-002/manifest.json` (SHA256 `b91c511a8ea416ebf70a5a90bebdd7275643152852472e53df9d103bb514a002`), `commercial/service.py` (SHA256 `1604d20f5d9f54997eeceb971bc19af9a0c76cdcaf79ba74b9bbd80112c9c9a3`)

## What was actually produced and checked?

The executed engineering cohort supplied 19000 source records across 19 orders: 16 accepted packages and 3 rejected jobs. This is not a population accuracy estimate.

Evidence: `campaign/commercial-010/service/executed-002/manifest.json` (SHA256 `b91c511a8ea416ebf70a5a90bebdd7275643152852472e53df9d103bb514a002`)

## What is the delivered outcome?

Delivery contains row-level reconciliation JSON and a CSV exception schedule. It does not edit bank records, file taxes, attest accounts or move funds.

Evidence: `commercial/service.py` (SHA256 `1604d20f5d9f54997eeceb971bc19af9a0c76cdcaf79ba74b9bbd80112c9c9a3`)

## How is ambiguous evidence handled?

Ambiguous matches remain in an exception schedule; a strict-completeness order is rejected when required rows remain unresolved rather than inventing an allocation.

Evidence: `commercial/service.py` (SHA256 `1604d20f5d9f54997eeceb971bc19af9a0c76cdcaf79ba74b9bbd80112c9c9a3`), `commercial/service_verifier.py` (SHA256 `ac79f1aa80fb5c2928827f08417a720cd041977df70e808860bc3dd4f5d61368`)

## Can input preparation run autonomously?

The CSV pipeline executed 19 synthetic exports: 17 canonical prepared-order identities, 2 input rejections and 16 independent service acceptances. Customer attention and the complete host bill were not measured.

Evidence: `campaign/commercial-010/onboarding/executed-001/RESULT.json` (SHA256 `4c22216a1a1c26b326e2f4a14faf07a0f37480cdec3da1ef39a6bb76eb71d1bb`), `commercial/onboarding.py` (SHA256 `68e9fbc6eaaceed9b2678ef604646025c02f6cb77183da9208b729486c5302cf`)

## Who checks acceptance?

A separately implemented checker recomputes row partitions, exact cents, references and customer isolation. Builder and checker share the host and agent family; this is not external certification.

Evidence: `commercial/service_verifier.py` (SHA256 `ac79f1aa80fb5c2928827f08417a720cd041977df70e808860bc3dd4f5d61368`)

## Are the demonstrated commercial payments real?

Customers, orders, payment protection, settlement and earned funds in the commercial model are SIMULATED. The service cohort reports zero actual customers and zero actual collections.

Evidence: `campaign/commercial-010/service/executed-002/manifest.json` (SHA256 `b91c511a8ea416ebf70a5a90bebdd7275643152852472e53df9d103bb514a002`), `campaign/commercial-010/POLICY.json` (SHA256 `dba429196ea3f7ccfda74f1d7a639a549e803f7b72e19b6c444b5c4e554bccee`), `vendor/alpha_claim/protected_exchange.py` (SHA256 `7b72c911d99a9aa12dc1f412d3b66f69ba58f3d4f2f50291310a7fd849df5272`)

## Are exact model bills available?

Host token billing and the exact routed model version are unavailable. Monetary conclusions require disclosed complete-resource cost envelopes; process CPU is not a complete monetary bill.

Evidence: `campaign/commercial-010/service/executed-002/manifest.json` (SHA256 `b91c511a8ea416ebf70a5a90bebdd7275643152852472e53df9d103bb514a002`), `campaign/commercial-010/ALLOCATION.json` (SHA256 `4a27bd50bb51432c2ad969f4680377417e113b4e7665a456ada1d62ca8f42032`)

## Was a human reviewer inserted into this workflow?

No human intervention is recorded for the source service orders. The autonomous comparison does not impose hypothetical human staffing; this statement is limited to the declared workflow.

Evidence: `campaign/commercial-010/service/executed-002/manifest.json` (SHA256 `b91c511a8ea416ebf70a5a90bebdd7275643152852472e53df9d103bb514a002`)

## What does strategic pricing establish?

The pricing policy seeks expected collected complete-cost profit and sustainable cash under declared buyer and competitor assumptions. Its tested prices are not observed market optima or a universal equilibrium certificate.

Evidence: `campaign/commercial-010/POLICY.json` (SHA256 `dba429196ea3f7ccfda74f1d7a639a549e803f7b72e19b6c444b5c4e554bccee`)

## How are earnings distinguished from capital?

The pinned native exchange separates seed liquidity, restricted custody, principal reserves and unrestricted earned funds, and admits continuation investment through its earned-funding gate. Seed capital may still back reserves.

Evidence: `vendor/alpha_claim/protected_exchange.py` (SHA256 `7b72c911d99a9aa12dc1f412d3b66f69ba58f3d4f2f50291310a7fd849df5272`)

## What operating permissions are in scope?

The declared operation authorizes public or synthetic inputs and simulated commerce. It grants no new spending, paid provider calls, real outreach, real payment execution or credential access.

Evidence: `campaign/commercial-010/ALLOCATION.json` (SHA256 `4a27bd50bb51432c2ad969f4680377417e113b4e7665a456ada1d62ca8f42032`)

A bounded 12-question technical evidence response, not a complete enterprise RFP, legal commitment, security attestation or observed sale.
