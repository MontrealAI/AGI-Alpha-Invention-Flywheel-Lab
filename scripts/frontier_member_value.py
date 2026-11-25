"""Compile public-file member material from the admitted Atlas and pinned instruments."""

from hashlib import sha256
from html import escape
from decimal import Decimal
from io import BytesIO
import json
import re
from pathlib import Path
import subprocess
import sys
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
FOUNDRY_ZIP = 'frontier-foundry-1.0.0.zip'
STUDY_ZIP = 'frontier-foundry-1.1.0.zip'
INVENTOR_ZIP = 'frontier-inventor-1.0.0.zip'
LEARNING_ZIP = 'frontier-learning-1.0.0.zip'
ACTIVATION_ZIP = 'frontier-activation-1.0.0.zip'
ACTIVATION_SHA256 = '66ecb99d319ec1c4aa0455e672ef9866e5bf44adb54e59845b19ccc26d98d17c'
AMPLIFICATION_ZIP = 'frontier-activation-1.1.0.zip'
AMPLIFICATION_PIN = '3e229271a5408961a8ad686fa32d0b0f2fd08663'
AMPLIFICATION_SHA256 = '158aa880e2a282915f011ff8c4786ec0641b6d5da82178a9e131d0c64a17499c'
SUBSTRATE_ZIP = 'frontier-activation-1.2.0.zip'
SUBSTRATE_PIN = '97dffcd9c40d3a7504466b6ed74140bcb53b2a8c'
SUBSTRATE_SHA256 = 'f4bc4141d5c86c251b04a9a2d129b65ab610242e5422755161e4882bb35cda06'
LIBERATION_ZIP = 'frontier-activation-1.3.0.zip'
LIBERATION_PIN = '96bf376e90acb2ae291a6317e72284a266389d27'
LIBERATION_SHA256 = 'c73a4f0f261a2be986bf6315bd7ce6102167ccad929d9c44bc31701a1386ff1f'
CASCADE_ZIP = 'frontier-activation-1.4.0.zip'
CASCADE_PIN = '0415b78818f795a7adef802e467ef076c00026db'
CASCADE_SHA256 = '075e28dae9c58c3b856eaad57faaf9ffe189cae925954211266dcef95ac9335e'
CASCADE_STUDIES = {'cascade-results.json': 'RESULTS.json', 'cascade-fresh-domain.json': 'FRESH-DOMAIN.json'}
FACTORY_ZIP = 'frontier-activation-1.5.0.zip'
FACTORY_PIN = '436bb1b142a0da1f2c272f77821b75c3efdd73fe'
FACTORY_SHA256 = '5a29bc8d215895216201b85dcf6f5af6709d0ecea857792cf24b3cc4d20ec791'
FACTORY_RESULTS = 'factory-results.json'
GAME_THEORY_ZIP = 'frontier-game-theory-1.0.0.zip'
GAME_THEORY_SHA256 = '5cf63237c4e41aece421d0330286e0521b572f4406e69915c01d66b104b11fcb'
OBSERVATION_ZIP = 'frontier-game-observation-1.0.0.zip'
OBSERVATION_SHA256 = '63c5554fade9082f84e5092fccea75da8aeab00af1d39feff83cd1e85a60f1df'
LEGACY_EXECUTOR_ZIP = 'frontier-harness-executor-1.0.0.zip'
EXECUTOR_BASELINE = 'c0a14ba028092db648516718f9127ae8166df63e'
LEGACY_EXECUTOR_SHA256 = '0e2c15569abd9112565f25485fa75c225764de6190cbded4e83127865bf5b9e3'
PREVIOUS_EXECUTOR_ZIP = 'frontier-harness-executor-1.1.0.zip'
PREVIOUS_EXECUTOR_BASELINE = '297a51c25c48031e1e6f964835f4dfae3ddb8023'
PREVIOUS_EXECUTOR_SHA256 = '58e1aac31e1cd1bfb92c53f213a16e28a7009580dd06072a029a331f959a491a'
OUTCOME_EXECUTOR_ZIP = 'frontier-harness-executor-1.2.0.zip'
OUTCOME_EXECUTOR_BASELINE = '1bdac817b471157092ea4aac881916824b66734e'
OUTCOME_EXECUTOR_SHA256 = 'bb56fe369550897904bdb875a0e3830029a84af02c18788210cd10c5832d1fb9'
INTELLIGENCE_EXECUTOR_ZIP = 'frontier-harness-executor-1.3.0.zip'
INTELLIGENCE_EXECUTOR_BASELINE = '3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c'
INTELLIGENCE_EXECUTOR_SHA256 = '0436a351d4ec5c5af48dbed9f93847c90a3fc6ac0e73a6a35eab53a11c29b71d'
ORIGINAL_INTELLIGENCE_EXECUTOR_ZIP = 'frontier-harness-executor-1.3.0-cef4d1c.zip'
ORIGINAL_INTELLIGENCE_EXECUTOR_BASELINE = 'cef4d1caa38b14555613dc25d180c42798b62b78'
ORIGINAL_INTELLIGENCE_EXECUTOR_SHA256 = '443f0288f5057f7b6f87ce875b8f009736a738c916bde06440adfce3fb4c7b1c'
EXECUTOR_ZIP = 'frontier-harness-executor-1.4.0.zip'
HISTORICAL_EXECUTORS = {LEGACY_EXECUTOR_ZIP: LEGACY_EXECUTOR_SHA256,
                        PREVIOUS_EXECUTOR_ZIP: PREVIOUS_EXECUTOR_SHA256,
                        OUTCOME_EXECUTOR_ZIP: OUTCOME_EXECUTOR_SHA256,
                        INTELLIGENCE_EXECUTOR_ZIP: INTELLIGENCE_EXECUTOR_SHA256,
                        ORIGINAL_INTELLIGENCE_EXECUTOR_ZIP: ORIGINAL_INTELLIGENCE_EXECUTOR_SHA256}
EXECUTION_PUBLICATION = MAIN / 'publication/mission-executor'
EVIDENCE_PUBLICATION = MAIN / 'publication/evidence-bound'
OUTCOME_PUBLICATION = MAIN / 'publication/outcome-driven'
INTELLIGENCE_PUBLICATION = MAIN / 'publication/bring-your-own-intelligence'
MISSION_MARKER = '<!-- UNIVERSAL_PUBLIC_RUNS -->'
PUBLIC_MISSIONS = MAIN / 'publication/universal'
MISSION_ASSETS = ('frontier-mission.mjs', 'frontier-mission-router.mjs', 'frontier-mission-ui.mjs', 'frontier-assisted-work.mjs',
                  'frontier-mission-context.mjs', 'frontier-artifact-exchange.mjs', 'dpp-source-review.mjs',
                  'frontier-battery-source-example.json',
                  'frontier-execution.mjs', 'frontier-browser-model.mjs', 'frontier-companion-link.mjs', 'companion-start.html',
                  GAME_THEORY_ZIP, OBSERVATION_ZIP,
                  *HISTORICAL_EXECUTORS, EXECUTOR_ZIP)
ACTIVATION_ARCHIVE_SHA256 = {
    ACTIVATION_ZIP: ACTIVATION_SHA256,
    AMPLIFICATION_ZIP: AMPLIFICATION_SHA256, SUBSTRATE_ZIP: SUBSTRATE_SHA256,
    LIBERATION_ZIP: LIBERATION_SHA256, CASCADE_ZIP: CASCADE_SHA256,
    FACTORY_ZIP: FACTORY_SHA256,
}
FOUNDRY_ENGINE = 'harness-engine.js'
FOUNDRY_INPUT = 'FOUNDRY_PUBLIC_DATA'
HARNESS_PIN = '39e76570c851b3527d78a526053a9ea2a611a993'
HARNESS = 'products/alpha-genesis-harness/'
FOUNDRY_ASSETS = ('foundry-core.mjs', 'foundry-ui.mjs', 'foundry-study.mjs', 'outcome-receipt.mjs',
                  FOUNDRY_ENGINE, FOUNDRY_ZIP, STUDY_ZIP, INVENTOR_ZIP, LEARNING_ZIP, ACTIVATION_ZIP,
                  AMPLIFICATION_ZIP, SUBSTRATE_ZIP, LIBERATION_ZIP, CASCADE_ZIP, *CASCADE_STUDIES,
                  FACTORY_ZIP, FACTORY_RESULTS)
INVENTOR_EVIDENCE = MAIN / 'publication/inventor'
LEARNING_EVIDENCE = MAIN / 'publication/adaptive'
ACTIVATION_EVIDENCE = MAIN / 'publication/activation'
AMPLIFICATION_EVIDENCE = MAIN / 'publication/amplification'
SUBSTRATE_EVIDENCE = MAIN / 'publication/substrate'
LIBERATION_EVIDENCE = MAIN / 'publication/liberation'
CASCADE_EVIDENCE = MAIN / 'publication/cascade'
FACTORY_EVIDENCE = MAIN / 'publication/factory'

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


def package(path, files, name, pin, scope, version='1.0.0'):
    manifest = {'schema': 'frontier/portable-capability-v1', 'id': name, 'version': version,
                'source': commit_url(pin),
                'rights': RIGHTS, 'qualification_scope': scope,
                'file_sha256': {key: digest(value) for key, value in files.items()}}
    with ZipFile(path, 'w', compression=ZIP_STORED) as release:
        for filename, raw in sorted({**files, 'manifest.json': stable(manifest) + b'\n'}.items()):
            entry = ZipInfo(filename)
            entry.compress_type = ZIP_STORED
            launcher = filename.removeprefix('runtime/') in {'Launch-FRONTIER.sh', 'Launch-FRONTIER.command'}
            entry.external_attr = (0o755 if launcher else 0o644) << 16
            release.writestr(entry, raw)
    return {**manifest, 'download': path.name, 'sha256': digest(path.read_bytes()), 'bytes': path.stat().st_size}


def foundry_example(fr=False):
    raw = pinned(ARCHIVE_PIN, ARCHIVE_PATH + 'evidence/confirmation.json')
    if digest(raw) != '5f2e47bb0f08b7efcfdf934683c1b9215d45c5b4e5c9f7795ea324ac250d5add':
        raise ValueError('Public NOAA byte-window source mismatch')
    domain = {'min': 0, 'max': 2_000_000_000}
    task = {
        'schema': 'frontier/foundry-mission-v1', 'language': 'fr' if fr else 'en',
        'objective': ('Vérifier le nombre d’octets d’une plage NOAA historique.'
                      if fr else 'Check the byte count of an archived NOAA response window.'),
        'rule': ('Retourner bytes = end - start + 1 et ordered = start <= end. Si ordered est faux, s’abstenir.'
                 if fr else 'Return bytes = end - start + 1 and ordered = start <= end. Abstain if ordered is false.'),
        'inputs': {'start': domain, 'end': domain}, 'outputs': {'bytes': 'integer', 'ordered': 'boolean'},
        'alternative': 'Arithmétique entière Python, RFC 9110 §14.1.2.' if fr else 'Python integer arithmetic, RFC 9110 §14.1.2.',
        'acceptance': ('Chaque résultat doit correspondre au nombre d’octets du reçu historique.'
                       if fr else 'Every result must match the observed byte count in the historical receipt.'),
    }
    start, end = {'field': 'start'}, {'field': 'end'}
    instrument = {'name': 'NOAA byte window', 'inputs': ['start', 'end'],
                  'outputs': {'bytes': {'op': 'add', 'args': [{'op': 'sub', 'args': [end, start]}, 1]},
                              'ordered': {'op': 'lte', 'args': [start, end]}}}
    cases = []
    for row in json.loads(raw)['receipt']['cases']:
        source = row['candidate']['source']
        first, last, _ = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', source['content_range']).groups()
        cases.append({'input': {'start': int(first), 'end': int(last)},
                      'expected': {'bytes': source['body_bytes'], 'ordered': True}})
    suite = {'schema': 'frontier/foundry-cases-v1', 'mission_sha256': digest(stable(task)),
             'reference': ('Réponse NOAA historique, reçu Ed25519 ' if fr else 'Historical NOAA response, Ed25519 receipt ') + ARCHIVE_PIN,
             'cases': cases}
    return {'task': task, 'candidate': instrument, 'suite': suite, 'sample': cases[0]['input']}


def build_foundry(destination):
    companion = TOOLS / 'foundry'
    files = {name: (companion / name).read_bytes() for name in
             ('README.md', 'foundry-cli.mjs', 'provider.py', 'formulas.py', 'local.example.json')}
    files.update({name: (ASSETS / name).read_bytes() for name in ('foundry-core.mjs', 'outcome-receipt.mjs')})
    files.update({name: pinned(HARNESS_PIN, HARNESS + name) for name in
                  ('LICENSE', 'NOTICE', 'bridge/adapters.py', 'bridge/instruments.py', 'bridge/output_schema.py', 'bridge/streaming.py')})
    files['example.json'] = stable(foundry_example()) + b'\n'
    publication = MAIN / 'publication/frontier-foundry'
    result = (publication / 'reference-model-trial.json').read_bytes()
    evidence = json.loads(result)
    sealed = evidence['asset']['output']
    comparison = evidence['s1_grade']['output']
    if comparison['summary']['matched'] != 14 or not evidence['fresh_run_matches_observation']:
        raise ValueError('Unqualified foundry asset in public package')
    suite = {'schema': 'frontier/foundry-cases-v1',
             'mission_sha256': sealed['asset']['mission_sha256'],
             'reference': comparison['summary']['reference'],
             'cases': []}
    historical = json.loads(pinned(ARCHIVE_PIN, ARCHIVE_PATH+'evidence/confirmation.json'))['receipt']['cases']
    sources = [item[route]['source'] for item in historical for route in ('candidate', 'reference')]
    for source in sources:
        first, last, _ = map(int, re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', source['content_range']).groups())
        suite['cases'].append({'input':{'start':first,'end':last},
                               'expected':{'bytes':source['body_bytes'],'ordered':True}})
    suite['cases'] += [{'input':{'start':7,'end':7},'expected':{'bytes':1,'ordered':True}},
                       {'input':{'start':8,'end':4},'expected':{'bytes':-3,'ordered':False}}]
    if digest(stable(suite)) != sealed['asset']['comparison']['suite_sha256']:
        raise ValueError('Retained confirmation cases changed')
    files.update({
        'retained/noaa-window.json': stable(sealed) + b'\n',
        'retained/noaa-cases.json': stable(suite) + b'\n',
        'retained/noaa-reuse-input.json': b'{"start":0,"end":31}\n',
        'retained/qualification.json': result,
    })
    files[FOUNDRY_ENGINE] = pinned(HARNESS_PIN, HARNESS + 'app/engine.js')
    (destination / FOUNDRY_ENGINE).write_bytes(files[FOUNDRY_ENGINE])
    legacy = package(destination / FOUNDRY_ZIP, files, 'frontier-foundry', HARNESS_PIN,
                     'Bounded HARNESS exchange and offline replay. Source identifies the upstream HARNESS pin. '
                     'The deployment receipt identifies integration source and distributed file hashes.')
    studies = {name: (companion / name).read_bytes() for name in
               ('study-cli.mjs', 'study-seal.mjs', 'study.py', 'SUCCESSORS.md')}
    studies['foundry-study.mjs'] = (ASSETS / 'foundry-study.mjs').read_bytes()
    for trial in ('successor-study', 'successor-followup'):
        for name in ('report.json', 'cases.json', 'source.json'):
            path = f'{trial}/{name}'
            studies[path] = (publication / path).read_bytes()
    package(destination / STUDY_ZIP, {**files, **studies}, 'frontier-foundry', HARNESS_PIN,
            'Bounded local successor studies and offline verification. The deployment receipt binds the integration.',
            version='1.1.0')
    return legacy


def build_inventor(destination):
    files = {name:(TOOLS / 'inventor' / name).read_bytes() for name in
             ('README.md','inventor.py','inventor_verify.py','relational.py','reproduce.py')}
    files.update({name:(TOOLS / 'foundry' / name).read_bytes() for name in
                  ('provider.py','study.py','formulas.py','local.example.json')})
    files.update({name:pinned(HARNESS_PIN, HARNESS + name) for name in
                  ('LICENSE','NOTICE','bridge/adapters.py','bridge/instruments.py','bridge/output_schema.py','bridge/streaming.py')})
    for name in ('evidence.json','reproduction.json','diagnostic-evidence.json','diagnostic-reproduction.json',
                 'larger-evidence.json','larger-reproduction.json','REGISTRATION.md','RESOURCE-FOLLOWUP.md',
                 'DIAGNOSTIC-FOLLOWUP.md','LARGER-FOLLOWUP.md','REPORT.md','run_pilot.py','protocol.py'):
        files['study/'+name] = (INVENTOR_EVIDENCE/name).read_bytes()
    return package(destination / INVENTOR_ZIP, files, 'frontier-inventor', HARNESS_PIN,
                   'Local read-only SQL construction, public-data replay and registered discovery-policy comparisons.')


def build_learning(destination):
    files = {name:(TOOLS/'adaptive'/name).read_bytes() for name in
             ('README.md','check.py','learning.py','operate.py','pages.py','research.py','reproduce.py',
              'self_test.py','wasm_policy.py','requirements-linux.txt')}
    files.update({name:(TOOLS/'inventor'/name).read_bytes() for name in ('inventor.py','relational.py')})
    files.update({name:(TOOLS/'foundry'/name).read_bytes() for name in
                  ('provider.py','study.py','formulas.py','local.example.json')})
    files.update({name:pinned(HARNESS_PIN,HARNESS+name) for name in
                  ('LICENSE','NOTICE','bridge/adapters.py','bridge/instruments.py','bridge/output_schema.py','bridge/streaming.py')})
    for name in ('REGISTRATION.md','REPORT.md','REPRESENTATION-FOLLOWUP.md','prepare.py','run_study.py','training.json','verification.json',
                 'runs.json','operation.json','cohort/inputs.json','cohort/fit.json','cohort/development.json',
                 'cohort/confirmation.json'):
        files[f'study/{name}']=(LEARNING_EVIDENCE/name).read_bytes()
    return package(destination/LEARNING_ZIP,files,'frontier-learning',HARNESS_PIN,
                   'Local read-only release observation, portable training and isolated experimental policy comparison.')


def render_learning(fr):
    result=json.loads((LEARNING_EVIDENCE/'verification.json').read_bytes())['forecast']
    reference=result['comparisons'][result['reference']]
    trained=result['comparisons']['trained']
    headers=('Prévision','Cas','Erreur absolue moyenne (s)','90e centile (s)') if fr else (
        'Forecast','Cases','Mean absolute error (s)','90th percentile (s)')
    alternatives=((('Référence conventionnelle' if fr else 'Conventional reference'),reference),
                  (('Modèle entraîné' if fr else 'Trained model'),trained))
    if result['verdict']=='QUALIFIED':
        outcome='Seuil de confirmation atteint. Adoption distincte.' if fr else 'Met the confirmation threshold. Adoption requires a separate decision.'
    else:
        outcome='Le seuil de confirmation n’a pas été atteint.' if fr else 'The model missed the confirmation threshold.'
    rows=''.join(f'<tr><th scope="row">{label}</th><td>{row["cases"]}</td><td>{row["mae_seconds"]:.1f}</td>'
                 f'<td>{row["p90_seconds"]}</td></tr>' for label,row in alternatives)
    return (f'<p>{outcome}</p><div class="foundry-pilot-table" tabindex="0" role="region" aria-label="{headers[0]}">'
            '<table><thead><tr>'+''.join(f'<th scope="col">{h}</th>' for h in headers)+
            '</tr></thead><tbody>'+rows+'</tbody></table></div>')


def activation_archive_files(root, names, prefix=''):
    # The merged 1.4 tree contains the exact payloads distributed in earlier Activation releases.
    return {prefix + name: pinned(CASCADE_PIN, (root / name).relative_to(MAIN).as_posix()) for name in names}


def build_activation_archive(path, files, pin, scope, version):
    release = package(path, files, 'frontier-activation', pin, scope, version=version)
    if release['sha256'] != ACTIVATION_ARCHIVE_SHA256[path.name]:
        raise ValueError(f'Activation {version} release bytes changed')
    return release


def activation_files():
    files = activation_archive_files(TOOLS / 'activation', (
        'README.md','activate.py','model_step.py','packets.py','phase.py','table_program.py',
        'verify_activation.py','reproduce_activation.py','research_next.py'))
    for directory,names in (
            ('adaptive',('pages.py','research.py','learning.py','wasm_policy.py','requirements-linux.txt')),
            ('inventor',('inventor.py','relational.py')),('foundry',('provider.py','study.py','formulas.py','local.example.json'))):
        files.update(activation_archive_files(TOOLS / directory, names))
    files.update({name:pinned(HARNESS_PIN,HARNESS+name) for name in (
        'LICENSE','NOTICE','bridge/adapters.py','bridge/instruments.py','bridge/output_schema.py','bridge/streaming.py')})
    names=['REGISTRATION.md','FOLLOWUP.md','REPORT.md','inventory.json','selection.json','live-case.json',
           'live-replay.json','phase-history.json','phase-events.json','initial-run.json','followup-run.json','verification.json',
           'next-research.json','phase-pr.json']
    names.extend('corpus/'+name+'.json' for name in (
        'catalogue','commitments','learning-replay-development','learning-replay-confirmation',
        'local-runner-development','local-runner-confirmation','inventor-audit-development','inventor-audit-confirmation'))
    files.update(activation_archive_files(ACTIVATION_EVIDENCE, names, 'study/'))
    return files


def build_activation(destination):
    return build_activation_archive(destination / ACTIVATION_ZIP, activation_files(), HARNESS_PIN,
                                    'Public evidence recovery, bounded Wasm table construction, and prospective Pages shadow forecasts.',
                                    '1.0.0')


def amplification_files():
    files = activation_files()
    files.update(activation_archive_files(TOOLS / 'activation', (
        'AMPLIFICATION.md','amplify.py','native_experiment.py','route_environment.py','reproduce_amplification.py',
        'calibration_environment.py','refine_amplification.py','discover_amplification.py')))
    files.update(activation_archive_files(AMPLIFICATION_EVIDENCE, (
        'REPORT.md','registration.json','discovery.json','development.json','confirmation.json',
        'provenance.json','trial.json','comparisons.json','build_cases.py','repair-registration.json',
        'context-followup.json','transfer-registration.json','calibration-development.json',
        'calibration-confirmation.json','calibration-trial.json','build_calibration.py','record_results.py',
        'next-investigation.json','phase-additional.json','diagnostic-audit.json',
        'initial-research-input.txt','next-research-input.txt'), 'study/amplification/'))
    return files


def build_amplification(destination):
    return build_activation_archive(destination / AMPLIFICATION_ZIP, amplification_files(), AMPLIFICATION_PIN,
                                    'Activation 1.1 with a separate native research sandbox, matched comparisons, '
                                    'and exact workload replay.', '1.1.0')


def substrate_files():
    files = amplification_files()
    files.update(activation_archive_files(TOOLS / 'activation', (
        'SUBSTRATE.md', 'science_substrate.py', 'science_reference.py', 'science_workbench.py',
        'substrate_study.py', 'verify_substrate.py')))
    files.update(activation_archive_files(SUBSTRATE_EVIDENCE, (
        'REGISTRATION.json', 'BINDINGS.json', 'CASE.json', 'DEVELOPMENT.json', 'CONFIRMATION.json',
        'SURVEYS.json', 'MANUAL-PACKET.json', 'MANUAL-RESPONSE.json', 'manual-candidate.json',
        'REPORT.md', 'assemble.py', 'RESULTS.json', 'NEXT.json', 'LOCAL-CONFIG.json',
        'model-evidence.json', 'record.py', 'covariance_pilot.py', 'PILOT-REGISTRATION.json', 'PILOT-RESULT.json'),
        'study/substrate/'))
    return files


def build_substrate(destination):
    return build_activation_archive(destination / SUBSTRATE_ZIP, substrate_files(), SUBSTRATE_PIN,
                                    'Exact scientific environments and bounded research on source-grounded executable knowledge.',
                                    '1.2.0')


def liberation_files():
    files = substrate_files()
    files.update(activation_archive_files(TOOLS / 'activation', (
        'LIBERATION.md', 'liberation.py', 'covariance_study.py', 'hydrology.py', 'independent_timing.py',
        'discovery_workbench.py', 'verify_liberation.py')))
    files.update(activation_archive_files(LIBERATION_EVIDENCE, (
        'REGISTRATION.json', 'FOLLOWUP.json', 'CONFIRMATION.json', 'CONSTRUCTION.json', 'SOURCES.json',
        'COVARIANCE.json', 'HYDROLOGY.json', 'PACKET.json', 'RESPONSE.json', 'NEXT.json', 'config.json',
        'FOLLOWON-REGISTRATION.json', 'INDEPENDENT-TIMING.json', 'REPORT.md', 'GATES.md', 'assemble.py'),
        'study/liberation/'))
    return files


def build_liberation(destination):
    return build_activation_archive(destination / LIBERATION_ZIP, liberation_files(), LIBERATION_PIN,
                                    'Historical scientific discovery, compact construction and source-bound hydrology.',
                                    '1.3.0')


def cascade_files():
    files = liberation_files()
    files.update(activation_archive_files(TOOLS / 'activation', (
        'cascade.py', 'cascade_fresh_domain.py', 'post_reveal_overlap.py', 'transit_cascade.py',
        'transit_ordinary.py', 'ttv_diagnostic.py', 'verify_cascade.py')))
    files.update(activation_archive_files(CASCADE_EVIDENCE, (
        'REGISTRATION.md', 'OWNER.md', 'GATES.md', 'REPLAY.md', 'PRIMARY.json', 'ORDINARY.json',
        'TTV.json', 'TTV-INPUT.json', 'POST-REVEAL-INPUT.json', 'POST-REVEAL.json',
        'LOCAL-CONFIG.json', *CASCADE_STUDIES.values()), 'study/cascade/'))
    return files


def build_cascade(destination):
    files = cascade_files()
    for output, filename in CASCADE_STUDIES.items():
        (destination / output).write_bytes(files[f'study/cascade/{filename}'])
    return build_activation_archive(destination / CASCADE_ZIP, files, CASCADE_PIN,
                                    'Historical transit timing from source photometry, matched use of tools and a climate evidence replay.',
                                    '1.4.0')


def build_factory(destination):
    files = cascade_files()
    for filename in ('evidence_truth.py', 'evidence_control.py', 'verify_factory.py', 'joint_transit.py'):
        path = TOOLS.relative_to(MAIN) / 'activation' / filename
        files[filename] = pinned(FACTORY_PIN, path.as_posix())
    for filename in ('REGISTRATION.md', 'REPORT.md', 'GATES.md', 'EVIDENCE.json', 'EVIDENCE-SOURCES.json',
                     'TRANSIT-INPUT.json', 'TRANSIT.json', 'FACTORY.json', 'hurricane-lineage-control.py',
                     'ground/README.md', 'ground/fit_ground.py', 'ground/fetch_ground.py',
                     'ground/GROUND-ONLY-REGISTRATION.json', 'ground/EXOFOP-FILES.json'):
        path = FACTORY_EVIDENCE.relative_to(MAIN) / filename
        files[f'study/factory/{filename}'] = pinned(FACTORY_PIN, path.as_posix())
    (destination / FACTORY_RESULTS).write_bytes(files['study/factory/FACTORY.json'])
    return build_activation_archive(destination / FACTORY_ZIP, files, FACTORY_PIN,
                                    'Read-only historical evidence rulings, source lineage, and astronomical attribution.',
                                    '1.5.0')


def executor_source_path(name):
    special = {
        'START-HERE.html': f'docs/research/{SITE}companion-start.html',
        'runtime/bridge/relational.py': 'products/frontier-member-tools/inventor/relational.py',
        'runtime/bridge/mission_assets/endpoint-screen.mjs': f'docs/research/{SITE}endpoint-screen.mjs',
        'runtime/local-model.example.json': 'publication/mission-executor/local-model.example.json',
    }
    if name in special:
        return special[name]
    if not re.fullmatch(r'runtime/[A-Za-z0-9._/-]+', name) or any(
            part in ('', '.', '..') for part in name.split('/')):
        raise ValueError('Unexpected companion payload path')
    return f'{HARNESS}{name.removeprefix("runtime/")}'


def executor_payload_revision(revision, paths):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Invalid site source revision')
    payload = subprocess.check_output(
        ['git', 'log', '--first-parent', '-1', '--format=%H', revision, '--', *paths], cwd=MAIN, text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', payload):
        raise ValueError('The companion payload source is unavailable')
    return payload


def build_mission_executor(destination, revision):
    harness = MAIN / HARNESS
    bridges = ('__init__', 'adapters', 'chatgpt', 'codex', 'codex_permissions', 'deployment', 'frontier_monitor',
               'genesis_next', 'instruments', 'mission_contracts', 'mission_tools', 'onboarding', 'output_schema',
               'pages_missions', 'proof_to_market', 'server', 'services', 'strategy_demo', 'streaming', 'universal_missions',
               'upgrade_foundry', 'workflow_demo', 'workflow_schemas', 'workflow_strategies', 'workflows', 'workshop', 'workshop_protocol')
    asset_paths = ('LICENSE', 'NOTICE', *(f'bridge/{name}.py' for name in bridges),
                   'app/index.html', 'app/app.js', 'app/engine.js', 'app/styles.css', 'app/workshop.js')
    sources = {
        **{name: harness / name for name in asset_paths},
        'bridge/relational.py': TOOLS / 'inventor/relational.py',
        'bridge/mission_assets/endpoint-screen.mjs': ASSETS / 'endpoint-screen.mjs',
        'START.md': EXECUTION_PUBLICATION / 'README.md',
        'local-model.example.json': EXECUTION_PUBLICATION / 'local-model.example.json',
    }
    legacy = {name: pinned(EXECUTOR_BASELINE, source.relative_to(MAIN).as_posix()) for name, source in sources.items()}
    released = package(destination / LEGACY_EXECUTOR_ZIP, legacy, 'frontier-harness-executor', EXECUTOR_BASELINE,
                       'Permission-bounded local HARNESS missions, development checks and source-bound output.')
    if released['sha256'] != LEGACY_EXECUTOR_SHA256:
        raise ValueError('The published HARNESS executor 1.0.0 changed')
    sources['START.md'] = EVIDENCE_PUBLICATION / 'README.md'
    sources.update({name: harness / name for name in (
        'bridge/intelligence_profiles.py', 'bridge/mission_evidence.py', 'requirements-chatgpt.txt',
        'docs/CHATGPT-PLAN.md', 'docs/MODEL-CONNECTIONS.md', 'scripts/probe_codex_sandbox.py',
        'Launch-FRONTIER.sh', 'Launch-FRONTIER.command', 'Launch-FRONTIER.cmd',
    )})
    previous = {name: pinned(PREVIOUS_EXECUTOR_BASELINE, source.relative_to(MAIN).as_posix())
                for name, source in sources.items()}
    released = package(destination / PREVIOUS_EXECUTOR_ZIP, previous, 'frontier-harness-executor', PREVIOUS_EXECUTOR_BASELINE,
                       'Permission-bounded local HARNESS missions with verified model selection and evidence-bound claims.',
                       version='1.1.0')
    if released['sha256'] != PREVIOUS_EXECUTOR_SHA256:
        raise ValueError('The published HARNESS executor 1.1.0 changed')
    sources['START.md'] = OUTCOME_PUBLICATION / 'README.md'
    sources.update({name: harness / name for name in (
        'bridge/mission_schema_context.py', 'bridge/mission_outcomes.py', 'bridge/mission_sources.py',
    )})
    outcome = {name: pinned(OUTCOME_EXECUTOR_BASELINE, source.relative_to(MAIN).as_posix())
               for name, source in sources.items()}
    released = package(destination / OUTCOME_EXECUTOR_ZIP, outcome, 'frontier-harness-executor',
                       OUTCOME_EXECUTOR_BASELINE,
                       'Local HARNESS missions with approved constructor schemas, exact arithmetic and evidence-derived outcomes.',
                       version='1.2.0')
    if released['sha256'] != OUTCOME_EXECUTOR_SHA256:
        raise ValueError('The published HARNESS executor 1.2.0 changed')
    sources['START.md'] = INTELLIGENCE_PUBLICATION / 'README.md'
    sources.update({name: harness / name for name in (
        'bridge/native_intelligence.py', 'bridge/paired_missions.py', 'app/native-intelligence.js',
    )})
    versions = ((INTELLIGENCE_EXECUTOR_ZIP, INTELLIGENCE_EXECUTOR_BASELINE, INTELLIGENCE_EXECUTOR_SHA256),
                (ORIGINAL_INTELLIGENCE_EXECUTOR_ZIP, ORIGINAL_INTELLIGENCE_EXECUTOR_BASELINE,
                 ORIGINAL_INTELLIGENCE_EXECUTOR_SHA256))
    for filename, pin, expected in versions:
        intelligence = {name: pinned(pin, source.relative_to(MAIN).as_posix()) for name, source in sources.items()}
        released = package(destination / filename, intelligence, 'frontier-harness-executor', pin,
                           'Private HARNESS missions with local intelligence, reviewed handoff and native mission-scoped provider authorization.',
                           version='1.3.0')
        if released['sha256'] != expected:
            raise ValueError(f'The published archive {filename} changed')
    del sources['START.md']
    sources.update({name: harness / name for name in ('app/frontier-pairing.js', 'bridge/mission_documents.py')})
    names = ['runtime/' + name for name in sources] + ['START-HERE.html']
    bundle_sources = {name: executor_source_path(name) for name in names}
    files = {name: (MAIN / source).read_bytes() for name, source in bundle_sources.items()}
    # An Atlas or research update with the same companion files retains the archive's source and bytes.
    payload_revision = executor_payload_revision(revision, bundle_sources.values())
    return package(destination / EXECUTOR_ZIP, files, 'frontier-harness-executor', payload_revision,
                   'Private HARNESS missions with companion approval, local intelligence and mission-scoped provider authorization.',
                   version='1.4.0')


def build_public_missions(destination, revision):
    directory = PUBLIC_MISSIONS / 'game-theory'
    archive = (directory / GAME_THEORY_ZIP).read_bytes()
    if digest(archive) != GAME_THEORY_SHA256:
        raise ValueError('The independently qualified Game Theory archive changed')
    with ZipFile(BytesIO(archive)) as bundle:
        receipt_bytes = bundle.read('game-theory/MISSION-RECEIPT.json')
        receipt = json.loads(receipt_bytes)
        report = directory.relative_to(MAIN) / 'REPORT.md'
        if (receipt_bytes != (directory / 'MISSION-RECEIPT.json').read_bytes()
                or bundle.read('game-theory/REPORT.md') != (MAIN / report).read_bytes()):
            raise ValueError('The public mission report differs from the portable receipt')
    (destination / GAME_THEORY_ZIP).write_bytes(archive)
    public = [{
        'ambition': receipt['original_ambition'], 'download': GAME_THEORY_ZIP,
        'report': f'{MONTREAL}/blob/{revision}/{report.as_posix()}',
        'capability': {
            'id': receipt['id'], 'en': receipt['card']['en']['title'], 'fr': receipt['card']['fr']['title'],
            'scopeEn': 'Zero-sum strategic allocation with declared hidden payoff scenarios. ' + receipt['scope'],
            'scopeFr': ('Allocation stratégique à somme nulle. Budgets entiers finis et déclarés, axes communs, '
                        'poids entiers non négatifs et additifs, '
                        'allocations simultanées privées et scénarios de gains cachés.'),
        },
        **{lang: ' '.join(receipt['card'][lang][field] for field in ('summary', 'verification'))
           for lang in ('en', 'fr')},
    }]
    observation = EXECUTION_PUBLICATION / 'game'
    observation_zip = destination / OBSERVATION_ZIP
    subprocess.run((sys.executable, '-S', str(observation / 'package_game.py'), str(observation_zip)),
                   check=True, capture_output=True)
    if digest(observation_zip.read_bytes()) != OBSERVATION_SHA256:
        raise ValueError('The independently qualified observation-game archive changed')
    capability = json.loads((observation / 'CAPABILITY.json').read_bytes())
    public.append({
        'ambition': receipt['original_ambition'], 'download': OBSERVATION_ZIP,
        'report': f'{MONTREAL}/blob/{revision}/{(observation / "REPORT.md").relative_to(MAIN).as_posix()}',
        'en': 'New solver for costly noisy observations and contingent allocations. Eleven independently authored games passed exact checks.',
        'fr': 'Nouveau solveur pour les observations bruitées à coût explicite et les allocations conditionnelles. Les onze jeux indépendants ont réussi les vérifications exactes.',
        'capability': {'id': capability['id'], 'en': 'Costly observation solver', 'fr': 'Solveur d’observations à coût explicite',
                       'scopeEn': capability['purpose']['en'], 'scopeFr': capability['purpose']['fr']},
    })
    build_mission_executor(destination, revision)
    return escape(stable(public).decode())


def render_cascade(fr):
    source = activation_archive_files(CASCADE_EVIDENCE, CASCADE_STUDIES.values())
    summary = json.loads(source['RESULTS.json'])['summary']
    tess = summary['tess']
    held = int(tess['held'])
    total = held + int(tess['development'])
    products = int(tess['products'])
    primary = int(tess['primary_agrees'])
    ordinary = int(tess['ordinary_agrees'])
    confirmed = int(tess['held_confirmed'])
    fresh = json.loads(source['FRESH-DOMAIN.json'])['observed']
    noaa = f'{int(fresh["matches_published"])}/{int(fresh["seasons_compared"])}'
    composition = summary['composition']
    jobs = int(composition['jobs'])
    completed_ordinary = f'{int(composition["completed-ordinary"])}/{jobs}'
    completed_typed = f'{int(composition["completed-typed"])}/{jobs}'
    advantage = int(composition['typed']) >= max(int(composition['ordinary']), int(composition['conventional'])) + 2
    if fr:
        timing = (f'Parmi les {total} événements historiques issus de {products} fichiers TESS, {held} ont servi à la confirmation. '
                  f'La méthode construite avec Codex a respecté le seuil d’écart au catalogue dans {primary}/{held} cas, '
                  f'et la méthode indépendante dans {ordinary}/{held} cas. '
                  f'Le contrôle conjoint des mesures et de leur provenance a retenu {confirmed}/{held} cas.')
        fresh_result = f'Le rejeu historique NOAA a reproduit {noaa} classifications saisonnières publiées.'
        comparison = 'Les outils à contrats typés sont restés sous le seuil d’avantage fixé par le protocole.'
        completion = ('Après l’achèvement déterministe des plans choisis par le modèle, les approches ordinaire et '
                      f'typée ont réussi {completed_ordinary} et {completed_typed} tâches, respectivement.')
        label, method, accepted = 'Comparer les cinq approches', 'Approche', 'Tâches acceptées'
        methods = ('Réponse directe', 'Outils et descriptions', 'Outils et contrats typés',
                   'Intégration déterministe', 'Contrats typés avec capacités retirées')
    else:
        timing = (f'The confirmation set contains {held} of {total} historical events across {products} TESS files. '
                  f'The Codex-built and independent methods met the catalogue timing criterion in '
                  f'{primary}/{held} and {ordinary}/{held} held cases, respectively. '
                  f'The joint timing and source check accepted {confirmed}/{held} cases.')
        fresh_result = f'The historical NOAA replay reproduced {noaa} published seasonal labels.'
        comparison = 'The typed tools fell short of the registered advantage threshold.'
        completion = ('After deterministic completion of the model-selected plans, the ordinary and typed approaches '
                      f'passed {completed_ordinary} and {completed_typed} jobs, respectively.')
        label, method, accepted = 'Compare the five approaches', 'Approach', 'Accepted jobs'
        methods = ('Direct answer', 'Tools with descriptions', 'Tools with typed contracts',
                   'Deterministic integration', 'Typed contracts with capabilities withdrawn')
    rows = ''.join(f'<tr><th scope="row">{title}</th><td>{int(composition[key])} / {jobs}</td></tr>'
                   for key, title in zip(('direct', 'ordinary', 'typed', 'conventional', 'withdrawn'), methods))
    comparison_html = '' if advantage else f'<p>{comparison}</p>'
    return (f'<p>{timing}</p><p>{fresh_result}</p>{comparison_html}<p>{completion}</p><details><summary>{label}</summary>'
            f'<div class="foundry-pilot-table" role="region" tabindex="0" aria-label="{accepted}">'
            f'<table><thead><tr><th scope="col">{method}</th><th scope="col">{accepted}</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></details>')


def render_factory(fr):
    path = FACTORY_EVIDENCE.relative_to(MAIN) / 'FACTORY.json'
    summary = json.loads(pinned(FACTORY_PIN, path.as_posix()))['summary']
    industry, hurricane, transit = (summary[key] for key in ('industry', 'hurricane', 'transit'))

    def witnessed(case, label, source_label):
        row = industry[case]
        stamp = escape(row['first_verified_by'])
        link = escape(row['source_url'])
        statement = (f'<p data-factory-claim="{case}" data-verdict="{escape(row["verdict"])}">'
                     f'<strong>{label}</strong> <time datetime="{stamp}">{stamp[:10]}</time>.</p>')
        return statement, f'<p class="mv-links"><a href="{link}">{source_label}</a></p>'

    def metric(name, value):
        return f'<strong data-factory-field="{name}">{escape(str(value))}</strong>'

    cases = metric('hurricane.cases', hurricane['cases'])
    shared = metric('hurricane.shared_origin', hurricane['shared_origin'])
    agreement = metric('hurricane.physical_agreement', hurricane['physical_agreement'])
    products = metric('transit.blind_products', transit['blind_products'])
    timings = metric('transit.detected_timings', transit['detected_timings'])
    matches = metric('transit.physical_matches', transit['physical_matches'])
    fresh = metric('transit.fresh_events', transit['fresh_events'])
    offset = str(transit['april_b_offset_days'])
    offset = metric('transit.april_b_offset_days', offset.replace('.', ',') if fr else offset)
    machine_verdict = escape(industry['bambu_machine']['verdict'])
    forecast_verdict = escape(transit['forecast_verdict'])
    if fr:
        prusa, prusa_source = witnessed('prusa_offer', 'Offre aux États-Unis attestée au', 'Voir la fiche Prusa archivée')
        prusa_scope = ('La fiche du fabricant couvre la mise à niveau à 400 °C pour la CORE One L. '
                       'La date du lancement, la disponibilité au Canada et la livraison restent à établir.')
        bambu, bambu_source = witnessed('bambu_software', 'Prise en charge logicielle attestée au',
                                       'Voir la fiche de version Bambu (JSON)')
        bambu_scope = 'La version v02.09.02.62 documente l’usage de buses mixtes avec FTS pour la H2D.'
        machine = ('<strong>Abstention sur le fonctionnement de la machine.</strong> Le fonctionnement réel de la H2D '
                   'et la prise en charge de la H2C ou de la X2D exigent des preuves distinctes.')
        hurricane_title = 'Provenance des données sur les ouragans'
        hurricane_result = (f'{shared} cas sur {cases} partagent une source en amont. '
                            f'{agreement} cas satisfont au critère de concordance physique entre sources indépendantes.')
        transit_title = 'Attribution des transits de TOI-216'
        transit_result = (f'La recherche a extrait {timings} instants de transit de {products} fichiers TESS. '
                          f'Les {fresh} comparaisons ont utilisé des références publiées. Une analyse distincte '
                          f'de mesures indépendantes au sol a trouvé {matches} concordance avec une couverture '
                          f'complète du transit. Le relevé historique d’avril se situait à {offset} jours du '
                          'candidat b ajusté le plus proche dans ce secteur. L’ajustement conjoint du secteur 64 '
                          'de TESS place le transit plus profond de c près de la date du relevé.')
        forecast = '<strong>Abstention sur les nouvelles prévisions.</strong> Planifier une observation exige une validation distincte.'
    else:
        prusa, prusa_source = witnessed('prusa_offer', 'U.S. offer documented by', 'Open the archived Prusa listing')
        prusa_scope = ('The manufacturer listing covers the 400 °C upgrade for the CORE One L. '
                       'Launch date, Canadian availability and fulfillment remain open.')
        bambu, bambu_source = witnessed('bambu_software', 'Software support documented by',
                                       'Open the Bambu release record (JSON)')
        bambu_scope = 'Version v02.09.02.62 documents mixed-nozzle support with FTS for the H2D.'
        machine = ('<strong>Abstain on machine operation.</strong> Actual operation on the H2D and support for the '
                   'H2C or X2D require separate evidence.')
        hurricane_title = 'Hurricane source lineage'
        hurricane_result = (f'{shared} of {cases} cases share an upstream source. '
                            f'{agreement} cases meet the physical agreement criterion using independent sources.')
        transit_title = 'TOI-216 transit attribution'
        transit_result = (f'The search measured {timings} transit times from {products} TESS products. '
                          f'The {fresh} scored comparisons used published references. A separate analysis of '
                          f'independent ground observations found {matches} match with full transit coverage. '
                          f'The historical April record was {offset} days from the nearest fitted b candidate in that '
                          'sector. The joint fit for TESS Sector 64 places the deeper c transit near the date of the record.')
        forecast = '<strong>Abstain on new forecasts.</strong> Scheduling an observation requires separate validation.'
    return (
        '<div class="mv-grid factory-findings">'
        '<article class="mv-tool" aria-labelledby="factory-prusa-title">'
        '<h5 id="factory-prusa-title">Prusa HT Hotend · CORE One L</h5>'
        f'{prusa}<p>{prusa_scope}</p>{prusa_source}</article>'
        '<article class="mv-tool" aria-labelledby="factory-bambu-title">'
        '<h5 id="factory-bambu-title">Bambu Studio · H2D</h5>'
        f'{bambu}<p>{bambu_scope}</p>'
        f'<p data-factory-claim="bambu_machine" data-verdict="{machine_verdict}">{machine}</p>{bambu_source}</article>'
        '<article class="mv-tool" aria-labelledby="factory-hurricane-title">'
        f'<h5 id="factory-hurricane-title">{hurricane_title}</h5><p>{hurricane_result}</p></article>'
        '<article class="mv-tool" aria-labelledby="factory-transit-title">'
        f'<h5 id="factory-transit-title">{transit_title}</h5><p>{transit_result}</p>'
        f'<p data-factory-claim="forecast" data-verdict="{forecast_verdict}">{forecast}</p></article>'
        '</div>'
    )


def render_liberation(fr):
    result=json.loads((LIBERATION_EVIDENCE/'COVARIANCE.json').read_bytes())['study']
    label='Vérification des prévisions' if fr else 'Forecast verification'
    headers=('Méthode','Transits couverts','Largeur médiane (s)') if fr else ('Method','Transits covered','Median width (s)')
    titles={
        'released_marginals':'Éphéméride publiée' if fr else 'Released ephemeris',
        'weighted':'Moindres carrés pondérés' if fr else 'Weighted least squares',
        'huber':'Ajustement robuste' if fr else 'Robust fit',
        'adaptive_horizon':'Étalonnage par horizon' if fr else 'Horizon-specific calibration',
    }
    rows=[]
    for key,title in titles.items():
        measured=result['methods'][key]
        rows.append(f'<tr><th scope="row">{title}</th><td>{int(measured["hits"])} / {int(measured["targets"])}</td>'
                    f'<td>{round(measured["median_full_width_s"])}</td></tr>')
    return (f'<div class="foundry-pilot-table" role="region" tabindex="0" aria-label="{label}"><table><thead><tr>'+
            ''.join(f'<th scope="col">{name}</th>' for name in headers)+'</tr></thead><tbody>'+
            ''.join(rows)+'</tbody></table></div>')


def substrate_example():
    case = json.loads((SUBSTRATE_EVIDENCE/'CASE.json').read_bytes())
    q = case['ephemeris']
    scale = 10**12
    scaled = [Decimal(x) * scale for x in (case['anchor'], q['t0_day'], q['period_day'], q['t0_sigma_day'],
                                           q['period_sigma_day'], q['duration_hour'])]
    if any(value != int(value) for value in scaled):
        raise ValueError('Browser example precision')
    return {'scale': str(scale), 'values': [str(int(value)) for value in scaled], 'witness': case['witness']}


def render_substrate(fr):
    results = json.loads((SUBSTRATE_EVIDENCE/'RESULTS.json').read_bytes())
    total = results['scoped_reference']['all_source_row_horizons_agree']
    manual = results['operator_assisted']['confirmation']['accepted']
    if fr:
        grouped = f'{total:,}'.replace(',', '\u202f')
        return (f'<p>Deux calculs indépendants concordent sur {grouped} vérifications des sources. '
                f'L’artefact construit avec transfert manuel et la référence exacte réussissent chacun {manual}/28 cas de confirmation.</p>')
    return (f'<p>Two independent calculations agree on {total:,} source checks. '
            f'The manually transferred artifact and the exact reference each pass {manual}/28 held cases.</p>')


def render_amplification(fr):
    study=json.loads((AMPLIFICATION_EVIDENCE/'comparisons.json').read_bytes())
    headings=('Modèle','Accès direct','HARNESS','Avec instrument') if fr else ('Model','Direct','HARNESS','With instrument')
    rows=[]
    for model, title, arms in (
        ('qwen3-4b-instruct-2507-q4_k_m','Qwen3-4B · 4K',study['arms']),
        ('qwen3-8b-q4-k-m','Qwen3-8B · 4K',study['arms']),
        ('qwen3-4b-instruct-2507-q4_k_m','Qwen3-4B · 8K',study['revised_arms']),
    ):
        cells=[]
        for method in ('direct','harness','amplified'):
            arm=arms.get(model+'/'+method)
            cells.append(f'{int(arm["accepted"])}/{int(study["held_cases"])}' if arm is not None else '—')
        rows.append(f'<tr><th scope="row">{title}</th>'+''.join(f'<td>{value}</td>' for value in cells)+'</tr>')
    if any(study['same_model_amplification'].values()):
        scope='Le seuil de l’essai circonscrit a été atteint.' if fr else 'The bounded comparison met its registered threshold.'
    elif study['revised_arms'] and not any(arm.get('selected_instrument_used') for arm in study['revised_arms'].values()):
        scope=('L’instrument expérimental a échoué aux contrôles et n’a pas guidé la construction.' if fr else
               'The experimental instrument failed validation and did not guide construction.')
    else:
        scope='Aucun gain n’a atteint le seuil de l’essai.' if fr else 'No gain met the registered threshold.'
    accepted, total=(int(study['conventional'][key]) for key in ('accepted','cases'))
    context=(f'Référence exacte · {accepted}/{total} cas de confirmation.' if fr else
             f'Exact reference · {accepted}/{total} confirmation cases.')
    label='Résultats de confirmation' if fr else 'Confirmation results'
    return (f'<p>{scope} {context}</p><div class="foundry-pilot-table" tabindex="0" role="region" aria-label="{label}">'
            '<table><thead><tr>'+''.join(f'<th scope="col">{value}</th>' for value in headings)+
            '</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>')


def render_activation(fr):
    recorded=json.loads((ACTIVATION_EVIDENCE/'verification.json').read_bytes())['followup']
    results=recorded['primary']
    labels={
        'learning-replay':('Replay the fitted model','Reproduire l’évaluation du modèle'),
        'local-runner':('Restore an independent runtime','Rétablir un environnement indépendant'),
        'inventor-audit':('Challenge earlier invention evidence','Examiner les preuves d’invention'),
    }
    title='Objectif choisi et résultat sur les cas de confirmation' if fr else 'Selected objective and held-out result'
    binding=escape(labels[recorded['objective']][fr])
    match=f'{int(results["exact"])}/{int(results["cases"])}'
    message=(f'{binding} · {match} décisions au coût optimal.' if fr else
             f'{binding} · {match} decisions matched the exact minimum.')
    if fr:
        lessons=('Dépendances mal reconstituées lors d’un essai antérieur.',
                 'Des réponses ont dépassé les limites du modèle ou du langage.',
                 'La méthode de sélection a changé les exemples sans produire de gain qualifié.')
    else:
        lessons=('An earlier instrument failed to recover downstream dependencies.',
                 'Responses hit model and language limits.',
                 'Case selection changed the evidence without a qualified productive gain.')
    return f'<p><strong>{title}</strong><br>{message}</p><ul>'+''.join(f'<li>{x}</li>' for x in lessons)+'</ul>'


def render_inventor(fr):
    evidence = json.loads((INVENTOR_EVIDENCE / 'evidence.json').read_bytes())
    missions = {'editions':('Atlas edition selection','Sélection des éditions de l’Atlas'),
                'endpoint':('Endpoint capacity','Capacité des services d’inférence'),
                'impact':('Release dependencies','Dépendances de la publication')}
    arms = {'original':('Original inventor','Inventeur initial'), 'ordinary':('Ordinary reuse','Réemploi ordinaire'),
            'augmented':('Augmented inventor','Inventeur augmenté'), 'withdrawn':('Method withdrawn','Méthode retirée'),
            'conventional':('Conventional reference','Référence conventionnelle')}
    first = evidence.get('first_mission')
    introduction = (('Première mission choisie par le modèle' if fr else 'First mission chosen by the model') +
                    ' — ' + missions[first][fr] + '.') if first in missions else (
                    'Le modèle s’est abstenu de choisir une première mission.' if fr else 'The model abstained from selecting a first mission.')
    rows = []
    for name in (['first'] if 'first' in evidence['assessments'] else []) + sorted(k for k in evidence['assessments'] if k != 'first'):
        result = evidence['assessments'][name]['assessment']
        label = ('Première invention' if fr else 'First invention') if name == 'first' else arms[result['arm']][fr]
        decision = ('Concordance' if fr else 'Matched') if result['verdict'] == 'MATCHED' else ('Refusé' if fr else 'Rejected')
        rows.append(f'<tr><th scope="row">{escape(missions[result["mission"]][fr])}</th><td>{escape(label)}</td>'
                    f'<td>{int(result["matched"])}/{int(result["total"])}</td><td>{decision}</td></tr>')
    followups = (
        ('diagnostic-evidence.json','Observed-output follow-up','Essai avec écarts observés'),
        ('larger-evidence.json','Larger-model follow-up','Essai avec le modèle de 8 milliards'),
    )
    for filename, en, french in followups:
        result = json.loads((INVENTOR_EVIDENCE / filename).read_bytes())['assessments']['first']['assessment']
        label = french if fr else en
        decision = ('Concordance' if fr else 'Matched') if result['verdict'] == 'MATCHED' else ('Refusé' if fr else 'Rejected')
        rows.append(f'<tr><th scope="row">{escape(missions[result["mission"]][fr])}</th><td>{label}</td>'
                    f'<td>{int(result["matched"])}/{int(result["total"])}</td><td>{decision}</td></tr>')
    if not rows:
        return f'<p>{escape(introduction)}</p>'
    headings = ('Mission','Démarche','Cas','Résultat') if fr else ('Mission','Arm','Cases','Outcome')
    return f'<p>{escape(introduction)}</p><div class="foundry-pilot-table" tabindex="0" role="region" aria-label="{headings[-1]}">' \
           '<table><thead><tr>' + ''.join(f'<th scope="col">{label}</th>' for label in headings) + \
           '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


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
                 'upstream_sha256': SUBMISSION_HASH, 'source_revision': ENDPOINT_PIN, 'rows': len(sample['rows']),
                 'highest_tested_load': comparative['highest_tested_load']}
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

REVIEW_FIELDS = ('possibility', 'why', 'missing_move', 'alternative', 'next', 'uncertainty',
                 'protocol', 'rights', 'economics')


def review_digest(brief, tools):
    tool = tools.get(brief['tool'])
    scope = {key: brief[key] for key in ('source_version', 'atlas_state', 'evidence', 'verdict', 'tool')}
    scope['tool_release'] = [tool['version'], tool['sha256']] if tool else None
    scope['sources'] = sorted(ref['url'] for ref in brief['evidence_links'])
    scope.update({lang: {key: brief[lang][key] for key in REVIEW_FIELDS} for lang in CAPTIONS})
    return digest(stable(scope))


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
        facts = ''.join(f'<div><dt>{names[fr]}</dt><dd data-field="{key}">{escape(local[key])}</dd></div>'
                        for key, names in FIELDS.items())
        links = ''.join(f'<a data-decision-source href="{escape(ref["url"])}">{escape(ref[lang])}</a>'
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
            f'<p class="mv-source-date" data-review="{brief["review_sha256"]}" data-tool="{brief["tool"] or ""}">'
            f'{source} · <time datetime="{timestamp}">{timestamp[:10]}</time> · <code>{escape(brief["source_version"])}</code></p>'
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
        action = ('Compare a single benchmark scope and keep a reference-checked receipt.',
                  'Comparez une seule configuration de banc d’essai et conservez un reçu vérifié par comparaison.')[fr]
        checks = ('Seven public measurements and four exact comparisons against indexed SQLite, which remains the operating incumbent.',
                  'Sept mesures publiques et quatre comparaisons exactes avec SQLite indexé, qui demeure la référence opérationnelle.')[fr]
        reuse = ('Open an authorized batch with the same schema. Validate any new operating limits and evidence separately.',
                 'Ouvrez un lot autorisé de même format. Validez séparément toute nouvelle limite opérationnelle et ses preuves.')[fr]
        instructions = 'Extraire le ZIP, puis lancer ces deux comparaisons dans le dossier extrait.' if fr else 'Extract the ZIP and run both comparisons from the extracted folder.'
        command = 'node endpoint-cli.mjs sample.json\npython3 endpoint-sqlite.py sample.json'
        accepted = 'Même résultat pour les deux sorties. Charge maximale mesurée admissible de 140 sur l’exemple. Adoption opérationnelle en abstention.' if fr else 'Expect matching output for the sample, a highest qualifying measured load of 140 and operational ABSTAIN.'
    else:
        action = ('Recover a native GFS grid value for a historical weather study.',
                  'Retrouvez une valeur sur la grille native GFS pour une étude météorologique historique.')[fr]
        checks = ('Six held forecasts match independent ecCodes decoding. Use NCAR when the point service covers the required grid and product.',
                  'Six prévisions réservées concordent avec le décodage indépendant ecCodes. Préférez NCAR si le service ponctuel couvre le produit et la grille recherchés.')[fr]
        reuse = ('Keep the validated coordinates, forecast time and output for a reproducible analysis.',
                 'Conservez les coordonnées validées, l’heure de prévision et la valeur pour reproduire l’analyse.')[fr]
        instructions = 'Extraire le ZIP. Vérifier les six cas signés hors ligne, puis interroger et vérifier le point historique près de Québec.' if fr else 'Extract the ZIP. Audit the six signed cases offline, then retrieve and check the historical point near Québec.'
        command = ('python3 archive-verify.py\npython3 archive-query.py --day 2024-01-18 --cycle 00 --latitude 46.75 '
                   '--longitude -71.25 > point.json\npython3 archive-verify.py point.json')
        accepted = 'Le vérificateur doit retrouver environ 257,85171875 K. Il s’agit d’une prévision historique. Préférer le service ponctuel NCAR si son produit et sa grille conviennent.' if fr else 'The verifier should match about 257.85171875 K for this historical forecast. Prefer NCAR when its product and grid fit your use.'
    how = 'Instructions et résultat attendu' if fr else 'Instructions and expected result'
    return (
        f'<article class="mv-tool" id="tool-{key}"><p class="packet-meta">v{manifest["version"]}</p>'
        f'<h4>{title}</h4><p class="mf-tool-purpose">{action}</p><p>{detail}</p><p>{environment}</p>'
        f'<p class="mv-links">{open_tool}<a href="{manifest["download"]}" download>{download}</a>'
        f'<a href="{manifest["source"]}">{source}</a></p>'
        f'<details class="mf-instructions"><summary>{how}</summary><p>{instructions}</p>'
        f'<pre><code>{escape(command)}</code></pre><p>{accepted}</p></details>'
        f'<details><summary>{"Validation, réutilisation et coûts" if fr else "Verification, reuse and costs"}</summary>'
        f'<p>{checks}</p><p>{reuse}</p>'
        f'<p>{"Coût complet non mesuré. Les droits sur les sources amont restent applicables." if fr else "Complete cost unmeasured. Upstream source rights still apply."}</p>'
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
    def facts(fields):
        return ''.join(f'<div><dt>{FIELDS[name][fr]}</dt><dd>{escape(local[name])}</dd></div>' for name in fields)
    label = 'Dossier à la une' if fr else 'Featured intelligence briefing'
    brief = 'Ouvrir le dossier décisionnel' if fr else 'Open the decision brief'
    runs = 'Vérification de publication' if fr else 'Publication verification'
    return (
        f'<article class="mf-feature" id="mf-edition" data-edition-run="{slot["member_run"]}">'
        f'<p class="packet-meta">{label} · {kind}</p><h4>{title}</h4><p>{escape(local["change"])}</p>'
        f'<p class="mf-meta">{timestamp_html(row["updated_at"])} · {escape(row["source_version"])}</p>'
        f'<dl>{facts(("why", "next"))}</dl>'
        f'<details><summary>{"Examiner les preuves et leurs limites" if fr else "Inspect the evidence and its limits"}</summary>'
        f'<dl>{facts(("possibility", "alternative", "uncertainty"))}</dl></details>'
        f'<p class="mv-links"><a class="mf-action" data-mv-open href="#decision-{row["id"]}">{brief}</a>'
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
        '<!-- ' + FOUNDRY_INPUT + ' -->': escape(stable(foundry_example(fr)).decode()),
        '<!-- INVENTOR_PILOT_RESULTS -->': render_inventor(fr),
        '<!-- LEARNING_RESULTS -->': render_learning(fr),
        '<!-- ACTIVATION_MAP -->': render_activation(fr),
        '<!-- AMPLIFICATION_RESULTS -->': render_amplification(fr),
        '<!-- AMPLIFICATION_EXAMPLE -->': escape(stable(json.loads((AMPLIFICATION_EVIDENCE/'trial.json').read_bytes())).decode()),
        '<!-- SUBSTRATE_EXAMPLE -->': escape(stable(substrate_example()).decode()),
        '<!-- SUBSTRATE_RESULTS -->': render_substrate(fr),
        '<!-- LIBERATION_RESULTS -->': render_liberation(fr),
        '<!-- CASCADE_RESULTS -->': render_cascade(fr),
        '<!-- FACTORY_RESULTS -->': render_factory(fr),
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
    for brief in briefs:
        brief['review_sha256'] = review_digest(brief, tools)
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
