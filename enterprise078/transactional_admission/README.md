# Transactional delivery and admission boundary

## Live source delivery increment

`snapshot.deliver(source, destination, identity, events)` now constructs a portable
database and derived CSV from a live committed WAL source using ordinary SQLite
online backup. It opens the source read-only, projects only the destination,
validates exact bytes with the existing typed checker and atomically publishes a
new directory under a POSIX publisher lock. An existing destination is refused.
Wrong commissioned input or interrupted acceptance publishes nothing. This does
not change the original account or grant native catalog admission.

Registered at `fad21fecfeae75ed9a695cc5389531a46c8513c1`; seven finite development
tests pass, including100,000 actual records, held writer connection/nonempty WAL,
later source append, refusal, acceptance exception and publisher exclusion.
See [the measured delivery receipt](../evidence/LIVE_SNAPSHOT.json). The produced
database has a new byte hash, as expected for a distinct backup; the original
published database bytes remain untouched. These tests do not establish bounded
latency under sustained concurrent writing or physical power-loss durability.

```sh
python -m unittest enterprise078.transactional_admission.test_snapshot -v
```

This removes a real delivery limitation of the selected SQL/CSV route: requiring
an offline, checkpointed input. Strong conventional SQLite backup is both the
implementation and comparator; no advantage over that method is claimed. This
is a supporting productive capability, not admission of a new Blue Sky flagship,
market demand, a financial transition or a profit result. Full construction and
commercial cost remain unknown. Do not expand this supporting work into a generic
database platform before qualifying the original-history catalog transition and
complete voluntary offer.

The new type is `enterprise078/transactional-database-and-derived-csv/v1`.
`contract.request` binds exact synthetic input, requested projection and output
columns. `contract.accept` validates a private temporary copy of exactly the
database/CSV bytes it hashes, against the existing independent Python reference
and SQLite integrity check. It rejects a live, nonempty WAL as a portable delivery.
This is ordinary SQLite reuse, not a discovery or general database migration claim.

The actual original 100,000-record output passes this typed contract with the same
database and CSV hashes. See `../evidence/TRANSACTIONAL_TYPED_RECEIPT.json`.
The inspected original hosted artifact is preserved byte-for-byte at
`../evidence/transactional-hosted-original.zip`, SHA256
`4b1ce6f48ce0a0a74e0e7ec5be16391eec584508f922cc19f139628c8f356ec1`.
It contains only the previously inspected public receipts and delivered outputs,
not signing authority. Retaining this requested original evidence prevents hosted
retention from removing the only original largest delivery.

## What admission means here

There is **no native catalog transition yet**. Neither a successful checker nor
an authored positive quote permits the immutable laboratory account to sell this
different service. `offer.compare` is read-only and always reports that dependency.
It cannot accept a caller's boolean claiming a transition succeeded. It explicitly
checks voluntary consent, budget, stronger outside option, every complete-cost
category and whole-delivery funding from present available earnings. Unknown cost
is `None`; no future income is spendable. Its conditional surplus is a conservative
authored downside-price comparison, not recognized accounting profit, forecast
`expected_net`, calibrated demand, or a reserve-to-expense conversion.

`authority.open_existing` requires an existing original tape, persistence proof,
journal and signing authority before entering canonical `BusinessAccount` /
`JournalAccount` / adaptive `Account`. It does not read out keys. Canonical POSIX
ownership, source, manifest, HMAC and full native replay remain authoritative.
Fresh test fixtures are explicitly labeled `TEST_ONLY_NOT_CONTINUATION` and never
copy an old balance. The fixture's $100 incurred loss is preserved across refusal
and reopening. This helper does not migrate sources or support hostile filesystem
custody. No original financial operation is performed by qualification.

## Reproduce bounded development checks

The finite protocol was published before implementation at
`90f25c850dd52481dcc553371ce8839fb20af684`.

```sh
python -m unittest enterprise078.transactional_admission.test_admission.NativeBoundaryTests -v
python -m unittest enterprise078.transactional_admission.test_admission.DeliveryTests enterprise078.transactional_admission.test_admission.CompleteOfferTests -v
```

Fifteen tests cover six native boundary controls, actual typed output, incorrect
type/input/DB/CSV, live WAL, and complete-offer refusal. The first full local suite
had one test error: its corruption fixture kept a SQLite connection open, so the
correct live-WAL guard rejected before row comparison. The test now closes that
connection before inspecting the persisted corruption. No guard was relaxed;
the failure and subsequent exposed development rerun are retained in the receipt.
Eleven existing staging/platform tests also passed locally. Hosted exact-head
qualification remains required; these local checks are not a release.

## Consequential arrangement and strongest alternatives

The selected useful outcome is an exactly accepted transactional database plus
derived portable CSV. Alternatives remain: a commissioned human/conventional SQL
delivery; internal SQL with mature Flyway/Liquibase migration controls; and no
purchase. All retain normal automated SQL speed and full delivery/support costs.
No measured human-versus-AI productivity or demand advantage is established.

SQLite's [backup API](https://www.sqlite.org/backup.html) is the suitable ordinary
mechanism for a coherent portable snapshot of a live database. Flyway's
[validation](https://documentation.red-gate.com/flyway/reference/commands/validate)
and Liquibase's [checksums](https://docs.liquibase.com/community/user-guide-5-0/what-is-a-changeset-checksum)
already protect migration history identity. They are strong mechanisms, not
evidence of this enterprise's reachable customers. No subscriptions were purchased
and no comparative product benchmark was run.

The 15-category one-unit cost vector in tests is only a deterministic sensitivity
fixture. Actual construction, model/host, distribution, delivery, correction,
capacity, financing, tax and liability costs for a commissioned offer remain
unquoted/unknown. There are zero SQL/CSV customer offers or booked sales. The
original complete-cost result cannot be updated by treating this new work as free.

Next: the financial owner must independently qualify an explicit append-only
typed catalog transition on fresh fixtures, preserving the old native prefix,
original manifest and authority, before original-history operation. Then obtain a
complete authored voluntary offer and justified downside funding scenario. Do not
rename lab jobs, pass invented positive `expected_net`, or infer willingness to
buy from capacity-skipped contacts in PR176. When the strongest ordinary complete
arrangement wins, retain that verdict.


## Complete buyer choice and prospective planning

The separate repair registered in `WHOLE_BUYER_CHOICE.md` addresses independent
[PR178](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/178).
`intent.evaluate` is now explicitly **retrospective**. Every buyer needs an exact
subset receipt containing joint gross value, four labeled outside net utilities,
whole-package consent and a quote bound to each offer's price and `terms_id`.
Individual values/consents are not joint evidence. Missing evidence refuses;
complementary complete packages may qualify even when their parts do not.
Partner participation likewise binds the exact partner package and contract.
The deliberately failing old comparator is preserved byte-for-byte only as a
source-hashed test control; do not use it for decisions.

`planning.plan` is the separate prospective interface. Offer rows contain only
id, buyer, price, terms_id and optional partner. Each registered scenario contains
buyers, exact-package partners, collection_lower_bounds, complete package costs
and assumptions_known_at. `costs` maps `choice.subset_key(full_bundle)` to all 15
cost categories, including shared coordination, partner compensation and tails.
No current receipts finance upfront commitments. Unknown bounds/costs refuse.
It selects one fixed bundle by worst-case complete net across all scenarios, with
no-entry winning ties. It cannot select a different action after discovering the
realized scenario. Realized collected/accepted fields and future-dated assumptions
are rejected. Lower bounds, timestamps, utilities and consent remain supplied
**authored assumptions**, not authenticated customer evidence or future guarantees.
Do not relabel forecasts or hindsight observations as predecision bounds. Each
per-offer lower bound must hold in every registered package containing it; use
distinct offer/contract IDs for package-dependent payment assumptions.

Every candidate is a mutually exclusive proposed arrangement, not a simultaneous
menu, an equilibrium, or an incentive-compatible mechanism. `terms_id` must name
the complete payment, fulfillment, risk/refund and partner-obligation contract;
a new obligation needs a new identity and refreshed participant evidence. The
utility model uses nonnegative exact microUSD equivalents. All named alternatives
must have a net utility or explicit `{'available': False}`; no-purchase remains
available. Actual availability and all economic assumptions need independent
support before practical reliance. Partner compensation enters complete costs;
the quote's price is the buyer price, not an inferred partner payment.

Focused reproduction:

```sh
python -m unittest enterprise078.transactional_admission.test_intent enterprise078.transactional_admission.test_choice -v
```

The first local focused run passed 38 tests. Independent implementation review
then found blanket partner acceptance and insufficient package-cost expression;
both were repaired before publication of implementation, adding two regressions.
The revised 40 focused tests pass; independent re-review found no further
substantive issue within the declared assumption model. The combined focused,
delivery, complete-offer, capacity and snapshot suite passes 66 tests. An earlier full discovery ran 66 tests: 64
passed, two could not materialize the historical 306-file science because the
low-disk sparse checkout lacked unrelated frozen files. This is a local coverage
blocker, not a source-guard waiver; full exact-head hosted qualification remains
required. No original account, finance source, historical outcome, PR174 owner
branch or PR178 reviewer branch is changed. Native activation is still missing.
