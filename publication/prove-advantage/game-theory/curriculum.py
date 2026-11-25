# SPDX-License-Identifier: Apache-2.0
"""Construct disjoint synthetic lessons for observation and rule citation."""

import argparse
from hashlib import file_digest
import json
from pathlib import Path
import random


ACCESS = ('known', 'hidden', 'unclear')
RULE_LIMIT = 8
FAMILIES = ('explicit-timing', 'permissions', 'bulletin', 'gate-order')


def digest(path):
    with Path(path).open('rb') as handle:
        return file_digest(handle, 'sha256').hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def validate_case(case):
    if set(case) != {'id', 'language', 'family', 'rules', 'queries'}:
        raise ValueError('Unexpected case fields')
    if case['language'] not in ('en', 'fr') or not all(
            isinstance(case[key], str) and case[key].strip() for key in ('id', 'family')):
        raise ValueError('Missing case identity')
    rules = case['rules']
    if not isinstance(rules, list) or not 1 <= len(rules) <= RULE_LIMIT or not all(
            isinstance(rule, str) and rule.strip() for rule in rules):
        raise ValueError('Invalid rule list')
    queries = case['queries']
    query_keys = {'observer', 'decision', 'datum'}
    if not isinstance(queries, list) or not 1 <= len(queries) <= 6 or not all(
            isinstance(query, dict) and set(query) == query_keys and all(
                isinstance(value, str) and value.strip() for value in query.values()) for query in queries):
        raise ValueError('Invalid observation queries')
    return case


def validate_oracle(case, oracle):
    if not isinstance(oracle, list) or len(oracle) != len(case['queries']):
        raise ValueError('Oracle coverage differs from queries')
    for answer in oracle:
        if (set(answer) != {'access', 'witness'} or answer['access'] not in ACCESS
                or not isinstance(answer['witness'], list) or not answer['witness']):
            raise ValueError('Invalid observation oracle')
        minimum = 0 if answer['access'] == 'unclear' else 1
        if any(type(index) is not int or not minimum <= index <= len(case['rules'])
               for index in answer['witness']):
            raise ValueError('Oracle cites a nonexistent or insufficient rule')
    return oracle


def read_cases(path):
    rows = json.loads(Path(path).read_bytes())
    if not isinstance(rows, list) or not rows:
        raise ValueError('Expected case list')
    cases = [validate_case(row) for row in rows]
    if len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Duplicate case IDs')
    return cases


def read_training(path):
    rows = json.loads(Path(path).read_bytes())
    for row in rows:
        validate_case(row['case'])
        validate_oracle(row['case'], row['oracle'])
    if not rows or len({row['case']['id'] for row in rows}) != len(rows):
        raise ValueError('Expected distinct lessons')
    return rows


def decisive(language, family, access, observer, other, choice, datum, place):
    index = ACCESS.index(access)
    if language == 'en':
        phrasings = {
            'explicit-timing': (
                f'{observer} receives the {datum} before filing the {choice}.',
                f'{observer} receives the {datum} after filing the {choice}, never earlier.',
                f'{observer} may receive the {datum} on either side of the {choice}; the timetable is unspecified.',
            ),
            'permissions': (
                f'{observer} checks the {datum} using a private display at the {choice}.',
                f'For the {choice} the {datum} is accessible only to {other}; {observer} has no way to see it.',
                f'The handbook does not say whether {observer} can access the {datum} at the {choice}.',
            ),
            'bulletin': (
                f'Everybody present in {place}, including {observer}, reads the {datum} before the {choice}.',
                f'The public display in {place} stays blank until {observer} finishes the {choice}; no earlier reading is possible.',
                f'Whether the display in {place} shows the {datum} before {observer} completes the {choice} is unresolved.',
            ),
            'gate-order': (
                f'The {choice} cannot become available to {observer} until the {datum} has been issued to them.',
                f'The {datum} cannot become available to {observer} until their {choice} has become final.',
                f'Both the {datum} and the {choice} go to {observer}, but no delivery order is guaranteed.',
            ),
        }
    else:
        phrasings = {
            'explicit-timing': (
                f'{observer} reçoit le {datum} avant de valider la {choice}.',
                f'{observer} reçoit le {datum} après la validation de la {choice}, jamais plus tôt.',
                f'{observer} pourra recevoir le {datum} avant ou après la {choice}. Le moment reste indéterminé.',
            ),
            'permissions': (
                f'{observer} consulte le {datum} sur un écran privé lors de la {choice}.',
                f'Au moment de la {choice}, seul {other} a accès au {datum}. {observer} ne peut pas le consulter.',
                f'Le règlement ne précise pas si {observer} pourra consulter le {datum} lors de la {choice}.',
            ),
            'bulletin': (
                f'Toutes les personnes dans la salle {place}, y compris {observer}, lisent le {datum} avant la {choice}.',
                f'L’affichage reste vide avant la {choice} de {observer}, sans autre moyen de lire le {datum}.',
                f'On ignore si l’affichage de la salle {place} montre le {datum} avant la {choice} de {observer}.',
            ),
            'gate-order': (
                f'{observer} ne peut faire la {choice} qu’une fois le {datum} reçu.',
                f'Le {datum} ne peut parvenir à {observer} qu’une fois la {choice} définitive.',
                f'On attend le {datum} et la {choice}, sans garantie de l’ordre pour {observer}.',
            ),
        }
    return phrasings[family][index]


def lesson(randomizer, split, language, family, access, number):
    people = ('Orla', 'Tavi', 'Nico', 'Jules', 'Amal', 'Iris', 'Maya', 'Elio', 'Nadir', 'Lea')
    observer, other = randomizer.sample(people, 2)
    beginning = split == 'train'
    if language == 'en':
        choices = ('price offer', 'allocation', 'reply', 'endorsement', 'order', 'seat reservation') if beginning else (
            'award ballot', 'deposit choice', 'closing vote', 'warehouse bid')
        data = ('blue tag', 'capacity code', 'reserve figure', 'shortlist', 'ledger cue', 'access mark') if beginning else (
            'supply note', 'gold key', 'seal value', 'load rating')
        place = randomizer.choice(('Atrium', 'Mile End', 'Block Three', 'Westfield'))
    else:
        choices = ('demande de quota', 'réponse', 'sélection', 'validation', 'réservation', 'proposition') if beginning else (
            'signature finale', 'conclusion', 'répartition', 'décision d’achat')
        data = ('code bleu', 'niveau de capacité', 'prix de réserve', 'signe privé', 'repère rouge', 'rang provisoire') if beginning else (
            'tarif cible', 'numéro de lot', 'taux de défaut', 'permis vert')
        place = randomizer.choice(('Berri', 'Noroît', 'Forillon', 'Gare'))
    choice, other_choice = randomizer.sample(choices, 2)
    datum, other_datum = randomizer.sample(data, 2)
    strength = decisive(language, family, access, observer, other, choice, datum, place)
    absent = access == 'unclear' and randomizer.randrange(4) == 0
    if absent:
        strength = (f'The clerk labels the envelope with the {datum}.' if language == 'en'
                    else f'Le greffe inscrit le {datum} sur l’enveloppe.')
    distract_access = randomizer.choice(ACCESS)
    distract_family = randomizer.choice(FAMILIES)
    distractor = decisive(language, distract_family, distract_access, other, observer, other_choice, other_datum, place)
    if language == 'en':
        ordinary = [f'The outcome uses the choices of {observer} and {other}.',
                    f'The {other_datum} denotes the inspection category.',
                    f'After both choices, records go to the clerk in {place}.']
    else:
        ordinary = [f'Le résultat dépend des choix de {observer} et de {other}.',
                    f'Le {other_datum} désigne la catégorie de contrôle.',
                    f'Après les deux choix, les dossiers sont déposés à la salle {place}.']
    rules = [(strength, 'answer'), (distractor, 'distractor'), *((rule, '') for rule in ordinary)]
    randomizer.shuffle(rules)
    witness = 0 if absent else next(i for i, (_, kind) in enumerate(rules, 1) if kind == 'answer')
    case = {'id': f'{split}-{number:03}', 'language': language, 'family': family,
            'rules': [rule for rule, _ in rules],
            'queries': [{'observer': observer, 'decision': choice, 'datum': datum}]}
    return {'case': case, 'oracle': [{'access': access, 'witness': [witness]}]}


def build(output):
    output.mkdir(parents=True)
    for split, repetitions, seed in (('train', 5, 152404), ('development', 1, 672113)):
        randomizer = random.Random(seed)
        rows = []
        for language in ('en', 'fr'):
            for family in FAMILIES:
                for access in ACCESS:
                    for _ in range(repetitions):
                        rows.append(lesson(randomizer, split, language, family, access, len(rows) + 1))
        randomizer.shuffle(rows)
        write_json(output / (split + '.json'), rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    build(parser.parse_args().output)
