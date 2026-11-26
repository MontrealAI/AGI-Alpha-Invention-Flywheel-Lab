# Research activation · Game Theory evaluation triage

**Registration before running the replay, November 26, 2026.** This is a retrospective secondary analysis of existing MONTREAL.AI evaluations. The published aggregate results were already available. The case-level results were not used to choose the sampling rules.

## Question and scope

The November 25 preprint [Evaluating More with Less](https://arxiv.org/abs/2611.34617v1) found different benefits for estimating aggregate success and finding failures early. Its category-based method motivates a local experiment on the cost of iterating the Game Theory specialist. Do case length and known evaluation strata make an eight-case diagnostic batch more informative than ordinary random or stratified sampling?

Use the repository's published, synthetic Game Theory held panels at revision [`b35f937f`](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/b35f937fcb77199334e267360e9a0c9e438a74ad/publication/prove-advantage/game-theory). Evaluate all four shared SmolLM2 arms: base direct, base retrieval, base word lookup and adapted direct. The primary-only Codex and Qwen arms are outside the two-panel overlap. These are frozen adjudicated outcomes from actual model runs.

| Input in `../game-theory` | SHA-256 |
| --- | --- |
| `PRIMARY-BRIEFS.json` | `caa9bd9596b36bded98d84c26f54bbfbd329587de1dee2c14c08a9d3a3db9529` |
| `PRIMARY-ADJUDICATION.json` | `951506c89269baf3a4f39e3b6a1bda63aebfbac42d9fc11a805b958e8d617154` |
| `CONFIRMATION-BRIEFS.json` | `2acf5f20f86bfd0c1cc2680a03ecc2f205f645d8d29ee13e817f51ec735dbf6d` |
| `CONFIRMATION-ADJUDICATION.json` | `df9aeaa8948f3a4815b2db93f8dc318d3a3f761c2a6c44ee4dbfa535f080b0d9` |

Require 18 unique cases and 50 queries, four panel-by-language strata of four or five cases each, exact metadata/outcome joins, and at least two matched arms with five or more cited successes and five or more failures. Stop the comparison if the inputs fail these checks. Preserve all four arm results if eligible, including degenerate arms.

The sampling unit is a complete case with all its queries. Per-query success requires correct access and a correct source-rule citation, under the existing adjudication. This outcome differs from complete-case acceptance. The diagnostic outcome denominator is the number of queries in the batch.

## Comparisons

Use a fixed budget of eight cases with a single separately reported complete reference. Compute all eligible combinations when a policy samples uniformly.

| Policy | Rule based on case metadata |
| --- | --- |
| Simple random | Eight cases from all 18 without replacement |
| Stratified random | Two cases from each of primary English, primary French, confirmation English and confirmation French |
| Length-balanced | Sort each stratum by total rule characters, with case ID as the tie-break. Split at the integer midpoint and sample one case per half-stratum |
| Longest-rule priority | Within each stratum select its two longest cases, with case ID as the tie-break |
| Query-count priority | Within each stratum select the two cases with most queries, with case ID as the tie-break |
| Complete reference | All 18 cases and 50 queries |

For aggregate estimation, expand observed cited success totals in each sampling group by the ratio of group size to cases sampled from it. Divide the sum by the full 50 queries. Report exact mean absolute error and 90th-percentile absolute error from the three randomised policies. Use nearest-rank for the percentile. Accept length balancing for estimation only if the across-arm mean absolute error improves by at least 10% versus the better random control and all four 90th-percentile errors are at most five percentage points.

For early failure detection, report failed queries found, proportion among all queries visited and fraction of the full reference's failures found. The longest-rule policy is worth advancing only if its mean failed-query proportion across the four arms improves by at least five percentage points over the best of the random, stratified and query-count controls, with no arm losing more than five points to that same control.

The replay uses included local computation and performs no inference or external actions. It does not change any original acceptance gate. Eight versus 18 cases quantifies the scope of a hypothetical diagnostic batch. Actual evaluation savings require a prospective measured run, including inference, review, missed errors and complete acceptance.
