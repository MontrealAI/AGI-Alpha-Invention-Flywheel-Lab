# 🌌♾️ MONTREAL.AI — FRONTIER Ω MACHINE ASSET OPERATIONS

**Status:** controlled research candidate, not production-qualified or commercially validated.
**Owner and beneficiary:** MONTREAL.AI.
**Mission:** discover, invent, own and operate machine-consumable productive assets. Keep the core invention engine and rights. Market admission requires independent evidence, not a token listing.

## Implemented
- Bounded transform and independent-candidate checker — gate.py
- Mainnet Ethereum and Solana $AGIALPHA verification — payment_receipts.py
- Private quote/settlement ledger, replay protection, paid-only delivery — market.py
- Dedicated offline adversarial tests, CI and machine-readable examples

This is a **supporting instrument**, not an invention breakthrough: the transform operations are commodity. See ADMISSION.md for the required commercial and competing-alternative test.

## Recognized $AGIALPHA identities

| Chain | Identity | Basis |
|---|---|---|
| Ethereum mainnet (chain ID 1) | 0xA61a3B3a130a9c20768EEBF97E21515A6046a1fA | Canonical in MontrealAI/AGIJobsv0/contracts/v2/Constants.sol; 18 decimals |
| Solana mainnet-beta | tWKHzXd5PRmxTF5cMfJkm2Ua3TcjwNNoSRUqx6Apump | Confirmed as valid by MONTREAL.AI's owner; token program and decimals must be queried on-chain |

Do not confuse either chain's token with another asset using the same name. Solana must match mainnet-beta genesis hash 5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d. The correct mint's current decimals are **read from on-chain source**, not inferred from token marketing material.

## Ethereum settled-payment verification
The server issues an expiring quote with a 48-bit random additive raw-unit amount fingerprint and a private access secret. The token must be transferred **exactly** from the declared EOA payer to the operator-approved Ethereum treasury. Only the canonical ERC-20 Transfer event from the token's contract is admitted. The server verifies on the configured mainnet RPC:
- chain ID 1, transaction hash, successful receipt, included canonical block and finalized block height;
- receipt time inside the original quote window;
- matching from address, to address, exact quoted raw token amount and uniquely identified log;
- atomic single-use event assignment to an order in SQLite.

Other payment routes, bridges, smart-account relays, multi-recipient batches and arbitrary transfers are outside this narrow adapter. A high-entropy quote amount is a binding aid, not identity proof or a guarantee against all adversarial on-chain activity. No assertion of real merchant value arises without settlement and separate financial reconciliation.

## Solana settled-payment verification
The buyer sends a **direct SPL transferChecked** on Solana mainnet-beta, using the authentic mint, from the declared payer to the approved merchant token account, with exactly one order-specific memo:

~~~text
FRONTIER-OMEGA:<order_id>:<nonce>
~~~

The operator-side read-only verifier checks finalized getTransaction, transaction signer and signature, transfer authority, mint, token program, exact raw units, current merchant token account owner/mint, token decimals from the mint, and exact credited pre/post token balance. It then consumes the signature once in the SQLite ledger.

Unsupported Token-2022 instructions, unparsed nested CPI transfers, nonfinalized transactions, alternative mints, duplicate memos or unproven treasury ownership are refused until an audited adapter supports them. This deliberately restricts transaction types rather than guessing what happened.

Primary references: https://solana.com/docs/payments/accept-payments/verification-tools ; https://solana.com/docs/rpc/http/gettransaction ; https://ethereum.org/developers/docs/apis/json-rpc/ .

## Reproduce without money, wallets, keys or Internet
Python 3.10+ standard library from this module's directory:

~~~sh
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 gate.py < example.json
python3 gate.py --verify < audit-example.json
python3 market.py --state /tmp/frontier-machine-local.sqlite3
python3 market.py --state /tmp/frontier-machine-local.sqlite3 --serve
~~~

The server binds **only 127.0.0.1:8790** and publishes health/catalog endpoints. Quotes and claims are disabled by default. Local fixtures can demonstrate anti-replay logic without becoming financial evidence. Non-public workloads must remain on an encrypted, controlled host; the local SQLite database stores input payloads and order-secret digests.

## Operator configuration — not activation authority

A subsequent approved live merchant integration needs the actual MONTREAL.AI-controlled recipient accounts and integer raw-token prices (not USD estimates), plus reliable HTTPS mainnet RPC endpoints:

~~~text
FO_ETH_TREASURY=<approved Ethereum recipient>
FO_SOL_TREASURY_OWNER=<approved Solana wallet owner>
FO_SOL_TREASURY_TOKEN_ACCOUNT=<approved Solana token account>
FO_ETH_PRICE_RAW=<integer $AGIALPHA base units for Ethereum>
FO_SOL_PRICE_RAW=<integer $AGIALPHA base units for Solana>
FO_ETH_RPC=<operator-approved HTTPS Ethereum mainnet RPC>
FO_SOL_RPC=<operator-approved HTTPS Solana mainnet RPC>
~~~

The additional explicit activation flag is FO_ENABLE_LIVE_PAYMENT=ENABLE_EXPLICIT_AGIALPHA_MAINNET_COLLECTION. **Do not set this from this guide.** No actual treasury destinations, token-denominated prices, approved RPC services, wallet authority, customer rights or production security review have been provided.

Before activation: verify both on-chain token identities, mint/account ownership, finality, decimals, destination proof, operator authority, privacy and security controls, replay/race behavior, refunds, disputes, accounting, taxes and relevant token/legal obligations. Production needs an authenticated and secured service perimeter, independent adversarial testing and audit; loopback research code does not qualify.

## $5B ambition: measurable admission, not a valuation claim

A quote is not revenue. A token balance is not earned profit. An internal test is not customer demand. A $AGIALPHA transfer is not automatically attributable company revenue until it is reconciled against a real, accepted product and obligations.

The path is **discovery → distinct productive capability → strong baseline comparison → independently accepted delivery → actual outside buyer payment → positive full-cost economics → repeat deployment → new independently improved invention**.

MONTREAL.AI retains the invention engine and chooses whether to operate, grant selective access or partner only when that improves its economics. The $5B ambition is not established by this module.
