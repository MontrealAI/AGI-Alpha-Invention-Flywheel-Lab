"""Generate training and development briefs from disjoint language templates."""

import argparse
from itertools import product
from pathlib import Path
import random

from formalize import COMPATIBLE, FIELDS, FormalizationEnvironment, write_jsonl


TRAIN = {
    "en": {
        "timing": [
            "The purchase and contingent policy are public. The opponent fixes a hidden state. A private cue reaches the chooser before the binding row action, and the opponent cannot revise.",
            "They announce whether they buy and their policy, then the rival locks the state. Before choosing an action the signal reaches the buyer alone. The rival has no change right.",
            "The choice is irrevocable before the signal comes in. The opponent's hidden state was fixed. Buying and the policy were public.",
            "An alert is delivered after the binding action. Its resolution cannot inform that choice. The opponent has fixed the state.",
            "The purchaser receives a private cue first and chooses a row. After seeing the realized row, the opponent may change the state.",
            "The opponent can revise its hidden state after observing the signal or the resulting decision.",
            "A noisy indicator is mentioned. The record does not specify when the chooser receives it or whether the opponent can react.",
            "The buyer might use a reading. Access and the order of commitments are unresolved.",
        ],
        "units": [
            "The payoffs and the charge are measured in the same game points.",
            "Both the fee and all returns use USD.",
            "Payoffs are in game points and the fee is in Canadian dollars. There is no approved conversion.",
            "Results use USD and the charge uses euros, without an exchange rate.",
            "The charge scale is not stated. Combining the monetary amounts would need confirmation.",
            "The payoff numbers use points. The fee denomination was never recorded.",
        ],
        "fee": [
            "Buying costs {fee}.",
            "The inspection charge is {fee}.",
            "No numeric fee is stated.",
            "The fee amount remains pending.",
        ],
        "accuracy": [
            "The cue is correct in {left}% of cases for the first state and {right}% for the second.",
            "The two known conditional accuracies are {left}% and {right}%, in state order.",
            "The conditional signal accuracies were not supplied.",
            "No calibrated confidence for either state is available.",
        ],
    },
    "fr": {
        "timing": [
            "L'achat et la politique conditionnelle sont publics. L'adversaire fixe l'état caché. L'agent seul reçoit le signal avant son choix irrévocable et l'adversaire ne peut plus changer l'état.",
            "On annonce l'achat et la politique, ensuite le rival fixe l'état. Le décideur reçoit un signal privé avant l'action. Le rival n'a aucun droit de révision.",
            "Le signal arrive après le choix définitif. L'état choisi par le rival est déjà fixé et l'achat a été annoncé.",
            "L'observation est révélée trop tard. Le décideur a déjà pris un engagement irrévocable.",
            "Après avoir vu la décision réalisée, le rival peut modifier son état caché.",
            "L'adversaire observe le signal obtenu et peut ensuite remplacer son état par un autre.",
            "Un signal est mentionné. Son moment d'arrivée et le caractère privé de l'observation restent inconnus.",
            "Le dossier ne précise pas l'ordre entre la lecture, l'engagement et le choix adverse.",
        ],
        "units": [
            "Les gains et le coût sont exprimés dans la même unité de points.",
            "Tous les montants, y compris les frais, sont en EUR.",
            "Les gains sont des points et les frais sont en dollars canadiens, sans conversion autorisée.",
            "Les gains utilisent des unités différentes de celles du prix, sans taux de conversion.",
            "La monnaie du coût reste inconnue.",
            "Le document précise l'unité des gains seulement. Le prix n'a pas de monnaie déclarée.",
        ],
        "fee": [
            "Le coût de l'achat est de {fee}.",
            "Les frais s'élèvent à {fee}.",
            "Le montant des frais est absent.",
            "Le coût d'acquisition reste à fournir.",
        ],
        "accuracy": [
            "Les précisions conditionnelles sont de {left} % et {right} %, dans l'ordre des états.",
            "La lecture est correcte dans {left} % des cas pour le premier état et {right} % pour le second.",
            "Aucune des précisions du signal n'a été fournie.",
            "Les données de calibration par état ne sont pas disponibles.",
        ],
    },
}

DEVELOPMENT = {
    "en": {
        "timing": [
            "An audience knows the inspection decision and conditional plan. The rival's concealed selection is sealed. Only the agent opens the reading and then selects a row.",
            "The decision process freezes the selected row when the readings are still sealed. Later, a technician supplies the reading.",
            "Seeing the chosen row gives the rival one last opportunity to substitute a different state.",
            "The test agreement leaves disclosure and the sequence of choices open.",
        ],
        "units": [
            "All transfer amounts including the charge are expressed in a single common USD scale.",
            "The ledger pays in production credits, whereas the observation invoice is in EUR and there is no approved conversion.",
            "The test record names no denomination for the observation invoice.",
        ],
        "fee": ["The amount on the invoice is {fee}.", "There is an invoice with the amount unresolved."],
        "accuracy": ["Verified calibration by state is {left}% and {right}%.", "A calibration report was not delivered."],
    },
    "fr": {
        "timing": [
            "Le projet annonce l'achat et la règle. L'adversaire scelle sa sélection cachée. Seul le décideur ouvre ensuite le relevé avant de réserver une ligne.",
            "Le décideur immobilise la ligne alors que le relevé est fermé. Il lit la mesure une fois son choix fixé.",
            "Une fois que le rival connaît la ligne jouée, il dispose d'un dernier droit de substitution de l'état.",
            "Le mandat laisse à préciser la divulgation et la chronologie des engagements.",
        ],
        "units": [
            "Les flux, y compris le prix de l'observation, font appel à une échelle commune en points.",
            "Les gains sont en crédits et la facture en EUR. Aucun taux n'est disponible.",
            "Le libellé monétaire de la facture ne figure pas dans le dossier.",
        ],
        "fee": ["Le montant acquitté est {fee}.", "Le montant de la facture est en attente."],
        "accuracy": ["Les deux taux, par ordre d'état, sont {left} % et {right} %.", "Le relevé de calibration n'a pas été transmis."],
    },
}

SEEDS = {"train": 758079, "development": 878243}


def materialize(partition):
    rng = random.Random(SEEDS[partition])
    bank = TRAIN if partition == "train" else DEVELOPMENT
    combinations = list(product(*FIELDS.values()))
    combinations.remove(tuple(COMPATIBLE.values()))
    pairs = []
    for lang, language in bank.items():
        selected = combinations + [tuple(COMPATIBLE.values())] * 17 if partition == "train" else (
            rng.sample(combinations, 12) + [tuple(COMPATIBLE.values())] * 4)
        for values in selected:
            timing, unit, missing = values
            fee = rng.randrange(2, 24) if missing in ("complete", "accuracy") else None
            accuracy = [rng.randrange(32, 100), rng.randrange(32, 100)] if missing in ("complete", "fee") else None
            payoffs = [rng.sample(range(-15, 25), 2) for _ in range(rng.randrange(2, 5))]
            variants = 2 if partition == "train" else 1

            def sentence(field, index):
                choices = language[field][index * variants:(index + 1) * variants]
                return rng.choice(choices)

            subjects = [sentence("timing", FIELDS["timing"].index(timing)),
                        sentence("units", FIELDS["units"].index(unit)),
                        sentence("fee", int(fee is None)).format(fee=fee),
                        sentence("accuracy", int(accuracy is None)).format(
                            left=None if accuracy is None else accuracy[0],
                            right=None if accuracy is None else accuracy[1])]
            rng.shuffle(subjects)
            identity = f"{partition}-{lang}-{len(pairs):03}"
            case = {"id": identity, "lang": lang, "brief": " ".join(subjects),
                    "payoffs": payoffs, "accuracy": accuracy, "fee": fee}
            oracle = dict(zip(FIELDS, values))
            environment = FormalizationEnvironment(case, oracle)
            environment.reset()
            _, reward, _, evidence = environment.step(oracle)
            if reward != 1:
                raise ValueError("Structured teacher could not verify a training or development case")
            pairs.append({"case": case, "oracle": oracle, "teacher_disposition": evidence["disposition"]})
    rng.shuffle(pairs)
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    for partition in SEEDS:
        write_jsonl(args.output / f"{partition}.jsonl", materialize(partition))


if __name__ == "__main__":
    main()
