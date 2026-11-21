# Ω ALPHA economic missions

Start with an ambition, a beneficiary, authorized primary sources and registered experiments. HARNESS collects the sources and asks a loopback model to compare opportunities. A literal quotation, a matching source ID and the model's proposed contract mapping do not establish that the experiment measures the beneficiary outcome. By default, that proposal remains unqualified and stops for review.

An operator may separately opt in to **registered instrument qualification only**. In this mode, the builder creates a declarative instrument, HARNESS seals its digest and then opens the withheld cases. Passing establishes output equality on those cases. The proposed economic outcome remains an unverified hypothesis, even if its wording matches the contract's goal. See [the outcome boundary and its regression evidence](ECONOMIC-MISSION-OUTCOME-BOUNDARY.md).

## Run the public-record experiment

Use a local HARNESS configuration for a running loopback model with at least 2,304 output tokens. The trial was designed for the [pinned local model and runtime used by HARNESS](../scripts/qualify_hosted_local.py). Specify their actual configured IDs. Enable `json_mode` for compatible local servers. Prefer `json_schema: false` if whole-response grammar constrains generation speed on your backend.

```sh
python3 scripts/qualify_economic_mission.py \
  --config /absolute/local-config.json --provider local --model YOUR_MODEL_ID \
  --instrument-only \
  --work /absolute/new-experiment
```

The experiment uses published British electricity-intensity observations, Canadian reference exchange rates and USGS catalogue records. The source snapshots, experiment criteria and fresh cohort are frozen before the first model call. Use `--sources /absolute/previous-experiment/SOURCES.json` to replay the original bytes, or `--language fr` to request French discovery. `RESULT.json` links the proposed selection, technical scope, provenance, model usage and each verdict. Completed instrument trials export `asset.json` and `RUN_INSTRUMENT.py`. Omit `--instrument-only` to retain hypotheses without admitting their unverified outcome-to-test mappings.

## Operate a private mission

The experiment writes a working `MISSION.json` for the existing workflow CLI and authenticated connector. For a new mission supply your objective, explicit researcher and builder routes, model and action allocations, and the sole `construct_instrument` permission. Set `economic_mission` to an object with:

- `beneficiary` and optional `language` of `en` or `fr`.
- `sources` keyed by short IDs. Each source has an exact HTTPS `url` and a `label`. An optional `anchor` selects a nearby excerpt. For offline operation include a `snapshot` with UTF-8 `body` and its `sha256`.
- `contracts` keyed by experiment IDs. Each entry has a textual `goal`, the relevant `source` ID, and disjoint `development` and `qualification` arrays. Each row has an `input` object and an independently derived `expected` object. An empty experiment map supports discovery and abstention.
- Optional `confirm_citations: true` adds one model call when a proposed selection fails the evidence checks. The model can choose among exact excerpts and compatible experiments for its original hypotheses. Both decisions remain in the mission history.
- Optional `qualification_scope: "registered_instrument"` authorizes only construction and withheld-case qualification of the nominated instrument. This is an operator-frozen field; the model cannot set it. Omission preserves the outcome hypothesis without admitting construction. No general outcome-specific evaluator is implemented here.

To use HARNESS's live public-source acquisition, set `local_only` to false in the mission and connector, list the exact hosts in `source_hosts` and omit the relevant snapshots. Inference still requires a loopback provider. HARNESS uses the existing pinned public-address and TLS checks. Source observations include their byte digests and any failure; matching an excerpt checks citation fidelity. The operator remains responsible for the relevance of the source and the validity and applicability of the experiments. Keep qualification inputs and answers outside the public context and development data.

```sh
python3 -m bridge.workflows create --config /absolute/local-config.json --spec /absolute/MISSION.json --workspace /absolute/private-workspace
python3 -m bridge.workflows run --config /absolute/local-config.json --run-id RUN_ID --workspace /absolute/private-workspace
python3 -m bridge.workflows inspect --run-id RUN_ID --workspace /absolute/private-workspace
python3 -m bridge.workflows export --run-id RUN_ID --workspace /absolute/private-workspace --output /absolute/ARCHIVE.json
```

If a request is interrupted, use `resume` with the same workspace, ID and model configuration. The checkpoint tracks model attempts and preserves a frozen candidate across interruptions. An interrupted request can have consumed resources before the result was recorded. Exports open when the mission ends and contain qualification answers and operator context. Review the archive before sharing it.

The portable evaluator accepts fresh input with `python3 RUN_INSTRUMENT.py asset.json input.json`. To re-execute every frozen case, run `python3 scripts/qualify_economic_mission.py --replay /absolute/ARCHIVE.json`. Reuse the qualified asset through the existing HARNESS capability registry and rerun independent checks for every new application. The trial compares the retained instrument with the same executable outside the registry and a competent conventional implementation.

The operating assessment uses the existing HARNESS proof-to-market calculator with the narrow instrument objective. `INSTRUMENT_CONSTRUCTION` and `REGISTERED_INSTRUMENT_ACCEPTANCE` report technical results. All broader outcome, invention, value and compounding verdicts remain `not_established`, on both technical success and technical failure. A failed calculator does not disprove the beneficiary outcome either. Complete monetary costs, adoption, actual settlement and frontier parity require separate evidence. Fresh inputs to the same formula are recorded as `fresh_instance_reuse`; they do not construct a second capability.

The [trial records](../evidence/ECONOMIC-MISSION-TRIALS.json) preserve completed and interrupted model requests with their source identities and dispositions.

## Français

Commencez par un objectif, un bénéficiaire, des sources primaires autorisées et des expériences enregistrées. Le modèle local propose plusieurs occasions et les associe à des sources et à des essais. Une citation exacte et une association proposée par le modèle ne prouvent pas que l'essai mesure le résultat attendu. Par défaut, la mission conserve les hypothèses et s'arrête pour examen.

Pour qualifier uniquement le calcul enregistré, utilisez `--instrument-only`, ou `qualification_scope: "registered_instrument"` dans une nouvelle mission. Le constructeur produit l'instrument; son empreinte est scellée avant l'ouverture des cas réservés. La réussite établit seulement les sorties calculées sur ces cas. Le résultat économique reste non vérifié. Ajoutez `--language fr` pour la découverte en français. `RESULT.json` conserve cette portée, la provenance, la consommation et les verdicts; `asset.json` et `RUN_INSTRUMENT.py` permettent une exécution séparée après réussite technique.

Pour une mission privée, utilisez le fichier `MISSION.json` produit par l'essai comme modèle. Indiquez `beneficiary`, `language`, les `sources` et les `contracts`. Chaque source possède une adresse HTTPS précise et un libellé. En mode hors ligne, fournissez aussi son contenu UTF-8 et son empreinte SHA-256 dans `snapshot`. Chaque contrat associe un objectif et une source à des cas de développement et de qualification distincts. Calculez les résultats attendus indépendamment et gardez les cas de qualification hors du contexte transmis au modèle. Avec `confirm_citations: true`, le modèle peut vérifier une seconde fois les extraits et le contrat de son choix initial.

Utilisez les commandes `create`, `run`, `inspect` et `export` ci-dessus. Reprenez un essai interrompu avec `resume`, le même identifiant, le même dossier de travail et le même modèle. Vérifiez le contenu de l'archive avant de la transmettre. Elle comprend les données et résultats de qualification ainsi que le contexte privé.

Vérifiez chaque nouvelle application de l'instrument. L'essai compare sa réutilisation dans le HARNESS, le même exécutable en dehors du registre et une solution conventionnelle. L'évaluation économique indique les coûts encore inconnus. L'adoption, les recettes encaissées, la parité avec un modèle de pointe et l'amélioration de la méthode d'invention exigent des preuves propres.
