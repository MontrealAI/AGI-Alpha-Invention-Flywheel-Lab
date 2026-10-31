# Native capital lifecycle P0 candidate

This opt-in candidate extends the existing mandatory `Account`, `JournalAccount`,
native event tape and `audit_account`. It does not replace the published default
enterprise or its failed released-operation receipt. No merge, release or hosted
CI qualification is claimed for P0.

All work, buyers, terms, cash and provider observations here are synthetic.
Production reexecutes the existing deterministic reconciliation service and its
independent checker. This is not a paid frontier-model service or observed
customer demand. Human/rival prices, buyer utilities, the resource invoice and
tax rate are explicit authored assumptions. Actual host and model billing are
unknown; reported profit is conditional.

## Register, operate, resume and audit

Use Python 3 with the repository's existing `requirements-commercial010.txt`.
Each output must be a new absolute directory under the operator's control.

```sh
python3 -m connected_enterprise register --config examples/native_capital020/central.json --output /absolute/new/capital-business
python3 -m connected_enterprise operate --output /absolute/new/capital-business --max-events 3
python3 -m connected_enterprise resume --output /absolute/new/capital-business
python3 -m connected_enterprise audit --output /absolute/new/capital-business
python3 -m connected_enterprise scoreboard --output /absolute/new/capital-business
```

Registration freezes source, configuration, opportunities and the canonical
service manifest before operation. Operation executes that frozen source in a
separate process. Resume retains the same account, event history, private local
simulation key and authenticated operating checkpoint. It never reseeds a
business. `--max-events` is an interruption/reproduction bound, not a new
economic horizon. The complete registered horizon includes settlement and
maturity drain. Integer native `day` fields mean **hours** in this operator.

The original `run`, `resume`, `audit` and `package` behavior remains available
for existing connected-enterprise outputs. Capital outputs are identified by
their distinct bound registration schema; ordinary outputs are not converted.

## Matched financing comparison and adverse cases

```sh
python3 -m connected_enterprise comparison --config examples/native_capital020/central.json --output /absolute/new/capital-comparison
python3 -m connected_enterprise audit --output /absolute/new/capital-comparison
python3 -m connected_enterprise scoreboard --output /absolute/new/capital-comparison
python3 -m connected_enterprise register --config examples/native_capital020/provider_default.json --output /absolute/new/capital-default
python3 -m connected_enterprise operate --output /absolute/new/capital-default
python3 -m connected_enterprise audit --output /absolute/new/capital-default
```

The comparison uses separately identified experimental accounts with the same
source, opportunities, prices, voluntary buyer policy, capabilities, seed and
prospective terms. It changes only permission to recycle earned funds. The
disabled arm retains unused cash and can spend only its reconciled remaining
original seed after working capital and costs/obligations. These accounts do
not replace the continuing business or erase its liabilities. Permanent versus
prospective terms is a different experiment; this comparison does not identify
that term effect or claim a real provider/legal finality.

This disabled arm is an explicit no-receipt-financing ablation. It is not the
strongest conventional revolving-capital policy. A benefit against that arm
does not establish superiority over competent conventional financing, nor
does the enabled policy require full seed repayment before reinvestment.

The default and outside-choice configurations retain adverse results. Provider
default can leave an incurred unpaid liability, a negative profit and stopped
investment. No future recovery is invented. Buyers taking an outside option do
not create sales for this enterprise. A losing case does not reset or overwrite
the positive-region account.

## Financial states and invariants

New immutable terms are registered before offer commitment and bind order,
version, price, collection timing, exposure, inclusive claim boundary, residual
liability, fees, premiums, coverage/deductible/exclusions/delay, default behavior,
counterparty obligations, jurisdiction and hypothetical legal/accounting rules.
Orders without prospective terms preserve the original permanent full tail.

The native path is registered terms → offer → consent → funding/custody →
independent acceptance → collected release → protected interval → exact eligible
maturity → current audited atomic reservation → subsequent accepted settlement.
Claims at the boundary precede maturity; maturity is strictly after the boundary.
Known unpaid claims and residual exposure remain protected. Late reversal does
not discard prospective claims or residuals. Premiums and fees are costs;
maturity is not income; coverage becomes cash only upon a bound collected
synthetic observation. Default and uncovered excess can stop investment.

Each maturity request has an immutable `event_id`; each claim payment/recovery
has an immutable `settlement_id`. Exact retries are idempotent. A changed request
under the same identifier is rejected; a legitimately later attempt needs a new
identifier. Native matured state prevents changed identifiers releasing twice.

## Owned-account authenticated source upgrade

The public upgrade API is `connected_enterprise.upgrades.authorize_upgrade`
followed by `JournalAccount.upgrade_source(..., authorization=ticket)`. It requires
the owned account's existing manifest, opening/working/contract values, path,
current audited state digest, selected target source and authoritative event
hour. The historical source directory must contain its pinned Python closure
and the original bound synthetic service inputs. No balance or identity is
copied and no old event is re-signed.

Authorization runs the old canonical owner/verifier in its pinned source,
checks its current state, and returns a local simulation HMAC authorization
without exporting the key. The transition retains the original signed journal
envelope, source inventories, pre-checkpoint and native history. A nonfinancial
native transition event binds the target, counter and checkpoint; new operations
continue on the same account. Ordinary legacy contract identifiers work.

Portable public audit can resolve historical source at its original directory
or at `CURRENT_ROOT/historical-source-versions/FROM_SOURCE_SHA256`. The full
signed inventory and historical data bindings must match; the signed original
path and authority are not rewritten. Keep all required historical versions.
At most four transitions are admitted by this bounded implementation; only the
tested transition count may be claimed qualified. Missing historical source,
tampered authorization, stale checkpoints, forks, downgrades or lost source
authority fail closed. Forward repairs require new explicit authorization.

The released/live accounts and another owner's recovery keys are outside P0.
Local simulated keys must stay private and out of commits, exports and bundles.
The implemented upgrade covers native financial Account/Journal continuity.
An already running legacy engine queue/checkpoint remains bound to its original
full operating source; conversion of that operating state is not implemented
or silently authorized by the financial transition. New capital operation has
its own tested fixed-source pause/resume path on one continuing account.

## Qualification and limits

```sh
python3 -m unittest discover -s tests -p 'test_native*.py' -v
python3 -m unittest discover -s tests -p 'test_connected_finance.py' -v
python3 -m unittest discover -s tests -p 'test_adaptive_account.py' -v
```

Migration tests extract pristine base commit
`10bdb2c5787f95158642b068756ba30b58140562` with `git archive`; retain that Git
history. Public audits are separate code paths and reexecute service checking,
but authors, models, tools, host and synthetic data are shared. This is not
external certification, statistical fresh commercial confirmation, a validated
annual scale bridge, capability compounding, or achieved US$3 billion profit.
Refer to the source-bound campaign receipt for actual passes, failures, resource
uncertainties and the candidate publication/integration boundary.
