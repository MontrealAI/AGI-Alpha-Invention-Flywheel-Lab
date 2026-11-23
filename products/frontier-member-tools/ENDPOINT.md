# Endpoint Evidence Screen 1.0.0

Find the highest **actually tested** concurrency satisfying both a declared throughput floor and a declared P90 time-to-first-token ceiling in one fixed environment. The output always marks operational adoption **ABSTAIN**. It cannot establish quality, availability, representativeness, operational cost, or production requirements.

## Run (qualified Linux CLI, Node 24, Python 3.12 with SQLite)

```sh
node endpoint-cli.mjs sample.json > measured-screen.json
python3 endpoint-sqlite.py sample.json > exact-reference.json
cmp measured-screen.json exact-reference.json
```

The published v1 trial uses seven official data rows selected from one NVIDIA hardware configuration, one GPT-OSS 120B workload, and one MLCommons Endpoints submission. The historical benchmark-screening contract is 100 tokens/s/user and 500 ms. It returns tested load **140**. These limits belong to the documented benchmark replay. Apply other limits only when they come from your own approved task. See the exact input, source commit and byte digests in `manifest.json`.

For your own authorized data, copy the structure in `sample.json`. Supply exactly one measured row per load with a unique opaque ID. Use ISO calendar days, positive integer load and unsigned fixed-decimal **strings** for tokens/s/user and P90 TTFT in milliseconds. A missing date or measurement is `null`. Use one batch for one model, workload and hardware configuration. Leave unverified data outside operating decisions. Do not mix configurations, infer untested loads, or give the results operational authority. CLI input is at most 256,000 bytes. A malformed date, ambiguous load or malformed decimal is rejected. An unsupported screen returns ABSTAIN and every row's disposition.

The browser workbench uses the same calculation. Both tools process files locally. The test reports measure only the scoped calculation and comparison. Data collection, measurement quality, operator effort, maintenance and complete costs remain unmeasured. The indexed SQLite reference is suitable when it already meets the job. Reuse the batch schema and evidence decisions when testing a separate configuration within fresh authority.

## Sources and use

This release distributes the named first-party tool and the seven attributed benchmark facts for public use and verification. The published result and evidence remain attributed to MLCommons and the submitting team. The full third-party corpus is referenced by source and digest. This package grants no broader redistribution rights over upstream data, names or marks. The separate research decision remains Endpoint ABSTAIN. The first-party package's distribution scope is recorded in its manifest.

## Français

Cet outil sélectionne la concurrence **réellement testée** la plus élevée qui respecte le débit minimal et la latence P90 maximale déclarés dans un seul environnement. La décision d’adoption opérationnelle demeure **ABSTENTION**. Le rejeu public retourne **140** à partir de sept mesures officielles. Ce seuil de laboratoire ne constitue pas une exigence de production. Les commandes ci-dessus comparent le calcul local à la référence SQLite indépendante. Pour un autre cas, utiliser des données autorisées, garder une seule configuration par fichier et respecter le schéma de `sample.json`. Les coûts complets et la transférabilité restent à établir. Les résultats sources sont attribués à MLCommons et à l’équipe qui les a soumis.
