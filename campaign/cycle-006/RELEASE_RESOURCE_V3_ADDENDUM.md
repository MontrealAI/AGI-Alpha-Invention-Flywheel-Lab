# Release addendum: qualified resource supervisor V3

This addendum supersedes active use of `experiments/resource006.py` for resource
supervision. Its original bytes, SHA-256
`8a59559fd1d02af280719dabf6499295afd82f23a36a812d0d7c757dee82f6d5`,
remain preserved under the unchanged scientific source freeze. Earlier receipts
and failures retain their original meanings; they are not rewritten as V3 runs.

Independent reproduction established two consequential defects in V2:

| Finding | Observed result | Replacement behavior tested |
| --- | --- | --- |
| P1: supervisor SIGTERM | Supervisor exited with signal 15 while its worker remained live; the pending record had no terminal receipt. | V3 handles catchable SIGTERM, terminates and reaps its owned worker, and records an interrupted outcome. Initialization and ownership transitions block those signals until their records are consistent. |
| P2: fast exit after excess output | Receipt said `complete` for 15676 bytes against a 10000 byte storage limit, while settlement blocked the ledger. | V3 checks terminal aggregate output, individual files and the receipt itself before declaring completion; the reproduced overrun returns a nonzero CLI result and blocks further reservations. |

The source-bound replacement is
[experiments/resource006_v3.py](../../experiments/resource006_v3.py), SHA-256
`8a10193e2cc29ca277560c7b2153d616e8cb46e64fbc7f54c102518dc2b71cbd`.
Its executing interface remains
`run(command, output, ledger, run_id, limits, cwd=None)`. The active
`run_cycle006.py` imports V3 explicitly and reserves 240 CPU seconds for its
bounded reproduction. It uses the existing resource ledger and allocation;
there is no new budget or competing accounting system.

The recorded qualification executes five V3 regressions and five CLI boundary
regressions. These include an actual SIGTERM sent to a supervisor with a live
worker, a pending initialization signal, and a deterministic schedule where the
first child observation already sees exit while real output exceeds the limit.
The final source-matched whole-chain reproduction and public CI are separate
receipts; this addendum does not substitute the older V2 archive test for them.

Exact original adjudications, replacement identities and qualification receipts
are linked in [RESOURCE_SUPERSESSION.json](RESOURCE_SUPERSESSION.json) and
[RESOURCE_WRAPPER_V3.md](RESOURCE_WRAPPER_V3.md). V3 is a trusted-command
supervisor, not the generated-program sandbox or a complete process-tree CPU
meter. The existing sandbox still confines generated arithmetic. Complete
monetary costs remain unknown.

This operational repair changes no protected scientific outcome, acceptance
threshold, commercial admission or earned-funding verdict. Both scientific
pilots still fail their declared advantage criterion; ordinary reuse still ties
inheritance, and commercial success remains unestablished.
