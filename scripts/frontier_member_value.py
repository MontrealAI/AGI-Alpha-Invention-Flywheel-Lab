"""Compile public-file member material from the admitted Atlas and pinned instruments."""

from hashlib import sha256
from html import escape
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZipInfo, ZIP_STORED

import frontier_member_first as editions

MAIN = Path(__file__).resolve().parents[1]
SITE = 'frontier-omega-alpha/'
ASSETS = MAIN / 'docs/research' / SITE
TOOLS = MAIN / 'products/frontier-member-tools'
MONTREAL = 'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
RESEARCH = 'products/frontier-omega-alpha/research/'
ENDPOINT_PIN = '522542e525e96556285560e65e4443c85cc7b709'
ARCHIVE_PIN = '6a635b77012fb45b4d96c404a33fa04327c19674'
ENDPOINT_PATH = RESEARCH + 'possibility_observatory/endpoint_study/'
ARCHIVE_PATH = RESEARCH + 'archive_point/'
ENDPOINT_SUBMISSION = 'd6b88dff-6bbb-4107-8d2e-1090decd4d53'
SUBMISSION_HASH = 'ce3226048090ba13e5d2369b582126f8440ba3485926f91ed81396fe15acada0'
ENDPOINT_ZIP = 'endpoint-evidence-screen-1.0.0.zip'
ARCHIVE_ZIP = 'noaa-archive-point-1.0.0.zip'
MEMBER_JSON = 'member-value.json'
OUTPUTS = frozenset(SITE + name for name in (ENDPOINT_ZIP, ARCHIVE_ZIP, MEMBER_JSON))
MARKER = '<!-- FRONTIER_MEMBER_VALUE -->'
PREVIEW_MARKER = '<!-- FRONTIER_MEMBER_PREVIEW -->'
PUBLIC_FEATURE_MARKER = '<!-- FRONTIER_PUBLIC_FEATURE -->'
RIGHTS = 'Authorized public distribution of this pinned package. Upstream material retains its own rights.'
VERDICTS = ('USE NOW', 'TEST NOW', 'PREPARE', 'WATCH', 'ABSTAIN', 'DISCARD')
FR_VERDICTS = ('UTILISER', 'TESTER', 'PRÉPARER', 'SURVEILLER', 'ABSTENTION', 'ÉCARTER')


def stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(raw):
    return sha256(raw).hexdigest()


def pinned(revision, path):
    return subprocess.check_output(('git', 'cat-file', 'blob', f'{revision}:{path}'), cwd=MAIN)


def commit_url(revision):
    return f'{MONTREAL}/commit/{revision}'


def endpoint_sample():
    source = json.loads(pinned(ENDPOINT_PIN, ENDPOINT_PATH + 'observations.json'))
    if source['source_sha256'] != SUBMISSION_HASH:
        raise ValueError('The published Endpoint sample source changed')
    rows = [r for r in source['rows'] if r['submission_id'] == ENDPOINT_SUBMISSION and
            r['facts']['submission'] == 'official' and r['facts']['run'] == 'valid-online' and
            r['facts']['model'] == 'GPT-OSS 120B' and r['facts']['dataset'] == 'perf' and r['published']]
    if len(rows) != 7 or len({r['system'] for r in rows}) != 1:
        raise ValueError('The frozen Endpoint case denominator changed')
    selection = {
        'schema': 'frontier/endpoint-screen-v1',
        'source': source['source'],
        'scope': {'model': 'GPT-OSS 120B', 'workload': 'MLPerf perf', 'system': rows[0]['system']},
        'cutoff': '2026-11-23', 'minimum_tokens_per_s': '100', 'maximum_p90_ttft_ms': '500',
        'rows': [{'id': r['id'], 'published': r['published'], 'load': r['load'],
                  'tokens_per_s': r['metric'], 'p90_ttft_ms': r['upper_metric']}
                 for r in sorted(rows, key=lambda r: r['load'])],
    }
    return selection


def archive_bytes():
    files = ('point.py', 'replay.py', 'query.py', 'registration.json', 'evidence/confirmation.json',
             'evidence/point-service-retry.json', 'evidence/standalone-query.json')
    contents = {ARCHIVE_PATH + name: pinned(ARCHIVE_PIN, ARCHIVE_PATH + name) for name in files}
    for name in ('common.py', 'cycle.py', 'evaluation.py'):
        path = RESEARCH + f'autonomous_endpoint/{name}'
        contents[path] = pinned(ARCHIVE_PIN, path)
    for name in ('archive-query.py', 'archive-verify.py'):
        contents[name] = (TOOLS / name).read_bytes()
    contents['README.md'] = (TOOLS / 'ARCHIVE.md').read_bytes()
    return contents


def package(path, files, name, pin, scope):
    manifest = {'schema': 'frontier/portable-capability-v1', 'id': name, 'version': '1.0.0',
                'source': commit_url(pin), 'rights': RIGHTS, 'qualification_scope': scope,
                'file_sha256': {key: digest(value) for key, value in files.items()}}
    with ZipFile(path, 'w', compression=ZIP_STORED) as release:
        for filename, raw in sorted({**files, 'manifest.json': stable(manifest) + b'\n'}.items()):
            entry = ZipInfo(filename)
            entry.compress_type = ZIP_STORED
            entry.external_attr = 0o644 << 16
            release.writestr(entry, raw)
    return {**manifest, 'download': path.name, 'sha256': digest(path.read_bytes()), 'bytes': path.stat().st_size}


def build_tools(destination):
    sample = endpoint_sample()
    endpoint = {name: (ASSETS / name).read_bytes() for name in ('endpoint-screen.mjs', 'outcome-receipt.mjs')}
    endpoint.update({
        'endpoint-cli.mjs': (TOOLS / 'endpoint-cli.mjs').read_bytes(),
        'endpoint-sqlite.py': (TOOLS / 'endpoint-sqlite.py').read_bytes(),
        'README.md': (TOOLS / 'ENDPOINT.md').read_bytes(),
        'reference.py': pinned(ENDPOINT_PIN, ENDPOINT_PATH + 'reference.py'),
        'sample.json': stable(sample) + b'\n',
    })
    # The qualification step independently computes the result with SQLite and
    # compares every row. No dynamic run telemetry enters the release fingerprint.
    comparative = {
        'schema': 'frontier/endpoint-result-v1', 'screening': 'QUALIFIED_TESTED_POINT',
        'highest_tested_load': 140, 'evidence_id': next(r['id'] for r in sample['rows'] if r['load'] == 140),
        'operating_adoption': 'ABSTAIN',
        'rows': [{'id': r['id'], 'load': r['load'],
                  'disposition': 'qualified' if r['load'] <= 140 else 'above-ceiling'} for r in sample['rows']],
    }
    reference = {'input_sha256': digest(stable(sample)), 'result_sha256': digest(stable(comparative)),
                 'upstream_sha256': SUBMISSION_HASH, 'source_revision': ENDPOINT_PIN, 'rows': len(sample['rows'])}
    tools = {
        'endpoint': package(destination / ENDPOINT_ZIP, endpoint, 'endpoint-evidence-screen', ENDPOINT_PIN,
                           'Linux Node 24 and Python 3.12 with SQLite, live Chromium workbench'),
        'archive': package(destination / ARCHIVE_ZIP, archive_bytes(), 'noaa-archive-point', ARCHIVE_PIN,
                          'Linux Python 3.12, curl and OpenSSL; offline audit and public-origin query'),
    }
    return tools, sample, reference


# Context comes from the eight reviewed Atlas records. The profile maps an
# outcome to its domain and technique without changing the experiment's verdict.
PROFILES = {
    'shift-alpha-1-availability': ('DISCARD', 'manufacturing', 'catalog', 'reader', 'analyst', 'review', None),
    'shift-anys1': ('PREPARE', 'agents', 'workflow', 'unspecified', 'researcher', 'study', None),
    'shift-archive-point': ('USE NOW', 'science', 'archive', 'linux', 'engineer', 'run', 'archive'),
    'shift-autonomous-endpoint': ('ABSTAIN', 'compute', 'screening', 'browser', 'engineer', 'run', 'endpoint'),
    'shift-measurement-gap': ('USE NOW', 'science', 'reconstruction', 'unspecified', 'researcher', 'study', None),
    'shift-photometry-resilience': ('USE NOW', 'science', 'resilience', 'unspecified', 'engineer', 'study', None),
    'shift-repofactory': ('PREPARE', 'agents', 'training', 'unspecified', 'researcher', 'study', None),
    'shift-qwen-harness-adapter': ('DISCARD', 'agents', 'maintenance', 'reader', 'engineer', 'review', None),
}
CAPTIONS = {
    'en': {
        'unknown': 'Unresolved in the available evidence.',
        'threshold': 'The matched-test eligibility and acceptance criteria remain to be frozen.',
        'public': 'Public reference, with independent experimental acceptance outstanding.',
        'cost': 'Complete operating cost and benefit remain unmeasured. Check prerequisites and source rights for your case.',
        'watch': 'Watch the primary source for a reproducible comparison or a material version change.',
        'prepare': 'Choose one reported outcome, freeze permitted inputs and compare against the strongest conventional method.',
        'review': 'Revisit when the registered input, comparator or operating evidence changes.',
        'reviewed': 'Reviewed scope from the linked Atlas evidence. Retain the result and its limits.',
        'pending_rights': 'Check the upstream licence and your authority before using materials or running a new case.',
        'unknown_alt': 'Establish the strongest existing method on the same authorized task before drawing a conclusion.',
        'no_mechanism': 'The source confirms the reference identity and version. A binding constraint and missing move still need investigation.',
        'not_proven': 'Applicability, complete cost and independent outcome on your workload remain unverified.',
    },
    'fr': {
        'unknown': 'Les preuves disponibles ne permettent pas de trancher.',
        'threshold': 'L’admissibilité et les critères d’acceptation de l’essai comparatif restent à fixer.',
        'public': 'Référence publique dont le résultat expérimental attend une validation indépendante.',
        'cost': 'Les coûts et les bénéfices complets restent à mesurer. Vérifier les prérequis et les droits applicables.',
        'watch': 'Surveiller la source primaire pour une comparaison reproductible ou une mise à jour déterminante.',
        'prepare': 'Choisir un résultat annoncé, figer les entrées autorisées et comparer à la meilleure méthode classique.',
        'review': 'Réexaminer si les entrées enregistrées, le comparateur ou les preuves opérationnelles changent.',
        'reviewed': 'Périmètre examiné dans les preuves de l’Atlas. Conserver le résultat et ses limites.',
        'pending_rights': 'Vérifier la licence de la source et votre autorisation avant de réutiliser des données ou de lancer un essai.',
        'unknown_alt': 'Établir la meilleure méthode existante sur la même tâche autorisée avant de conclure.',
        'no_mechanism': 'L’identité et la version de la source sont confirmées. La contrainte déterminante et le mécanisme restent à étudier.',
        'not_proven': 'L’applicabilité, le coût complet et le résultat indépendant sur votre charge restent à démontrer.',
    },
}


def reviewed_brief(entry):
    latest = entry['editorial'][-1]
    item = latest['record']
    default = ('WATCH', 'research', 'evidence', 'unspecified', 'analyst', 'review', None)
    verdict, domain, task, hardware, skill, effort, tool = PROFILES.get(entry['id'], default)
    profile = {'beneficiary': 'research-teams', 'industry': domain, 'outcome': task, 'hardware': hardware,
               'expertise': skill, 'effort': effort, 'evidence': entry['state'], 'action': verdict}
    if entry['state'] == 'falsified':
        kind = 'correction'
    elif tool and entry['state'] == 'verified':
        kind = 'capability'
    elif entry['state'] == 'verified':
        kind = 'verified-result'
    else:
        kind = 'revision' if len(entry['editorial']) > 1 else 'review'
    brief = {'id': entry['id'], 'edition_kind': kind, 'observed_at': entry['editorial'][0]['observed_at'],
             'updated_at': latest['observed_at'], 'source_version': latest['reviewed_commit'],
             'atlas_state': entry['state'], 'evidence': item['evidence'], 'verdict': verdict, 'tool': tool,
             'profile': profile, 'evidence_links': item['sources'], 'receipt': commit_url(latest['reviewed_commit']),
             'publication': 'public-file', 'protected_release': None, 'member_lead_seconds': None,
             'review_trigger': 'source-or-scope-change', 'complete_cost': None}
    for lang, words in CAPTIONS.items():
        local = item[lang]
        assessment = item.get('assessment', {}).get(lang, {})
        brief[lang] = {
            'title': local['title'], 'change': local['signal'],
            'why': assessment.get('decision', words['reviewed']),
            'possibility': assessment.get('decision', words['unknown']),
            'missing_move': local['next'],
            'alternative': assessment.get('alternative', words['unknown_alt']),
            'retain': words['reviewed'], 'economics': words['cost'], 'next': local['next'],
            'uncertainty': words['not_proven'], 'rights': words['pending_rights'],
        }
    return brief


def source_brief(entry):
    versions, = entry['sources'].values()
    item = max(versions, key=lambda row: (int(row['source_version'].rsplit('v', 1)[1])
                                         if row['source'] == 'arxiv' else 0, row['observed_at']))
    verdict = 'PREPARE' if item['decision'] == 'test' else 'WATCH'
    brief = {'id': entry['id'], 'edition_kind': 'revision' if len(versions) > 1 else 'discovery',
             'observed_at': versions[0]['observed_at'], 'updated_at': item['observed_at'],
             'source_version': item['source_version'], 'atlas_state': entry['state'], 'evidence': 'source-identity-only',
             'verdict': verdict, 'tool': None,
             'profile': {'beneficiary': 'research-teams', 'industry': 'research', 'outcome': 'evidence',
                         'hardware': 'unspecified', 'expertise': 'analyst', 'effort': 'review',
                         'evidence': entry['state'], 'action': verdict},
             'evidence_links': [{'url': item['url'], 'en': 'Versioned primary source', 'fr': 'Source primaire versionnée'}],
             'receipt': commit_url(item['publisher_commit']), 'source_sha256': item['primary_sha256'],
             'publication': 'public-file', 'protected_release': None, 'member_lead_seconds': None,
             'review_trigger': 'source-or-scope-change', 'complete_cost': None}
    for lang, words in CAPTIONS.items():
        brief[lang] = {
            'title': item['title'], 'change': words['public'], 'why': words['no_mechanism'],
            'possibility': words['unknown'], 'missing_move': words['no_mechanism'],
            'alternative': words['unknown_alt'], 'retain': words['public'],
            'economics': words['cost'], 'next': words[verdict.lower()], 'uncertainty': words['threshold'],
            'rights': words['pending_rights'],
        }
    return brief


def decision_briefs(ledger):
    return [reviewed_brief(entry) if entry['editorial'] else source_brief(entry) for entry in ledger['records']]

# A source-bound short explanation for reviewed outcomes that already have a
# registered comparison. No prose from the automated public inbox is used here.
CONTEXT = {
    'shift-alpha-1-availability': {
        'en': ('The dated announcement was being used as an availability boundary. A September 29 storefront capture documents an earlier offer.',
               'Correct historical eligibility screening for the five tested CORE One configurations.',
               'Bind the claim to the first documented offer and replay both comparison dates.',
               'The dated listing and the reproduced 42 technical decisions.',
               'Compare the same 24 registered paths under both documented October cutoffs.'),
        'fr': ('L’annonce datée servait de seuil de disponibilité. Une capture du 29 septembre atteste une offre antérieure.',
               'Corriger l’évaluation historique des cinq configurations CORE One testées.',
               'Fonder l’affirmation sur la première offre documentée et rejouer les deux dates.',
               'La fiche fabricant datée et les 42 décisions techniques reproduites.',
               'Comparer les mêmes 24 parcours enregistrés aux deux dates d’octobre documentées.'),
    },
    'shift-autonomous-endpoint': {
        'en': ('The experiment had a fixed public archive. Real traffic, service limits and separately administered operational custody remain outstanding.',
               'Screen the documented highest measured load on any one fixed, authorized evidence set.',
               'Use exact dated predicates and an independent SQLite check before interpreting a result.',
               'The portable input contract, indexed SQL reference and signed custody evidence.',
               'Match 64 held public decisions. A production recommendation needs the separate #565 authority and representative requirements.'),
        'fr': ('L’essai disposait d’une archive publique figée. La charge réelle, les limites de service et la garde indépendante restent à établir.',
               'Repérer la charge maximale effectivement mesurée dans un ensemble autorisé et homogène.',
               'Appliquer les seuils exacts et vérifier la décision par SQLite avant de l’interpréter.',
               'Le contrat d’entrées portable, la référence SQLite et les preuves de garde signées.',
               'Reproduire les 64 décisions publiques réservées. Une recommandation opérationnelle exige les conditions représentatives et l’autorisation #565.'),
    },
    'shift-archive-point': {
        'en': ('The original archive gives full GRIB fields, while many research tasks need a single native grid point.',
               'Obtain a reproducible historical NOAA forecast value at an exact grid point under the tested payload limit.',
               'Read the minimum retained prefix of the original spatial-difference packing and match it against a complete ecCodes decode.',
               'The direct query, six signed independent cases and the cheaper NCAR point-service comparison.',
               'Six held date and coordinate pairs. Require the same native index and value within 0.00005 K under 384 KiB.'),
        'fr': ('L’archive originale donne des champs GRIB entiers. De nombreuses recherches n’exigent qu’un point natif.',
               'Obtenir une valeur de prévision historique NOAA reproductible à un point exact sous la limite testée.',
               'Lire le préfixe utile du champ différentiel et comparer sa valeur à un décodage complet ecCodes.',
               'La requête directe, six cas indépendants signés et le comparateur NCAR plus économe en données.',
               'Six couples date et coordonnées réservés. Même indice natif et écart maximal de 0,00005 K sous 384 Kio.'),
    },
    'shift-measurement-gap': {
        'en': ('Some time-series observations are unavailable. The test retained observations on both sides of each hidden epoch.',
               'Estimate a missing 2-band measurement within the evaluated retrospective conditions.',
               'Use the conventional multiband Gaussian process. The tested correction added no value over interpolation.',
               'The independent comparison and its favorable operating envelope for the conventional method.',
               '15 objects and 85 held measurements. Count predictions within 0.15 magnitude.'),
        'fr': ('Certaines mesures temporelles manquent. L’essai disposait de mesures de part et d’autre de chaque instant masqué.',
               'Estimer une mesure manquante dans deux bandes selon les conditions rétrospectives évaluées.',
               'Utiliser le processus gaussien multibande classique. La correction à l’essai a égalé l’interpolation.',
               'La comparaison indépendante et le périmètre testé de la méthode classique.',
               '15 objets et 85 mesures réservées. Compter les prédictions dans la tolérance de 0,15 magnitude.'),
    },
    'shift-photometry-resilience': {
        'en': ('Replay withheld a stored primary response. Both live providers had returned HTTP 200 during acquisition.',
               'Recover corroborated historical pairs during a replayed source disruption.',
               'Try the ordinary SQLite fallback and corroborate the measurement at the data-source level.',
               'The two matched pairs, rejected witness, failure receipt and original acquisition provenance.',
               'Compare pair recovery on the same held inputs. Keep the fresh target set and the missing result.'),
        'fr': ('Le rejeu a retiré une réponse primaire enregistrée. Les deux fournisseurs avaient répondu HTTP 200 lors de l’acquisition.',
               'Récupérer des paires historiques corroborées lors d’une interruption simulée de la source.',
               'Essayer le repli SQLite ordinaire et corroborer la mesure à sa source de données.',
               'Les deux paires concordantes, le témoin rejeté, le reçu d’échec et la provenance originale.',
               'Comparer la récupération sur les mêmes entrées réservées. Conserver la nouvelle cohorte et son absence de résultat.'),
    },
}


def context_for(brief):
    context = CONTEXT.get(brief['id'], {})
    version = brief['source_version']
    source_context = SOURCE_CONTEXT.get(version, {}) if brief['id'] == 'watch-arxiv-' + version.partition('v')[0] else {}
    for lang, words in CAPTIONS.items():
        local = brief[lang]
        value = context.get(lang)
        if value:
            local.update(zip(('why', 'possibility', 'missing_move', 'retain', 'protocol'), value))
        else:
            local['protocol'] = words['threshold']
            if brief['evidence'] != 'source-identity-only':
                local['why'] = words['not_proven']
                local['missing_move'] = words['reviewed']
        sourced = source_context.get(lang)
        if not context and sourced:
            local.update(zip(('change', 'why', 'possibility', 'alternative', 'next', 'uncertainty'), sourced))
    return brief


# Exact-version editorial notes. New versions use the ordinary source-only
# brief until the new evidence supports carrying these descriptions forward.
SOURCE_CONTEXT = {
    '2611.09822v3': {
        'en': (
            'The authors report an agent workflow that generates quantum programs and checks their correctness and resource cost with a Lean library.',
            'A formal specification can support comparison beyond the small circuit instances amenable to classical simulation.',
            'Screen a candidate arithmetic circuit before allocating laboratory or fault-tolerant hardware time.',
            'A hand-designed reversible circuit checked against the same formal specification and resource model.',
            'Choose one publicly specified arithmetic circuit. Freeze the correctness specification, ancilla budget and gate model. Replay the proof and compare the counted resources with the best published circuit under those constraints.',
            'This is a version-checked author report. Independent replication, hardware benefit and full costs remain open.',
        ),
        'fr': (
            'Les auteurs décrivent un processus à agents qui produit des programmes quantiques et vérifie leur exactitude et leur coût en ressources avec une bibliothèque Lean.',
            'Une spécification formelle permet d’envisager des comparaisons au-delà des petits circuits simulables classiquement.',
            'Évaluer un circuit arithmétique candidat avant de réserver du temps de laboratoire ou du matériel tolérant aux fautes.',
            'Un circuit réversible conçu par un spécialiste et évalué avec la même spécification formelle et le même modèle de ressources.',
            'Choisir un circuit arithmétique spécifié publiquement. Figer la spécification, le budget de qubits auxiliaires et le modèle de portes. Rejouer la preuve et comparer les ressources avec celles du meilleur circuit publié soumis aux mêmes contraintes.',
            'La version du rapport des auteurs est confirmée. La réplication indépendante, le gain sur matériel et les coûts complets restent à établir.',
        ),
    },
    '2611.21541v1': {
        'en': ('SciResearch-Eval tests how agents infer thermal properties when their model of the experiment can be wrong.',
               'A narrow reported interval can hide a biased physical model.',
               'Test whether a laboratory assistant can choose measurements that stay reliable under simulator errors.',
               'A scientist or scripted design that checks residuals and uses a measurement regime with known model error.',
               'On held licensed cases, compare interval coverage, interval score and time under the same experiment budget.',
               'The authors report results on one thermal inference task. Check calibration on the intended apparatus before relying on it.'),
        'fr': ('SciResearch-Eval évalue comment les agents estiment des propriétés thermiques lorsqu’un simulateur peut être erroné.',
               'Un intervalle étroit peut masquer un modèle physique biaisé.',
               'Vérifier si un assistant de laboratoire sait choisir des mesures robustes aux erreurs du simulateur.',
               'Un spécialiste ou un protocole déterministe qui examine les résidus et choisit un régime dont l’erreur de modèle est connue.',
               'Sur des cas réservés dont l’usage est autorisé, comparer la couverture, le score des intervalles et le temps à budget expérimental identique.',
               'Les auteurs rapportent une seule tâche d’inférence thermique. Vérifier l’étalonnage sur l’appareil visé avant de s’y fier.'),
    },
    '2611.23509v1': {
        'en': ('GRAFT uses selected traces of previous agent successes and failures when recombining candidate designs.',
               'Aggregate scores alone do not reveal which component helped on a particular case.',
               'Reuse diagnostic evidence already collected during optimization to choose the next design.',
               'Score-only search with the same initial designs, held tasks and execution budget.',
               'Pre-register a held comparison that changes only access to prior traces. Count evaluator calls, failures and total cost.',
               'The reported gains are the authors’ results. Transfer to our workflows and cost advantage remain unverified.'),
        'fr': ('GRAFT exploite des traces sélectionnées de réussites et d’échecs pour recombiner des architectures d’agents.',
               'Un score agrégé ne révèle pas quel composant a aidé dans un cas donné.',
               'Réutiliser les preuves diagnostiques déjà recueillies pour choisir la prochaine architecture.',
               'Une recherche guidée uniquement par le score, avec mêmes architectures initiales, tâches réservées et budget.',
               'Préenregistrer une comparaison qui ne fait varier que l’accès aux traces. Compter les appels d’évaluation, les échecs et le coût complet.',
               'Les gains sont rapportés par les auteurs. Le transfert à nos processus et l’avantage de coût restent à vérifier.'),
    },
    '2611.26722v1': {
        'en': ('TOUMAII describes paired correct and plausible incorrect tool calls for preference training.',
               'Valid syntax alone does not guarantee that an agent chose the correct function or argument.',
               'Compare training on contrastive calls with enforcing a validator at runtime for one authorized tool.',
               'The same model with strict schema checks and deterministic validation of business rules.',
               'On a rights-cleared held task, compare accepted calls and failure recovery under a matched budget before training more broadly.',
               'Dataset size and performance are author-reported. Review upstream terms and test for task overlap and transfer.'),
        'fr': ('TOUMAII décrit des paires d’appels corrects et d’appels erronés plausibles pour l’apprentissage par préférences.',
               'Une syntaxe valide ne garantit pas le bon choix de fonction ou d’argument.',
               'Comparer un apprentissage contrastif à un contrôle pendant l’exécution pour un outil autorisé.',
               'Le même modèle, avec contrôle strict du schéma et validation déterministe des règles métier.',
               'Sur une tâche réservée dont l’usage est autorisé, comparer les appels acceptés et la reprise après échec à budget égal.',
               'La taille du jeu et les résultats proviennent des auteurs. Vérifier les droits, le chevauchement des tâches et le transfert.'),
    },
}


FACETS = {
    'beneficiary': ('Beneficiary', 'Bénéficiaire'),
    'industry': ('Domain', 'Domaine'),
    'outcome': ('Intended outcome', 'Résultat visé'),
    'hardware': ('Hardware', 'Matériel'),
    'expertise': ('Expertise', 'Expertise'),
    'effort': ('Time commitment', 'Temps à prévoir'),
    'evidence': ('Evidence state', 'État de la preuve'),
    'action': ('Next action', 'Action possible'),
}
TERMS = {
    'research-teams': ('Research teams', 'Équipes de recherche'),
    'manufacturing': ('Manufacturing', 'Fabrication'), 'agents': ('AI workflows', 'Processus d’IA'),
    'science': ('Scientific instruments', 'Instruments scientifiques'),
    'compute': ('Inference compute', 'Calcul d’inférence'), 'research': ('Public research', 'Recherche publique'),
    'catalog': ('Catalog screening', 'Vérification de catalogue'), 'archive': ('Archive query', 'Requête d’archive'),
    'workflow': ('Workflow decision', 'Décision sur un processus'), 'screening': ('Endpoint screening', 'Analyse Endpoint'),
    'reconstruction': ('Measurement reconstruction', 'Reconstruction de mesures'),
    'resilience': ('Source continuity', 'Continuité des sources'), 'evidence': ('Evidence review', 'Examen des preuves'),
    'training': ('Training environments', 'Environnements d’entraînement'),
    'maintenance': ('Record maintenance', 'Maintenance des dossiers'),
    'reader': ('Read only', 'Lecture seule'), 'unspecified': ('Confirm first', 'À confirmer'),
    'browser': ('Desktop browser', 'Navigateur de bureau'), 'linux': ('Linux CLI', 'Terminal Linux'),
    'analyst': ('Analyst', 'Analyste'), 'engineer': ('Engineer', 'Ingénierie'),
    'researcher': ('Researcher', 'Recherche'), 'review': ('Read and review', 'Lire et examiner'),
    'study': ('Plan a matched test', 'Préparer un essai comparatif'), 'run': ('Run a scoped tool', 'Exécuter un outil circonscrit'),
    'verified': ('Verified within scope', 'Vérifié dans le périmètre'),
    'discovered': ('Discovered', 'Repéré'), 'falsified': ('Falsified', 'Réfuté'), 'abstain': ('Abstain', 'Abstention'),
}
FIELDS = {
    'change': ('What changed', 'Ce qui a changé'), 'why': ('Why now', 'Pourquoi maintenant'),
    'possibility': ('Opportunity', 'Possibilité'), 'missing_move': ('Missing move', 'Intervention proposée'),
    'alternative': ('Strongest alternative', 'Meilleure solution de rechange'),
    'retain': ('Reusable evidence or asset', 'Preuve ou outil réutilisable'),
    'economics': ('Costs and dependencies', 'Coûts et dépendances'),
    'protocol': ('Acceptance protocol', 'Protocole d’acceptation'),
    'next': ('Next step', 'Prochaine étape'), 'uncertainty': ('Uncertainty', 'Incertitude'),
    'rights': ('Rights', 'Droits'),
}

def label(value, fr):
    if value in VERDICTS:
        return FR_VERDICTS[VERDICTS.index(value)] if fr else value
    return TERMS.get(value, (value.capitalize(), value.capitalize()))[fr]


def controls(briefs, fr):
    any_value = 'Tous' if fr else 'All'
    html = []
    for axis, names in FACETS.items():
        values = sorted({row['profile'][axis] for row in briefs})
        options = ''.join(f'<option value="{escape(value)}">{escape(label(value, fr))}</option>' for value in values)
        html.append(f'<label for="mv-{axis}">{names[fr]}<select id="mv-{axis}" data-mv-filter="{axis}">'
                    f'<option value="">{any_value}</option>{options}</select></label>')
    return ''.join(html)


def cards(briefs, lang):
    fr = lang == 'fr'
    for brief in briefs:
        local = brief[lang]
        attributes = ' '.join(f'data-{k}="{escape(v)}"' for k, v in brief['profile'].items())
        facts = ''.join(f'<div><dt>{names[fr]}</dt><dd>{escape(local[key])}</dd></div>' for key, names in FIELDS.items())
        links = ''.join(f'<a href="{escape(ref["url"])}">{escape(ref[lang])}</a>'
                        for ref in brief['evidence_links'])
        source = 'Source et version' if fr else 'Source and version'
        receipt = 'Reçu Git' if fr else 'Git receipt'
        history = 'Historique de l’Atlas' if fr else 'Atlas history'
        detail = 'Ouvrir le dossier décisionnel' if fr else 'Open decision brief'
        recommendation = '' if not brief['tool'] else (
            f'<p><a href="#tool-{brief["tool"]}">{"Ouvrir l’outil" if fr else "Open the capability"}</a></p>')
        timestamp = brief['updated_at']
        yield (
            f'<article class="mv-decision" id="decision-{escape(brief["id"])}" data-mv-record data-observed="{timestamp}" {attributes}>'
            f'<p class="packet-meta">{escape(label(brief["verdict"], fr))} · {escape(label(brief["atlas_state"], fr))}</p>'
            f'<h4>{escape(local["title"])}</h4><p>{escape(local["possibility"])}</p>'
            f'<details><summary>{detail}</summary>'
            f'<p class="mv-source-date">{source} · <time datetime="{timestamp}">{timestamp[:10]}</time> '
            f'· <code>{escape(brief["source_version"])}</code></p>'
            f'<dl>{facts}</dl><p class="mv-links">{links}'
            f'<a href="{brief["receipt"]}">{receipt}</a><a href="#{escape(brief["id"])}">{history}</a></p>'
            f'{recommendation}</details></article>'
        )


def tool_card(key, manifest, fr):
    labels = {
        'endpoint': (
            ('Endpoint Evidence Screen', 'Évaluation des mesures Endpoint'),
            ('Screen one documented test scope and return its highest qualifying measured load. SQLite provides an independent reference.',
             'Analyser une configuration testée et relever la plus haute charge mesurée admissible avec SQLite comme référence indépendante.'),
            ('Browser workbench and Linux CLI. Benchmark screening. The operating verdict remains ABSTAIN.',
             'Atelier dans le navigateur et terminal Linux. Analyse de banc d’essai. L’adoption demeure en abstention.'),
        ),
        'archive': (
            ('NOAA Archive Point', 'Point d’archive NOAA'),
            ('Extract one exact archived GFS forecast temperature. Six held values match independent ecCodes decoding.',
             'Extraire une température de prévision GFS à un point exact. Six valeurs réservées concordent avec le décodage indépendant ecCodes.'),
            ('Linux, Python, curl and OpenSSL. Retrieval uses NOAA over HTTPS. The signed audit also runs offline.',
             'Linux, Python, curl et OpenSSL. Requête HTTPS vers NOAA. Le contrôle signé fonctionne aussi hors ligne.'),
        ),
    }
    title, detail, environment = [row[fr] for row in labels[key]]
    download = 'Télécharger le ZIP' if fr else 'Download ZIP'
    source = 'Source figée' if fr else 'Pinned source'
    open_tool = ''
    if key == 'endpoint':
        open_tool = f'<a href="#mv-endpoint-run">{"Exécuter" if fr else "Run in browser"}</a>'
    if key == 'endpoint':
        instructions = 'Extraire le ZIP, puis lancer ces deux comparaisons dans le dossier extrait.' if fr else 'Extract the ZIP and run both comparisons from the extracted folder.'
        command = 'node endpoint-cli.mjs sample.json\npython3 endpoint-sqlite.py sample.json'
        accepted = 'Même résultat pour les deux sorties. Charge maximale mesurée admissible de 140 sur l’exemple. Adoption opérationnelle en abstention.' if fr else 'Expect matching output for the sample, a highest qualifying measured load of 140 and operational ABSTAIN.'
    else:
        instructions = 'Extraire le ZIP. Vérifier les six cas signés hors ligne, puis interroger et vérifier le point historique près de Québec.' if fr else 'Extract the ZIP. Audit the six signed cases offline, then retrieve and check the historical point near Québec.'
        command = ('python3 archive-verify.py\npython3 archive-query.py --day 2024-01-18 --cycle 00 --latitude 46.75 '
                   '--longitude -71.25 > point.json\npython3 archive-verify.py point.json')
        accepted = 'Le vérificateur doit retrouver environ 257,85171875 K. Il s’agit d’une prévision historique. Préférer le service ponctuel NCAR si son produit et sa grille conviennent.' if fr else 'The verifier should match about 257.85171875 K for this historical forecast. Prefer NCAR when its product and grid fit your use.'
    how = 'Instructions et résultat attendu' if fr else 'Instructions and expected result'
    return (
        f'<article class="mv-tool" id="tool-{key}"><p class="packet-meta">v{manifest["version"]}</p>'
        f'<h4>{title}</h4><p>{detail}</p><p>{environment}</p>'
        f'<p class="mv-links">{open_tool}<a href="{manifest["download"]}" download>{download}</a>'
        f'<a href="{manifest["source"]}">{source}</a></p>'
        f'<details class="mf-instructions"><summary>{how}</summary><p>{instructions}</p>'
        f'<pre><code>{escape(command)}</code></pre><p>{accepted}</p></details>'
        f'<details><summary>{"Empreinte de l’archive" if fr else "Archive checksum"}</summary>'
        f'<p><code>SHA-256 {manifest["sha256"]}</code></p></details></article>'
    )


EDITION_LABELS = {
    'discovery': ('Source checked', 'Source confirmée'), 'revision': ('Evidence revised', 'Preuves révisées'),
    'review': ('Evidence reviewed', 'Preuves examinées'), 'verified-result': ('Result verified', 'Résultat vérifié'),
    'correction': ('Finding corrected', 'Conclusion révisée'), 'capability': ('Tool available', 'Outil disponible'),
}


def timestamp_html(when):
    return f'<time datetime="{escape(when)}">{escape(when[:16].replace("T", " "))} UTC</time>'


def home_preview(compiled, lang):
    fr = lang == 'fr'
    featured = next(row for row in compiled['briefs'] if editions.key(row) == editions.key(compiled['member_first']['edition']))
    local = featured[lang]
    source = featured['evidence_links'][0]
    archive = next(row for row in compiled['briefs'] if row['tool'] == 'archive')
    decision = archive[lang]
    evidence = ('Piste externe · source confirmée' if fr else 'External lead · source checked') if featured['evidence'] == 'source-identity-only' else EDITION_LABELS[featured['edition_kind']][fr]
    steps = ('Choisir une tâche', 'Exécuter l’outil', 'Examiner le résultat', 'Exporter le reçu') if fr else (
        'Choose a task', 'Run the tool', 'Inspect the result', 'Export a receipt')
    outcome = ('Essayez l’exemple Endpoint avec sept mesures publiques. L’analyse et le reçu restent sur votre appareil.' if fr else
               'Try the Endpoint example with seven public measurements. The analysis and receipt stay on your device.')
    tool_list = (
        ('Endpoint Evidence Screen', 'Charge maximale testée admissible. SQLite comme référence. Adoption opérationnelle en abstention.' if fr else
         'Highest qualifying tested load. SQLite reference. Operational adoption remains ABSTAIN.'),
        ('NOAA Archive Point', 'Prévision GFS historique à un point précis. Six cas vérifiés avec ecCodes. NCAR peut utiliser moins de données.' if fr else
         'Historical GFS forecast at an exact point. Six cases checked against ecCodes. NCAR can use less data.'),
    )
    tools = ''.join(f'<li><strong>{title}</strong> · {detail}</li>' for title, detail in tool_list)
    findings = ''.join(f'<dt>{FIELDS[name][fr]}</dt><dd>{escape(decision[name])}</dd>' for name in ('alternative', 'next'))
    return (
        f'<div class="preview-grid" data-preview-version="{escape(featured["source_version"])}" data-preview-count="{len(compiled["briefs"])}">'
        f'<article class="preview-card" id="preview-intelligence"><p class="packet-meta">{"Bulletin Member First" if fr else "Member First intelligence"}</p>'
        f'<h3>{escape(local["title"])}</h3><p>{escape(local["possibility"])}</p>'
        f'<p class="preview-meta">{evidence} · {timestamp_html(featured["updated_at"])} · <a href="{escape(source["url"])}">{escape(source[lang])}</a></p></article>'
        f'<article class="preview-card" id="preview-decisions"><p class="packet-meta">{"Bureau d’aide à la décision" if fr else "Frontier Decision Desk"}</p>'
        f'<h3>{len(compiled["briefs"])} {"dossiers consultables" if fr else "searchable decision briefs"}</h3>'
        f'<p>{escape(decision["possibility"])}</p><p><strong>{escape(label(archive["verdict"], fr))}</strong> · {"Dans le périmètre testé" if fr else "Within the tested scope"}</p><dl>{findings}</dl></article>'
        f'<article class="preview-card" id="preview-capabilities"><p class="packet-meta">{"Bibliothèque d’outils" if fr else "Frontier Capability Library"}</p>'
        f'<h3>{len(compiled["capabilities"])} {"outils qualifiés" if fr else "qualified tools you can run"}</h3><ul>{tools}</ul></article>'
        f'<article class="preview-card" id="preview-outcomes"><p class="packet-meta">{"Atelier de vérification" if fr else "Outcome Workbench"}</p>'
        f'<h3>{"Du résultat à la preuve" if fr else "From result to evidence"}</h3><p>{outcome}</p>'
        f'<ol>{"".join(f"<li>{step}</li>" for step in steps)}</ol></article></div>'
    )


def feature_html(slot, compiled, lang):
    fr = lang == 'fr'
    row = next(entry for entry in compiled['briefs'] if editions.key(entry) == editions.key(slot))
    local = row[lang]
    title = escape(local['title'])
    reference = row['evidence_links'][0]
    kind = EDITION_LABELS[row['edition_kind']][fr]
    inputs = ('why', 'possibility', 'alternative', 'next', 'uncertainty')
    facts = ''.join(f'<div><dt>{FIELDS[name][fr]}</dt><dd>{escape(local[name])}</dd></div>' for name in inputs)
    label = 'Dossier à la une' if fr else 'Featured intelligence briefing'
    brief = 'Ouvrir le dossier décisionnel' if fr else 'Open the decision brief'
    runs = 'Vérification de publication' if fr else 'Publication verification'
    return (
        f'<article class="mf-feature" id="mf-edition" data-edition-run="{slot["member_run"]}">'
        f'<p class="packet-meta">{label} · {kind}</p><h4>{title}</h4><p>{escape(local["change"])}</p>'
        f'<p class="mf-meta">{timestamp_html(row["updated_at"])} · {escape(row["source_version"])}</p>'
        f'<dl>{facts}</dl><p class="mv-links"><a class="mf-action" data-mv-open href="#decision-{row["id"]}">{brief}</a>'
        f'<a href="{escape(reference["url"])}">{escape(reference[lang])}</a>'
        f'<a href="{editions.RUNS}{slot["member_run"]}">{runs}</a></p></article>'
    )


def public_feature(compiled, lang):
    slot = compiled['member_first']['public_feature']
    if not slot:
        return ''
    fr = lang == 'fr'
    row = next(entry for entry in compiled['briefs'] if editions.key(entry) == editions.key(slot))
    caption = 'Du bulletin Member First' if fr else 'From the Member First briefing'
    observe = 'Première vérification de l’édition membre' if fr else 'First verified member-edition visibility'
    evidence = 'Vérification du résumé public' if fr else 'Public summary verification'
    return (
        f'<aside class="atlas-editorial" id="atlas-editorial" data-public-run="{slot["public_run"]}">'
        f'<p class="packet-meta">{caption}</p><h3>{escape(row[lang]["title"])}</h3>'
        f'<p>{escape(row[lang]["change"])}</p><p>{observe} {timestamp_html(slot["member_checked_at"])}</p>'
        f'<p><a href="#{row["id"]}">{"Dossier public" if fr else "Public record"}</a> · '
        f'<a href="{editions.RUNS}{slot["public_run"]}">{evidence}</a></p></aside>'
    )


def render(lang, compiled, sample):
    fr = lang == 'fr'
    tools = compiled['capabilities']
    briefs = compiled['briefs']
    template = (TOOLS / f'member.{lang}.html').read_text()
    highlights = []
    for row in sorted(briefs, key=lambda entry: (entry['updated_at'], entry['id']), reverse=True)[:4]:
        highlights.append(f'<li>{timestamp_html(row["updated_at"])} '
                          f'<a data-mv-open href="#decision-{escape(row["id"])}">{escape(row[lang]["title"])}</a> '
                          f'<span>{EDITION_LABELS[row["edition_kind"]][fr]}</span></li>')
    replacements = {
        '<!-- MF_FEATURE -->': feature_html(compiled['member_first']['edition'], compiled, lang),
        '<!-- MF_UPDATED -->': timestamp_html(compiled['updated_at']),
        '<!-- MV_TIMELINE -->': ''.join(highlights),
        '<!-- MV_FILTERS -->': controls(briefs, fr),
        '<!-- MV_BRIEFS -->': ''.join(cards(briefs, lang)),
        '<!-- MV_TOOLS -->': ''.join(tool_card(k, v, fr) for k, v in tools.items()),
        '<!-- MV_SAMPLE -->': escape(stable(sample).decode()),
        '<!-- MV_REFERENCE -->': escape(stable(compiled['endpoint_reference']).decode()),
        '<!-- MV_TOOL_MANIFEST -->': escape(stable(tools['endpoint']).decode()),
    }
    for marker, value in replacements.items():
        if template.count(marker) != 1:
            raise ValueError('Invalid member rendering template')
        template = template.replace(marker, value)
    return template


def prepare(directory, ledger, atlas_sha256, run='1', previous=None, witness=lambda run: None, promote=True):
    tools, sample, reference = build_tools(directory)
    briefs = [context_for(brief) for brief in decision_briefs(ledger)]
    value = {'schema': 'frontier/public-member-value-v1', 'publication': 'public-file',
             'atlas_sha256': atlas_sha256, 'updated_at': ledger['updated_at'],
             'protected_member_first': None, 'member_lead_seconds': None, 'real_member_trials': None,
             'independently_accepted_member_trials': None, 'measured_productivity_advantage': None,
             'member_redeployments': None, 'source_policy': 'existing-approved-atlas-inputs-only',
             'capabilities': tools, 'endpoint_reference': reference, 'briefs': briefs,
             'member_first': editions.feed(briefs, previous or {}, run, witness, promote)}
    raw = stable(value) + b'\n'
    (directory / MEMBER_JSON).write_bytes(raw)
    return value, {lang: render(lang, value, sample) for lang in CAPTIONS}, digest(raw)
