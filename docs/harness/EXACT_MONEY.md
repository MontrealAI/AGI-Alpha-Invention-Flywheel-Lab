# Exact money for fresh native accounts

New scaling runners should use the explicit fresh-account constructor:

```python
from connected_enterprise.engine import fresh_account_config, run_world
cfg, registered_manifest = fresh_account_config(prepared_manifest, root=repo)
# Declare finite market, cost and horizon inputs in cfg before execution.
result = run_world(repo, registered_manifest, cfg, seed, world, NEW_ACCOUNT_PATH)
```

The constructor defaults to `exact-permanent-v2`. Supply a validated
`prospective_policy` to select `exact-prospective-v2`; finite liability and risk
assumptions remain explicit, not guaranteed insurance. Both modes use exact
Python integers and existing text-valued native storage without an arbitrary
per-action monetary ceiling. Config and manifest are copied and source-checked.

This is a **new-account registration**, not permission to change a persisted
account's engine, history, source identity or obligations. Historical
`default_config()` and explicitly registered legacy versions remain unchanged;
old pinned engines retain their historical limits. Existing runners must adopt
the new constructor deliberately: this patch does not silently upgrade them.

The controlled tests reconcile payments, complete incurred costs, tax, retained
claims, recovery and a full 365-day accounting window above $100 billion and
beyond signed 64-bit amounts. These are exact-arithmetic engineering controls,
**not evidence of that much profitable demand or achieved commercial profit**.
JSON/text payload limits and actual memory/time limits remain. Ordinary
floating-point economic forecasts and optional diagnostic cash bounds are not
made globally exact or unbounded by this native-money patch; qualify the separate
rational planner before making exact large-scale decision claims.
