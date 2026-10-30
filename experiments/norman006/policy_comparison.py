import copy
import hashlib
import json
from pathlib import Path
import time
import numpy as np

from mechanisms import policy006
from . import inheritance, model


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def stopping_configuration():
    return {'language': model.LANGUAGE, 'expressions': [], 'ridge': 1, 'symmetric': False, 'constraints': []}


def catalog(configurations):
    result, seen = [], set()
    for configuration in [stopping_configuration()] + configurations:
        model.validate_configuration(configuration)
        identity = digest(configuration)
        if identity not in seen:
            seen.add(identity)
            result.append({'id': 'representation-' + identity[:24], 'configuration': configuration, 'sha256': identity})
    if len(result) > 128:
        raise ValueError('CATALOG_BOUND')
    return result


def signature(configuration):
    def tokens(value):
        if type(value) is list:
            return [str(value[0])] + tokens(value[1]) + tokens(value[2])
        return [str(value)]
    result = set()
    for expression in configuration['expressions']:
        result.update(tokens(expression))
    result.add('symmetric:%s' % configuration['symmetric'])
    result.add('ridge:%s' % configuration['ridge'])
    return result


def distance(first, second):
    a, b = signature(first), signature(second)
    return 1 - len(a & b) / max(1, len(a | b))


def history_rows(search, repair_report=None):
    rows = [{'configuration': row['configuration'], 'median_pair_rmse': row['median_pair_rmse'],
             'source_sha256': digest(row), 'scope': 'Exposed predecessor development calibration, not target truth'}
            for row in search['records'] if row['status'] == 'executed']
    if repair_report is not None:
        metric = repair_report['same_development_split_metrics']['repaired']
        rows.append({'configuration': repair_report['construction']['configuration'], 'median_pair_rmse': metric['median_pair_rmse'],
                     'source_sha256': digest(repair_report), 'scope': 'Exposed predecessor repaired development calibration'})
    if not rows:
        raise ValueError('ACTUAL_DEVELOPMENT_HISTORY_REQUIRED')
    return rows


class Broker:
    def __init__(self, configurations, history, fits, output, data=None, source_sha=None):
        self.catalog = catalog(configurations)
        self.history, self.fits, self.output, self.data, self.source_sha = history, fits, Path(output), data, source_sha
        self.output.mkdir(parents=True, exist_ok=False)
        self.executed, self.rows = [], []
        self.reference = next((row['median_pair_rmse'] for row in history if not row['configuration']['expressions']), max(row['median_pair_rmse'] for row in history))
        if data is not None:
            self.training = model.subset(data, data['fit_indices'])
            self.validation = model.subset(data, data['calibration_indices'], False)
            self.truth = data['AB'][data['calibration_indices']]

    def observe(self):
        actions = []
        for item in self.catalog:
            if item['id'] in self.executed:
                continue
            configuration = item['configuration']
            nearest = min(self.history, key=lambda row: (distance(configuration, row['configuration']), row['source_sha256']))
            mismatch = distance(configuration, nearest['configuration'])
            estimated_gain = max(0., min(1., (self.reference - nearest['median_pair_rmse']) / max(self.reference, 1e-12)))
            redundancy = max((1 - distance(configuration, row['configuration']) for row in self.rows), default=0)
            complexity = sum(len(str(value)) for value in configuration['expressions'])
            features = {'gain': estimated_gain * (1 - mismatch), 'cost': 1 / self.fits,
                        'rarity': mismatch, 'redundancy': redundancy,
                        'breadth': min(1., complexity / 300), 'remaining': (self.fits - len(self.executed)) / self.fits}
            actions.append({'id': item['id'], 'kind': 'represent', 'features': features,
                            'feature_provenance': {key: 'development_prediction' if key == 'gain' else 'observed' for key in policy006.FEATURES},
                            'source_identities': [nearest['source_sha256'], item['sha256']], 'cost_units': 1})
        evidence = {'catalog': [item['sha256'] for item in self.catalog], 'executed': self.executed,
                    'history': [row['source_sha256'] for row in self.history], 'target_outcomes_used_in_features': False}
        return {'actions': actions, 'evidence_sha256': digest(evidence)}

    def execute(self, identity):
        item = next(value for value in self.catalog if value['id'] == identity)
        if identity in self.executed or len(self.executed) >= self.fits:
            raise ValueError('DUPLICATE_OR_EXCESS_REPRESENTATION_EXPERIMENT')
        self.executed.append(identity)
        if self.data is None:
            exact = [row for row in self.history if digest(row['configuration']) == item['sha256']]
            if not exact:
                raise ValueError('REPLAY_REQUIRES_EXACT_EXPOSED_CONFIGURATION')
            row = {'configuration': item['configuration'], 'median_pair_rmse': exact[0]['median_pair_rmse'],
                   'functional_contract_passed': None, 'execution': 'Read-only replay of actual exposed predecessor receipt; no new fit is claimed'}
            artifact_sha = exact[0]['source_sha256']
        else:
            artifact = model.fit(self.training, item['configuration'], self.source_sha)
            prediction = model.predict(artifact, self.validation)['prediction']
            swapped = dict(self.validation)
            swapped['A'], swapped['B'] = self.validation['B'], self.validation['A']
            swapped_prediction = model.predict(artifact, swapped)['prediction']
            swap_error = float(np.max(np.abs(prediction - swapped_prediction)))
            errors = np.sqrt(np.mean((prediction - self.truth) ** 2, axis=1))
            row = {'configuration': item['configuration'], 'median_pair_rmse': float(np.median(errors)),
                   'pooled_rmse': float(np.sqrt(np.mean((prediction - self.truth) ** 2))), 'pair_rmse': errors.tolist(),
                   'max_swap_difference': swap_error, 'functional_contract_passed': swap_error <= 1e-10,
                   'execution': 'Actual fresh-target development fit/predict; protected target outcomes never supplied'}
            artifact_sha = artifact['artifact_sha256']
            write(self.output / ('artifact-%02d.json' % (len(self.executed) - 1)), artifact)
        row.update({'id': identity, 'configuration_sha256': item['sha256'], 'artifact_sha256': artifact_sha})
        self.rows.append(row)
        write(self.output / ('experiment-%02d.json' % (len(self.executed) - 1)), row)
        return {'action_id': identity, 'kind': 'represent', 'cost_units': 1,
                'artifact_sha256': artifact_sha, 'observation_sha256': digest(row)}


def budget(fits):
    if type(fits) is not int or not 1 <= fits <= 6:
        raise ValueError('MATCHED_FIT_BUDGET')
    return {'steps': fits, 'cost_units': fits, 'kinds': {kind: fits if kind == 'represent' else 0 for kind in policy006.KINDS}}


def nominate_policy(history, root, output, seed, fits):
    proposals = policy006.generate(seed, 8)
    policy_source = Path(root) / 'mechanisms/policy006.py'
    source_sha = hashlib.sha256(policy_source.read_bytes()).hexdigest()
    rows = []
    for index, candidate in enumerate(proposals['programs']):
        broker = Broker([row['configuration'] for row in history], history, fits, Path(output) / ('policy-%02d' % index))
        execution = policy006.run(candidate, broker, budget(fits), policy_source, source_sha)
        best = min((row['median_pair_rmse'] for row in broker.rows), default=float('inf'))
        rows.append({'index': index, 'policy': candidate, 'execution': execution, 'best_replayed_median_pair_rmse': best if np.isfinite(best) else None})
    eligible = [row for row in rows if row['best_replayed_median_pair_rmse'] is not None]
    if not eligible:
        raise ValueError('NO_REPLAY_NOMINEE')
    winner = min(eligible, key=lambda row: (row['best_replayed_median_pair_rmse'], row['index']))
    return {'selected_policy': winner['policy'], 'selected_index': winner['index'], 'generated': proposals, 'records': rows,
            'scope': 'Policy nomination replays exposed predecessor development receipts only; this may overfit that history and is not fresh discovery-policy advantage'}


def run(data, store, target_conditions, equivalent_record, original_search, repair_report, output, root, seed=41, fits=4):
    started = time.monotonic()
    output, root = Path(output), Path(root)
    output.mkdir(parents=True, exist_ok=False)
    history = history_rows(original_search, repair_report)
    nominated = nominate_policy(history, root, output / 'policy-nomination', seed, fits)
    write(output / 'POLICY_NOMINATION.json', nominated)
    retrieved = inheritance.retrieve_and_generate(store, target_conditions, root, seed, count=8)
    if len(retrieved['candidates']) != 1:
        raise ValueError('EXACTLY_ONE_APPLICABLE_ACQUIRED_GENERATOR_REQUIRED')
    acquired_catalog = retrieved['candidates'][0]['generated']['configurations']
    ordinary_result = inheritance.ordinary_generate([copy.deepcopy(equivalent_record)], root, seed, count=8)
    ordinary_catalog = ordinary_result[0]['generated']['configurations']
    if digest(ordinary_catalog) != digest(acquired_catalog):
        raise ValueError('ORDINARY_CONTENT_OR_GENERATION_MISMATCH')
    old_catalog = [row['configuration'] for row in original_search['records'] if row['status'] == 'executed']
    removed = inheritance.generate_related(equivalent_record, root, seed, count=8, remove_operator=True)['configurations']
    fixed = {'language': policy006.LANGUAGE, 'priority': ['div', 'gain', 'cost'], 'stop_below': 0}
    selected = nominated['selected_policy']
    plans = [('old_policy_old_tools', fixed, old_catalog), ('old_policy_new_tools', fixed, acquired_catalog),
             ('new_policy_old_tools', selected, old_catalog), ('new_policy_new_tools', selected, acquired_catalog),
             ('ordinary_equivalent', selected, ordinary_catalog), ('operator_removed', selected, removed),
             ('frozen_initial', fixed, old_catalog), ('reset_rebuild', fixed, old_catalog),
             ('history_best_conventional', {'language': policy006.LANGUAGE, 'priority': 'gain', 'stop_below': 0}, acquired_catalog)]
    policy_source = root / 'mechanisms/policy006.py'
    policy_sha = hashlib.sha256(policy_source.read_bytes()).hexdigest()
    model_sha = hashlib.sha256((root / 'experiments/norman006/model.py').read_bytes()).hexdigest()
    arms = {}
    for name, candidate_policy, configurations in plans:
        broker = Broker(configurations, history, fits, output / name, data, model_sha)
        execution = policy006.run(candidate_policy, broker, budget(fits), policy_source, policy_sha)
        accepted = [row for row in broker.rows if row['functional_contract_passed']]
        best = min(accepted, key=lambda row: (row['median_pair_rmse'], row['pooled_rmse'], row['id'])) if accepted else None
        arms[name] = {'policy': candidate_policy, 'execution': execution, 'experiments': broker.rows,
                      'best_functionally_admitted': best, 'fit_allowance': fits,
                      'ordinary_and_structured_content_equal': name in ('ordinary_equivalent', 'new_policy_new_tools')}
        write(output / (name + '.json'), arms[name])
    report = {'schema': 'agi-alpha-cycle006-actual-policy-capability-cross/v1', 'arms': arms,
              'retrieval': retrieved, 'ordinary_generation': ordinary_result,
              'input_pair_ids': [str(x) for x in data['pairs']], 'input_gene_axis_sha256': digest([str(x) for x in data['genes']]),
              'history_sha256': digest(history), 'policy_nomination_sha256': digest(nominated),
              'resources': {'wall_seconds': time.monotonic() - started, 'full_lifecycle_cost': None},
              'cost_boundary': 'All policy proposals/replays and every actual failed/successful fit remain recorded. The enclosing prospective run receipt meters aggregate process resources; acquisition/history/development and inference costs are not erased or treated as zero.',
              'reset_scope': 'Frozen/reset arms restore the initial constructor catalog and refit target data; all retain the same ordinary exposed history content. This is a starting-capability ablation, not a full acquisition-lifecycle reset or an independent replication of the four-cell cross.',
              'strongest_control_boundary': 'History-best is an action-order control, not the strongest scientific method. The full-information commutative multioutput ridge and other frozen domain controls must be compared by the external domain verifier.',
              'verdict': 'Executed finite construction-policy/toolbox engineering comparison; no learned-policy, protected scientific, lifecycle or commercial superiority follows.'}
    write(output / 'REPORT.json', report)
    return report
