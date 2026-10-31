"""Scope-limited categorical source-group reflection, not a universal truth oracle."""
from collections import Counter
from .core import ContractError, exact_keys, identifiers, digest

REFLECT_SCHEMA = 'agi-alpha/mechanism-reflection/v1'


def reflect(model):
    exact_keys(model, {'schema', 'question_id', 'fault_budget_groups', 'records', 'declared_fault_model'}, 'REFLECTION_FIELDS')
    if model['schema'] != REFLECT_SCHEMA or model['declared_fault_model'] != 'AT_MOST_T_DISTINCT_SOURCE_GROUPS_WRONG':
        raise ContractError('UNSUPPORTED_REFLECTION_SCOPE')
    identifiers([model['question_id']], 'QUESTION')
    t = model['fault_budget_groups']
    if type(t) is not int or not 0 <= t <= 16:
        raise ContractError('BOUNDED_FAULT_BUDGET_REQUIRED')
    rows = model['records']
    if type(rows) is not list or len(rows) > 128:
        raise ContractError('BOUNDED_REFERENCE_RECORDS_REQUIRED')
    sources = {}
    for row in rows:
        exact_keys(row, {'source_group', 'value', 'reference_id'}, 'REFERENCE_FIELDS')
        identifiers([row['source_group']], 'SOURCE_GROUP')
        identifiers([row['value']], 'VALUE')
        identifiers([row['reference_id']], 'REFERENCE_ID')
        group = row['source_group']
        if group in sources and sources[group] != row['value']:
            return result(model, 'INCONSISTENT_WITH_DECLARED_PREMISES', None, len(sources), 'A single source group supplied conflicting outcomes')
        sources[group] = row['value']
    if len(sources) <= 2*t:
        return result(model, 'INSUFFICIENT_INDEPENDENT_GROUPS_ASSUMED', None, len(sources), 'Source labels do not prove independence; the declared group count cannot tolerate the stated faults')
    votes = Counter(sources.values())
    leaders = sorted((v for v, c in votes.items() if c >= len(sources)-t))
    if len(leaders) != 1:
        return result(model, 'INCONSISTENT_WITH_DECLARED_PREMISES', None, len(sources), 'No value meets the full-group bound given the proposed fault budget')
    return result(model, 'CONDITIONAL_RECOVERY', leaders[0], len(sources), 'Value recovered only if group independence and fault-budget assumptions actually hold')


def result(model, status, value, groups, limitation):
    return {'schema': 'agi-alpha/mechanism-reflection-result/v1', 'reference_sha256': digest(model), 'status': status, 'recovered_value': value, 'distinct_source_groups': groups, 'declared_fault_budget_groups': model['fault_budget_groups'], 'scope': 'CATEGORICAL_EQUALITY_WITH_ASSUMED_SOURCE_FAULT_BOUND', 'limitation': limitation, 'current_proof': None, 'authority': []}
