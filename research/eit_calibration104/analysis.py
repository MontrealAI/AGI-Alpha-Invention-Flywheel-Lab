"""Frozen EIT104 retrospective leave-*level*-out physical decision calibration.

No physical acquisition, external commerce, financing or trained frontier model.
The seven physical-level groups, policies and acceptance rule were frozen in
PROTOCOL.md at 7f6c0375abb06c0251ec6068ffd7245c45a543b8 before this code.
"""
from collections import Counter, defaultdict
from hashlib import sha256
import json
import re

SOURCE_PROJECTION_SHA256 = '3717c65a9f1c1a8fd2171ac83307aadd8bc60e84f7f2a8391062d1f181f8d22c'
SOURCE_EIT103_HEAD = '10b25ce984c22aff861da3d295f5b5d3b8d7299c'
SOURCE_EIT102_ZIP_SHA256 = '8efee93d9e4b142907bea786701c6b78047b68a51e248b498c3df9e9c01e37b2'
SOURCE_EIT102_RESULT_SHA256 = '7b8f0fcc58e0e1881d6bdc88d37b4c0a92216b25aa6de70440e05e061e99857c'
FROZEN_PROTOCOL_HEAD = '7f6c0375abb06c0251ec6068ffd7245c45a543b8'
ROWS = """level1/data1.mat 04 05 05 05
level1/data2.mat c0 c0 c0 c0
level1/data3.mat 01 01 01 01
level2/data1.mat 50 50 50 50
level2/data2.mat 08 08 08 08
level2/data3.mat 90 f0 f0 f0
level3/data1.mat 07 37 37 37
level3/data2.mat 0f 0f 0f 0f
level3/data3.mat 40 c0 d0 c0
level4/data1.mat 42 42 52 52
level4/data2.mat 1c 1c 1c 1c
level4/data3.mat 5a fa fa fa
level5/data1.mat ce ec ec ec
level5/data2.mat 04 25 25 25
level5/data3.mat 20 f0 f0 f0
level6/data1.mat f0 f0 f0 f0
level6/data2.mat 2d 2d 2d 2d
level6/data3.mat 5a fa fa fa
level7/data1.mat 87 f7 d7 f7
level7/data2.mat 2f 0f 0f 0f
level7/data3.mat 09 09 09 09"""
LEVELS = tuple(f'level{i}' for i in range(1, 8))
POLICIES = ('direct40', 'full76', 'pooled', 'position', 'nested', 'absent', 'impute40', 'majority')


def unpack(value):
    if type(value) is not str or not re.fullmatch(r'[0-9a-f]{2}', value):
        raise ValueError('SOURCE_EXACT_BINARY_BYTE_REQUIRED')
    n = int(value, 16)
    return tuple((n >> j) & 1 for j in range(8))


def read_rows(source=ROWS, *, pinned=True):
    if pinned and sha256(source.encode()).hexdigest() != SOURCE_PROJECTION_SHA256:
        raise ValueError('SOURCE_PROJECTION_CHANGED')
    lines = source.splitlines()
    if len(lines) != 21:
        raise ValueError('SOURCE_EXACT_21_REQUIRED')
    rows, seen = [], set()
    for line in lines:
        cols = line.split()
        if len(cols) != 5 or not re.fullmatch(r'level[1-7]/data[1-3]\.mat', cols[0]):
            raise ValueError('SOURCE_EXACT_SPECIMEN_OR_COLUMNS_REQUIRED')
        identity = cols[0]
        if identity in seen:
            raise ValueError('SOURCE_DUPLICATE_SPECIMEN')
        seen.add(identity)
        truth, full, direct, impute = map(unpack, cols[1:])
        rows.append({'id': identity, 'level': identity.split('/')[0],
                     'truth': truth, 'full76': full,
                     'direct40': direct, 'impute40': impute})
    expected = {f'{level}/data{i}.mat' for level in LEVELS for i in range(1, 4)}
    if seen != expected:
        raise ValueError('SOURCE_MISSING_OR_FOREIGN_SPECIMEN')
    return tuple(rows)


def validate_rows(rows):
    if len(rows) != 21:
        raise ValueError('EXACT_21_PHYSICAL_SPECIMENS')
    seen = set()
    for row in rows:
        if row['id'] in seen or row.get('level') != row['id'].split('/')[0]:
            raise ValueError('DUPLICATE_OR_MALFORMED_GROUP')
        seen.add(row['id'])
        for name in ('truth', 'full76', 'direct40', 'impute40'):
            bits = row.get(name)
            if type(bits) is not tuple or len(bits) != 8 or any(type(v) is not int or v not in (0, 1) for v in bits):
                raise ValueError('EXACT_EIGHT_BINARY_DECISIONS')
    expected = {f'{level}/data{i}.mat' for level in LEVELS for i in range(1, 4)}
    if seen != expected:
        raise ValueError('EXACT_SOURCE_GROUP_MEMBERS_REQUIRED')


def calibrator(training, policy):
    if policy not in ('pooled', 'position'):
        raise ValueError('UNREGISTERED_CALIBRATOR')
    if not training or len({r['level'] for r in training}) < 1:
        raise ValueError('NONEMPTY_TRAINING_REQUIRED')
    counts = Counter()
    for row in training:
        for j, predicted in enumerate(row['direct40']):
            group = j // 4 if policy == 'pooled' else j
            counts[(group, predicted, row['truth'][j])] += 1
    def predict(row):
        bits = []
        for j, predicted in enumerate(row['direct40']):
            group = j // 4 if policy == 'pooled' else j
            positive = counts[(group, predicted, 1)]
            total = positive + counts[(group, predicted, 0)]
            comparison = 2 * (positive + 1) - (total + 2)
            bits.append(1 if comparison > 0 else 0 if comparison < 0 else predicted)
        return tuple(bits)
    return predict


def score(pairs):
    if not pairs:
        raise ValueError('NONEMPTY_SCORE_REQUIRED')
    c = Counter()
    for actual, predicted in pairs:
        if type(actual) is not int or type(predicted) is not int or actual not in (0, 1) or predicted not in (0, 1):
            raise ValueError('EXACT_BINARY_SCORE_REQUIRED')
        c[(actual, predicted)] += 1
    positives = c[(1, 0)] + c[(1, 1)]
    negatives = c[(0, 0)] + c[(0, 1)]
    tp, tn = c[(1, 1)], c[(0, 0)]
    ba = ((tp / positives + tn / negatives) / 2) if positives and negatives else None
    return {'correct': tp + tn, 'total': len(pairs), 'positive': positives,
            'negative': negatives, 'tp': tp, 'tn': tn,
            'false_positive': c[(0, 1)], 'false_negative': c[(1, 0)],
            'accuracy': (tp + tn) / len(pairs), 'balanced_accuracy': ba}


def pairs_for(rows, policy, *, training=None):
    if policy in ('pooled', 'position'):
        if training is None:
            raise ValueError('TRAINING_SET_REQUIRED')
        predict = calibrator(training, policy)
    elif policy == 'direct40':
        predict = lambda row: row['direct40']
    elif policy == 'full76':
        predict = lambda row: row['full76']
    elif policy == 'impute40':
        predict = lambda row: row['impute40']
    elif policy == 'absent':
        predict = lambda row: (0,) * 8
    elif policy == 'majority':
        predict = lambda row: tuple(int(sum(row[name][j] for name in ('full76','direct40','impute40')) >= 2) for j in range(8))
    else:
        raise ValueError('UNREGISTERED_POLICY')
    return [(row['truth'][j], predicted) for row in rows for j, predicted in enumerate(predict(row))]


def inner_choose(training):
    levels = tuple(sorted({row['level'] for row in training}))
    if len(levels) != 6 or len(training) != 18:
        raise ValueError('EXACT_SIX_TRAINING_LEVELS')
    policies = ('direct40', 'pooled', 'position')
    totals = {policy: [] for policy in policies}
    for held in levels:
        inner_train = [row for row in training if row['level'] != held]
        inner_test = [row for row in training if row['level'] == held]
        if len(inner_train) != 15 or len(inner_test) != 3:
            raise ValueError('EXACT_INNER_GROUPS')
        for policy in policies:
            totals[policy].extend(pairs_for(inner_test, policy,
                                         training=inner_train if policy != 'direct40' else None))
    results = {policy: score(totals[policy]) for policy in policies}
    if any(results[policy]['balanced_accuracy'] is None for policy in policies):
        raise ValueError('INNER_CLASSES_UNDEFINED')
    selected = max(policies, key=lambda policy:(results[policy]['balanced_accuracy'],
                                                results[policy]['accuracy'],
                                                -policies.index(policy)))
    return selected, results


def evaluate(rows=None):
    rows = read_rows() if rows is None else rows
    validate_rows(rows)
    all_pairs = defaultdict(list)
    level_details = []
    for level in LEVELS:
        train = [row for row in rows if row['level'] != level]
        test = [row for row in rows if row['level'] == level]
        if len(train) != 18 or len(test) != 3:
            raise ValueError('EXACT_OUTER_TRAIN_TEST_GROUPS_REQUIRED')
        choice, inner_scores = inner_choose(train)
        fold_pairs = {}
        for policy in POLICIES:
            effective = choice if policy == 'nested' else policy
            values = pairs_for(test, effective,
                               training=train if effective in ('pooled', 'position') else None)
            if len(values) != 24:
                raise ValueError('FOLD_DENOMINATOR_CHANGED')
            fold_pairs[policy] = values
            all_pairs[policy].extend(values)
        level_details.append({'heldout_group': level, 'train_specimens': 18,
                              'test_specimens': 3, 'nested_selected': choice,
                              'nested_inner_scores': inner_scores,
                              'heldout': {policy: score(pairs) for policy, pairs in fold_pairs.items()}})
    pooled = {policy: score(all_pairs[policy]) for policy in POLICIES}
    by_material = {}
    for policy in POLICIES:
        pairs = all_pairs[policy]
        by_material[policy] = [score([p for j, p in enumerate(pairs) if (j % 8) // 4 == m])
                               for m in (0, 1)]
    d, e, b = (pooled[p] for p in ('position','nested','full76'))
    success = (d['balanced_accuracy'] is not None and e['balanced_accuracy'] is not None and
               b['balanced_accuracy'] is not None and
               d['balanced_accuracy'] >= e['balanced_accuracy'] + 0.05 and
               d['balanced_accuracy'] >= b['balanced_accuracy'] + 0.05 and
               d['accuracy'] >= e['accuracy'] and d['accuracy'] >= b['accuracy'] and
               all(by_material['position'][m]['balanced_accuracy'] is not None and
                   by_material['nested'][m]['balanced_accuracy'] is not None and
                   by_material['position'][m]['balanced_accuracy'] >=
                       by_material['nested'][m]['balanced_accuracy'] - 0.05
                   for m in (0,1)))
    return {'schema':'agi-alpha/eit104-retrospective-levelout-calibration/v1',
            'frozen_protocol_commit':FROZEN_PROTOCOL_HEAD,
            'source_projection_sha256':SOURCE_PROJECTION_SHA256,
            'source_eit103_commit':SOURCE_EIT103_HEAD,
            'source_eit102_zip_sha256':SOURCE_EIT102_ZIP_SHA256,
            'source_eit102_result_sha256':SOURCE_EIT102_RESULT_SHA256,
            'exposed_physical_specimens':21, 'outer_levels':list(LEVELS),
            'actual_new_physical_acquisitions':0, 'actual_customer_accepted_outputs':0,
            'physical_decisions':168, 'counted_fold_predictions':7*3*8,
            'policies':pooled, 'by_material':by_material, 'by_level':level_details,
            'position_challenger_technical_gate':success,
            'comparators':{'nested_ordinary_policy':'nested','original_full76':'full76',
                           'original_direct40':'direct40','no_acquisition':'absent'},
            'scope':'POST_HOC_EXPOSED_PHYSICAL_DATA_GROUP_CV_NOT_PROSPECTIVE',
            'native_accounts_operated':0, 'native_financial_actions':0,
            'actual_collected_revenue_usd':0,'complete_cost_profit_usd':None,
            'actual_host_model_billing_usd':None,
            'usd_3b_trailing365_qualified':False,
            'decision':'RETROSPECTIVE_TECHNICAL_GATE_ONLY_NO_BID_NO_DEPLOY' if success
                       else 'REJECT_POSITION_CALIBRATION_NO_BID_NO_DEPLOY'}


if __name__ == '__main__':
    print(json.dumps(evaluate(), sort_keys=True, indent=2, allow_nan=False))
