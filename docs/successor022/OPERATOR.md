# Continuing connected businesses across source versions

This successor candidate originally combined released `9facd934` and capital
candidate `3981b182`. Completion023 recovers its final runtime `56d27d99…` and
composes it with qualified operator `8abfb96d…`; see the
[current operator notes](../completion023/OPERATOR.md). The owner's 31 October
completion mandate authorizes ordinary engineering, qualification and normal
integration within actual platform constraints. Historical allocations retain
their original interpretation. Existing releases, source pins, accounts and
historical outcomes are preserved. All commerce below is synthetic; actual
host/model billing is unknown.

## Start and operate a registered business

The existing connected engine, mandatory adaptive `Account`, native ledger and
`JournalAccount` remain the operating path. Registration does not replace them.

```sh
python3 -m pip install -r requirements-commercial010.txt
python3 -m connected_enterprise register \
  --config examples/connected022/continuing-world.json \
  --seed 2610312231 --cohort-seed 2610312231 --arm growth \
  --output /absolute/new/connected022
python3 -m connected_enterprise operate \
  --output /absolute/new/connected022 --max-events 18
python3 -m connected_enterprise resume --output /absolute/new/connected022
python3 -m connected_enterprise audit --output /absolute/new/connected022
python3 -m connected_enterprise scoreboard --output /absolute/new/connected022
```

This initial registration retains permanent terms. The `business` directory
contains the same continuing account, signed operating checkpoint, native tape,
write-ahead journal and local simulation key. The `source` directory freezes the
actual executing dependency closure. Retain both to resume. Public audit exports
omit private accounts and keys and do not transfer ownership.

## Authorize a prospective source upgrade

Use an owned experimental account and its exact signed checkpoint. The target
checkout must contain the approved source. Do not modify another owner's account.
The same command handles a legacy world directory from a batch run: supply that
world's `STATE.json`, its original frozen source and matching `SERVICES.json`.

```sh
CONNECTED_CHECKPOINT=$(python3 -c \
  'import json,sys;from commercial.ledger import digest;print(digest(json.load(open(sys.argv[1]))))' \
  /absolute/new/connected022/business/STATE.json)
python3 -m connected_enterprise upgrade \
  --output /absolute/new/connected022/business \
  --historical-source /absolute/new/connected022/source \
  --manifest /absolute/new/connected022/SERVICES.json \
  --policy examples/connected022/prospective-policy.json \
  --expected-checkpoint "$CONNECTED_CHECKPOINT" --id connected022-upgrade-1
python3 -m connected_enterprise operate \
  --output /absolute/new/connected022/business --max-events 18
python3 -m connected_enterprise resume --output /absolute/new/connected022/business
python3 -m connected_enterprise audit --output /absolute/new/connected022/business
python3 -m connected_enterprise scoreboard --output /absolute/new/connected022/business
```

After upgrading, operate the upgraded world directory, whose `OPERATOR.json`
selects its new frozen source. A later approved forward upgrade uses the current
checkpoint, the current frozen source as `--historical-source`, and a new ID.
Previous intents, receipts and operator descriptors are retained in versioned
history directories. The native source counter remains bounded at four;
downgrades, stale tickets, changed retries and forks fail closed. An engine-only
change is bound by the financial source identity and requires authentication.
Retrying the same upgrade ID also requires the same frozen target source.

`MIGRATION_INTENT.json` preserves the original signed checkpoint, original signed
journal, source inventories, target runtime, policy and owner authorization. A
native `source_transition` records the same account's forward version change.
The registered upgrade invoice is charged once. Neither history nor old HMAC
signatures are rewritten. The old verifier replays the old history using its
original source before a transition is accepted.

The current policy's $1 upgrade invoice and $0.10 prospective premium are declared
simulation prices, not observed bills. The full business ledger also retains
setup, acquisition, qualification, failed offers, production, prepaid support,
payment fees, maintenance and modeled tax provisions. Unknown actual billing
limits profitability to the declared cost envelopes.

## Financial and checkpoint behavior

An authenticated obsolete checkpoint intent can be archived automatically only
when the current signed STATE matches the latest native checkpoint anchor.
Invalid signatures, unknown source authority, and replayed STATE still fail.
Genuine unfinished intent is recovered exactly once through its normal WAL.

For an older frozen verifier that predates this recovery, the public
`recover-checkpoint` command takes the same `--output`, `--historical-source`,
`--manifest`, `--expected-checkpoint` and `--id` arguments as the upgrade command
(without `--policy`). It runs the unchanged historical canonical Account and
audits under the account and world locks. It archives an objectively obsolete
intent and signs a separate recovery receipt while preserving all bytes of the
live STATE, journal, native tape and the account's key identity. It neither
upgrades source nor advances the business. Follow with an authenticated forward
upgrade using the current checkpoint. An unsafe or unresolved financial WAL
cannot be repaired by this metadata operation.
If a financial source transition has already committed while STATE remains its
exact signed predecessor, recovery additionally requires that same authenticated
transition and its exact native transition/invoice tail. Complete that existing
upgrade before authorizing another one. An arbitrary predecessor cannot confer
this recovery authority.

New quotes register immutable terms before commitment. Existing orders and
prepared legacy plans retain their original terms and costs. Prospective payment
fees and premiums are charged by the native contract; the resource invoice
excludes those charges to prevent double counting. Collection is recognized
separately from reserve release. Maturity occurs after the inclusive claim
boundary and changes restrictions without creating cash or profit. Existing
claims, residual protection, delayed recoveries and defaults remain obligations.

The connected engine schedules maturity explicitly and processes due financial
events before a new funding snapshot. Native reservations bind the audited
sequence, available cash and earned funds atomically. Positive profit cannot
authorize spending protected or committed cash. Claim, settlement and recovery
invariants are exercised through the public native account facade; claim
continuity tests are separate from the legacy operating-queue test.

Every canonical operating checkpoint has a monotonic native
`operating_checkpoint` commitment. The commitment covers economic and operating
state; seven diagnostic CPU/wall timing fields are excluded from its semantic
digest so independently executed identical work can retain identical finance.
The full local HMAC still covers every checkpoint byte. Monetary amounts,
obligations, queues, decisions and event clocks are included in the commitment.

Checkpoint persistence uses an authenticated write intent, native commitment,
atomic `STATE.json` replacement, and acknowledgement. A crash before or after the
native commitment recovers the exact intended state. An older signed state or
intent cannot replace later committed operating history. The current account
writer lock and per-world run lock prevent competing writers.

Failures preserve the native tape and pending intent. Reopen with the same
approved source and local simulation key; `resume` completes authenticated pending
work. A changed source, corrupted signature, lost authority, stale checkpoint or
incompatible transition stops execution. Do not reset the account or reseed it.

## Reproduce the bounded composition qualification

The protocol is frozen in
`campaign/successor-022/QUALIFICATION_PROTOCOL.json`. It uses 21 planning days plus
a bounded maturity/settlement drain. The coverage checkpoint contains queued
production, acceptance and clearing, a prepared current event, and an extant
permanent tail. Its selection is for engineering coverage, not economic success.

```sh
python3 campaign/successor-022/qualify.py setup \
  --output /absolute/new/qualification-prospective --arm prospective
python3 campaign/successor-022/qualify.py step \
  --output /absolute/new/qualification-prospective
```

Each `step` processes at most 18 events on the same account. Repeat it while its
receipt reports `complete: false`, respecting actual platform limits. Original
resource receipts and historical inode claims remain historical; a restored
account must compare its preserved key bytes and record its new filesystem
inode rather than claiming the old inode survived restoration. Then run:

```sh
python3 campaign/successor-022/qualify.py finish \
  --output /absolute/new/qualification-prospective
python3 campaign/successor-022/qualify.py export \
  --output /absolute/new/qualification-prospective
```

The export is audited from its own source with the original absolute historical
source temporarily unavailable. This tests portable key-free reconstruction. It
is not a download of a published release. Use the same setup command with
`--arm permanent_control` and a different output directory for the matched term
regime control. Keep each business and seed separate.

The inherited fixed-terms recycling comparison remains available:

```sh
python3 -m connected_enterprise comparison \
  --config examples/native_capital020/central.json \
  --output /absolute/new/recycling-comparison
python3 -m connected_enterprise scoreboard --output /absolute/new/recycling-comparison
```

That control disables receipt financing. It is an ablation, not the strongest
conventional financing arrangement. The term-regime comparison and the financing
ablation answer different questions; neither establishes empirical buyer demand,
legal enforceability, frontier-model economics, annual profit or invention
compounding. The US$3 billion trailing-year profit target remains open.

## Local regression commands

```sh
python3 -m unittest tests.test_connected_checkpoint_anchor -v
python3 -m unittest tests.test_connected_operating_upgrade -v
python3 -m unittest tests.test_native_claim_source_upgrade -v
python3 -m unittest tests.test_native_source_upgrade -v
python3 -m unittest tests.test_connected_engine -v
```

The legacy test closures are byte-bound copies from `9facd934` and `10bdb2` under
`historical/successor022`; they support tests and historical verification and do
not require a populated Git object database. Shared author, model, host and tools
limit independence. Canonical replay and separate checking code provide local
engineering evidence, not independent external certification.
