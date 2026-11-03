# FLYWHEEL Ω: an executed experiment and seller-workflow prototype

This continuation constructs an experiment policy, executes it against a declared
process simulator, checks the useful output independently and exercises a
simulated seller lifecycle. **It has not established Super Alpha, physical
commissioning, demand, a fully autonomous business or complete-cost profit.**
The original water experiment and seller account remain unchanged.

## Start locally

Use Python 3.12 from this repository checkout. The buyer process constructor is
deterministic; no model, API key, network connection or model installation is
required. The existing scientific/accounting dependencies are pinned in
`omega/requirements.txt`. Install them only in an already authorized environment:

Linux/Python 3.12 is the qualified environment in this continuation. macOS and
Windows installation and browser interaction are untested. The interface here
is an actual CLI, not a finished consumer installer or GENESIS download.

```sh
python -m pip install -r omega/requirements.txt
python -m unittest omega.test_process omega.test_process_independent tests.test_omega_commerce -v
python -m omega.continuation --output /absolute/new/omega-continuation
```

The output directory must be new. It contains small local workflow databases,
the policy delivered to the simulated buyer and a source-bound `RESULT.json`.
These databases contain **no seller financial account or seed**. The seller
downloads the actual policy bytes; this artifact is a research fixture, not a
released or licensed GENESIS product. No payment is accepted.

The complete run reports 20 candidate/conventional comparisons, eight declared
production journeys, two coverage adversaries, successor controls, six seller
workflow examples and conditional unit/capacity sensitivities. Exact numbers
are reproducible model outputs; host timing is telemetry, not human effort or a
price for computing. No human or independent frontier-model productivity study
has been run.

## Run one buyer journey yourself

The example is an authored finite process: two active experiments distinguish
four mechanisms that passive observations leave ambiguous. All response tables,
costs and target yields are supplied; the product does not discover an unknown
real process from a sentence. The request's consent applies only to local
simulation. It never grants physical-operation authority.

```sh
python -m omega.process example > /tmp/omega-request.json
python -m omega.process new --request /tmp/omega-request.json --session /tmp/omega-buyer-NEW.sqlite
python -m omega.process observe --session /tmp/omega-buyer-NEW.sqlite --action-id probe-1 --experiment a --value 1
python -m omega.process accept --session /tmp/omega-buyer-NEW.sqlite --action-id accept-1 --recipe a --yield-value 10
python -m omega.process status --session /tmp/omega-buyer-NEW.sqlite
```

This supplied observation selects recipe `a`; the observation costs 4 modeled
cents and production costs 18, for 22 cents on this path. The policy's worst case
across all four admitted mechanisms costs 31 cents. Values are abstract authored
USD units, not industrial measurements, supplier quotes or full economics.

Repeating an identical action ID returns its existing checked receipt. Changing
its payload is rejected. Reopening the same session with `status` recovers its
events without another observation. A changed request requires a distinct
session and new acceptance; it does not migrate the old result. Existing
unrelated databases are rejected without modification. SQLite recovery assumes
trusted local filesystem custody; this is not signed third-party certification.

If the next observation is not predicted by any remaining model, the session
stops with `MODEL_MISMATCH`. If the actual supplied production yield is too low,
it returns `PRODUCTION_REJECTED`. A mechanism outside the supplied family can
match every probe and still fail production. A model-valid policy does not
establish that nature belongs to the model family. The simulator's independent
checker uses its own response/yield oracle; CLI values are explicitly supplied
observations and are not authenticated physical evidence.

To decline while a session is still waiting:

```sh
python -m omega.process decline --session /tmp/omega-buyer-NEW.sqlite --action-id stop-1
python -m omega.process help MODEL_MISMATCH
```

Declining blocks further actions and preserves already incurred modeled costs.
The local helper retrieves actual `PROCESS_HELP.json` entries, hashes that
documentation and leaves unknown issues unresolved. It is a deterministic
documentation helper, not a tested language-model support assistant.

## What the buyer must supply

- A precise outcome, acceptance target and permission to use the inputs.
- A justified model family, all allowed observations and recipes, and consistent
  units. Missing predictions cannot silently become zero or an assumed fact.
- The relevant cost budget, observation capacity and a credible way to obtain
  and independently check real outputs before any deployment claim.
- Their own compatible computer and, for a future model adapter, model resources.
  Hardware, electricity, latency, context/capability limits and reliability are
  buyer costs/constraints; they are not free because processing is local.

This edition accepts at most eight models, eight experiments, eight recipes and
four new experiments in a policy, with a 100,000-state constructor safeguard.
These are declared implementation limits. Resource exhaustion is not proof of
physical or mathematical impossibility. The declared 32 MiB preflight is an
envelope, not a measured universal memory guarantee.

The implemented route is local deterministic computation. A requested local LLM
route reports unavailable. An external route first requires explicit data and
cost authorization and then reports that the provider adapter is unimplemented.
Neither route silently falls back, calls a provider or requests a key. Buyer
external compute routing is a product requirement still to implement and test.
No private customer data is retained for learning; only these public authored
fixtures and generic code are reused.

## Seller operation and optional offers

The seller simulator uses the same optional prices as the prior experiment,
explicitly in **USD as a modeling convention**. Commercial currency is unresolved.

| Offer | Defined purpose and deliverable | Modeled founder burden |
| --- | --- | --- |
| GENESIS, $299 one time | A defined edition with setup, first workflow, documentation and diagnostics; no continuing updates, personal support, earnings or unlimited AI promise. Current downloadable experiment is not yet this complete product. | Exception handling remains possible and must be budgeted. |
| 101 webinar, $99/person | Optional product orientation and bounded group questions; maximum 500 attendees, not an occupancy assumption. | 180 minutes preparation + 90 presentation + 60 administration per modeled session. |
| Private session, $20,000 | Review one decision from a supplied brief and evidence; 30-minute conversation plus a concise decision/next-test note; no deployment, profit guarantee or ongoing advice. | 15 minutes prerequisite review + 45 preparation + 30 conversation + 15 delivery/administration. |

`omega.commerce` exercises explicit consent, failed/unavailable payment test
doubles, capture versus settlement, entitlement, actual copied bytes, onboarding,
self-service, refunds and disputes. Refund/dispute and security obligations do
not disappear because the commercial preference excludes personal support.
Optional sessions are human-service exceptions, not autonomous delivery.

The fixture quotes acquisition, payment, delivery and founder costs and names
remaining unknowns. Fees are authored USD envelopes, not current local provider
quotes. Eventbrite eligibility/fees/refund rules, applicable taxes, Zoom licensing,
the proposed storefront's delivery capability and legal/consumer terms need a
qualified configuration before a live launch. No campaigns, events or storefront
changes occur in this research.

## Economics and the original account

`omega.economics` is a read-only sensitivity calculation, not a ledger. It keeps
buyer gross value/net benefit unknown, separates contribution from full profit,
tests favorable/refund/exception/imitation/adverse conditions, and reports the
orders/traffic/time that assumptions would require. It neither generates
customers nor simulates a financed full year.

The sensitivity model assumes acquisition cost per paying buyer, including
unsuccessful acquisition; the workflow fixture instead charges each explained
offer, including declines. They are explicitly different authored cost bases,
not measurements of a sales funnel. Conversion determines required traffic in
the sensitivity only. No repeat purchases or referrals are assumed.

The original PR #191 report recorded one US$100,000 account with US$75,200 cash,
zero sales and a −US$24,800 modeled result over [0,8760) hours. This is the **last
published historical result**, not a new current complete-cost result. This
continuation's actual costs are unknown and have not been posted.

The authenticated original account/recovery directory is not in the checkout.
`omega.commerce inspect-continuation` can inspect a supplied candidate directory
without creating accounts or keys; content consistency alone does not prove
original custody or authorize continuation. A product-specific native acceptance
adapter is also missing. The sole authoritative account must retain its original
identity and obligations. Never invoke `omega.seller` to replace or reseed it.
Engineering regression fixtures are not business accounts to pool into earnings.

Positive recorded profit does not imply spendable cash. The included read-only
regression retains $1,000 profit while deferring $100 investment when only $50
unrestricted cash is available. Any real native reservation still requires the
original account and its existing mandatory guards.

## Rights and publication

At source `38846ad9…`, no root license, contribution-license agreement, or verified
whole-repository redistribution grant was found. This is a rights dependency,
not permission to label the repository open source. No license is changed here.
`THIRD_PARTY.md` identifies Apache-2.0 notices for the pinned native exchange;
`vendor/alpha_structure/LICENSE` also contains Apache-2.0. Installed package
metadata identifies NumPy/SciPy redistribution notices and cryptography
`Apache-2.0 OR BSD-3-Clause`; wheel-specific bundled notices must accompany any
redistributed build. Those component rights do not grant rights to the whole lab.

The proposed free foundation must remain useful and inspectable; no deliberate
breakage or mandatory fee for existing rights is introduced. A distributable
edition needs the owner's chosen root grant, contribution provenance and a
complete distribution-specific dependency inventory. The current work is an
additive draft on PR #191. Publication is not adoption, merge, release, physical
qualification, customer validation or attainment of the $3B profit objective.

See the [protocol](../campaign/omega-continuation-20261103/PROTOCOL.md),
[three-business comparison](../campaign/omega-continuation-20261103/PRIOR_ART.md)
and the final report in that campaign directory for exact source and results.
