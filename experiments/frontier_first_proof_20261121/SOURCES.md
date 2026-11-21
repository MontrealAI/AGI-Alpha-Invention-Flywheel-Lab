# Chemistry source validation for FRONTIER Ω

Validated 2026-11-21. This note documents sources and interpretation only. No successor optimization was run by the source-validation researcher, and no successor optimum or selected panel is disclosed here.

## Frozen immediate source

Repository: [doyle-lab-ucla/bandit-optimization](https://github.com/doyle-lab-ucla/bandit-optimization/tree/ae3e910dcea27cfd1631a28b793b6c63607baedd).

Commit: `ae3e910dcea27cfd1631a28b793b6c63607baedd`.

The recursive Git tree returned this exact SHA and `truncated: false`. Each local source file below was checked against the Git blob SHA returned for that commit. SHA-256 was independently computed over the local bytes. Original index columns remain in the CSVs.

| Local source | Original repository path | Bytes | Git blob SHA-1 |
|---|---|---:|---|
| amidation.csv | datasets/amidation.csv | 151756 | 0e9b6fa543eb79274b7133446c7d2d4d3ed1734e |
| nib-etoh.csv | datasets/nib-etoh.csv | 18648 | 85ab353d601ab33192a62bf4d31c9cf64e812c27 |
| nib-meoh.csv | datasets/nib-meoh.csv | 18544 | 1cccdd52f969415e59ee19579542469749d6da63 |
| SOURCE-DATASETS-README.md | datasets/README.md | 2407 | c5c32d5bf7679c5f723d395060271adb862753fe |
| LICENSE.md | LICENSE.md | 35149 | f288702d2fa16d3cdf0035b15a9fcbc552cd88e7 |

The immediate source repository contains **LICENSE.md**, the GNU General Public License, Version 3, 29 June 2007. A lookup for a file named LICENSE alone would miss this file. This identifies the repository's published license, rather than establishing a legal conclusion about every third-party experimental fact included in it.

The same three CSV Git blobs also occur under `deebo/` in [doyle-lab-ucla/ochem-data at e739f4d4d2002218fd225de5e8b2e6c235cabd6b](https://github.com/doyle-lab-ucla/ochem-data/tree/e739f4d4d2002218fd225de5e8b2e6c235cabd6b). That repository's LICENSE.md is Creative Commons Attribution 4.0 International, blob `10fabd90118f7ce38bb2e4753e105e744442a429`. Retain the immediate source license and authorship attribution; do not silently relabel the source repository license.

## Amidation data and scope

The pinned datasets README attributes amidation.csv to the authors' own collected amide-coupling measurements. The originating publication is Wang et al., *Identifying general reaction conditions by bandit optimization*, Nature 626, 1025–1033 (2024), [DOI 10.1038/s41586-024-07021-y](https://doi.org/10.1038/s41586-024-07021-y). An accessible primary author-hosted copy is [the Doyle laboratory PDF](https://doyle.chem.ucla.edu/wp-content/uploads/2024/02/s41586-024-07021-y.pdf).

The study concerns a fixed carboxylic acid, indomethacin, coupled to ten aniline nucleophiles. Figure 4 gives the fixed context: base 3 equivalents, activator 1.3 equivalents, solvent at 0.1 M, room temperature, 24 hours. Its original generality objective ranks activator/base combinations with solvent variation inside the scope. A portfolio of explicit activator/base/solvent triplets is therefore a new analysis objective applied to these historical measurements.

Direct structural checks on the frozen CSV:

- 960 rows and 960 distinct nucleophile/activator/base/solvent keys.
- Ten nucleophiles, eight activators, four bases and three solvents; a complete 10 × 96 table.
- No missing numerical yield entries and no values above 100.
- Three negative entries; minimum −0.8 and maximum 98.71.
- These are recorded numerical yields, not newly measured performance, isolated-product yields verified in this work, or theoretical maxima.

The percentage scale is confirmed by the original authors' [analysis code](https://github.com/doyle-lab-ucla/bandit-optimization/blob/ae3e910dcea27cfd1631a28b793b6c63607baedd/dataset-analysis/amidation.py), which labels yield in percent, and [deebo/utils.py](https://github.com/doyle-lab-ucla/bandit-optimization/blob/ae3e910dcea27cfd1631a28b793b6c63607baedd/deebo/utils.py), whose scaler assumes 0–100. The authors' bandit simulation divides by 100 and clips outside [0,1], as called by [deebo/chem_simulate.py](https://github.com/doyle-lab-ucla/bandit-optimization/blob/ae3e910dcea27cfd1631a28b793b6c63607baedd/deebo/chem_simulate.py). A direct analysis of recorded yields should preserve CSV values and document any chosen transformation separately.

The CSV has no replicate identifier, standard error, assay-calibration record, or per-record uncertainty field. The supplementary experimental characterization was not accessible through the research tools in this pass. Assay type, replicate treatment and a defensible measurement-error bound therefore remain unverified here. Decimal precision must not be interpreted as experimental accuracy. Negative entries are consistent with measurement or calibration effects, but the cause was not verified.

## Interpretation of the first construction

For substrate s, define b_s as its maximum recorded yield across the 96 conditions. A condition covers s at threshold τ only if its recorded yield is at least τ × b_s. The declared primary τ = 0.90 and sensitivity values 0.50, 0.70, 0.80, 0.90, 0.95 are design choices, not chemical constants or fitted assay tolerances.

This constructs the smallest catalog of conditions sufficient to preserve a declared fraction of each listed substrate's best recorded outcome. The reference assignment for each substrate is part of the usable artifact. It is useful for selecting a compact historical-condition repertoire and preparing replication priorities. It does not prove prospective coverage of new anilines, a reduction in the experiments that produced this already complete table, transfer to other acids, scale-up performance, purchasing savings, or new chemistry.

Exact optimization proves a combinatorial property conditional on the input table and contract. The best single condition, greedy selection and an independent exact solver are the appropriate comparisons. Any stronger economic claim requires the relevant cost, reliability and implementation evidence.

## Nickel borylation provenance and complete-subset caveat

The pinned README attributes nickel data to Stevens et al., *Advancing Base Metal Catalysis through Data Science: Insight and Predictive Models for Ni-Catalyzed Borylation through Supervised Machine Learning*, Organometallics 41 (2022), 1847–1864, [DOI 10.1021/acs.organomet.2c00089](https://doi.org/10.1021/acs.organomet.2c00089). That original paper reports 33 substrates, 36 unique monophosphine ligands, two solvents and 1632 reactions. It links the authors' [original machine-learning data repository](https://github.com/jun-li-2020/Ni_Borylation); its inspected main tree resolved to `dceee5750a08ef9b15f06ed2ad17876e7952ddf0`.

The two files used here are a smaller complete rectangular subset:

- Each file has 759 unique electrophile/ligand keys = 33 electrophiles × 23 ligands.
- Each covers exactly one solvent, ethanol or methanol; both yield ranges are 0–100.
- Neither file has missing yields or duplicate electrophile/ligand keys.
- Both use columns for index, electrophile_id, ligand_name and yield. The percentage scale is confirmed by the [authors' nickel analysis](https://github.com/doyle-lab-ucla/bandit-optimization/blob/ae3e910dcea27cfd1631a28b793b6c63607baedd/dataset-analysis/nickel-borylation.py).

The upstream [NiB/rxns/descriptions.txt](https://github.com/doyle-lab-ucla/ochem-data/blob/e739f4d4d2002218fd225de5e8b2e6c235cabd6b/NiB/rxns/descriptions.txt), blob `78455f127dd51f94568ad60a80daee3961677606`, explains that PnBu3 HBF4 lacked three substrates in the 24-ligand table; removing it yields the complete 33 × 23 × 2 table. It separately identifies an external set of two substrates, twelve new ligands and two solvents. Its text contains the filename typo `inchi_32l.csv`; the actual tree contains `inchi_23l.csv`. The description's component counts do not fully reconcile to the original paper's 1632 reactions; no unverified explanation is assigned here.

The source analysis contains commented-out code that would zero yield differences within five percentage points. That is not evidence of a measured error bar, and it was not an active transformation. The selected CSVs contain no replicate-level uncertainty metadata. Long decimal expansions do not establish whether values are replicate averages.

## Interpretation of a distinct diagnostic successor

A genuine second objective can select a small panel of substrate/solvent probes that separates the catalogued ligand response profiles. Its objects of interest are pairs of response profiles; a candidate probe covers a pair only if their recorded yields differ by at least the predeclared separation. The retained cover solver can then be reused unchanged, while the adapter, domain semantics and success criterion differ from yield preservation.

The useful artifact is a compact **reference response panel** for comparative catalyst benchmarking or planning follow-up experiments. A guarantee about separation in the recorded reference library does not identify unknown chemical composition or establish a catalytic mechanism. Prospective identification would additionally assume library membership, comparable experimental conditions and bounded observation error, and would require independent measurements. If each predicted reference measurement may move by ε, a gap greater than 2ε is needed for disjoint worst-case intervals. A chosen ten-percentage-point separation, for example, is an engineering resolution, not a verified ±5-point assay accuracy.

Do not select a separation threshold because it produces a favorable panel size. Report intrinsically indistinguishable profile pairs rather than silently removing them. The panel's value is preservation of declared distinctions with fewer listed probes; it is not proven physical experiment savings from an unknown-data campaign.

## Prior art and current practical relevance

1. Sivilotti et al., *Active learning high coverage sets of complementary reaction conditions*, Digital Discovery 4 (2025), 846–852, [DOI 10.1039/d4dd00365a](https://doi.org/10.1039/d4dd00365a); [authors' code](https://github.com/TheJacksonLab/condition_set_opt). This is direct prior art: small complementary condition sets, comparison with single general conditions, set cover for complete known outcomes, and active learning when outcomes are unknown. The present task must not claim invention of this scientific idea or of set cover. Its bounded contribution is a reproducible constructed artifact and demonstrated reuse across distinct objectives.

2. Rana et al., *Standardizing Substrate Selection: A Strategy toward Unbiased Evaluation of Reaction Generality*, ACS Central Science 10 (2024), 899–906, [DOI 10.1021/acscentsci.3c01638](https://doi.org/10.1021/acscentsci.3c01638), [primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC11046462/). The authors demonstrate purposeful selection of representative substrate panels for testing reaction scope. This supports the practical relevance of panel design, while their structural-diversity criterion differs from pairwise recorded-response discrimination proposed here.

3. Stevens et al., *Structured HTE Data and Integrated Bayesian Optimization Accelerate Scalable Amidation Process Development*, ACS Organic & Inorganic Au 6 (2026), 624–635, [DOI 10.1021/acsorginorgau.6c00051](https://doi.org/10.1021/acsorginorgau.6c00051), [primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC13650955/). This current industrial account describes beginning amidation development with six focused conditions informed by prior performance and commercial precedent, followed by Bayesian optimization. It supports the value of focused condition repertoires, but does not validate our specific selected portfolio or its economic value.

## Boundaries of this validation

Verified: pinned source bytes; named immediate and upstream repository licenses; basic schema and completeness; yield percentage scale; historical measurement attribution; full-table rather than sparse-learning semantics; relevant direct prior art.

Not verified: prospective chemical reproducibility, assay-specific uncertainty, full analytical calibration chain, manufacturing suitability, reagent prices, patent novelty, customer demand or realized commercial value. No second-task optimum was computed in this research pass.
