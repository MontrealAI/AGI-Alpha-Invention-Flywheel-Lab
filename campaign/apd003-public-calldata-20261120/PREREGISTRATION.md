# APD003 — preregistered public-calldata / reverted-payment adversarial witness

**Source freeze:** APD002 original executing commit `2e1f8fb12738457ec7f47a537c6c58cb6dd91d82`, buyer-scoped contract blob `350d936c51dd342cc686e413310f8273ad0df67e`, original APD001 contract blob `d9b4b0a736b2d276e16220954203667db63c24cf`. No changes to either original contract, original tests, ledger, main or accounts.

## Prior mechanism claim to falsify
A computational certificate that is disclosed in a public EVM claim transaction is not necessarily economically exchanged for settlement, even when the contract reverts safely on recipient failure. Safety of the monetary state and confidentiality of the productive answer are distinct. This is not a demonstration that an actor manipulated a real transaction pool.

## Fixed test before implementation
1. In local EVM, an ephemeral buyer funds a buyer-scoped graph contract with 1000 synthetic wei and a seller receiver that refuses Ether. The seller submits the mathematically valid graph and certificate. The exact calldata is independently decoded by an external observer (no seller authority) before execution. Claim must revert, escrow must remain Funded, buyer balance and fees must remain unchanged, and refund after expiry must succeed.
2. The same observer decodes the accepted certificate from a compliant-seller claim; settlement is 990/10, showing that the verifier operates correctly when transfers succeed.
3. A strong zero-fee ordinary software solver and no-deploy remain complete competing alternatives. Nothing here proves any paid need, confidentiality on a public mempool, private-transaction availability, commercial novelty or actual dollar benefit.

Use unchanged original Solidity and Foundry tests on the exact selected branch, standard `ubuntu-latest`, 360-minute job and initial `AGI_JOB_START_EPOCH` marker. Precommit no seed selection; deterministic cycle graph, synthetic accounts and explicit false/refund paths. All negative and failed runs remain in their original form. Both test obligations and exclusions are frozen by this file commit.

**Safety:** No financial source writes, no real chain, no new API credentials, no private data/outreach/spend. Not an escrow deployment proposal. If the witness succeeds, record confidentiality as NOT QUALIFIED, not accepted paid commerce.
