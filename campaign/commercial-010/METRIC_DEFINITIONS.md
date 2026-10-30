# Commercial010 conversion metrics: reporting correction

The immutable raw result field `win_probability` is **settled collections divided by scheduled opportunity slots in executed cycles**. It is not the probability of winning conditional on an arriving buyer. Prices, costs, financial events, verdicts, scenario seeds and raw results are unchanged.

`CONVERSION_METRICS.json` derives all 168 confirmation runs from their archived raw decisions and native orders. Each file hash must match the lossless archive index. The derivation checks decision partition, arrival/participation booleans, native prepare events, released orders, paid outcome counts and actual quality-check receipts.

| Symbol | Meaning | Rate |
| --- | --- | --- |
| N | Scheduled/produced opportunity slots | Denominator for the legacy field |
| A | Buyer arrival decisions | A/N: opportunity arrival |
| W | Participating buyers selecting the offer | W/A: conditional participation wins |
| Q | Native prepared orders after functional acceptance | Q/W: technical acceptance after a win |
| C | Native released/collected orders | C/W: collection after a win; C/Q: collection after technical acceptance |
| C/N | Settled collections per scheduled slot | Exact interpretation of legacy `win_probability` |

A zero denominator is `null` (undefined), never silently zero. Shared keyed random inputs do not force identical arrival indicators after purchase histories diverge: the modeled repeat-arrival propensity depends on buyer state. These are simulated commercial conversions, not observed customer rates. Functional checks are actual scoped replays of disclosed synthetic artifacts and do not establish real-population quality.

For the combined strategic/autonomous-onboarding region: N=288, A=269, W=Q=220 and C=212. Conditional wins are 81.78%; collections/wins 96.36%; settled/slot 73.61%. Fixed pricing with autonomous onboarding has N=288, A=269, W=Q=228 and C=220: conditional wins84.76%, collections/wins96.49%, settled/slot76.39%.

Reproduce from a reassembled lossless archive:

```sh
python scripts/derive_commercial010_conversion.py --source-root <directory-containing-artifacts> --output <new-report.json>
```

The prior paper and exact builder are preserved under `docs/commercial010/history/reporting-v1`. Its earlier display label is superseded by this correction; its numeric results remain unchanged.
