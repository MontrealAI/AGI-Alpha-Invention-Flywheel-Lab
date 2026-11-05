"""Thin existing-harness integration; records facts, not Super Alpha by assertion."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
from mechanism_harness.core import SCHEMA, audit, compose, digest
from .water import construct, conventional_milp, validate
from .verify import corner_check, verify, exhaustive_optimum


def plan_path(external=False):
    initial = ['request'] + (['proposal'] if external else [])
    operators = []
    if not external:
        operators.append({'id': 'construct', 'requires': ['request'], 'provides': ['proposal'], 'cost': 1, 'effect': 'pure', 'origin': 'developer_supplied'})
    operators.append({'id': 'verify', 'requires': ['proposal', 'request'], 'provides': ['checked_blueprint'], 'cost': 1, 'effect': 'pure', 'origin': 'developer_supplied'})
    spec = {'schema': SCHEMA, 'purpose': {'initial': sorted(initial), 'goal': ['checked_blueprint'], 'max_cost': 10, 'max_steps': 4, 'max_states': 50, 'allowed_effects': ['pure']}, 'mechanisms': operators, 'candidate_bridges': []}
    plan = compose(spec)
    check = audit(spec, plan)
    return spec, plan, check


def buyer(request, proposal=None):
    validate(request)
    external = request.get('model_route') == 'buyer_owned_account_external'
    if external and proposal is None:
        raise ValueError('EXTERNAL_PROPOSAL_FILE_REQUIRED_NO_ACCOUNT_WILL_BE_CALLED')
    if not external and proposal is not None:
        raise ValueError('LOCAL_ROUTE_DOES_NOT_ACCEPT_EXTERNAL_PROPOSAL')
    spec, pathway, path_check = plan_path(external)
    result = {'request_sha256': digest(request), 'model_route': request['model_route'], 'model_api_calls': 0, 'pathway': pathway, 'symbolic_audit': path_check, 'plan': proposal}
    for step in pathway['sequence']:
        if step == 'construct':
            result['plan'] = construct(request)
        elif step == 'verify':
            if result['plan']['status'] == 'MODEL_PLAN':
                result['certificate'] = verify(request, result['plan'])
                result['interval_corners_checked'] = corner_check(request, result['plan'])
            else:
                result['certificate'] = None
                result['interval_corners_checked'] = 0
    result['scope'] = 'MATHEMATICAL_BLUEPRINT_ONLY; NO_PHYSICAL_DELIVERY_OR_AUTHORITY'
    return result


def cases(root):
    base = json.loads((Path(root) / 'omega/request.json').read_text())
    primary = copy.deepcopy(base)
    successor = copy.deepcopy(base)
    successor['name'] = 'Fresh successor with changed source quality'
    successor['sources'][1]['upper_quality'][0] = 9
    infeasible = copy.deepcopy(base)
    infeasible['name'] = 'Known insufficient total supply'
    infeasible['freshwater_cap'] = 0
    for source in infeasible['sources']:
        source['capacity'] = 1
    declined = copy.deepcopy(base)
    declined['name'] = 'Source participation withdrawn'
    declined['sources'][0]['consent'] = False
    selected = [primary, successor, infeasible, declined]
    rng = random.Random(20261103)
    for index in range(20):
        request = copy.deepcopy(base)
        request['name'] = 'Authored stress case ' + str(index)
        request['freshwater_cap'] = rng.randrange(5)
        for source in request['sources']:
            source['capacity'] = rng.randrange(1, 6)
            source['upper_quality'] = [rng.randrange(1, 10), rng.randrange(1, 10)]
            source['unit_cost_cents'] = rng.randrange(10, 120)
        for sink in request['sinks']:
            sink['demand'] = rng.randrange(1, 5)
            sink['max_quality'] = [rng.randrange(1, 7), rng.randrange(1, 7)]
        selected.append(request)
    return selected


def source_identity(root):
    root = Path(root)
    paths = sorted([*root.glob('omega/*.py'), root/'omega/request.json', root/'omega/requirements.txt', root/'campaign/omega-water-20261103/PROTOCOL.md', root/'mechanism_harness/core.py'])
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def experiment(root):
    root = Path(root)
    rows = []
    fixtures = cases(root)
    for request in fixtures:
        delivery = buyer(request)
        candidate, control = delivery['plan'], conventional_milp(request)
        control_check = verify(request, control) if control['status'] == 'MODEL_PLAN' else None
        exact_oracle = exhaustive_optimum(request)
        if candidate['objective'] != exact_oracle['objective']:
            raise AssertionError('EXACT_INTEGER_ORACLE_DISAGREES')
        if candidate['status'] != control['status'] or candidate['objective'] != control['objective']:
            raise AssertionError('CANDIDATE_AND_CONVENTIONAL_OPTIMUM_DISAGREE:' + request['name'])
        rows.append({'name': request['name'], 'request_sha256': digest(request), 'candidate_status': candidate['status'], 'candidate_objective': candidate['objective'], 'conventional_status': control['status'], 'conventional_objective': control['objective'], 'candidate_accepted': delivery['certificate'] is not None, 'conventional_accepted': control_check is not None, 'interval_corners_checked': delivery['interval_corners_checked'], 'integer_oracle': exact_oracle})
    old_plan = construct(fixtures[0])
    try:
        verify(fixtures[1], old_plan)
    except ValueError as error:
        stale_rejected = str(error)
    else:
        raise AssertionError('STALE_PLAN_ACCEPTED')
    successor = buyer(fixtures[1])
    ordinary = buyer(copy.deepcopy(fixtures[1]))
    identities = source_identity(root)
    return {'schema': 'omega/coupled-probe/v1', 'scope': 'FINITE_AUTHORED_SYNTHETIC_MODELS_NOT_CUSTOMER_VALIDATION', 'source_files_sha256': identities, 'source_sha256': digest(identities), 'case_count': len(rows), 'cases': rows, 'primary_delivery': buyer(fixtures[0]), 'successor': {'stale_plan_rejected': stale_rejected, 'fresh_certificate': successor['certificate'], 'ordinary_equal_content_reuse_identical': successor == ordinary, 'retained_method_advantage': False, 'discovery_policy_advantage': None}, 'benchmark': {'competent_human_conventional_software': 'Independent exact mixed-integer optimizer executed at machine speed', 'human_plus_ai': 'Not independently timed or sampled; same complete optimizer is permitted', 'frontier_ai_arm': 'Implementation constructed with included assistant; runtime is deterministic, not a measured model comparison', 'measured_human_labor_hours': None, 'measured_ai_development_cost': None, 'full_productivity_ratio': None, 'complete_construction_coordination_physical_costs': None}, 'verdicts': {'blue_sky': 'STOP: complete conventional control matches every tested outcome', 'buyer_tool': 'MODEL_SCOPED_CAPABILITY; NO_PHYSICAL_INSTALLATION', 'retained_method': 'NO_ADVANTAGE_OVER_EQUAL_CONTENT_ORDINARY_REUSE', 'actual_commerce': 'NONE', 'super_alpha': 'NOT_ESTABLISHED'}, 'learning': {'tried': 'Robust voluntary water reuse construction plus fresh successor', 'outcome': 'Conventional complete optimizer matches; independent certificates remain useful', 'why': 'Interval upper-bound robust counterpart and integer allocation are established methods', 'next_or_avoid': 'Do not promote or repeatedly rebrand this optimizer. Require an evidenced physical or coordination residual before new flagship investment.'}}
