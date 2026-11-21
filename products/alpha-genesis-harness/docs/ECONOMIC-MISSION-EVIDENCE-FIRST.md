# Ω ALPHA — Evidence-first opportunity discovery (research mode)

**Scope:** An experimental two-pass local-model discovery mode stacked on the source-bound economic mission in PR #514 and the schema repair in PR #516. This is not a release, not an accepted invention, and not a finding of economic advantage.

## The problem this changes

The earlier discovery prompt included **the complete goals of the operator-registered calculations** before the model proposed an economic opportunity. The successful path could therefore be "choose an already described calculation" rather than discover a missing economic means.

A recorded local trial also echoed the supplied experiment instructions as if they were primary-source evidence, proposed duplicate outcomes and generated no verified source quotation. The strict source checker properly refused the proposals. That negative evidence remains preserved.

## What now executes

Opt in with `--blind-discovery` in the existing public-record experiment, or set `economic_mission.blind_discovery=true` and `confirm_citations=true` in a normal authorized mission.

1. **Evidence-first discovery.** HARNESS collects source snapshots; the first model prompt receives the actual beneficiary, ambition and bounded source excerpts, **not the operator-registered experiment goals or identifiers**. The output schema requires every initial hypothesis's `contract` to be null. The model can nominate one hypothesis or abstain. An attempt to use a contract prematurely is rejected even on a backend that ignores the JSON Schema.
2. **Separate citation/experiment nomination.** A second model response sees the immutable first-pass hypotheses, exact source citation options and available registered experimental goals. It may nominate a contract or abstain. The source/contract checker validates literal citation evidence and registered source identity; it does **not** independently establish that the experiment measures the proposed economic outcome. The second stage cannot edit the first hypothesis's proposed outcome.
3. **Outcome boundary.** A cited, same-source nomination now remains `outcome_contract_linkage_unverified` by default. The prior claim that this predicate rejected unrelated tests was false: the [LINKAGE218 counterexample](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/518) demonstrated admission of a clinic-service hypothesis to an arithmetic test. The [repair](ECONOMIC-MISSION-OUTCOME-BOUNDARY.md) preserves the hypothesis and withholds construction. An explicit operator `qualification_scope: "registered_instrument"` may instead run the registered calculation under a technical-only claim; the hypothesis remains unverified. A new outcome-specific evaluator would require a separately frozen mission and independent adequacy evidence.
4. **Source-bound receipt.** The runner labels this protocol as `evidence-first`; previous experiments and their exact input contracts remain unchanged. The system can refuse and preserve a hypothesis that lacks suitable experimental evidence.

## Live reproduction

Use a real local loopback model (with a valid operator-approved configuration), the unchanged public-source identities and the same permitted HARNESS construction tool:

    cd products/alpha-genesis-harness
    python3 scripts/qualify_economic_mission.py \
      --config /absolute/local-config.json \
      --provider local \
      --model YOUR_AUTHORIZED_MODEL_ID \
      --sources /absolute/previous/SOURCES.json \
      --blind-discovery \
      --instrument-only \
      --work /absolute/new-evidence-first-experiment

This command explicitly opts into technical instrument qualification. Omit `--instrument-only` to perform discovery without granting outcome admission. The flags `--language fr` and `--replay` retain their documented purpose. Use a fresh `--work` path. Neither the model configuration nor source snapshots are invented by this note. Check exact local provider capacity and costs. No paid API is required or authorized.

Existing regression tests cover the first-pass non-disclosure of registered calculations and sealed answers, exact schema null contract, separate second-pass matching, refusal of premature contracts, and abstention. These are **protocol correctness tests**; they cannot show that a real AI discovered a valuable outcome.

## Consequential next experiment

Replace the historical preselected calculations with a beneficiary-centric envelope and actual operating records for **MONTREAL.AI**. Let the model identify the activity, binding constraint, missing executable capability and testable economic effect, without giving it a proposed solution.

- Freeze the beneficiary outcome and independent acceptance condition, not the intended algorithm or business model.
- Collect at least two legitimate independent operational/market records. Do not fabricate demand, beneficiaries or transactions.
- Keep strong complete alternatives and operator permissions intact. An ordinary specialist tie must be reported.
- Permit a newly identified hypothesis with no available contract to remain `HOLD` while an independent team prospectively defines a valid test.
- On a first truly accepted useful capability, construct a **different useful capability** in a second mission, then compare retained-vs-unretained under matched conventional tools, information, acceptance and full costs. Two new inputs for the same formula are **not** a second invention.
- Keep actual revenue, technical correctness, new economic attainability, inventor improvement and after-cost compounding separate.

The next scientific milestone remains **one autonomously discovered and independently verified economically useful capability**. The present two-pass protocol improves experimental separation, but does not independently certify novelty or economic benefit. No such result is claimed here.

## Français

**Découverte d'abord, proposition d'essai ensuite.** Le modèle reçoit les preuves primaires, le bénéficiaire et l'objectif, sans les calculs définis à l'avance. Lors d'une seconde étape, il peut proposer une association entre les hypothèses inchangées, une citation exacte et un essai. Cette association reste non qualifiée tant que la pertinence de l'essai pour le résultat attendu n'est pas établie indépendamment.

L'option `--blind-discovery` active cette procédure avec le modèle local autorisé. `--instrument-only` autorise séparément la qualification du calcul enregistré sur ses cas réservés. Ni la réussite ni l'échec de ce calcul ne qualifie le résultat économique. Les essais historiques et leurs échecs restent intacts.
