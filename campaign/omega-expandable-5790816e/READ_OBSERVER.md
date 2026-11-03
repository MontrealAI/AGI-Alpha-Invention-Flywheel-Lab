# Qualified external read-observation continuation

The registered financial runtime, market policy,144 cases and accounts remain
frozen at `6ff45e25a85a590d4921aef6e197148252b92cce`. Its comparison source hash is
`048b4ceb0322a2cd2cbd4c2f9cb9e5cdc2929034e3888a375ad650f8cbe37462`.

`omega/recording_cache.py` is an external observation wrapper, not financial
authority. It reuses repeated snapshot views only between routed mutations.
Every advance, spend and delivery still executes the unchanged native checks.
The original recorder and original independent operating auditor remain in use;
all recorded views must match the actual native financial prefixes.

Five focused tests pass. Matched reference/cached executions have identical
decisions, market state, public trace, financial actions and balances. Tests also
exercise pending-call recovery, delayed collection, source/funding rejection,
copy isolation and detected unrouted mutations. Independent review accepts the
following narrow conditions: exclusive routed mutations, a new proxy on restart,
fresh source/owner checks, refusal after detected bypass, and final full replay.
Hostile same-length in-memory mutation is outside this observer's custody claim;
it does not replace independent full auditing or authorize cached spending.

`resume_verified.py` loads the exact original frozen policy, financial bridge and
auditor, then supplies that observer. It records both source identities and the
previous financial-tape prefix. It does not alter frozen files, regenerate keys,
copy balances, add capital or reinterpret prior outcomes. Already completed
accounts remain untouched. Optional `--max-steps` produces a same-account
operating checkpoint, never an annual result or a market-size limit.

Use only after stopping other writers for these accounts:

```sh
python campaign/omega-expandable-5790816e/resume_verified.py \
  --output /absolute/existing/expansion-confirmation --workers 7
```

This is a performance continuation, not a new economic confirmation or a claim
that the broader native history-scaling problem is solved. A separate segmented
journal candidate is not adopted by this observer.
