# Source-contract warehouse wave construction

The included agent generated `wave.py` from the public OR-License `19_wave`
requirements, input schema and original client verifier/evaluator. This is actual
agent development followed by deterministic CPU software execution. Python has
no frontier-model callable, simulated generator or model-weight editing here.
Standard max-flow, MILP and local search are ordinary algorithms; no algorithmic
novelty or retained-method advantage is claimed.

The primary source case was inspected for schema and counts only before freeze:
2,101 orders, 30,547 SKU lines, 132 integer slots, two eligible slots per order,
five waves per slot, four orders and 10,000 lines per wave. The largest order has
110 lines and the four largest orders together have 400. The source input hash
is `c922e1b892b4bb62e9080e94013f9e66ff0b8a7df2c42ac6f2b47a82aecb30f8`.
No case08 primary assignment, source expert solution, ORSIM or K2 input was read
or executed by this constructor author during development.

The executable procedure first checks exact input types and invariants. For each
slot it sums the largest four eligible order line counts. When that sum fits the
line limit, every cardinality-legal group fits the line limit. Feasibility then
reduces exactly to ordinary bipartite maximum flow: one unit per order, edges to
its eligible typed slots, and slot capacity `max_waves * max_orders_per_wave`.
Grouping each slot's assignments into at most four orders yields no more than its
wave quota. If the sufficient line-capacity condition fails, the code uses an
ordinary wave-indexed binary MILP with exact per-wave count and line constraints.
A solver's unresolved outcome is not labeled proven infeasible.

The initial assignment is grouped for SKU overlap, then improved by ordinary
eligible order moves and swaps. Every accepted move strictly reduces an integer
sum of wave SKU-union sizes, so descent terminates. The result is a local optimum
for that neighborhood, not a proof of globally best overlap. Exact coverage,
typed eligibility, wave cardinality/lines and slot wave quota are checked again.
The original client must accept the final delivered artifact separately.

`build(data, retained=None)` returns `(artifact, trace)`, while `construct` returns
the artifact alone. The CLI takes `--input`, `--output` and `--trace`. Construction
trace records attempted methods, applicability, solver status when used, local
search improvements, exact objective, artifact digest, CPU, wall time and peak
RSS. Unknown actual billing stays null. No paid APIs or GPU resources are used.

The retained executable instruments are `canonical_identity`, `exact_cover`,
`canonical_contract` and `validate_wave`; `RETAINED.json` contains their source
digests, applicability and failure lessons. The JSON is metadata rather than an
interpreted learner. The optional retained argument records its presence; input
properties select the algorithm. Ordinary comparison receives the same software
and substantive content.

Small structural development included residual reassignment in max-flow,
integer-versus-string slot identity, Boolean rejection, a Hall-capacity failure,
binding-line MILP feasibility and infeasibility, disjoint eligibility, duplicate
and missing orders, wrong slot type, five-order rejection, and strict overlap
descent. Twelve substantive fixture checks passed. One additional acceptance
attempt misfired: running the public `verifier.py` wrapper as a CLI only imported
it. That zero exit was not acceptance and is retained as a failed attempt. An
explicit `verify()` and `evaluate()` subprocess on the same small fixture then
accepted it with score zero. A review counterexample then reproduced an overflow
for an enormous positive integer quantity, which the original source permits.
One code correction restricted finite-float checks to floats and added CLI
JSON/I/O failure traces. The repaired integer fixture passed both construction
and original-client verification; malformed JSON produced an explicit failure
trace. There was one initial implementation and one review-driven correction.
All sixteen attempts and measured resources are retained in `RETAINED.json`;
the earlier import-only child's CPU was not
separately captured and is explicitly unknown.

An independent child agent reviewed only `wave.py`, without source data or K2.
It found no core feasibility or scoring loophole and confirmed the local-only
optimization claim. This review does not replace original client acceptance.

K1 wave matching and SKU batching do not solve irreversible routing. Exact
identity or coverage checks may transfer only when the successor independently
revalidates what entities, timing, eligibility, capacity and output acceptance
mean. An imported check does not establish causal necessity, a new productive
frontier, market demand or the $3 billion profit milestone.
