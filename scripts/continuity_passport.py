#!/usr/bin/env python3
"""Read recorded CONTINUITY Ω v1 artifacts in English or French, without auditing.

Lire les artefacts CONTINUITÉ Ω v1 consignés en anglais ou en français, sans audit.
No core imports, subprocesses, network calls, financial actions, or input writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

# These are presentation vocabularies for the published v1 schemas, not audit rules.
ISSUES = {
    'MISSING_FROM_RESTORED_SNAPSHOT': ('Missing from the restored snapshot', 'Absent de l’instantané restauré'),
    'STALE_OR_CHANGED_RESTORED_QUANTITY': ('Stale or changed restored quantity', 'Quantité restaurée périmée ou modifiée'),
    'CANCELLED_ORDER_REAPPEARED': ('Cancelled order reappeared', 'Commande annulée réapparue'),
    'UNSUPPORTED_RESTORED_ORDER': ('Restored order without supporting source', 'Commande restaurée sans source justificative'),
}
FAILURES = {
    'BAD_AMENDMENT': 'Modification de commande invalide',
    'BAD_FULFILLMENT': 'Exécution de commande invalide',
    'BAD_RESTORED_RECORD': 'Enregistrement restauré invalide',
    'BETTER_DECLARED_SUPPLIER_IGNORED': 'Meilleur fournisseur déclaré ignoré',
    'BLOCKED_DOMAINS_INVALID': 'Domaines de défaillance exclus invalides',
    'BUYER_BUDGET': 'Budget de l’acheteur incohérent',
    'BUYER_BUDGET_INVALID': 'Budget de l’acheteur invalide',
    'BUYER_SYNTHETIC_ELIGIBILITY_MISSING': 'Admissibilité synthétique de l’acheteur absente',
    'DEADLINE_INVALID': 'Échéance invalide',
    'DEADLINE_MISMATCH': 'Échéances incohérentes',
    'DUPLICATE_ACCEPTANCE': 'Acceptation en double',
    'DUPLICATE_RESTORED_RECORD': 'Enregistrement restauré en double',
    'DUPLICATE_SUPPLIER_IDENTITY': 'Identité de fournisseur en double',
    'ECONOMIC_ARITHMETIC': 'Arithmétique économique incohérente',
    'EVENT_MALFORMED': 'Événement mal formé',
    'EVENT_PRODUCT_INVALID': 'Produit de l’événement invalide',
    'EVENT_PROVENANCE_MISSING': 'Provenance de l’événement absente',
    'EXERCISE_IDENTITY': 'Identités d’exercice incohérentes',
    'EXERCISE_ID_INVALID': 'Identifiant d’exercice invalide',
    'FAILURE_DOMAIN_IDENTITY': 'Identité du domaine de défaillance incohérente',
    'FULL_COST_CATEGORIES': 'Catégories de coûts complets invalides',
    'HANDOFF_DOES_NOT_MATCH_ORIGINAL_COMMITMENTS': 'Transfert différent des engagements d’origine',
    'HANDOFF_SCHEMA': 'Schéma du transfert invalide',
    'IDEMPOTENCY_BINDING': 'Liaison d’idempotence incohérente',
    'INPUT_SCHEMA': 'Schéma d’entrée invalide',
    'INVALID_ACCEPT_QUANTITY': 'Quantité acceptée invalide',
    'INVALID_EVENT_ORDER_ID': 'Identifiant de commande de l’événement invalide',
    'INVALID_EVENT_TARGET': 'Commande visée par l’événement invalide',
    'NO_OUTSTANDING_ORDERS': 'Aucune commande restante',
    'OBJECTIVE_HORIZON_INVALID': 'Horizon de l’objectif invalide',
    'OBJECTIVE_PRODUCT_INVALID': 'Produit de l’objectif invalide',
    'OUTCOME_CHARTER_RELAXED': 'Engagement fonctionnel assoupli',
    'OUTCOME_WINDOW_EXCEEDED': 'Fenêtre d’exécution dépassée',
    'PASSPORT_HANDOFF_BINDING': 'Liaison entre le passeport et le transfert incohérente',
    'PASSPORT_SCHEMA': 'Schéma du passeport invalide',
    'PERMITTED_DATA_SCOPE_ABSENT': 'Autorisation de partage des données absente',
    'PRODUCER_VERDICT_SCOPE': 'Portée du verdict du constructeur incorrecte',
    'QUOTED_COST_CHANGED': 'Coût annoncé modifié',
    'REQUIRED_UNITS': 'Quantité requise incohérente',
    'RESTORED_SNAPSHOT_MISSING': 'Instantané restauré absent',
    'RESTORE_CHALLENGE_FINDINGS': 'Constats de restauration incohérents',
    'SCOPE_MISREPRESENTED': 'Portée présentée de manière incorrecte',
    'SELECTED_SUPPLIER_IDENTITY': 'Identité du fournisseur sélectionné incohérente',
    'SOURCE_BINDING': 'Liaison à la source incohérente',
    'SOURCE_SEAL_INVALID': 'Empreinte de la source invalide',
    'SPEC_PROVENANCE_MISSING': 'Provenance des spécifications absente',
    'SUPPLIER_CAPACITY_OVERBOOKED': 'Capacité du fournisseur surréservée',
    'SUPPLIER_ID_INVALID': 'Identifiant du fournisseur invalide',
    'SUPPLIER_LATE': 'Fournisseur en retard',
    'SUPPLIER_NOT_QUALIFIED_OR_SIMULATED_COMMITTED': 'Qualification ou engagement simulé du fournisseur absent',
    'SUPPLIER_QUALIFICATION_FLAG_INVALID': 'Indicateur de qualification du fournisseur invalide',
    'SUPPLIER_RECORD_INVALID': 'Enregistrement du fournisseur invalide',
    'SUPPLIER_RESERVATION_INVALID': 'Réservation du fournisseur invalide',
    'SUPPLIER_RESOURCE_INVALID': 'Ressource du fournisseur invalide',
    'SUPPLIER_SHARED_OUTAGE': 'Fournisseur touché par la même panne',
    'SYNTHETIC_ONLY_REQUIRED': 'Portée limitée au synthétique requise',
    'UNRECOGNIZED_EVENT': 'Événement non reconnu',
    'UNSUPPORTED_SUPERIORITY': 'Supériorité non étayée',
    'UNVIABLE_OR_UNAFFORDABLE_OFFER': 'Offre non viable ou au-delà du budget',
}
BOUNDARIES = {
    'real_supplier_consent': ('Real supplier consent', 'Consentement réel du fournisseur'),
    'real_customer_acceptance': ('Real customer acceptance', 'Acceptation réelle du client'),
    'real_recovery_proof': ('Real recovery proof', 'Preuve de reprise réelle'),
    'real_payment': ('Real payment', 'Paiement réel'),
    'external_independent_certification': ('External independent certification', 'Certification indépendante externe'),
    'disaster_wide_continuity': ('Disaster-wide continuity', 'Continuité à l’échelle du sinistre'),
}
REASONS = {
    'amendment erases delivered units': 'La modification efface des unités déjà livrées.',
    'amendment, cancel or fulfillment without active order': 'Modification, annulation ou exécution sans commande active.',
    'buyer has not met even the synthetic participation condition': 'L’acheteur ne satisfait pas la condition de participation, même synthétique.',
    'cannot relax the signed-off functional promise': 'L’engagement fonctionnel approuvé ne peut être assoupli.',
    'duplicate acceptance': 'Acceptation en double.',
    'duplicate recovered order': 'Commande restaurée en double.',
    'duplicate supplier identity': 'Identité de fournisseur en double.',
    'empty/reversed reservation interval': 'Intervalle de réservation vide ou inversé.',
    'information-sharing permission absent from scenario': 'L’autorisation de partage d’information est absente du scénario.',
    'invalid blocked domains': 'Domaines de défaillance exclus invalides.',
    'invalid capacity reservation': 'Réservation de capacité invalide.',
    'invalid recovered snapshot': 'Instantané restauré invalide.',
    'invalid supplier record': 'Enregistrement du fournisseur invalide.',
    'missing buyer': 'Acheteur absent.',
    'missing complete modeled cost categories': 'Catégories complètes de coûts modélisés absentes.',
    'missing objective': 'Objectif absent.',
    'missing recovered snapshot': 'Instantané restauré absent.',
    'missing verifiable specification digest': 'Empreinte vérifiable des spécifications absente.',
    'modeled cost categories incomplete': 'Catégories de coûts modélisés incomplètes.',
    'no alternative providers declared': 'Aucun fournisseur de repli déclaré.',
    'no nonnegative modeled contribution after full costs': 'Aucune contribution modélisée non négative après les coûts complets.',
    'no outstanding eligible commitment': 'Aucun engagement admissible restant à honorer.',
    'no simulated supplier can satisfy capacity and deadline': 'Aucun fournisseur simulé ne satisfait la capacité et le délai.',
    'noncontiguous event provenance': 'Séquence de provenance des événements non contiguë.',
    'order falls outside frozen deadline horizon': 'La commande dépasse l’horizon temporel fixé.',
    'over-fulfillment': 'Exécution dépassant la quantité commandée.',
    'proposed offer exceeds buyer hypothetical budget': 'L’offre proposée dépasse le budget hypothétique de l’acheteur.',
    'protected source-event seal mismatch': 'L’empreinte des événements sources protégés ne correspond pas.',
    'real-world authority is never supplied by this exercise': 'Cet exercice ne confère jamais d’autorité sur des opérations réelles.',
    'source event list missing or exceeds local drill bound': 'La liste des événements sources est absente ou dépasse la borne de cet exercice local.',
    'supplier quoted cost differs from modeled full-cost plan': 'Le coût annoncé par le fournisseur diffère du plan de coûts complets modélisés.',
    'supplier reservation records missing': 'Enregistrements de réservation du fournisseur absents.',
    'unrecognized event type': 'Type d’événement non reconnu.',
    'unsupported drill horizon': 'Horizon de l’exercice non pris en charge.',
    'unsupported exercise schema': 'Schéma d’exercice non pris en charge.',
}
# Only field/suffix pairs emitted by the published constructor are supported.
# New prose requires an explicit translation, never an arbitrary-text fallback.
FIELD_REASONS = {
    'exercise_id': ('identifiant d’exercice', 'invalid identifier'),
    'product': ('produit', 'invalid identifier'),
    'recovered order id': ('identifiant de commande restaurée', 'invalid identifier'),
    'supplier_id': ('identifiant du fournisseur', 'invalid identifier'),
    'supplier product': ('produit du fournisseur', 'invalid identifier'),
    'supplier failure domain': ('domaine de défaillance du fournisseur', 'invalid identifier'),
    'event order': ('commande de l’événement', 'invalid identifier'),
    'order product': ('produit de la commande', 'invalid identifier'),
    'blocked failure domain': ('domaine de défaillance exclu', 'invalid identifier'),
    'deadline_hours': ('échéance en heures', 'expected positive integer'),
    'recovered quantity': ('quantité restaurée', 'expected positive integer'),
    'maximum_offer': ('offre maximale', 'expected positive integer'),
    'proposed offer': ('offre proposée', 'expected positive integer'),
    'capacity_units': ('capacité en unités', 'expected positive integer'),
    'reservation end': ('fin de la réservation', 'expected positive integer'),
    'reservation units': ('unités réservées', 'expected positive integer'),
    'accepted units': ('unités acceptées', 'expected positive integer'),
    'order deadline': ('échéance de la commande', 'expected positive integer'),
    'amended units': ('unités après modification', 'expected positive integer'),
    'delivered units': ('unités livrées', 'expected positive integer'),
    'quoted_cost': ('coût annoncé', 'expected nonnegative integer'),
    'lead_hours': ('délai en heures', 'expected nonnegative integer'),
    'reservation start': ('début de la réservation', 'expected nonnegative integer'),
}
for _key, _label in {
    'assessment': 'évaluation', 'setup': 'mise en place', 'reservation': 'réservation',
    'supplier': 'fournisseur', 'transport': 'transport', 'verification': 'vérification',
    'support': 'assistance', 'rights': 'droits', 'contingency': 'imprévus',
}.items():
    FIELD_REASONS['cost:' + _key] = ('coût : ' + _label, 'expected nonnegative integer')
GATES = {
    'protect independent source evidence': 'Protéger des éléments sources indépendants.',
    'obtain customer permission and confirmed supplier commitment': 'Obtenir l’autorisation du client et un engagement confirmé du fournisseur.',
    'execute scoped authorized drill': 'Exécuter un exercice autorisé dans un périmètre défini.',
    'independent buyer acceptance': 'Obtenir une acceptation indépendante par l’acheteur.',
    'real invoice, collected payment and full cost reconciliation': 'Établir une facture réelle, encaisser le paiement et rapprocher tous les coûts.',
    'fresh different successor task; compare with competent conventional route': 'Tester une nouvelle tâche différente et comparer à une voie classique compétente.',
}
SUCCESSOR = 'Test a new product family only after independent specifications, capacity, rights and costs are requalified.'
AUDIT_SCOPE = 'SYNTHETIC_ONLY; independent code, same research authorship; no third-party certification'
REJECTION_SCOPE = 'SYNTHETIC_ONLY; incurred real costs and customer consequences NOT measured'
FIELDS = {
    'HANDOFF.json': 'schema exercise_id source_events_sha256 orders required_units supplier_id supplier_failure_domain supplier_available_units_in_window rehearsed_completion_hours latest_required_hours idempotency_key scope',
    'PASSPORT.json': 'schema exercise_id technical_verdict restoration_findings source_events_sha256 handoff_sha256 economics comparison evidence_boundary successor_hypothesis',
    'AUDIT.json': 'schema exercise_id verdict failure_count failures replayed_orders replayed_units restoration_gaps scope source_digest_sha256 handoff_sha256 required_real_world_gates',
    'REJECTION.json': 'schema exercise_id verdict reason scope',
}
SCHEMAS = {'HANDOFF.json': 'continuity-omega/handoff-v1', 'PASSPORT.json': 'continuity-omega/passport-v1',
           'AUDIT.json': 'continuity-omega/audit-v1', 'REJECTION.json': 'continuity-omega/rejection-v1'}


class PresentationError(ValueError):
    def __init__(self, en, fr, detail=''):
        self.en, self.fr, self.detail = en, fr, detail
        super().__init__(en)


def choice(language, en, fr):
    return fr if language == 'fr' else en if language == 'en' else en + ' / ' + fr


def fail(en, fr, detail=''):
    raise PresentationError(en, fr, str(detail))


def fields(value, names, location):
    expected = set(names.split()) if isinstance(names, str) else set(names)
    if not isinstance(value, dict) or set(value) != expected:
        fail('Missing or unsupported fields; this reader cannot present this schema completely.',
             'Champs absents ou non pris en charge ; ce lecteur ne peut présenter ce schéma intégralement.', location)


def string(value, location):
    if not isinstance(value, str) or not value.strip():
        fail('A nonempty string is required.', 'Une chaîne non vide est requise.', location)


def identifier(value, location):
    if not isinstance(value, str) or re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,63}', value) is None:
        fail('A supported identifier is required; control or markup characters are not accepted.',
             'Un identifiant pris en charge est requis ; les caractères de contrôle ou de balisage sont refusés.', location)


def integer(value, location):
    if type(value) is not int:
        fail('An exact integer is required; Boolean values are not amounts.',
             'Un entier exact est requis ; les booléens ne sont pas des montants.', location)


def known(value, vocabulary, location):
    if not isinstance(value, str) or value not in vocabulary:
        fail('Unsupported recorded text or token; no partial translation was produced.',
             'Texte ou code consigné non pris en charge ; aucune traduction partielle n’a été produite.', location)


def sequence(value, location):
    if not isinstance(value, list):
        fail('A list is required.', 'Une liste est requise.', location)


def findings(value, location):
    sequence(value, location)
    for item in value:
        fields(item, 'order_id issue', location)
        identifier(item['order_id'], location + '.order_id')
        known(item['issue'], ISSUES, location + '.issue')


def failure_description(code, language):
    if not isinstance(code, str):
        fail('An audit finding must be a code string.', 'Un constat d’audit doit être une chaîne de code.', 'AUDIT.json.failures')
    if code in FAILURES:
        return choice(language, 'Recorded failed condition: ' + code.replace('_', ' ').lower(), FAILURES[code])
    prefix = 'IMPROPER_REAL_WORLD_CLAIM_'
    if isinstance(code, str) and code.startswith(prefix):
        key = code[len(prefix):].lower()
        if key in BOUNDARIES:
            label = choice(language, *BOUNDARIES[key])
            return choice(language, 'Unsupported real-world claim: ', 'Affirmation réelle non étayée : ') + label
    fail('Unsupported audit finding.', 'Constat d’audit non pris en charge.', code)


def reason_description(reason, language):
    string(reason, 'REJECTION.json.reason')
    if reason in REASONS:
        return choice(language, reason, REASONS[reason])
    field, separator, suffix = reason.rpartition(': ')
    if separator and field in FIELD_REASONS and suffix == FIELD_REASONS[field][1]:
        fr = {'expected positive integer': 'entier strictement positif attendu',
              'expected nonnegative integer': 'entier non négatif attendu',
              'invalid identifier': 'identifiant invalide'}[suffix]
        return choice(language, reason, FIELD_REASONS[field][0] + ' : ' + fr)
    match = re.fullmatch(r'undeclared (available|simulated_qualification|simulated_commitment) is not consent', reason)
    if match:
        label = {'available': 'disponibilité', 'simulated_qualification': 'qualification simulée',
                 'simulated_commitment': 'engagement simulé'}[match[1]]
        return choice(language, reason, 'L’indicateur non déclaré de ' + label + ' (' + match[1] + ') ne constitue pas un consentement.')
    fail('Unsupported refusal reason; no partial translation was produced.',
         'Motif de refus non pris en charge ; aucune traduction partielle n’a été produite.', 'REJECTION.json.reason')


def validate(records):
    if not isinstance(records, dict) or set(records) not in ({'REJECTION.json'}, {'HANDOFF.json', 'PASSPORT.json', 'AUDIT.json'}):
        fail('Choose a complete handoff record set or a single refusal record.',
             'Choisir un ensemble complet d’enregistrements de transfert ou un seul enregistrement de refus.')
    for filename, data in records.items():
        fields(data, FIELDS[filename], filename)
        known(data['schema'], {SCHEMAS[filename]}, filename + '.schema')
        identifier(data['exercise_id'], filename + '.exercise_id')
    if 'REJECTION.json' in records:
        data = records['REJECTION.json']
        known(data['verdict'], {'REJECTED_BEFORE_HANDOFF'}, 'REJECTION.json.verdict')
        known(data['scope'], {REJECTION_SCOPE}, 'REJECTION.json.scope')
        reason_description(data['reason'], 'fr')
        return
    handoff, passport, audit = (records[name] for name in ('HANDOFF.json', 'PASSPORT.json', 'AUDIT.json'))
    known(handoff['scope'], {'SYNTHETIC_ONLY_NOT_AN_AUTHORIZATION'}, 'HANDOFF.json.scope')
    for key in ('required_units', 'supplier_available_units_in_window', 'rehearsed_completion_hours', 'latest_required_hours'):
        integer(handoff[key], 'HANDOFF.json.' + key)
    for key in ('supplier_id', 'supplier_failure_domain'):
        identifier(handoff[key], 'HANDOFF.json.' + key)
    sequence(handoff['orders'], 'HANDOFF.json.orders')
    for order in handoff['orders']:
        fields(order, 'order_id units product spec_sha256 deadline_hours source_sequences', 'HANDOFF.json.orders')
        for key in ('order_id', 'product'):
            identifier(order[key], 'HANDOFF.json.orders.' + key)
        if not isinstance(order['spec_sha256'], str) or re.fullmatch(r'[0-9a-f]{64}', order['spec_sha256']) is None:
            fail('The specification digest is malformed.', 'L’empreinte des spécifications est mal formée.', 'HANDOFF.json.orders.spec_sha256')
        for key in ('units', 'deadline_hours'):
            integer(order[key], 'HANDOFF.json.orders.' + key)
        sequence(order['source_sequences'], 'HANDOFF.json.orders.source_sequences')
        for value in order['source_sequences']:
            integer(value, 'HANDOFF.json.orders.source_sequences')
    known(passport['technical_verdict'], {'READY_FOR_INDEPENDENT_SYNTHETIC_AUDIT'}, 'PASSPORT.json.technical_verdict')
    findings(passport['restoration_findings'], 'PASSPORT.json.restoration_findings')
    econ = passport['economics']
    fields(econ, 'currency offer modeled_cost modeled_contribution customer_budget', 'PASSPORT.json.economics')
    known(econ['currency'], {'ILLUSTRATIVE_USD'}, 'PASSPORT.json.economics.currency')
    for key in ('offer', 'modeled_cost', 'modeled_contribution', 'customer_budget'):
        integer(econ[key], 'PASSPORT.json.economics.' + key)
    fields(passport['comparison'], 'conventional_route incremental_advantage', 'PASSPORT.json.comparison')
    known(passport['comparison']['conventional_route'], {'SAME_INPUTS_AND_SUPPLIER_ACCESS'}, 'PASSPORT.json.comparison.conventional_route')
    known(passport['comparison']['incremental_advantage'], {'NOT_ESTABLISHED'}, 'PASSPORT.json.comparison.incremental_advantage')
    fields(passport['evidence_boundary'], BOUNDARIES, 'PASSPORT.json.evidence_boundary')
    for key, value in passport['evidence_boundary'].items():
        if type(value) is not bool:
            fail('A Boolean declaration is required.', 'Une déclaration booléenne est requise.', key)
    known(passport['successor_hypothesis'], {SUCCESSOR}, 'PASSPORT.json.successor_hypothesis')
    known(audit['verdict'], {'PASS_SYNTHETIC_ONLY', 'FAIL'}, 'AUDIT.json.verdict')
    known(audit['scope'], {AUDIT_SCOPE}, 'AUDIT.json.scope')
    for key in ('failure_count', 'replayed_orders', 'replayed_units'):
        integer(audit[key], 'AUDIT.json.' + key)
    sequence(audit['failures'], 'AUDIT.json.failures')
    for code in audit['failures']:
        failure_description(code, 'fr')
    count = audit['failure_count']
    if count < len(audit['failures']) or (audit['verdict'] == 'PASS_SYNTHETIC_ONLY' and (count != 0 or audit['failures'])) or (audit['verdict'] == 'FAIL' and (count <= 0 or not audit['failures'])):
        fail('Recorded audit verdict and failure fields contradict one another.', 'Le verdict d’audit consigné et ses champs d’échec se contredisent.', 'AUDIT.json')
    findings(audit['restoration_gaps'], 'AUDIT.json.restoration_gaps')
    sequence(audit['required_real_world_gates'], 'AUDIT.json.required_real_world_gates')
    for gate in audit['required_real_world_gates']:
        known(gate, GATES, 'AUDIT.json.required_real_world_gates')
    if len(audit['required_real_world_gates']) != len(GATES) or set(audit['required_real_world_gates']) != set(GATES):
        fail('The recorded real-world gate list is incomplete or duplicated.', 'La liste consignée des conditions réelles est incomplète ou comporte des doublons.', 'AUDIT.json.required_real_world_gates')
    for filename, data in records.items():
        for key in ('source_events_sha256', 'handoff_sha256', 'source_digest_sha256', 'idempotency_key'):
            if key in data and (not isinstance(data[key], str) or re.fullmatch(r'[0-9a-f]{64}', data[key]) is None):
                fail('A recorded SHA-256 value is malformed.', 'Une empreinte SHA-256 consignée est mal formée.', filename + '.' + key)


def resolved(path):
    try:
        return Path(path).resolve()
    except RuntimeError:
        fail('The path cannot be resolved; check for symbolic-link loops.',
             'Le chemin ne peut être résolu ; vérifier les boucles de liens symboliques.')


def load_records(directory):
    directory = resolved(directory)
    if not directory.is_dir():
        fail('Input directory is missing.', 'Le dossier d’entrée est absent.', directory)
    refused = (directory / 'REJECTION.json').exists()
    nominal = ('HANDOFF.json', 'PASSPORT.json', 'AUDIT.json')
    if refused and any((directory / name).exists() for name in nominal):
        fail('Refusal and handoff records are mixed; choose one intact recorded exercise.',
             'Des données de refus et de transfert sont mélangées ; choisir un exercice consigné intact.', directory)
    names = ('REJECTION.json',) if refused else nominal
    records, identities = {}, {}
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail('Duplicate JSON field.', 'Champ JSON en double.', key)
            result[key] = value
        return result
    def invalid_constant(value):
        fail('Non-finite JSON number.', 'Nombre JSON non fini.', value)
    def parse_integer(value):
        if len(value.lstrip('-')) > 4096:
            fail('JSON integers longer than 4096 digits are not supported.',
                 'Les entiers JSON de plus de 4096 chiffres ne sont pas pris en charge.')
        return int(value)
    for name in names:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            fail('Required input must be a regular file, not a symbolic link.',
                 'L’entrée requise doit être un fichier ordinaire, sans lien symbolique.', name)
        try:
            raw = path.read_bytes()
            records[name] = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                                       parse_constant=invalid_constant, parse_int=parse_integer)
        except PresentationError:
            raise
        except (UnicodeError, ValueError, RecursionError):
            fail('Input is not supported UTF-8 JSON.', 'L’entrée n’est pas du JSON UTF-8 pris en charge.', name)
        identities[name] = hashlib.sha256(raw).hexdigest()
    validate(records)
    return records, identities


def literal(value):
    # Inline code keeps raw IDs/tokens intact and treats markup as literal text.
    text = str(value).replace('\r', ' ').replace('\n', ' ')
    delimiter = '`' * (max((len(run) for run in re.findall(r'`+', text)), default=0) + 1)
    return delimiter + ' ' + text.replace('|', '&#124;') + ' ' + delimiter


def render(records, identities, language):
    validate(records)
    say = lambda en, fr: choice(language, en, fr)
    lines = ['# ' + say('CONTINUITY Ω', 'CONTINUITÉ Ω') + ' — ' + say('Recorded Passport reader', 'Lecture du Passeport consigné'), '',
        '**' + say('Recorded information only. No fresh audit was performed.', 'Informations consignées uniquement. Aucun nouvel audit n’a été exécuté.') + '**', '',
        say('This reader translates stored declarations. It does not establish their current validity, completeness, authenticity, real recovery, delivery, payment or independent certification. A stored pass remains a stored software decision.',
            'Ce lecteur traduit des déclarations enregistrées. Il n’établit ni leur validité actuelle, ni leur exhaustivité, ni leur authenticité, ni une reprise réelle, une livraison, un paiement ou une certification indépendante. Une validation enregistrée reste une décision logicielle consignée.'), '',
        say('The historical checker uses separate code under shared research authorship. These records supply no operational authorization.',
            'Le vérificateur historique utilise un code distinct produit par les mêmes auteurs. Ces enregistrements ne confèrent aucune autorisation opérationnelle.'), '',
        say('The historical checker has known weaknesses involving Boolean monetary values, malformed input and stale displays. Coherently rewriting a record and its digest can preserve internal consistency without authenticating the original scenario. This reading tool repairs none of those checker behaviors.',
            'Le vérificateur historique présente des faiblesses connues concernant les montants booléens, les entrées mal formées et les affichages périmés. Réécrire de manière cohérente un dossier et son empreinte peut préserver leur cohérence interne sans authentifier le scénario d’origine. Cet outil de lecture ne corrige aucun de ces comportements du vérificateur.'), '']
    def heading(en, fr):
        lines.extend(['## ' + say(en, fr), ''])
    def item(en, fr, value):
        lines.append('- **' + say(en, fr) + say(':** ', ' :** ') + literal(value))
    def show_findings(data):
        if not data:
            lines.append(say('No discrepancy is listed in this record.', 'Aucune divergence n’est indiquée dans cet enregistrement.'))
        for row in data:
            lines.append('- ' + literal(row['order_id']) + ': ' + choice(language, *ISSUES[row['issue']]) + ' — ' + literal(row['issue']))
        lines.append('')
    if 'REJECTION.json' in records:
        rejection = records['REJECTION.json']
        heading('Recorded refusal', 'Refus consigné')
        item('Exercise identifier', 'Identifiant d’exercice', rejection['exercise_id'])
        item('Recorded verdict', 'Verdict enregistré', rejection['verdict'])
        lines.extend(['', reason_description(rejection['reason'], language), '',
            say('The constructor recorded a refusal before handoff. No real costs or customer consequences were measured. This reader has not rerun that decision.',
                'Le constructeur a consigné un refus avant le transfert. Les coûts réels et les conséquences pour les clients n’ont pas été mesurés. Ce lecteur n’a pas réexécuté cette décision.'), ''])
    else:
        handoff, passport, audit = (records[name] for name in ('HANDOFF.json', 'PASSPORT.json', 'AUDIT.json'))
        heading('Recorded decisions', 'Décisions consignées')
        for name, data in records.items():
            item(name + ' exercise identifier', name + ' : identifiant d’exercice', data['exercise_id'])
        item('Producer readiness marker', 'Indicateur de préparation du constructeur', passport['technical_verdict'])
        item('Stored audit verdict', 'Verdict de l’audit enregistré', audit['verdict'])
        lines.extend(['', say('READY is a producer marker, not acceptance. PASS_SYNTHETIC_ONLY records a synthetic pass; FAIL records a failed audit condition. Neither is a new verdict from this reader.',
            'READY est un indicateur du constructeur, pas une acceptation. PASS_SYNTHETIC_ONLY consigne une validation synthétique ; FAIL consigne l’échec d’une condition d’audit. Aucun de ces codes n’est un nouveau verdict de ce lecteur.'), ''])
        heading('Handoff as recorded', 'Transfert tel qu’il est consigné')
        for key, en, fr in [('required_units','Required units','Unités requises'),('supplier_id','Simulated supplier','Fournisseur simulé'),('supplier_failure_domain','Declared failure domain','Domaine de défaillance déclaré'),('supplier_available_units_in_window','Declared available units','Unités disponibles déclarées'),('rehearsed_completion_hours','Modeled lead time (hours)','Délai modélisé (heures)'),('latest_required_hours','Required deadline (hours)','Échéance requise (heures)')]:
            item(en, fr, handoff[key])
        lines.append('')
        lines.append(say('| Order | Product | Units | Deadline (hours) | Source event numbers | Specification digest |', '| Commande | Produit | Unités | Échéance (heures) | Numéros des événements sources | Empreinte des spécifications |'))
        lines.append('| --- | --- | --- | --- | --- | --- |')
        for order in handoff['orders']:
            lines.append('| ' + ' | '.join(literal(order[key]) for key in ('order_id','product','units','deadline_hours','source_sequences','spec_sha256')) + ' |')
        lines.append('')
        heading('Discrepancies listed by the producer', 'Divergences indiquées par le constructeur')
        show_findings(passport['restoration_findings'])
        heading('Stored audit observations', 'Observations de l’audit enregistré')
        item('Recorded replayed orders', 'Commandes réexécutées consignées', audit['replayed_orders'])
        item('Recorded replayed units', 'Unités réexécutées consignées', audit['replayed_units'])
        item('Recorded failure count', 'Nombre d’échecs consigné', audit['failure_count'])
        lines.append('')
        for code in audit['failures']:
            lines.append('- ' + literal(code) + ': ' + failure_description(code, language))
        show_findings(audit['restoration_gaps'])
        heading('Modeled amounts as recorded', 'Montants modélisés tels qu’ils sont consignés')
        item('Currency marker', 'Code de devise', passport['economics']['currency'])
        for key, en, fr in [('offer','Proposed offer (illustrative USD)','Offre proposée (USD illustratifs)'),('modeled_cost','Modeled full cost (illustrative USD)','Coût complet modélisé (USD illustratifs)'),('modeled_contribution','Modeled contribution (illustrative USD)','Contribution modélisée (USD illustratifs)'),('customer_budget','Hypothetical buyer budget (illustrative USD)','Budget hypothétique de l’acheteur (USD illustratifs)')]:
            item(en, fr, passport['economics'][key])
        lines.extend(['',say('These are stored model values, not collected revenue or spendable money. This reader does not recalculate economics or establish actual complete costs.',
            'Il s’agit de valeurs enregistrées du modèle, et non de recettes encaissées ou de fonds disponibles. Ce lecteur ne recalcule pas l’économie et n’établit pas les coûts complets réels.'),''])
        heading('Comparison and evidence boundaries', 'Comparaison et limites des éléments probants')
        item('Conventional comparison: same inputs and supplier access', 'Comparaison classique : mêmes entrées et accès aux fournisseurs', passport['comparison']['conventional_route'])
        item('Incremental advantage: not established', 'Avantage supplémentaire : non établi', passport['comparison']['incremental_advantage'])
        lines.extend(['',say('The following are recorded declarations, not verified real-world outcomes. A value of true does not establish the claimed event.',
            'Les valeurs suivantes sont des déclarations consignées, pas des résultats réels vérifiés. La valeur true n’établit pas que l’événement revendiqué a eu lieu.'),''])
        for key, names in BOUNDARIES.items():
            item(names[0], names[1], key + ' = ' + str(passport['evidence_boundary'][key]).lower())
        lines.append('')
        heading('Proposed successor', 'Occasion suivante proposée')
        lines.extend([say(SUCCESSOR,'Tester une nouvelle famille de produits uniquement après requalification indépendante des spécifications, de la capacité, des droits et des coûts.'),''])
        heading('Real-world gates listed by the recorded audit', 'Conditions réelles indiquées par l’audit enregistré')
        for gate in audit['required_real_world_gates']:
            lines.append('- ' + say(gate, GATES[gate]))
        lines.append('')
    heading('Recorded technical references', 'Références techniques consignées')
    for name, data in records.items():
        for key in ('schema','scope','source_events_sha256','source_digest_sha256','handoff_sha256','idempotency_key'):
            if key in data:
                item(name + ' · ' + key, name + ' · ' + key, data[key])
    lines.append('')
    heading('Identity of the files read', 'Identité des fichiers lus')
    lines.extend([say('These SHA-256 values identify the bytes read for this presentation. They do not authenticate the producer or recompute the historical audit. No input file was changed.',
        'Ces empreintes SHA-256 identifient les octets lus pour cette présentation. Elles n’authentifient pas le producteur et ne recalculent pas l’audit historique. Aucun fichier d’entrée n’a été modifié.'),''])
    for name, sha in identities.items():
        item(name, name, sha)
    lines.extend(['',say('Reader success means only that supported records were rendered. Preserve the original JSON and use the separately documented verification procedure when a new check is needed.',
        'La réussite du lecteur signifie uniquement que des enregistrements pris en charge ont été présentés. Conserver les JSON d’origine et utiliser la procédure de vérification documentée séparément lorsqu’un nouveau contrôle est nécessaire.'),''])
    return '\n'.join(lines)


def present(directory, language, output=None):
    if language not in ('en','fr'):
        fail('Choose --language en or --language fr.', 'Choisir --language en ou --language fr.')
    source = resolved(directory)
    target = None
    if output is not None:
        candidate = Path(output)
        if not candidate.is_absolute():
            fail('Output must be a new absolute file path.', 'La sortie doit être un nouveau chemin de fichier absolu.')
        target = resolved(candidate)
        if candidate.is_symlink() or candidate.exists():
            fail('Output already exists; it will not be overwritten.', 'La sortie existe déjà ; elle ne sera pas écrasée.', candidate)
        if target == source or target.is_relative_to(source):
            fail('Output must be outside the evidence directory.', 'La sortie doit être hors du dossier des éléments probants.', candidate)
        if not target.parent.is_dir():
            fail('The output parent directory must already exist.', 'Le dossier parent de la sortie doit déjà exister.', target.parent)
    records, identities = load_records(source)
    result = render(records, identities, language)
    if target is not None:
        with target.open('x', encoding='utf-8') as stream:
            stream.write(result)
    return result


class LocalizedParser(argparse.ArgumentParser):
    def format_help(self):
        result = super().format_help()
        return result.replace('usage:', choice(self.language, 'usage:', 'utilisation :'), 1)

    def error(self, message):
        fail('Invalid arguments or a missing value; use --help.', 'Arguments invalides ou valeur manquante ; utiliser --help.')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    language = None
    for index, value in enumerate(argv):
        if value == '--language' and index + 1 < len(argv) and argv[index+1] in ('en','fr'):
            language = argv[index+1]
        if value in ('--language=en','--language=fr'):
            language = value.split('=')[1]
    try:
        parser = LocalizedParser(add_help=False, description=choice(language,
            'Read recorded CONTINUITY Ω v1 artifacts. No fresh audit, input changes or real-world authority.',
            'Lire les artefacts CONTINUITÉ Ω v1 consignés. Aucun nouvel audit, changement des entrées ou pouvoir réel.'),
            usage='%(prog)s --in-dir PATH --language {en,fr} [--out NEW_FILE]')
        parser.language = language
        parser._optionals.title = choice(language, 'Options', 'Options')
        parser.add_argument('--in-dir', metavar='PATH', help=choice(language,'Recorded evidence directory','Dossier des éléments probants consignés'))
        parser.add_argument('--language', metavar='{en,fr}', help=choice(language,'Required presentation language','Langue requise pour la présentation'))
        parser.add_argument('--out', metavar='NEW_FILE', help=choice(language,'New absolute Markdown file outside the evidence directory; default: stdout','Nouveau fichier Markdown absolu hors du dossier probant ; par défaut : sortie standard'))
        parser.add_argument('-h','--help', action='store_true', help=choice(language,'Show help; bilingual when no language is selected','Afficher l’aide ; bilingue si aucune langue n’est choisie'))
        opts = parser.parse_args(argv)
        if opts.help or not argv:
            parser.print_help()
            return 0
        if opts.language not in ('en','fr'):
            fail('Choose --language en or --language fr.', 'Choisir --language en ou --language fr.')
        language = opts.language
        if not opts.in_dir:
            fail('The --in-dir evidence directory is required.', 'Le dossier probant --in-dir est requis.')
        text = present(opts.in_dir, language, opts.out)
        if opts.out:
            print(choice(language,'Recorded presentation written; no fresh audit: ','Présentation des données consignées écrite ; aucun nouvel audit : ') + str(opts.out))
        else:
            print(text, end='')
        return 0
    except PresentationError as error:
        message = choice(language,error.en,error.fr)
        if error.detail:
            message += ' [' + json.dumps(error.detail, ensure_ascii=False) + ']'
        print(choice(language,'Presentation refused: ','Présentation refusée : ') + message,file=sys.stderr)
        return 2
    except OSError as error:
        print(choice(language,'Cannot read or create the requested file; no evidence was changed.','Impossible de lire ou de créer le fichier demandé ; aucun élément probant n’a été modifié.') + ' [' + str(error.errno) + ']',file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
