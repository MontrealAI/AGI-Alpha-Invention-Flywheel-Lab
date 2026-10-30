# Independent seeded channel authority

The prior checker treated a claimed activation event as sufficient channel
activation authority. The preserved standalone forged-history fixtures show that
reliability zero could still claim activation and two exposures, and realization
zero could still claim reach. These are engineering counterexamples without a
financial account or business run.

The independent audit now reconstructs activation, bounded retries, failure
remedies, expiry, slot realization, overlapping audience ranking, deduplication,
contact cooldown/fatigue, supplier tranche limits and all final counters from the
frozen seed, contracts, purchases and finite buyer population. It uses its own
hash/draw implementation and does not invoke ChannelBook.expose or producer draw
helpers. Exact daily records, contact histories, per-plan event sequences and
causal processing-day order must match. Existing structural checks remain.

Complete channel audit requires the seed and contracts explicitly; existing
fixtures now supply their known values. Generic skipped-day clients remain
supported. Complete business audit additionally requires exactly the frozen
horizon's canonical exposure-day keys, preventing extra calendar rights. The
producer, financial ledger, prices, costs and default policy remain unchanged.

The read-only original package scan verifies each of eight source-bound result
hashes and reconstructs their channel histories successfully. Original source abc
and its achieved outcomes remain historical evidence, not current-source release
qualification. Composed release checks remain required separately.
