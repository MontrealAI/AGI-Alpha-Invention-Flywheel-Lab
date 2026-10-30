# Capacity lifetime bound to financed terms

The original `_check_investments` accepted the published 2610301901 central-growth
trace even after all four paid capacity assets were changed to activate at
purchase and expire 100,000 hours later. The original source hash, result hash,
mutations and accepted helper receipt are preserved in COUNTEREXAMPLE.before.json.
This probe changed an in-memory copy only, without reopening any account.

The independent investment check now requires positive integer lead, duration and
units from the financed work. Lead and duration must match frozen supplier terms;
the existing one-unit-per-day model must purchase one unit. Investment identity,
contract kind, amount and purchase time must match the resource request and native
reserve/finish invoice times. Activation must equal purchase plus financed lead;
expiry must equal activation plus financed duration. Subsequent actual-use and
daily throughput checks remain enforced.

Five focused tests cover valid paid productive use, early activation, extended or
missing expiry, moved purchase time, malformed/boolean/nonpositive terms,
changed frozen terms and invoice/request inconsistencies. The read-only original
eight-world scan finds eight capacity investments and 20 actual uses with zero
violations. The forged timing is rejected in both original growth traces.

The engine, finance authority, costs, public native audit and historical source
records are unchanged. This is narrower than full source-qualified commerce:
original economics and the original CPU qualification failure retain their
identity; the repaired composed source still requires exact-head qualification.

Reproduce the read-only helper scan with:

`python evidence/completion015/capacity-contract-repair/scan_history.py /path/to/original/public-package /tmp/capacity-impact.json`
