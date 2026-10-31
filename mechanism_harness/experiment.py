"""Finite illustrative comparison; never a commercial or recursive-discovery certificate."""
import copy
from .core import audit, compose, digest
from .evidence import reflect


def compare_case(spec):
    incumbent = copy.deepcopy(spec)
    incumbent['candidate_bridges'] = []
    base = compose(incumbent)
    candidate = compose(spec)
    base_check = audit(incumbent, base)
    candidate_check = audit(spec, candidate)
    if not base_check['accepted'] or not candidate_check['accepted']:
        raise ValueError('CHECKER_MUST_ACCEPT_SYMBOLIC_COMPARISON')
    result = {
        'source_sha256': digest(spec),
        'incumbent': {'status': base['status'], 'sequence': base['sequence'], 'cost_units': base['cost_units'], 'audit_sha256': digest(base_check)},
        'candidate': {'status': candidate['status'], 'sequence': candidate['sequence'], 'cost_units': candidate['cost_units'], 'audit_sha256': digest(candidate_check)},
        'symbolic_incremental_cost_units': None,
        'supports_real_accepted_delivery': False,
    }
    if base_check['goal_achieved_symbolically'] and candidate_check['goal_achieved_symbolically']:
        result['symbolic_incremental_cost_units'] = base['cost_units'] - candidate['cost_units']
    return result


def experiment(primary, successor, reference):
    a, b = compare_case(primary), compare_case(successor)
    reflection = reflect(reference)
    return {
        'schema': 'agi-alpha/mechanism-harness-study/v1',
        'scope': 'LOCAL_FINITE_DEVELOPER_AUTHORED_SYMBOLIC_STUDY',
        'primary': a, 'fresh_surface_successor': b,
        'categorical_reflection': reflection,
        'actual_customers': 0, 'actual_collected_usd': 0,
        'observed_successor_inheritance_benefit': None,
        'observed_discovery_policy_gain': None,
        'physical_productive_gain': None,
        'claims': ['BOUNDED_SYMBOLIC_COMPOSITION', 'SOURCE_BOUND_PLAN_REPLAY', 'NARROW_FAULT_MODEL_REFLECTION'],
        'not_established': ['TRUE_MECHANISM_SEMANTICS', 'NOVEL_AUTONOMOUS_INVENTION', 'CAUSAL_SUCCESSOR_GAIN', 'OPEN_ENDED_SELF_IMPROVEMENT', 'OBSERVED_COMMERCE', 'CIVILIZATION_SCALE_EXPANSION'],
    }
