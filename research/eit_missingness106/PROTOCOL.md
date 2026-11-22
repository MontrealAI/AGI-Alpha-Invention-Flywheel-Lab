# EIT106 — prospective, source-locked independent diagnostic of rejected physical CSV

**Freeze before running this diagnostic or inspecting new CSV data.** Base: `main` commit `de9546ef9083f64a25186f1c5163e3a3a4eaeae5`. Separate research branch; no edits to the source or workflow of EIT105 owner PR #309, and no writes to the original signed financial account.

## Why this exists

The third-party, independently measured SpectraEIT 16-electrode PETG record [Zenodo 7192883 v1](https://zenodo.org/records/7192883) is a potential new observation channel, distinct from the already exposed FIPS EIT 21 specimens. EIT105's **original strict finite-only source preflight FAILED** on physical `NA` values (run 42551099436); its explicitly separate, prospectively registered masked interpretation **also FAILED** in run 42551635036 at `INVALID_OR_EMPTY_MEASUREMENT`, after 23/23 ordinary and 23/23 optimized synthetic checks succeeded. Both remain failures. Unknown source tokens cannot simply be renamed as measured data or accepted physical channels.

## Registered independent question, fixed inputs and one-shot stop

What *kinds* of CSV cell representations are actually present at the original rejected source, and how many channels/rows do they affect? This **diagnostic is not a validator** and does not make EIT105 pass.

* Download exactly `circle_petg.csv`, Zenodo v1, official upstream MD5 `262a968766cd034914155ac2bfcd121e`; require nonempty <=15,000,000 bytes; retain independent SHA256, actual length and source URL. Refuse changing bytes, oversize, missing headers, duplicate headers, malformed rows, invalid electrode indices and >250,000 rows.
* Inspect only rows explicitly labeled `measurement`. Keep original 16 `E_01` through `E_16` voltage columns and excitation electrodes 0–15. Classify cells **without imputation** as finite numeric, exact `NA`, empty string, whitespace-only, padded `NA`, padded finite numeric, nonfinite numeric, or other text. Report exact aggregate counts by category, channel, injection/non-injection location, number of affected measurement rows, min/max actual finite voltages per row, and number of distinct injection pairs. Never print raw voltages, arbitrary unidentified text or row-level data.
* Make at most **one source fetch per hosted execution** with a 90s network timeout; no alternate file, retries, new seeds or adaptive thresholds. Stop after processing the source once, whether or not the result is unfavorable. Tests use authored synthetic rows only and run under ordinary and optimized Python.
* The acceptance condition is successful *identity-verified diagnostic coverage*, **not** a physical/acquisition/commercial pass. If source verification or parsing fails, record a failure without relaxing this protocol. An empty/space token, if found, remains an unmeasured/invalid input until separately specified evidence and a prospective new protocol justify a masking rule; no silent coercion.
* Record executable source revision, immutable upstream identity, diagnostic counts, original failed run IDs, all new failures and wall/CPU process measurements if available. Actual cloud/model dollar billing stays UNKNOWN.

## Commercial and scientific separation

Compare a future accepted interior-property decision against ordinary/specialist full-injection EIT, self-service and no measurement, using genuinely withheld physical specimens, actual injection counts, independent acceptance and complete costs. Here: **0 newly acquired physical specimens, 0 buyer acceptances, 0 collections, 0 financial accounts operated; P0 remains under separate exclusive custody; NO BID / NO DEPLOY**. The fact that metadata and CSV can be diagnosed does not evidence a viable business, paid demand, earned investment, improved discovery or the US$3B trailing-365-day profit objective.
