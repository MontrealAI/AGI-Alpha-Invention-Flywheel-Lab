# A real future holdout, not a profit result

This bounded experiment freezes a conventional convex ensemble of public European wind/load forecasts before the delivery interval. It does not establish buyer demand, commercial value, originality, $3B profit, or a better successor. See PROTOCOL.md for the fixed comparison and stopping rule. Attribution: Foretec Energy Bench, https://github.com/ujohn33/foretec-energy-bench and https://energybench.foretec.co/ ; published forecast data CC BY 4.0, https://creativecommons.org/licenses/by/4.0/ . Selected data are transformed into fit matrices and predictions. Code here follows the repository license.

Today’s 12:00 CET market gate had passed before construction. The frozen forecasts are only an independent post-gate accuracy trial, not an official entry or a trading-capable result. The source’s cutoff metadata does not prove our output existed before the gate. Historical labels are revised as read, not a vintage backtest. No secret credentials or paid service is used. Public source operation is not assumed costless.

## Reproduce and score

Requires existing Python, NumPy and SciPy. From repository root:

    python campaign/live-energy093/run.py --snapshots /path/to/first-snapshots --out /path/to/reproduction
    python campaign/live-energy093/audit.py

A new live retrieval may differ from saved source hashes. Exact published fit inputs and future member predictions are preserved in evidence/fit_inputs.json; use the audit for deterministic arithmetic checks. evidence/forecast.json retains all available published point comparators, including newer foundation models, not just the fixed six fit members. `tso_final` is a separately labeled later-information reference, never an eligible incumbent.

After Nov5 delivery finishes (Nov5 23:00 UTC), retrieve issue2026-11-04 JSON to a **new** path and run:

    python campaign/live-energy093/score.py campaign/live-energy093/evidence/forecast.json /path/to/new-actual.json --out /path/to/dated-score.json

Preserve retrieval time, raw bytes, source URL and SHA256 with every score. Partial or revised data are reported, not silently replaced by a final result. No fit step reads the actual snapshot. Completeness is not a guarantee of finality.

After issueNov6 is available, before Nov6 23:00 UTC, construct the retained successor with a **fresh snapshot directory**, so issueNov4 can now carry completed first-trial outcomes:

    python campaign/live-energy093/run.py --snapshots /path/to/new-successor-snapshots --out /path/to/successor --successor-from campaign/live-energy093/evidence/forecast.json

It reuses the exact original fit_inputs.json rows, adding only newly completed issueNov3 and issueNov4. Old-label revisions are not incorporated. It compares updated weights, unchanged parent weights and an equally informed ordinary refit, which should exactly reproduce the updated weights. Score deliveryNov7 after it finishes, with the same independent scorer. Stop after the two delivery days; do not choose replacements to obtain success. Missing authority/source is a blocker, not permission to fabricate outcomes.

## Cost and economic arrangement

The frozen file records process CPU, wall time and bytes in the successful construction stage, not the entire research effort or underlying forecast production. An earlier parser attempt stopped on the legitimate 100-quarter DST day; the repaired runner excludes it from fixed96 training. These development and review costs are not monetized and cannot be zeroed in a profit claim. The data are freely reusable by prospective buyers and competitors.

An optional fee capped by demonstrated avoided forecast loss is only a proposed arrangement. No buyer, willingness to pay, operational tariff, complete cost or qualifying financial surplus has been established. A positive point-error result would merit another independent study, not commercial admission. Equal-information ordinary reuse remains a decisive successor control.

## Executed construction result (Nov4)

Ten series have 13 complete training days each. DK1_load and DK2_load have only four, below the fixed seven-day minimum, and remain unavailable. Therefore the original all12-series primary acceptance criterion cannot pass this trial, regardless of later accuracy. We do not relax that condition. The 100-quarter DST delivery day is excluded consistently from all fits. Ten-series accuracy remains useful descriptive fresh evidence, not a replacement primary win.

Independent alternate LP verification and ordinary equal-information reconstruction pass for all ten constructed series. Ordinary refits reproduce the weights and predictions exactly: retained code/input reuse is useful, but does not establish a unique successor advantage. Seven adversarial scoring tests include a case where restricted primary controls are beaten while a stronger published rival wins. The scorer reports pairwise comparator coverage to avoid hiding incomplete rivals in a common-series macro.
