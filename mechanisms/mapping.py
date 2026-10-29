"""Bounded typed subgraph discovery and role-parameterized adaptation compilation."""
from __future__ import annotations

import hashlib
import json
import math

MAX_NODES = 12
MAX_RELATIONS = 64
TRANSFORMS = frozenset({'protect', 'atomic_publish', 'compensate'})


class MappingRefused(ValueError):
    pass


def _copy(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise MappingRefused('NON_JSON_REPRESENTATION') from error
    if len(raw.encode()) > 65536:
        raise MappingRefused('REPRESENTATION_SIZE_LIMIT')
    return json.loads(raw)


def _identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _name(value):
    return type(value) is str and 0 < len(value) <= 128


def _conditions(value):
    if type(value) is not dict or any(not _name(k) for k in value):
        raise MappingRefused('TYPED_CONDITIONS_REQUIRED')
    for item in value.values():
        if type(item) not in (str, int, float, bool) or (type(item) is float and not math.isfinite(item)):
            raise MappingRefused('INVALID_CONDITION_VALUE')


def validate_graph(graph):
    graph = _copy(graph)
    if type(graph) is not dict or not {'id', 'nodes', 'relations', 'conditions'} <= set(graph):
        raise MappingRefused('GRAPH_SCHEMA')
    if not _name(graph['id']) or type(graph['nodes']) is not list or not 1 <= len(graph['nodes']) <= MAX_NODES:
        raise MappingRefused('GRAPH_NODE_LIMIT_OR_ID')
    nodes = {}
    events = set()
    for node in graph['nodes']:
        if type(node) is not dict or not {'id', 'kind', 'unit'} <= set(node):
            raise MappingRefused('NODE_SCHEMA')
        if any(not _name(node[k]) for k in ('id', 'kind', 'unit')) or node['id'] in nodes:
            raise MappingRefused('NODE_IDENTITY_OR_TYPE')
        if 'event' in node and not _name(node['event']):
            raise MappingRefused('EVENT_IDENTITY')
        event = node.get('event', node['id'])
        if event in events:
            raise MappingRefused('DUPLICATE_EVENT_BINDING')
        nodes[node['id']] = node
        events.add(event)
    if type(graph['relations']) is not list or len(graph['relations']) > MAX_RELATIONS:
        raise MappingRefused('RELATION_LIMIT')
    edges = set()
    for edge in graph['relations']:
        if type(edge) is not list or len(edge) != 3 or any(not _name(x) for x in edge):
            raise MappingRefused('RELATION_SCHEMA')
        a, relation, b = edge
        if a not in nodes or b not in nodes or tuple(edge) in edges:
            raise MappingRefused('RELATION_ENDPOINT_OR_DUPLICATE')
        edges.add(tuple(edge))
    _conditions(graph['conditions'])
    return graph


def target_from_task(task):
    if type(task) is not dict or not _name(task.get('id')) or type(task.get('phases')) is not list:
        raise MappingRefused('TASK_SCHEMA')
    nodes, relations = [], []
    for phase in task['phases']:
        if type(phase) is not dict or not {'id', 'kind', 'deps'} <= set(phase) or type(phase['deps']) is not list:
            raise MappingRefused('TASK_PHASE_SCHEMA')
        nodes.append({'id': phase['id'], 'kind': phase['kind'], 'unit': phase.get('unit', 'event'), 'event': phase['id']})
        relations.extend([[dependency, 'precedes', phase['id']] for dependency in phase['deps']])
    return validate_graph({'id': task['id'], 'nodes': nodes, 'relations': relations, 'conditions': task.get('conditions', {})})


def _mismatches(donor, target):
    return [key for key, value in donor['conditions'].items()
            if key not in target['conditions'] or type(target['conditions'][key]) is not type(value)
            or target['conditions'][key] != value]


def check_mapping(donor, target, role_map):
    donor, target = validate_graph(donor), validate_graph(target)
    if _mismatches(donor, target):
        raise MappingRefused('APPLICABILITY_CONDITION_MISMATCH')
    source = {n['id']: n for n in donor['nodes']}
    destination = {n['id']: n for n in target['nodes']}
    if type(role_map) is not dict or set(role_map) != set(source) or any(type(v) is not str for v in role_map.values()):
        raise MappingRefused('ROLE_MAP_SCHEMA')
    if len(set(role_map.values())) != len(role_map) or any(v not in destination for v in role_map.values()):
        raise MappingRefused('ROLE_MAP_NOT_INJECTIVE_OR_UNKNOWN')
    for role, mapped in role_map.items():
        if (source[role]['kind'], source[role]['unit']) != (destination[mapped]['kind'], destination[mapped]['unit']):
            raise MappingRefused('ROLE_KIND_OR_UNIT_MISMATCH')
    edges = {tuple(edge) for edge in target['relations']}
    if any((role_map[a], relation, role_map[b]) not in edges for a, relation, b in donor['relations']):
        raise MappingRefused('DIRECTED_RELATION_MISMATCH')
    return donor, target


def discover(donors, target, max_mappings=32, max_search=10000):
    if type(donors) is not list or not 1 <= len(donors) <= 32:
        raise MappingRefused('DONOR_COUNT_LIMIT')
    if type(max_mappings) is not int or not 1 <= max_mappings <= 128 or type(max_search) is not int or not 1 <= max_search <= 100000:
        raise MappingRefused('SEARCH_BOUND')
    target = validate_graph(target)
    target_nodes = {n['id']: n for n in target['nodes']}
    target_edges = {tuple(edge) for edge in target['relations']}
    reports = []
    for source in donors:
        donor = validate_graph(source)
        mismatches = _mismatches(donor, target)
        domains = {n['id']: sorted(t['id'] for t in target['nodes'] if (n['kind'], n['unit']) == (t['kind'], t['unit'])) for n in donor['nodes']}
        order = sorted(domains, key=lambda role: (len(domains[role]), role))
        maps, explored, truncated = [], 0, False

        def search(partial, used):
            nonlocal explored, truncated
            if explored >= max_search or len(maps) > max_mappings:
                truncated = True
                return
            explored += 1
            if len(partial) == len(order):
                maps.append(dict(sorted(partial.items())))
                return
            role = order[len(partial)]
            for node in domains[role]:
                if node in used:
                    continue
                proposed = {**partial, role: node}
                if any(a in proposed and b in proposed and (proposed[a], relation, proposed[b]) not in target_edges
                       for a, relation, b in donor['relations']):
                    continue
                search(proposed, used | {node})
                if truncated:
                    return

        if not mismatches and len(donor['nodes']) <= len(target_nodes):
            search({}, set())
        status = 'bounded' if truncated else ('unique' if len(maps) == 1 else 'ambiguous' if maps else 'refused')
        report = {'source': donor['id'], 'target': target['id'], 'source_graph': donor, 'donor_graph': donor,
                  'target_graph': target, 'correspondences': maps[:max_mappings], 'status': status,
                  'applicable': bool(maps) and not mismatches, 'search_complete': not truncated,
                  'search_nodes': explored, 'candidate_limit': max_mappings, 'search_limit': max_search,
                  'unresolved_mismatches': mismatches,
                  'typed_domain_failures': [role for role, values in domains.items() if not values],
                  'preserved_relations': donor['relations'] if maps else [],
                  'changed_assumptions': {k: v for k, v in target['conditions'].items() if k not in donor['conditions']},
                  'origin': 'Developer supplied typed representations and role recipes; bounded search discovers correspondences, ignoring labels.'}
        reports.append(report)
    return sorted(reports, key=lambda report: (not report['applicable'], report['source']))


def _transform(template, target_events, provenance):
    if type(template) is not dict or not {'kind', 'role_ids'} <= set(template):
        raise MappingRefused('ROLE_TRANSFORM_SCHEMA')
    allowed = {'kind', 'role_ids', 'resource_role_ids'}
    if set(template) - allowed or template['kind'] not in TRANSFORMS:
        raise MappingRefused('UNSUPPORTED_ROLE_TRANSFORM')
    roles = template['role_ids']
    if type(roles) is not list or not roles or any(type(role) is not str or role not in target_events for role in roles) or len(set(roles)) != len(roles):
        raise MappingRefused('TRANSFORM_ROLE_REFERENCE')
    result = {'kind': template['kind'], 'phase_ids': [target_events[role] for role in roles], 'provenance': provenance}
    if 'resource_role_ids' in template:
        resources = template['resource_role_ids']
        if template['kind'] != 'compensate' or type(resources) is not list or not resources or any(type(role) is not str or role not in target_events for role in resources) or len(set(resources)) != len(resources):
            raise MappingRefused('RESOURCE_ROLE_REFERENCE')
        result['resource_phase_ids'] = [target_events[role] for role in resources]
    return result


def compile_mapping(donor, target, role_map):
    donor, target = check_mapping(donor, target, role_map)
    target_nodes = {node['id']: node for node in target['nodes']}
    target_events = {role: target_nodes[node].get('event', node) for role, node in sorted(role_map.items())}
    provenance = {'origin': 'structural-transfer-hypothesis', 'donor_id': donor['id'], 'target_id': target['id'],
                  'donor_sha256': _identity(donor), 'target_sha256': _identity(target), 'role_map_sha256': _identity(role_map)}
    obligations, recipes = donor.get('obligations', []), donor.get('strategy_recipe', [])
    if type(obligations) is not list or type(recipes) is not list or not (obligations or recipes):
        raise MappingRefused('NO_ROLE_PARAMETERIZED_TRANSFORMATION')
    if len(obligations) + len(recipes) > 32:
        raise MappingRefused('TRANSFORM_COUNT_LIMIT')
    compiled = [_transform(template, target_events, provenance) for template in obligations]
    recipe = [_transform(template, target_events, provenance) for template in recipes]
    return {'source': donor['id'], 'target': target['id'], 'source_graph': donor, 'donor_graph': donor,
            'target_graph': target, 'role_map': dict(sorted(role_map.items())), 'mapped_roles': target_events,
            'target_events': target_events, 'obligations': compiled, 'strategy_recipe': recipe,
            'preserved_relations': [[role_map[a], relation, role_map[b]] for a, relation, b in donor['relations']],
            'applicability': {'conditions': donor['conditions'], 'checked': True, 'status': 'hypothesis-awaiting-execution'},
            'prediction': {'obligation_event_sets': [item['phase_ids'] for item in compiled],
                           'claim': 'The constructed target strategy must independently satisfy these transferred obligations.'},
            'provenance': provenance}


def discover_one(donor, target, max_search=10000):
    report = discover([donor], target, max_search=max_search)[0]
    if report['status'] != 'unique':
        raise MappingRefused('MAPPING_' + report['status'].upper())
    return compile_mapping(donor, target, report['correspondences'][0])
