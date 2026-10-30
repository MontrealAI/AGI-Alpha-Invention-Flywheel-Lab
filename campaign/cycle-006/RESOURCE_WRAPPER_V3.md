The active bounded entry point now uses `experiments.resource006_v3.run(command, output, ledger, run_id, limits, cwd=None)`. The frozen `experiments/resource006.py` version remains exact historical evidence and is unsupported for active supervision. Its original documentation remains unchanged because the scientific source freeze includes it.

Independent criticism established two defects in the old version: terminating the supervisor with SIGTERM could leave its new-session worker alive without a terminal receipt, and a fast aggregate-output crossing could be reported as complete even though settlement subsequently blocked the ledger. Original failures and the old executable source are retained. `RESOURCE_SUPERSESSION.json` identifies the receipts and exact versions.

V3 uses the same prospective ledger schema and allocation. It handles SIGTERM in the main-thread API and CLI, defers termination until initialization and worker ownership are recorded, restores the child's signal mask before execution, and makes reaping and ownership updates signal-atomic. Cleanup kills the owned process group and writes an interruption receipt. It checks final aggregate output, individual file sizes and the terminal receipt's own bytes before declaring completion. A detected limit crossing produces `overrun`, a nonzero CLI exit and a blocked ledger.

```sh
python -m experiments.resource006_v3 --ledger /tmp/alpha006-resources.json --run-id NEW_ID --output NEW_DIRECTORY --wall 40 --cpu 20 --memory-bytes 1073741824 --output-bytes 4194304 --storage-bytes 16777216 -- /absolute/path/to/python -c 'print("trusted bounded command")'
```

`run_cycle006.py` imports V3 explicitly and reserves 240 CPU seconds per replay; its nested unchanged historical runner needs a per-process CPU ceiling of at least 180. It still verifies the old V2 identity as part of the preserved original scientific source closure, without using V2 for active supervision.

This is a trusted-command supervisor, not the generated-program sandbox. Per-process limits and waited-child usage do not establish exact aggregate CPU attribution; the original conservative reservation/no-refund rule and unknown complete monetary costs remain. Generated arithmetic programs continue to execute under the independently qualified sandbox. SIGKILL and host-crash durability are outside the handled-signal guarantee.
