# CAPABILITY FORGE Ω · first release-candidate evidence

## What was built

The private HARNESS connects a pinned local model to diagnostic and construction calls, executes generated Python under seccomp, freezes a development-accepted artifact and verifies it independently on withheld cases. The registry can execute an admitted artifact on new inputs and retains a digest, its contract and its verification scope. The bilingual graphical view, CLI and authenticated API share the same workflow implementation.

The investigated problem is exact recovery of a linear scientific contrast when some readings may be wrong. A correct answer determines a reduced rational value, establishes ambiguity, or reports inconsistency. The study uses synthetic measurements and the rational model specified in [the preregistration](../../docs/CAPABILITY-FORGE-PROTOCOL.md). Sparse-corruption observability has an established mathematical literature. [Fawzi, Tabuada and Diggavi](https://arxiv.org/abs/1205.5073)

## What the system actually achieved

- Real Qwen3-4B-Instruct-2507 inference produced the original diagnosis and the source used by the repair arm. Model-only construction and model-led repair failed the exposed tests. The last two generated candidates passed 4/8 and 3/8 development checks. [Rejected source and outcomes](model-repair-rejections.json) · [Earlier interrupted attempts](interrupted-attempts.json)
- An engineered search over predeclared source mutations selected a candidate after independent development checks. The first winner passed 24/24 qualification and 16/16 transfer cases and subsequently failed two probes when every reading could be faulty. The final trial added those counterexamples and a combinatorial resource probe, registered a new search and sealed new cohorts. [Experiment and recovery history](../../docs/CAPABILITY-FORGE-ANALYSIS.md)
- The final repaired tool passed 14/14 exposed checks, 24/24 fresh qualification cases and 16/16 fresh transfer cases. A standalone replay of the exported archive passed all 40 cases. Eight additional boundary probes passed, including both earlier failures. [Exact source, inputs and verdicts](qualified-repair.json)
- HARNESS admitted that artifact and reused the identical bytes on another 24 qualification and 16 transfer cases with zero new model calls. Direct ordinary execution of the same bytes also passed 40/40. That test supports portability and reuse. It provides no evidence of an improved discovery process. [Reuse and export receipts](qualified-repair.json)

The final source search evaluated 16 variants using exposed data. The selected variant used complement cardinality, exact comparisons, permission for the empty retained set and a single necessary cardinality. The qualified program composes a general exact affine-system primitive. The investigator defined the repair operations after observing development failures. The executor selected and applied the operations and the verifier checked the frozen result. This is evidence for **model-originated code plus an engineered program search**. The autonomous discovery of the repair space and of a new mathematical algorithm remain unproved.

For a fault allowance of k among m readings, any compatible state fits some subset of exactly m minus k readings. Every state fitting such a subset is compatible. Each feasible subset gives an affine solution space. The target has a unique value on that space when it is zero along every null-space direction. A nonzero direction projection, or different fixed values from two feasible subsets, establishes ambiguity. Without a feasible subset the observations are inconsistent. This justifies the mathematical reduction. The receipts establish what the implementation executed under its resource limits.

## Comparisons

| System | Final qualification | Transfer |
| --- | ---: | ---: |
| A · Qwen3-4B alone, concise reasoning at 512 tokens | 0/24 | Unmeasured |
| B · Qwen3-4B and the existing exact specialist, one whole-cohort delegation | 24/24 | Unmeasured |
| C · Model-originated program and bounded source search | 24/24 | 16/16 |
| D · Qwen2.5-Coder-7B and the existing exact specialist, one whole-cohort delegation | 24/24 | Unmeasured |
| E · Restricted frontier reference | Unmeasured | Unmeasured |
| F · Direct conventional FLINT solver | 24/24 | 16/16 |

B and D delegated the entire qualification cohort to FLINT. Each retained its real model request, timing and exact answers. This controls for amortizing the model decision across the cohort. The independent verifier used a fraction-free row-space computation. GitHub receipts and the local study preserve the tool-equipped and direct conventional paths. [Model routes](tool-controls.json) · [Conventional and independent receipts](qualified-repair.json)

Observed warm qualification application took 1.526 seconds total for the isolated Forge tool and 0.0040 seconds total for the direct FLINT calls. Those measurements include the Forge worker startup on each application. They exclude cold construction and denote the respective observed call paths. The incumbent completed the same outcome and ran faster. Restricted-frontier parity, physical equipment performance and economic benefit remain unverified.

An exploratory trial used 37 different matrices. Forge passed 36 and the direct specialist passed all 37. The dense 32-by-16 case with a two-fault allowance exhausted the Forge worker CPU allocation without producing a verdict. The current release candidate therefore has a measured performance limit at the upper input envelope. [New cases and repeat receipt](exploratory-stress.json)

On the final cohort, the model-alone arm answered 0/24 under its reasoning prompt without a numeric example. The paired exact test on that cohort had 24 Forge-only correct pairs and 0 model-only correct pairs (two-sided p = 1.19e-07). The result applies to this model and prompt. The arm retained 1 failed provider or output responses (PROVIDER_STREAM). [Matched model-alone receipt](model-alone-final.json)

The first exposed model-alone run produced 1/8 accepted structured answers. Decoding only explicit string-encoded final answers raised the diagnostic score to 4/8. A later compact prompt copied a numeric exemplar frequently and scored 0/24 on the earlier source-search cohort. Keep that interface failure distinct from mathematical capability. [Original responses](original-development.json) · [Scoring procedure](../../docs/CAPABILITY-FORGE-ANALYSIS.md)

## Resources and release scope

The actual local models use public pinned GGUF weights with llama.cpp on Linux x86-64 CPU. The host exposed nine logical CPUs and about 9.7 GiB of memory. The final model-originating arm used two inference threads and a 4,096-token context. The last source-search stage took 21.74 wall seconds, including unsuccessful search variants and qualification. This figure excludes the earlier inference, interruptions and engineering. Complete end-to-end cost, human setup time and energy are unmeasured. The warm results support the incumbent's practical advantage on this workload. [Model, timing and source receipts](qualified-repair.json)

The two measured model-only composition segments took 151.05 and 206.30 wall seconds and used 299.75 and 408.20 model-server CPU seconds. The later model-originating run peaked at 4.66 GiB server resident memory. The whole-cohort B and D routing calls took 10.33 and 17.99 wall seconds after their servers were ready. Setup and prior interrupted inference are separate recorded expenses where available. The duration of the final source search is therefore only one part of the cost of obtaining the tool. [Live attempt history](interrupted-attempts.json) · [Tool-equipped receipts](tool-controls.json)

The product distribution remains a draft HARNESS package. Linux with libseccomp is required for generated Python. The portable tool replays without model weights. Multiple unrelated scientific domains, continuous frontier scouting, restricted-reference parity and a causal discovery-compounding advantage remain open.

The decisive next experiment is a consequential second task with an observed residual against competent open tools, followed by the same sealed qualification and an authorized restricted reference on identical inputs.

## Français

Le connecteur privé HARNESS a exécuté un modèle Qwen3-4B local et vérifié ses propositions. Les constructions et corrections produites uniquement par le modèle ont été rejetées. Une recherche programmée parmi des transformations explicites a réparé le code issu du modèle. Les transformations ont été définies à partir des erreurs observées avant la qualification. La recherche a choisi et appliqué la solution, puis un vérificateur exact indépendant l’a contrôlée sur des cas scellés.

L’outil final a réussi **24/24 cas de qualification et 16/16 cas de transfert**. L’archive reproduit ces 40 résultats sans poids de modèle. Huit essais supplémentaires, dont deux contre-exemples qui avaient invalidé une première version, ont aussi réussi. Le registre a réutilisé le même artefact sur 40 autres cas sans appel au modèle. La réutilisation directe ordinaire a obtenu le même résultat.

Les deux modèles ouverts outillés ont délégué 24 cas sur 24 au solveur conventionnel FLINT. Ce dernier a également réussi en exécution directe et été plus rapide. Aucun système de référence fermé n’a été mesuré. L’équivalence avec un système de pointe, le gain économique et l’accélération de la découverte demeurent à établir. La version reste un candidat HARNESS pour Linux.

Dans une vérification exploratoire distincte, Forge a réussi 36 des 37 cas et FLINT les a tous réussis. Le cas dense de 32 lignes, 16 variables et deux pannes possibles a dépassé l’allocation CPU du processus Forge. Il n’a rendu aucun verdict. [Cas et résultat de la reprise](exploratory-stress.json)

Le contrôle final du modèle Qwen3-4B seul a réussi 0 cas sur 24 sur le même jeu de qualification. L’essai fixe un modèle et une formulation. [Résultats détaillés](model-alone-final.json)
