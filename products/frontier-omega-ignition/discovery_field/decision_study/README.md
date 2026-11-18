# When does a source change the next experiment?

A power-systems research group needs to decide what to benchmark. A microscopy imaging core needs to know how a difficult evaluation set was selected. For each beneficiary, a second paper in the same field can sound persuasive while answering a different question. This study registers the actual comparison the beneficiary needs, so removing its source can invalidate a research decision while leaving a proposed experiment available for inspection.

## Read and run

From `products/frontier-omega-ignition`, using ordinary Python:

```sh
python3 -B -m discovery_field.decision_study.evaluate packet 1
python3 -B -m discovery_field.decision_study.evaluate packet 1 --prepared
python3 -B -m discovery_field.decision_study.evaluate lookup
python3 -B -m discovery_field.decision_study.evaluate replay discovery_field/decision_study/included.json
python3 -B -m unittest discover -s discovery_field -v
```

The source packet, four comparisons and scoring rule were committed before model execution at `f40e267`. The lookup checks a curator-reviewed relation and can return a decision with no model call. A research model sees the passages and an open question. It can propose any uncertainty, action and decisive test. The prepared variant also supplies editorial scope notes that separate the population and metric. Preparing and maintaining the extra information in these notes takes research time.

In the private workbench, `python3 -B -m discovery_field.decision_study.private_sources 1` emits the mission purpose and attributed source objects for import or for `ignition.research.investigate`. A trial in `test_private.py` executes the actual research route. Add `--reacquired` to include the later full publisher-response identity. A receipt dated before that acquisition cannot attest those bytes. The trial checks that the right same-domain comparison can support an incumbent decision and that source withdrawal, a changed passage, unsupported source identity, or a missing factual binding can withhold it. Existing missions select this path by importing the explicitly marked decision sources. The included article snippets confer no execution permissions.

The fresh Qwen experiment can be repeated with an operator's already approved model and pinned runtime archives:

```sh
python3 -B -m discovery_field.decision_study.observe --assets /path/to/verified-cache --threads 4 --output /tmp/new-qwen-observation.json
python3 -B -m discovery_field.decision_study.evaluate replay /tmp/new-qwen-observation.json
```

The cache contains `llama.tar.gz` and `model.gguf` with the existing Field Lab hashes. The process checks both files, starts a fresh loopback CPU server, uses the existing streaming HARNESS for eight independent requests, records their source and request identities, and shuts down its own process. Each model response is scored without repair. Replaying checks historical responses. Re-running inference creates a different observation.

## How to interpret a decision

| Question | Supporting finding | Competing fact with different scope |
| --- | --- | --- |
| Should a physics solver be treated as a serious bulk-throughput competitor on ordinary AC power flow? | In the reported comparison, a sufficiently parallel conventional solver matched or exceeded the throughput of the tested learned surrogates. | 12.2 ms for one model and one hourly scenario on an edge device. This observation does not decide throughput at the lab. |
| How was the difficult microscopy association set selected? | CellTrack-Bench used overlapping mistakes by different specialized trackers to select the difficult cases. | The Cell Tracking Challenge compares methods on real and simulated movies. Its general description does not specify the separate paper's selection rule. |

When a source is absent in the second presentation, the beneficiary may still design a test. They cannot attribute its desired outcome to the missing publication. These are interventions on the information available in a trial, not publisher retractions. The machine checks the registered conclusion, available ID and a verbatim passage containing the reviewed relation. On arbitrary prose it leaves the design unadjudicated. Independent qualitative assessment of the generated content must also check the claimed scope, comparable outcome and a possible disconfirming result. Each qualitative judgment identifies the exact answer reviewed and gives a reason that another reader can challenge.

The direct, included route used two independent assistant turns. Each turn read two packets from different domains, one turn for the complete source pairs and another for the two withdrawal cases. The four Qwen contexts were presented one per call on the same model and physical configuration. The included route therefore has shared cross-domain context and a different transport. Qwen used a shared server. The arms alternated order across contexts and may have benefited from a warm prefix cache. Exact included model identity, provider token usage and monetary cost were unavailable. Cross-model comparisons cannot isolate a model-size or orchestration effect.

## What the models actually decided

Two of the four contexts support a narrow affirmative answer. The other two warrant abstention. Each route below had four opportunities to get this distinction right.

| Route | Correct decision label | Correct decision and bound evidence or explicit abstention | Also supplied a usable new test on independent qualitative review | Metered model input / output tokens |
| --- | ---: | ---: | ---: | --- |
| Qwen, direct excerpts | 2/4 | 2/4 | 0/4 | 1,613 / 681 |
| Same Qwen, scope notes added | 3/4 | 2/4 | 0/4 | 1,798 / 692 |
| Independent included assistants, direct excerpts | 4/4 | 4/4 | 4/4 | Unavailable |
| Conventional reviewed lookup | 4/4 | 4/4 | No design generated | No inference calls |

The scope notes helped Qwen identify the shared-failure sampling rule. Both Qwen arms still deferred the full power-flow question even while repeating the study's reported conclusion in their prose. With the comparative paper removed, the prepared arm correctly chose to abstain but supplied JSON strings containing the word `null` for the source and quotation. The direct arm recorded proper nulls. On the tracking withdrawal, both Qwen arms proposed a new synthetic experiment as a way to learn the historical benchmark design. On power flow they proposed testing one scenario's duration to decide a bulk-throughput claim. These are scientific mismatches even where the abstention itself was correct. The included grid proposal instead counted cases meeting a common physical accuracy requirement per second under the same hardware budget.

The eight public Qwen requests took 737.390 seconds in the direct arm and 716.920 seconds in the prepared arm. The complete measured session on four AMD EPYC 9V45 CPU threads took 1,460.986 seconds wall time, 4,250.770 child CPU-seconds and 3.189 client CPU-seconds. Rechecking and extracting the cached model assets took 2.518 seconds. The GGUF and llama.cpp archive were acquired previously. Their original acquisition, training, infrastructure price and complete labour costs cannot be priced from this run. The source-matched runner and evaluator hashes appear in the receipt. The run launched with the two scripts present in the worktree at `fdb3d56`. Both executed files match their subsequent committed bytes in `12bf100`. The old five-candidate Qwen failure remains on its own mission and source packet. [Qwen answers and HARNESS receipts](qwen.json) · [Included answers](included.json) · [Independent answer-specific judgments](scientific_review.json)

```sh
python3 -B -m discovery_field.decision_study.report
```

## Five possibilities and the decision to build

[The bilingual opportunity field](possibilities.json) identifies the beneficiary, positive evidence and counterexamples, a strong alternative, an executable next test, distribution conditions and unmeasured costs. [The seven primary source excerpts](sources.json) carry publisher attribution, date or release status, limitations and a cryptographic identity of the observed passage. The arXiv reader exposed the article identifiers and exact passages but did not expose complete publisher-response bytes or revision suffixes. A direct shell request for the solver abstract timed out, and the web reader did not retrieve the version-suffixed URLs attempted separately. Those attempts produced no raw-page hash. A subsequent independent HTTPS acquisition recovered all seven complete responses. Every passage matched. [The public source receipt](publisher_observations.json) records full-response SHA-256 digests, sizes, timing and observed paper revisions. Four articles were on v1, and the formalization article was on v2, dated October 21. The documentation pages did not state page publication dates. The Fink rate fields themselves are marked as available since December 2023.

The selected construction is an observer’s as-of change queue with a later scientific check. A conventional rate estimate already exists. What can be tested immediately is whether the observations available at an earlier date support an alert and whether a later exposure corroborates it under a declared rule. Frozen survey measurements can falsify the result cheaply. Comparing the same outcomes with a direct query is essential. A correct individual alert cannot establish better science yield or economic priority over the other four opportunities. The earlier NOMAI study motivates inspecting rare-transient alert streams. Its population estimate does not qualify the queue or any individual classification. [Primary classifier publication](https://doi.org/10.1051/0004-6361/202660399) · [Fink rate fields](https://doc.ztf.fink-broker.org/broker/science_modules/)

| Other possible investment | What the installed competitor changes | Next decision before an investment |
| --- | --- | --- |
| Offline power-flow simulation | The authors already distribute a batched physics solver. A learned replacement must still justify itself against strong parallel CPU and GPU baselines at the required physical accuracy. | Find a licensed, representative offline workload and capture complete accepted batches per second, including cold start, preprocessing and validation. [Public solver](https://github.com/Grid2op/gpusim2grid/blob/7ca10468af719232ed9835fe2ae162290bd3f918/README.md) |
| Microscopy review time | The authors supply stored predictions and a review-budget reproduction. Their project states that the source datasets and derived benchmark items cannot be redistributed. Reproducing their table would not deliver a new imaging-core result. | With an imaging core’s own authorized sequences, hide whole movies and measure net corrected links, new mistakes and review minutes alongside the tracker’s confidence ranking. [Primary repository](https://github.com/royerlab/celltrack-bench/blob/ea35c35cbc4a93fd11b02406cf844b06da3aae14/README.md) |
| Mathematical library maintenance | Lean checks a proof against an encoded proposition. The upstream FLMF project also tests translations mechanically. Faithful source-to-proposition adjudication remains valuable. | Ask a willing library maintainer to specify a held-out identity family, annotate known translation/domain errors, and adjudicate against the upstream method and independent numerical checks. [Mei and Douglas](https://arxiv.org/abs/2610.20573) |
| Instrument logic | Existing synthesizable counter IP or a direct HDL engineer may already meet the objective. Two signed-off human-team designs are evidence for an assisted workflow, not the operation of an untouched new chip. | Freeze a fresh passive-counter timing contract. Compare equivalence, reset, area and timing against a parameterized IP block before considering physical access. [AI Hardware Design League](https://arxiv.org/abs/2610.18891) |

Two linked READMEs were additionally checked against the retrieved Git objects. The Grid2op README is 15,154 bytes with SHA-256 `8aa366a2488620c4db973eb7c18957c6684b03ab078131f026638ed7ec9575fe`. The CellTrack-Bench README is 9,125 bytes with SHA-256 `4518a48e930e6de3622b08f7ecc030bcb99071180a0f92349710935d6f130fd4`. Those identities apply to the source documents, not to downloaded datasets or running software. For an independently acquired paper page use `python3 -B -m discovery_field.decision_study.verify_source B page.html` to match the normalized frozen passage and record that local file's full hash.

## An open proposal that led to an executable result

One separate included assistant received all seven compact primary records and a fresh mission for a network of shared research facilities. It saw none of the five exhibition cards. In 290.738 seconds it independently proposed a division census, flash-start exposure windows, voltage-crossing certificates, calibration bounds and detector counting-bias simulation. All five contained genuine quotations. Source content materially informed the census sampling design and the choice of the power-flow comparator. Three others cited accurate contextual facts that did not establish the enabling idea. Each was assessed separately. [Original proposals and judgments](open_included.json) · [Registered open prompt](OPEN_REGISTRATION.md)

Its first choice was a probability audit of cell divisions. Reviewing an entire sampled block can reveal a division missing from every tracker's output. The comparison needs whole movies with hidden lineage references, independently produced tracker outputs and a matched single-tracker confidence audit. The published hard sample contains selected difficult links, and the broader released construction also selects links by difficulty. More importantly, the authors report feeding gold detections to all three trackers at every frame. Those graph predictions already use information that the proposed operational trial must withhold. The public CTC training sets include lineage ground truth, while official challenge test annotations are kept secret. A new comparison can use a sequence-level split of the training sets with competing pipelines that produce their own detections. No benefit per review minute was measured. [Archive inventory and exact stop condition](census_access.json) · [Tracker construction](https://github.com/royerlab/celltrack-bench/blob/ea35c35cbc4a93fd11b02406cf844b06da3aae14/construction/README.md) · [Official reference annotations](https://celltrackingchallenge.net/annotations/)

The fourth proposal gave an exact claim we could build and test immediately. Suppose method A passes 8 of 10 trials with site sizes 8 and 2. Method B passes 7 of 10 with site sizes 2 and 8. A leads in pooled counts. Its equal-site mean advantage could nevertheless be as low as **−5/16** or as high as **+7/16**. Feasible values are discrete. The two endpoint allocations respectively give site pass counts A=(8,0), B=(2,5) and A=(6,2), B=(0,7). A direct exact calculator returns sharp bounds and their witnesses for supplied positive site sizes and pooled counts. To maximize a method's equal-site rate, place passes in the smallest sites first, where each contributes the most. Reverse the order for the minimum. The methods' allocations can be chosen independently under this margins-only question.

SQLite independently enumerated all nine compatible allocations in the model's example. It checked 2,025 further two-site margin cases and 6,561 compatible joint allocations. Every endpoint and witness agreed. The calibration-paper citation establishes the authors' own method comparison and provides no site margins for this example. This finite result checks an original proposal with synthetic inputs. Historical novelty, operational benefit and commercial relevance require different evidence. [Calculator](calibration_bounds.py) · [Observed comparison](calibration_observation.json) · [Follow-up registration](ENABLING_CHECK.md)

```sh
python3 -B -m discovery_field.decision_study.open_decisions
python3 -B discovery_field/decision_study/calibration_bounds.py --check
python3 -B discovery_field/decision_study/calibration_bounds.py --margins your-site-totals.json
```

## Decision cost and scientific scope

The conventional lookup reproduced four decisions in 0.633 ms wall time and 0.629 ms process CPU in one warm Python 3.12.14 process, including the check of each answer. It uses reviewed relations entered in advance and generates no new design. The included assistants reported that the full pair occupied 21.883 s through the last answer write. The withdrawal pair took 33.66 s through validation. Each interval covers a whole assistant turn. Case-level times and prices remain unknown.

Costs still to measure include acquiring and interpreting evidence, failed attempts, annotation, permission to redistribute, training or inference, independent adjudication, revalidation of revised publications, operating support, demand and opportunity cost. No human time study, buyer, paid delivery, funding or realized savings was observed. Qualified costs per accepted *productive* result need a prospective beneficiary trial.

The constructive intervention follows OUT-THINK, pp. 3–10 and 12–16. A proposition's scope stays attached to its source and a withdrawal changes which conclusions can be supported. The exact relation map is validated on two questions. A new scientific proposition needs its own evidence and qualification. [Research foundation and implementation conditions](../../../../docs/harness/OUT_PAPERS.md)

## En français

L’essai porte sur deux décisions scientifiques. Dans le premier cas, une mesure de latence sur un appareil embarqué ne répond pas à une question de débit en lots. Dans le second, la description générale d’un concours de suivi cellulaire ne suffit pas à caractériser la sélection d’un jeu difficile. L’instrument vérifie l’extrait pertinent, puis conserve séparément l’hypothèse et le test proposé.

Sur quatre contextes, Qwen obtient deux décisions entièrement étayées avec les extraits seuls et deux avec les notes de portée. Le nombre d’étiquettes correctes passe néanmoins de deux à trois. Les assistants inclus et la consultation classique réussissent chacun les quatre décisions. Seuls les assistants proposent aussi quatre tests jugés utilisables.

Le modèle invité à proposer librement de nouveaux instruments a choisi de recenser les divisions cellulaires à partir d’un échantillon probabiliste de blocs vidéo. Les archives publiques contiennent bien des fichiers de référence. Les trois suivis publiés ont cependant utilisé les détections de référence pour chacune des images, y compris hors de l’échantillon. Une comparaison fidèle exige donc des suivis produits sans cette information.

Une autre proposition a donné lieu à un calcul exécutable. Sur un exemple construit où A réussit 8 essais sur 10 et B en réussit 7, le résultat dépend de la pondération des sites. En donnant le même poids à chacun, l’écart A moins B peut atteindre −5/16 ou +7/16. Une énumération SQL indépendante retrouve ces deux valeurs, leurs répartitions par site et tous les résultats sur 2 025 autres cas. L’utilité pour une installation réelle reste à établir.
