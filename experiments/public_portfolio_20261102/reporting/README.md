# Read-only R2 financial reporting

`generate.py` reads explicit JSON files beneath a supplied `public/` directory. It imports no financial runtime, opens no account, follows no recovery/signing path and writes no input. Symlink escapes are rejected. Data include the existing public native summaries and exact 365-day observers, rather than a newly calculated company ledger.

Final generation requires the full `RESULTS.json` plus all 110 registered case results. It produces only standalone SVG figures, `REPORT.md` and `CLAIMS.json`. Amounts remain integer microUSD in the claims file; SVG coordinates are floating-point USD for display. The report does not add separately seeded company profits, count initial equity as profit, annualize short cohorts, infer actual demand or change any scientific qualification.

```bash
python -m pip install --only-binary=:all: -r experiments/public_portfolio_20261102/reporting/requirements.txt
python experiments/public_portfolio_20261102/reporting/generate.py --public /absolute/evidence/public --output /absolute/report
```

An optional `--preview` reads only already completed public cases and writes explicitly named exploratory files outside the repository. Missing cases are not filled with zero and no final campaign conclusion is warranted. The canonical `REPORT.md` and `CLAIMS.json` names are not emitted by previews.

The final modeled operating window is 2028-11-01T00:00:00Z to 2029-11-01T00:00:00Z, start inclusive and end exclusive. Cumulative company profit, final exact trailing-year profit, cash, available cash and protected cash remain distinct. Protected cash is the native cash-minus-available difference, not an additional expense; no potentially overlapping reserve components are summed.

The finite capital/frontier display compares native records, not new financing or an optimal enterprise. R1's failed 25-case source-closure prefix is preserved separately; R2 is a source-qualified engineering reproduction, not a continuation using R1 funds or fresh blinded market calibration. Producer audit acceptance shown by this report does not replace independent financial replay. All five scientific limits remain; no human-baseline, physical, industry-creation or actual-commerce claim follows from the plots.
