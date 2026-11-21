# 🌌♾️ FRONTIER Ω — Capturing the Exponential

**Understand what may become possible. Discover what can become possible sooner. Invent the missing means. Prove the value. Capture it. Compound it.**

Its first decisive achievement should be concrete: **one valuable future outcome made useful today, followed by evidence that the means retained from achieving it help construct a second valuable capability.**

## Implemented research path

FRONTIER now connects attributed foresight documents, present prerequisite evidence, source-led opportunity selection, executable construction, and a comparison on a different second objective. It uses the existing HARNESS ownership, model-access and authenticated HTTP boundaries. It reuses Capability Forge's exact Linux/seccomp executor. It introduces no financial account, paid API access, or automatic deployment.

This is an executable research implementation. Passing its software tests does not establish the decisive achievement above. The live evidence report records the actual trial separately.

| Stage | Executable component | Result and boundary |
| --- | --- | --- |
| Read envisioned futures | `bridge/foresight_extract.py` | A local model extracts attributed forecasts, scenarios and intervention hypotheses from supplied snapshots. Exact quotations and hashes are checked. Extracted claims cannot become current operational observations. |
| Characterize conditions | `bridge/foresight.py` | Recomputes common outcome requirements and alternative-route requirements. Expired, disputed, reported, forecast and retracted evidence cannot satisfy present conditions. A future model can be a prerequisite of one route without becoming a prerequisite of the outcome. |
| Reopen affected work | Existing `bridge/frontier_monitor.py` | Initial or changed public-source observations are compared with registered evidence. Pending invalidation survives restart and retries after callback failure. Changed bytes require reassessment; they do not establish improved capability. |
| Discover an opportunity | `bridge/frontier_mission.py` | Requests at least three distinct candidate families, their missing means, strong alternatives, falsification tests, rival futures and value hypotheses. The model selects an attributed opportunity or abstains before receiving a construction contract. |
| Freeze acceptance | Mission `contract` action | Independently supplied development and withheld examples bind the selected outcome. The contract records reviewer, basis and limitations. Acceptance cannot be revised after seeing results in the same experiment. |
| Construct the missing means | `bridge/frontier_builder.py` | Generates isolated Python `solve(data)` programs. Development failures permit repair. Candidate source freezes before the withheld cohort, whose feedback cannot trigger a repair. This is broader than the previous arithmetic-expression grammar. |
| Construct a different successor | Mission second discovery and construction arms | First construction must qualify before a second objective is revealed. Both arms construct new code for the same second contract, with and without the exact retained source. Ordinary common tooling remains available to both. |
| Account for the result | `bridge/frontier_transfer.py` | Checks source, asset, task, information, runtime, attempt and resource identities. Reports engineering acceptance, distinctness review, resource differences, full acquisition costs, conventional comparison and economic claims separately. Unknown cost is not zero. |

HARNESS executes and preserves evidence. SUCCESSOR FABRIC uses the constructor to build missing capabilities. The retained source can participate in later construction. An improved inventor still requires a separate method comparison; retaining a useful tool does not establish RSI.

## Starting from documents

The public example, [`examples/frontier-foresight.json`](../examples/frontier-foresight.json), contains four deliberately short attributed excerpts:

- [Bush, *As We May Think* (1945)](https://www.theatlantic.com/magazine/archive/1945/07/as-we-may-think/303881/).
- [Licklider, *Man-Computer Symbiosis* (1960)](https://groups.csail.mit.edu/medg/people/psz/Licklider.html).
- [Engelbart, *Augmenting Human Intellect* (1962)](https://dougengelbart.org/pubs/augment-3906.html).
- [Aschenbrenner, *Situational Awareness: From GPT-4 to AGI* (2024)](https://situational-awareness.ai/from-gpt-4-to-agi/).

The example's source hashes cover the stated **excerpts**, not entire remote pages. Its claims are an attributed starting set; they are not a representative sample of humanity's foresight. Its conditions and outcomes begin empty so a prescribed solution catalogue does not determine the first discovery. Its contemporary forecast remains a dated forecast, not an accepted future date. No market size, probability, measured productive benefit or revenue is supplied.

Additional authorized document snapshots can be passed to the `extract` action:

```json
{
  "route": {"provider": "local", "model": "your-configured-model"},
  "catalog_id": "my-foresight-corpus",
  "version": "1",
  "recorded_at": "2026-11-21T18:00:00Z",
  "sources": {
    "source-id": {
      "url": "https://example.org/document",
      "title": "Document title",
      "kind": "historical",
      "published_at": "1962-10",
      "observed_at": "2026-11-21T17:00:00Z",
      "snapshot": {"body": "Authorized source text", "sha256": "ACTUAL_SHA256", "scope": "excerpt"}
    }
  }
}
```

Replace illustrative metadata and hashes with actual source evidence. Extraction validates snapshots, requests source-bound claims, and permits abstention. It does not establish whether a claim is true or whether its conditions hold today. Source retrieval remains with the existing authorized source transport or an explicitly prepared offline snapshot.

## Run it

Commands below run from `products/alpha-genesis-harness`. Keep the private workspace outside the repository. Local configuration uses the existing connector format and explicit provider/model aliases. The implemented experimental constructor requires a local model and the existing Linux sandbox; no paid model key is needed. Other native HARNESS platforms retain their existing functions, but this particular Python/seccomp construction path is Linux-specific.

For a local server already available to the client:

```bash
python scripts/frontier_mission.py register \
  --workspace /absolute/private/frontier \
  --config /absolute/private/local-model.json \
  --input examples/frontier-foresight.json \
  --output /absolute/private/registered.json

python scripts/frontier_mission.py discover \
  --workspace /absolute/private/frontier \
  --config /absolute/private/local-model.json \
  --id MISSION_ID --stage first \
  --output /absolute/private/first-discovery.json
```

Use the returned mission ID. A runtime that rejects the request, a malformed reply, a fabricated quotation and abstention all remain unsuccessful observations. A source-backed proposal is not yet a validated opportunity.

The hash-pinned launcher owns the CPU model and client in the same process environment. This also works where separate execution calls have separate loopback namespaces:

```bash
python scripts/run_frontier_local.py discover \
  --workspace /absolute/private/frontier \
  --server /absolute/llama-server \
  --server-sha256 ACTUAL_SERVER_SHA256 \
  --model /absolute/model.gguf \
  --model-sha256 ACTUAL_MODEL_SHA256 \
  --mission examples/frontier-foresight.json \
  --output /absolute/private/first-discovery.json
```

The included example uses alias `frontier-qwen-coder-7b`; the launcher pins the actual supplied bytes rather than trusting the alias. It records context, threads, seed, temperature, launcher identity, startup time and observed model CPU/RSS. Its current receipt explicitly excludes shutdown CPU and unknown acquisition, energy, human and host costs. It refuses to overwrite an existing trial output. Context and per-request output limits are actual runtime resources, not a universal invention horizon.

## Independent acceptance after discovery

The `contract` action takes `id`, `stage` and a `contract` containing:

```json
{
  "objective": "EXACT_SELECTED_OUTCOME",
  "family": "EXACT_SELECTED_TASK_FAMILY",
  "acceptance": "The observable outcome and its input/output semantics, without prescribing the mechanism.",
  "development": [{"input": {}, "expected": {}}],
  "qualification": [
    {"input": {"case": "withheld-a"}, "expected": {}},
    {"input": {"case": "withheld-b"}, "expected": {}}
  ],
  "review": {
    "reviewer": "Actual reviewer identity",
    "basis": "How expected answers and their link to the beneficial outcome were independently established.",
    "limitations": "Unmeasured operational usefulness and other genuine limitations."
  }
}
```

This block describes the interface, not a valid economic experiment. Use actual independently checked examples. Inputs cannot repeat across the development/qualification split. Ordinary mission views expose only the withheld cohort's count and identity. An authenticated explicit export includes the full experiment for the operator and independent review; it must never be placed in a builder prompt.

The present implementation does not autonomously certify its own proposed acceptance cases. This boundary prevents a model from inventing an easy test and treating success on it as useful invention. A model may help prepare a proposed contract, but an independent outcome/answer check remains necessary. The reviewer can be an appropriately attributed separate assistant, a domain evaluator or an operator; that role is not commercial certification.

Build the first capability using the configured connector or the pinned launcher:

```bash
python scripts/frontier_mission.py contract \
  --workspace /absolute/private/frontier --input /absolute/private/first-contract.json

python scripts/run_frontier_local.py build \
  --workspace /absolute/private/frontier --id MISSION_ID --arm first \
  --server /absolute/llama-server --server-sha256 ACTUAL_SERVER_SHA256 \
  --model /absolute/model.gguf --model-sha256 ACTUAL_MODEL_SHA256 \
  --output /absolute/private/first-construction.json
```

Construction emits an executable program and exact test receipts. All generated programs run with the existing executor's filesystem, network and process restrictions. Its conventional `rational_affine` helper is available equally to all arms; it is not the retained invention. Failed candidates and uncertain dispatches stay in the record. An interrupted arm cannot silently restart as if its earlier work cost nothing. A materially revised experiment receives a new registration while preserving its predecessor.

## A genuinely different second construction

After the first capability qualifies, run second discovery with `--stage second`, independently freeze its contract, and execute both `--arm with_asset` and `--arm without_asset`. The first arm receives the verified retained source for composition or adaptation; the second has the same public contract, base model and common tooling without that source. Each must construct a fresh program. The second contract and comparison policy freeze before either construction arm starts.

Different labels, output names or input rows cannot by themselves establish a different valuable objective. The protocol requires an attributed independent distinctness review. The service rejects an identical objective/family or repeated qualification cohort, and the stronger audit rejects an unchanged first artifact relabelled as the second.

The `compare` action records the three arm results. An optional conventional source program can be checked on the same withheld cohort. This is a useful executable reference; a supplied program does not establish that a competent human-plus-conventional-software route has been fully measured. The standalone transfer protocol also accepts separately attributed conventional construction, ordinary reuse and value-review receipts. Strong outside routes must be admitted when evaluating real economics; the sandbox's finite library set is not evidence that a broader existing route cannot solve the problem.

The report separates first-asset acquisition, second-arm construction, failed work, integration, verification, execution and maintenance. Client and sandbox telemetry does not include an independently hosted model's CPU. Model usage is not a bill. Unknown amounts and missing resource stages remain unknown. Actual revenue requires its own reconciled commercial evidence through the existing enterprise accounting; this component creates no ledger or spending authority.

## Dynamic evidence and recovery

`observe` recomputes the frozen catalogue using new condition observations or source retractions. Each observation binds a condition, source hash, exact quotation, explicit evidence kind, status, observation time and expiry. The example functions in `tests/test_foresight.py` show a complete valid record. `kind="observed"` is an explicit operational attestation; a paper reporting performance uses `reported`. Quote verification alone does not establish semantic entailment.

Action-time refresh detects expired evidence even without a new manual observation. Existing source monitoring reopens affected missions when their underlying public bytes differ. A short excerpt and a full-page transport hash describe different byte sets; a mismatch conservatively requires recapture and review rather than proving the excerpt false. Invalidating a source preserves the earlier asset and its historical tests, but blocks further advancement under that source version. Old implementation-bound experiments remain historical and cannot run under changed code.

The HTTP connector exposes authenticated `/api/frontier-missions/{extract,register,get,observe,discover,contract,build,compare,export}` actions and a status endpoint. It reuses existing token and origin protections. There is no new unattended model-generation worker: periodic observation uses the existing monitor's explicit configuration; invention stages run through an invoked mission action. This implementation does not schedule an external automation or claim autonomous operation while no worker is active.

## Vérification et utilisation en français

FRONTIER Ω relie maintenant les documents de prospective, les conditions observables, la découverte d'une occasion, la construction d'un programme et une comparaison portant sur un second objectif différent. Le système conserve les sources et leurs empreintes, les tentatives infructueuses, les limites des mesures et les coûts inconnus.

Une prévision, même célèbre, ne devient jamais une observation actuelle. Une condition nécessaire à une voie particulière ne devient pas automatiquement nécessaire au résultat recherché. Les voies alternatives restent ouvertes. Une modification de source, une rétractation ou l'expiration d'une observation provoque une réévaluation sans effacer l'expérience précédente.

Le modèle propose plusieurs possibilités avant de recevoir le contrat de construction. Après sélection, le contrat d'acceptation doit être vérifié indépendamment et figé. Le constructeur voit les exemples de développement, mais pas les cas de qualification réservés. Le programme est figé avant cette qualification. Une qualification réussie démontre uniquement la réussite des cas enregistrés.

Pour le deuxième objectif, le même inventeur construit avec puis sans le moyen conservé, sous le même contrat public et avec les mêmes outils ordinaires. Une revue distincte doit établir que l'objectif est réellement différent et utile. Un changement d'étiquette ou de données d'entrée ne suffit pas. L'amélioration de l'inventeur, l'utilité économique, la monétisation et la valeur cumulée après tous les coûts restent des conclusions séparées.

Les commandes ci-dessus utilisent exclusivement un modèle local et le bac à sable Linux existant. Elles n'autorisent ni API payante, ni dépense, ni déploiement. Les résultats scientifiques réels sont ceux du rapport d'expérience lié à cette version; les tests logiciels et les scénarios de vérification ne constituent pas une invention économique démontrée.
