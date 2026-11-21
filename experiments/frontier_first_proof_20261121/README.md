# FRONTIER Ω — Two useful decisions from one retained capability

[Français](README.fr.md) · Experiment: 21 November 2026

**We constructed and reproduced two computational decision tools:** a minimum reaction-condition repertoire that preserves recorded yield quality, and a minimum substrate panel that preserves distinctions between catalyst response profiles. Both use the same unchanged, 8,216-byte exact optimization kernel.

This makes a small part of a future automated chemistry workflow usable today: turn published measurements into compact, auditable choices. The first result supplies a concrete condition repertoire; the retained capability then solves a different experimental-design objective.

## 1. First outcome: five complementary conditions

The source contains **960 recorded reactions**: indomethacin coupled to ten aniline nucleophiles under 96 activator/base/solvent combinations. For each substrate, the requirement is at least **90% of that substrate’s best recorded yield**. Five conditions are necessary and sufficient to meet it for **10/10 substrates**. The best single condition covers **4/10**.

| Activator | Base | Solvent | Assigned source substrate IDs |
|---|---|---|---|
| TCFH | 1-Methylimidazole | DMF | n3, n9 |
| TCFH | 2,6-Lutidine | THF | n5, n6, n7, n8 |
| HATU | Diisopropylethylamine | MeCN | n10 |
| TCFH | Diisopropylethylamine | MeCN | n4 |
| DPPCl | N-methylmorpholine | MeCN | n1, n2 |

The [complete result](evidence/first_portfolio.json) supplies substrate names, assignments, recorded yields, individual thresholds, source lines and an optimality certificate. Use it as a reference repertoire and a starting point for planning replication. The source paper supplies the full experimental context; this table lists the varying components.

**Relative yield preservation has important limits.** The lowest assigned absolute yield is **16.59%**. The smallest margin above the required threshold is **0.04 percentage points**. Measurement uncertainty is unknown, so this is an exact guarantee about the recorded table. It does not establish a robust yield guarantee in a new experiment.

## 2. Successor: six probes preserve 253 distinctions

The second tool asks which substrates distinguish ligand response profiles in nickel-catalyzed borylation. In the primary ethanol case, the declared distinction is an absolute recorded-yield difference of at least **20 percentage points**.

The minimum panel is **six of 33 substrates**:

**s10 · s15 · s2 · s21 · s33 · s7**

For every one of the **253 pairs among 23 ligands**, at least one selected substrate preserves that distinction. The [successor result](evidence/successor.json) includes the panel, source-linked yield witnesses for every pair, and its certificate.

This is a compact reference panel for comparing recorded catalyst behavior and planning follow-up measurements. The `s…` labels are the source’s `electrophile_id` values; names and molecular identifiers are available in the [pinned source mapping](https://github.com/doyle-lab-ucla/ochem-data/blob/e739f4d4d2002218fd225de5e8b2e6c235cabd6b/NiB/rxns/inchi_23l.csv). Prospective identification requires comparable measurements, a justified error model and an appropriate reference library. The 20-point separation is a declared resolution, not a calibrated assay-error bound.

## What transferred—and what the comparisons show

[`cover.py`](cover.py) implements known exact set-cover methods and emits independently checkable optimality certificates. The first adapter turns yield requirements into coverage constraints. The successor adapter turns distinguishable ligand pairs into coverage constraints. **The kernel stayed byte-for-byte unchanged** after the [first-asset freeze](evidence/FIRST_ASSET_FREEZE.json); the second tool reused its solving and certificate capability.

| Primary case | Retained kernel | Independent greedy | Independent HiGHS |
|---|---:|---:|---:|
| Amidation, 90% relative yield | 5 conditions | 5 | 5 |
| Nickel / ethanol, 20-point separation | 6 substrates | 8 | 6 |

All **15 declared cases** were completed. Independent source reconstruction, semantic checks and certificate verification accepted [all five first cases](independent/FIRST_FULL_VERDICT.json) and [all ten successor cases](independent/SUCCESSOR_FULL_VERDICT.json). HiGHS and a separate exact implementation agree with every minimum. The executed [equal-content control](independent/WRAPPER_TRANSFER_QUALIFIED.json) reused a separate identical source copy and matched all ten successor results and certificates across five repetitions per arm. The [independent review](independent/REVIEW.md) records 36 rejected semantic/proof tamper cases. These results place this construction alongside capable conventional methods.

The [current complete audit](independent/WRAPPER_AUDIT_QUALIFIED.json) also verifies frozen-code provenance. The [wrapper review](independent/WRAPPER_REVIEW.json) records 16 additional CLI rejection tests, corrections, and the earlier receipts they supersede. [Outcome and lessons](OUTCOME_AND_LESSONS.json) retain the experiment's useful contribution, actual failures, unmeasured costs and missing economic proof.

| First-case retention threshold | 50% | 70% | 80% | 90% | 95% |
|---|---:|---:|---:|---:|---:|
| Minimum conditions | 2 | 3 | 5 | 5 | 7 |

| Successor separation, percentage points | 10 | 15 | 20 | 25 | 30 |
|---|---:|---:|---:|---:|---:|
| Minimum ethanol panel | 3 | 4 | 6 | 9 | 10 |
| Minimum methanol panel | 4 | 4 | 6 | 9 | 9 |

At 30 points, four ethanol pairs and three methanol pairs are indistinguishable even using the full table; the output reports them explicitly. The three input files contain **2,478 recorded rows** in total: 960 + 759 + 759.

The demonstrated transfer was planned: the second problem family was anticipated, and a new adapter used an existing solver. This establishes two usable retrospective instruments and concrete capability reuse. Autonomous economic invention, a superior invention procedure, new chemistry, physical assay savings and revenue remain unestablished. Complementary condition sets and set cover have direct prior art.

## Reproduce locally

Run from this directory with Python 3.12 or later. The core tools and audit use only the standard library. Internet access is needed to fetch the pinned sources; existing files are hash-checked.

```bash
python fetch_sources.py --data-dir data
python portfolio.py --csv data/amidation.csv --output outputs/first.json
python successor.py --data-dir data --output outputs/successor.json
python audit.py --data-dir data --first outputs/first.json --successor outputs/successor.json --output outputs/audit.json
```

The JSON outputs contain the decisions, evidence and certificates. Audit them before relying on a reproduced result. Runtime fields can differ across machines.

For the optional independent solver comparisons:

```bash
python -m pip install -r requirements-comparison.txt
python independent/baselines.py --stage first --source-root data --output outputs/first-baselines.json --repeats 5
python independent/baselines.py --stage successor --source-root data --output outputs/successor-baselines.json --repeats 5
python transfer_check.py --successor outputs/successor.json --baseline outputs/successor-baselines.json --output outputs/transfer-control.json --repeats 5
```

## Sources and interpretation

- **Pinned data:** [Doyle laboratory repository, commit ae3e910…](https://github.com/doyle-lab-ucla/bandit-optimization/tree/ae3e910dcea27cfd1631a28b793b6c63607baedd). Original values, including three negative amidation yields, are preserved. The nickel files are a complete 23-ligand subset of the original study. Hashes, GPLv3 source-license information and calibration caveats are documented in [SOURCES.md](SOURCES.md).
- **Amidation measurements:** Wang et al., *Identifying general reaction conditions by bandit optimization*, Nature (2024). [DOI: 10.1038/s41586-024-07021-y](https://doi.org/10.1038/s41586-024-07021-y).
- **Nickel measurements:** Stevens et al., *Advancing Base Metal Catalysis through Data Science*, Organometallics (2022). [DOI: 10.1021/acs.organomet.2c00089](https://doi.org/10.1021/acs.organomet.2c00089).
- **Direct portfolio prior art:** Sivilotti et al., *Active learning high coverage sets of complementary reaction conditions*, Digital Discovery (2025). [DOI: 10.1039/d4dd00365a](https://doi.org/10.1039/d4dd00365a).
- **Practical context:** Stevens et al., *Structured HTE Data and Integrated Bayesian Optimization Accelerate Scalable Amidation Process Development* (2026), describes focused condition repertoires in industrial development. [DOI: 10.1021/acsorginorgau.6c00051](https://doi.org/10.1021/acsorginorgau.6c00051). It does not validate this particular portfolio.
