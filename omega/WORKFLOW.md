# FLYWHEEL Ω: buyer workflow and native commercial experiment

This edition constructs a finite experiment policy, exercises its production
path, independently checks its output, and operates a conditional seller through
the existing native financial account. It has not established Super Alpha,
physical commissioning, observed demand, or actual complete-cost profit.
The original failed verdicts and original seller account remain preserved.

## Install and run the buyer workflow

Use Python 3.12 and the pinned `omega/requirements.txt` dependencies in an
already authorized environment. Linux/Python 3.12 is tested. macOS, Windows and
a finished consumer installer are not qualified. This workflow uses deterministic
local computation; no model installation, key, network or paid API is required.

```sh
python -m pip install -r omega/requirements.txt
python -m omega.process example > /tmp/omega-request.json
python -m omega.process new --request /tmp/omega-request.json --session /tmp/omega-buyer-NEW.sqlite
python -m omega.process observe --session /tmp/omega-buyer-NEW.sqlite --action-id probe-1 --experiment a --value 1
python -m omega.process accept --session /tmp/omega-buyer-NEW.sqlite --action-id accept-1 --recipe a --yield-value 10
python -m omega.process status --session /tmp/omega-buyer-NEW.sqlite
```

The authored example has four possible process mechanisms that passive
observation cannot distinguish. The supplied active observation selects recipe
`a`: observation costs4 modeled cents and production18, totaling22 on this path.
The complete policy's worst admitted path costs31 cents. These are abstract USD
model units, not physical measurements or industrial cost estimates. A competent
conventional constructor reaches the same result.

The session database contains no seller account or seed. Repeating an identical
action ID returns its checked receipt; a changed payload is rejected. Reopening
the same session recovers prior events. A changed request needs a separate
session and fresh acceptance. An unrelated existing database is rejected without
modification. Local SQLite recovery assumes trusted local filesystem custody.

An observation outside the admitted family stops with `MODEL_MISMATCH`; a low
production yield produces `PRODUCTION_REJECTED`. A real mechanism can match all
supplied probes yet fail later, so finite-model acceptance never qualifies nature
or physical operation. CLI observations are supplied inputs, not authenticated
physical measurements. The independent simulator/checker is separate from the
candidate constructor.

To decline while the workflow is waiting, or get documentation-based help:

```sh
python -m omega.process decline --session /tmp/omega-buyer-NEW.sqlite --action-id stop-1
python -m omega.process help MODEL_MISMATCH
```

Declining preserves incurred modeled costs and stops further work. The local
helper retrieves and hashes actual `PROCESS_HELP.json` entries, diagnoses known
cases, and leaves unknown problems unresolved. It is a deterministic helper,
not an unbounded language-model support promise.

## What the buyer supplies and what this edition cannot do

The buyer supplies a precise outcome, legitimate input rights and consent,
consistent units, a justified model family, observation/recipe predictions,
acceptance thresholds, resource limits, and a credible independent way to check
real outcomes before deployment. A vague ambition cannot supply those facts.

The finite constructor accepts at most8 models,8 experiments,8 recipes and4 new
observations, with a100,000-state computation safeguard. Exhaustion is not proof
of impossibility. A declared32MiB route preflight is an envelope, not a universal
measured memory guarantee.

Hardware amortization, electricity, latency, model capability/context limits and
reliability remain buyer costs. The implemented route is deterministic local
computation. A local-LLM request reports unavailable. An external route requires
explicit data/cost authorization, then reports that its provider adapter remains
unimplemented. No silent routing, spending, key retrieval or provider fallback
occurs. Only public authored fixtures and generic code are retained for reuse;
no permission to retain private customer information or intellectual property is
implied.

## The optional offers

All prices below are **USD model assumptions**; commercial currency is unresolved.

| Offer | Defined scope and deliverable | Modeled founder burden |
|---|---|---|
| GENESIS, initially$299 once | Defined edition, guided setup, actual first workflow, documentation and diagnostics. No continuing updates, personal support, earnings or unlimited-AI promise. Five software prices$49/99/149/299/499 compete in the simulation. | No assumed manual delivery. Exceptional mandatory remedies remain possible. |
| 101 webinar,$99/person | Optional orientation and bounded group questions via hypothetical Zoom/Eventbrite configuration; at most500 attendees, without assumed demand. |180min preparation+90presentation+60administration per selected session. |
| Private session,$20,000 | Review one decision from a qualified brief and evidence;30-minute conversation plus concise decision/next-test note. No deployment, guarantee, continuing advice or unlimited follow-up. |15min prerequisite review+45preparation+30conversation+15note/administration. |

Sessions are fictional attendance/outcome models and deliberate human-service
exceptions. A private session contributes access/review value, not a completed
deployment. A webinar can reduce a bounded learning/setup burden; it does not
replace the productive software or complete outside route.

`omega.product` binds each order to the exact price, request, itemized costs,
budget, complete buyer alternatives and explicit simulated consent. It generates
actual software bytes and independently checks every selected output. All bundle
items must prepare before any payment is released. Nonpayment cancels unfunded
offers. Rejection refunds the entire bundle. A refunded companion invalidates
another item's release. Native event IDs make interruption/restart idempotent;
resolved refunds are separate from completed useful delivery. Settlement remains
sequential and recoverable, not distributed atomic commerce.

The downloaded software bundle is tested by extracting its files and running the
CLI through independently accepted production. It remains a research artifact;
there is no released/licensed GENESIS edition or actual payment.

## Run the seller comparison from the full repository

The seller compares preserving cash, launching existing software, buying a small
information experiment, packaging the process workflow, changing price/channel,
reusing profitable delivery and stopping. The ordinary-reuse comparator has the
same useful code, information, actions and resource rates. The policy is a
public-information receding-horizon heuristic, not a proved global optimum or
market equilibrium. Free core and capable ordinary tools retain full capability.

```sh
python -m omega.market_native register --output /absolute/new/omega-market
python -m omega.market_native operate --output /absolute/new/omega-market --max-steps 1
python -m omega.market_native operate --output /absolute/new/omega-market
python -m omega.market_native audit --output /absolute/new/omega-market
```

Registration requires a clean source checkout. The complete registered comparison
has8 conditional scenarios and6 policies. Each has one independent US$100,000
reference account for all4 operating rounds and the exact365-day endpoint. They
are counterfactual businesses, never pooled and never called a continuation of
the original account. `--development` selects the development cases instead.

Preserve the whole private output, frozen source, account sidecars and identity
for recovery. An existing destination cannot be reset. Interruption before native
initialization may fail closed; it is not recovered by inventing new authority.
Supported checkpoints and settlement interruptions resume the same account.

Only selected actions incur their itemized task, channel, delivery and obligation
costs. Native funding checks occur before spending; future collections never
finance current action. The exact annual result separates revenue, collections,
incurred/paid expenses, modeled tax, reserves, payables, available cash and noncash
founder opportunity cost. Resource quantities/rates, values, acquisition, trust,
tax and security envelopes are authored assumptions, not measured bills, demand
or legal sufficiency. Actual complete profit remains unknown. Founder minutes
constrain capacity/cost; timestamps are simulated technical delivery events,
not measured human schedules or actual Zoom appointments. No repeat purchases
or referrals are assumed.

The separate command `python -m omega.qualification_pool` executes the compact
shared-qualification discovery. Its4 feasible arrangements and8 non-entry cases
all tie an unrestricted ordinary organizer. They are prospective planning
calculations, with zero native accounts/postings and no physical coalition.

## Original-account boundary

The preserved historical experiment recorded US$100,000 seed, US$24,800 modeled
expenses, US$75,200 cash and no sales over[0,8760). Its unconditional cost schedule
is a failed experimental design, not measured market spending or optimal strategy.
The authenticated original account is absent from this checkout. The inspected
saved lifecycle archive is explicitly a separate US$1,000 engineering fixture.

The native commercial adapter now operates, but it cannot manufacture original
custody. Keep the original identity, costs and obligations; never copy its balance
or call a reference runner a recovery. The US$3billion primary objective remains
unestablished. Positive profit is distinct from spendable cash; native tests
reject protected-cash spending and stale competing reservations.

## Rights and release boundary

No verified root license, contribution grant or whole-repository redistribution
permission was found. No license is changed. `THIRD_PARTY.md` and pinned component
licenses identify Apache-2.0 material; dependency rights do not license the entire
repository. A real distributable edition requires the owner's root grant,
contribution provenance and complete dependency-specific notices.

The proposed free core remains useful; no deliberate breakage or mandatory fee
for rights already granted is introduced. Eventbrite/Zoom eligibility and actual
fees, taxes, consumer terms, security obligations and storefront delivery need
qualified live configuration before a launch. The no-support/no-update commercial
preference does not remove mandatory obligations.

See the repository campaign's protocol, paper-application map, prior-art comparison
and source-bound result at `campaign/omega-strategy-20261103/`. Publication is a
reviewable draft, distinct from adoption, merge, release, real commerce or a
qualified physical breakthrough. The bundle contains this guide; campaign files
and the full seller/account source belong to the repository, not its small buyer
package.
