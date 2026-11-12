# Ordinary rolling grocery-dispatch control

The ordinary control implements conventional online VRPTW planning directly from
the public task contract. It receives the same visible windows, public customer
attributes, directed duration matrix and prior own dispatches as the treatment.
It may receive all retained K1 information through the supplied state; it does
not execute untrusted retained code or require a novel algorithm. This is a
software control, not a measured human labor or historical client-fee estimate.

## Fixed procedure before source outcomes

At each of the six public hourly departures, form the currently confirmed,
not-yet-dispatched order pool. An order is mandatory now when its solo route
cannot satisfy the service and depot-return windows at the next known departure;
every remaining order is mandatory in the final round. This is ordinary latest-
safe rolling batching, with no forecast from future confirmations. Deferring an
optional order preserves a checked feasible solo route at the next departure;
that check is not a guarantee of future consolidation or optimal cost.

When a current dispatch is required, build complete static partitions of all
currently known pending orders with four conventional constructions: earliest-
deadline cheapest insertion, farthest-first insertion, largest-demand-first
insertion and regret insertion. Choose the cheapest complete partition, then
apply directed 2-opt, cross-route relocation and pair swaps. Every candidate is
checked against capacity, service-start windows, service times, directed road
durations and the depot-return deadline. Dispatch the routes containing mandatory
orders; hold optional-only routes for a later visible pool. No upstream client
validity or objective feedback is consumed during any of the 18 submissions.

The sole source of order identities and confirmations is `window['orders']`.
State records already dispatched identities separately for each day, avoiding
duplicates when later windows repeat earlier confirmations. It contains no
future-order file, day-specific policy table or evaluator result.

## Search and comparison boundary

Each decision admits at most 50,000 full route-feasibility checks and 12
best-improvement passes. Search reserves four checks per currently pending order
for solo qualification, next-departure qualification and final coverage/route
checks; unused safety allowance is not represented as consumed resources. Search
and safety calls, their actual total and budget exhaustion are recorded. These are
finite experiment settings, not a claim of a business-size or mission limit.
Insertion-option counts are also recorded. Cached solo costs and cheap demand
pruning avoid some full route checks; their loop CPU is still execution resource
use, not free labor. A visible pool too large to reserve its safety checks within
this finite allowance produces an explicit failure instead of an uncharged run.
There is no random seed or wall-time-dependent solution selection. The control
uses a self-contained standard insertion/local-search implementation. OR-Tools
was subsequently made available in the task environment; it is not needed by
this frozen comparator, and is not withheld from either arm.

The policy can lose to another competent conventional policy. It establishes no
global online optimum, minimum configuration cost, physical delivery, customer
acceptance outside the source client, privacy guarantee or willingness to pay.
All elapsed compute, development and validation costs belong in the comparison;
CPU time is not fictional human review time.

Pre-freeze development uses small synthetic directed-matrix examples only. The
published order confirmations, hidden client knowledge and expert solutions must
not enter development or policy decisions. A source-data failure after freeze is
reported without retrospective policy tuning.

The full K1 `wave.py` code and retained facts were made available before K2
freeze. Their typed identity, exact coverage and applicability lessons are
ordinary reusable information; K1's slot max-flow reduction does not solve
directed vehicle routing. The ordinary comparator may build the required routing
method directly rather than perform an artificial reuse of that reduction.

Small synthetic development checked an asymmetric two-order route (26 driving
seconds versus 50 for the two solo routes), a capacity-forced separation,
latest-safe deferral followed by required dispatch, repeated cumulative windows,
and duplicate-round refusal. No original K2 order stream or scorer outcome was
read or executed during this development.
