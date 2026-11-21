# Economic mission response-schema repair

This dependent correction addresses an observed failure before construction in
PR #514. It is supporting engineering work. The first economic invention and
causal second-invention proof remain unestablished.

## Observed defect and correction

The previous generation schema allowed arbitrary strings. The parser limited
quotes to 180 characters, identifiers to 40, descriptions to 1,000 and the
rationale to 1,200. A recorded response with quotation lengths 582, 584 and 582
therefore satisfied the supplied schema but failed the parser. A later
confirmation returned one citation for three hypotheses.

The corrected schema uses the existing parser limits. When the existing local
connection explicitly supports JSON Schema, it also enumerates registered
source/contract identifiers and requires one confirmation per prior hypothesis.
Null selection and null contracts remain available. The engine does not rewrite
quotes, normalize identifiers, infer a selection or weaken evidence admission.
Qualification inputs and answers remain outside model requests.

## Executed evidence

See [the compact source-bound receipt](../evidence/ECONOMIC-MISSION-SCHEMA-REPAIR.json).

- 32 focused tests passed, including three new regressions for the observed
  failures, actual schema dispatch, preserved abstention and withheld answers.
- The full local Python suite ran 559 tests: 558 passed and one skipped.
- A separate assistant agent reviewed the patch without editing it and found
  no material issue. This is code review, not independent commercial validation.
- A Qwen3 4B reproduction remained paused. Its history retains two context
  preflight refusals, an intervening server-start failure and a later backend
  connection loss during prompt processing. These are not successful inference.
- A separately registered Qwen2.5 Coder 1.5B trial completed one response
  (1,332 input tokens; 677 output tokens). The response passed schema/parser
  checks, but repeated one proposed outcome, supplied no verified source quotes
  and explicitly abstained. The run ended `needs_review`, with no builder call,
  qualification check or productive asset.

Source hashes and prior negative trial identities are retained. The local
registrations preceded execution; this report is published after observation.
Measured command wall/CPU time is not full monetary cost. No paid API request or
real transaction was made. No performance-success probability is estimated from
these two different model routes.

## Reproduce the focused checks

From `products/alpha-genesis-harness`:

```sh
python -B -m unittest tests.test_economic_mission tests.test_output_schema tests.test_workflow_schemas -v
python -B -m unittest discover -s tests -q
```

The ordinary mission CLI in [ECONOMIC-MISSION.md](ECONOMIC-MISSION.md) remains the
operating entry point. Enable `json_schema: true` only for a compatible local
connection. Configure its real context capacity to cover the conservative
prompt, schema, framing and output estimate. A context refusal or backend
interruption remains a recorded failure; resume its existing workspace only
after diagnosing the cause.

## Scope of the next proof

A source-associated contract verifies its stated calculation. It does not by
itself verify a proposed economic outcome. The current pilot supplies complete
arithmetic goals, and its last-two-input cohort tests reuse within the same
task. Neither establishes discovery without a supplied solution or construction
of a second different invention. The next substantive experiment still needs a
real beneficiary workflow, independently checked useful benefit, strong complete
alternatives, full costs and a distinct successor construction with and without
the retained capability. An external customer or prior sale is not required for
that internal experiment; monetization remains separate.

## Français

Cette correction dépendante répare un échec observé avant la construction dans
la PR no 514. Le schéma de génération autorisait des chaînes que l'analyseur
refusait ensuite : trois citations mesuraient 582, 584 et 582 caractères alors
que la limite était de 180. Un autre essai avait fourni une seule confirmation
pour trois hypothèses.

Le schéma reprend maintenant les limites existantes, énumère les identifiants
enregistrés lorsqu'une connexion locale compatible utilise JSON Schema et exige
une confirmation par hypothèse. L'abstention reste possible. Les citations ne
sont ni corrigées ni tronquées, et les critères d'admission demeurent inchangés.
Les données et réponses de qualification ne sont pas transmises au modèle.

Les 32 tests ciblés ont réussi. La suite complète a exécuté 559 tests : 558
réussites et un test ignoré. Une revue de code séparée n'a trouvé aucun problème
substantiel. L'essai Qwen3 4B est resté en pause après des refus de contexte et
des interruptions du moteur local. L'essai distinct Qwen2.5 Coder 1.5B a produit
une réponse conforme au format, mais a répété le même résultat proposé, fourni
aucune citation vérifiée et choisi de s'abstenir. Il s'est terminé par
`needs_review`, sans construction ni qualification d'un actif.

La correction améliore la cohérence du protocole de sortie. Elle ne démontre
pas une invention économiquement utile. Le premier cycle demandé reste à
établir sur une activité réelle, puis sur la construction d'une seconde
capacité différente, avec comparaison causale et coûts complets. Aucun client
externe ni vente préalable n'est nécessaire pour cette expérience interne. La
monétisation conserve sa propre exigence de preuve.
