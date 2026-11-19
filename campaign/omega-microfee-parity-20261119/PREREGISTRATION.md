# Ω ALPHA micro-payment settlement parity — preregistered 2026-11-19

## Independence, source, and decision target

Independent, additive qualification of owner PR #486, pinned to original head `a3a803edbce39caf69e9a335579f75dcb45df9ec`, original `FrontierProofExchange.sol` Git blob `ef6fc9f03a3fc284df7e63d3ad1b20de1bfd2f83`, and `invent.py` Git blob `9f86912d5bdbd724cef6783ae46540968a380064`. Neither owner file is to change. Preserve the prior successful tests, original security failures, all historical business-account liabilities and original source identity.

**Question:** Does a modeled exact-rational fee from each author-defined synthetic opportunity translate into positive collected ERC-20 smallest-unit fees when settled as independent on-chain orders? The Python model explicitly uses `SYNTHETIC_UNITS_NOT_MONEY`; this experiment conditionally tests a hypothesized one-synthetic-unit-to-one-token-raw-unit mapping, **not** an existing money conversion, market demand, or a new chain deployment. Real token contract, decimals, participant rights and exchange value remain unverified.

## Fixed cases, no seed selection

- Compliant full-credit ERC-20 mock, 100 fee basis points, accepted job, 99 raw units: expected treasury **0**, seller **99**; Python model's *rational synthetic* owner fee is 99/100 units if zero modeled operating cost.
- Compliant accepted job, 100 raw units: treasury **1**, seller **99**.
- 20 **distinct** successfully accepted 99-raw-unit jobs on one contract: treasury **0** raw units, seller **1,980**, no residual escrow. Compare one separately accepted 1,980-raw-unit bundle (different job) at the same rate: treasury **19**, seller **1,961**, no residual escrow. A hypothetical rational model would assign 99/5 synthetic units to 20 independent transactions; the raw EVM does not collect it. Bundling changes job/acceptance obligations and cannot be silently substituted for the 20 orders.
- Compliant accepted 1,000-raw-unit job: treasury **10**, seller **990**.
- Refusal/alternative: no-entry yields zero proceeds, and a competent fee-free on-chain escrow remains a valid rival. A break-even paid-offer decision is **not** inferred without independent buyers, distribution, capacity, verification and complete resource costs.

Use the *unchanged* owner EVM contract with fresh local mock funding; compute Python synthetic model with unchanged `value()` as a separately labelled baseline. Implement a local read-only precision preflight computing **per-job floor(amount*bps/10000)**, total per-order raw fees, pooled hypothetical upper bound and lost-to-rounding gap, with explicit refusal of invalid arguments. Do not treat the pooled bound as collected or billable. No financial account, production wallet, HMAC state, native enterprise ledger, paid API, real transactions or new spending.

## Frozen acceptance and loss accounting

All enumerated cases must run; no substituted amounts or selected favorable examples. Pass means accurate **observed local EVM arithmetic**, consistency with Python's *distinct modeled units*, and refusal of a positive protocol-revenue claim where per-order raw fees are zero. Failing assertions or CI remain FAILED until a **prospective** correction is separately recorded; no protocol relaxation after outcome. Reject ordinary claim of novel cryptography, commercial advantage, actual profit, protocol moat, observed buyer uptake or eligibility for main deployment. Independently qualify exact-source hosted tests under standard `ubuntu-latest`, 360-minute platform job, first-step AGI_JOB_START_EPOCH, no privileged credentials or paid providers. Compare fixed ordinary direct/fee-free and no-deploy controls. Document proof boundaries and then submit the instrument to the original implementation owner as a selective review, never a wholesale merge of dependent branches.

Current main qualified runtime `f0987aa48d5c9136b28540f54eabf5367e63bbe6` and the original native-capital owner remain entirely untouched. Pending authentic source/account custody prohibits any P0 migration attempt.
