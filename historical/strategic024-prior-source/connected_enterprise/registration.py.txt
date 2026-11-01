"""Finite public configurations for the existing connected operating path."""
from __future__ import annotations
import copy
from datetime import datetime
import re
from commercial.ledger import canonical, digest
from .engine import default_config, validate_config

SCHEMA = 'agi-alpha/connected014-registration/v1'
ARMS = {'baseline', 'channel', 'growth', 'competitive_growth'}


def validate(value):
    fields = {'schema', 'label', 'evidence_role', 'seeds', 'configs', 'arms',
              'control_arm', 'candidate_arm', 'service_cohort_seed', 'workers'}
    if not isinstance(value, dict) or set(value) != fields or value['schema'] != SCHEMA:
        raise ValueError('EXACT_CONNECTED_REGISTRATION_REQUIRED')
    result = copy.deepcopy(value)
    if not isinstance(value['label'], str) or not re.fullmatch('[a-z][a-z0-9-]{0,79}', value['label']):
        raise ValueError('SAFE_REGISTRATION_LABEL_REQUIRED')
    if value['evidence_role'] not in {'development', 'reproduction', 'finite_authored_comparison'}:
        raise ValueError('EXPLICIT_ENGINEERING_OR_FINITE_COMPARISON_SCOPE_REQUIRED')
    seeds = value['seeds']
    if not isinstance(seeds, list) or not seeds or any(type(s) is not int or s < 0 for s in seeds) or len(seeds) != len(set(seeds)):
        raise ValueError('UNIQUE_FINITE_INTEGER_SEEDS_REQUIRED')
    arms = value['arms']
    if not isinstance(arms, list) or len(arms) < 2 or any(not isinstance(a, str) or a not in ARMS for a in arms) or len(arms) != len(set(arms)):
        raise ValueError('DISTINCT_SUPPORTED_MATCHED_ARMS_REQUIRED')
    if value['control_arm'] not in arms or value['candidate_arm'] not in arms or value['control_arm'] == value['candidate_arm']:
        raise ValueError('DISTINCT_REGISTERED_CONTROL_AND_CANDIDATE_REQUIRED')
    if type(value['workers']) is not int or value['workers'] < 1:
        raise ValueError('POSITIVE_WORKER_COUNT_REQUIRED')
    if type(value['service_cohort_seed']) is not int or value['service_cohort_seed'] < 0:
        raise ValueError('INTEGER_SERVICE_COHORT_SEED_REQUIRED')
    configs = value['configs']
    if not isinstance(configs, dict) or 'central' not in configs or any(not isinstance(k, str) or not re.fullmatch('[a-z][a-z0-9_]{0,79}', k) for k in configs):
        raise ValueError('CENTRAL_AND_SAFE_FINITE_CASE_NAMES_REQUIRED')
    for case, cfg in configs.items():
        normalized = validate_config(cfg)
        if normalized != cfg or cfg['schema'] != default_config()['schema']:
            raise ValueError('CANONICAL_COMPLETE_CONNECTED_CONFIGURATION_REQUIRED')
        epoch = datetime.fromisoformat(cfg['epoch_utc'].replace('Z', '+00:00'))
        if epoch.utcoffset() is None or epoch.utcoffset().total_seconds() != 0:
            raise ValueError('UTC_REGISTRATION_EPOCH_REQUIRED')
        for key in ['price_pressure_bps', 'value_bps', 'buyer_budget_multiplier_bps']:
            if type(cfg[key]) is not int or cfg[key] < 0:
                raise ValueError('NONNEGATIVE_BUYER_AND_PRICE_MULTIPLIER_REQUIRED')
        for key in ['supplier_outage_start_day', 'supplier_outage_days']:
            if type(cfg[key]) is not int or cfg[key] < (-1 if key.endswith('start_day') else 0):
                raise ValueError('FINITE_SUPPLIER_OUTAGE_REQUIRED')
        if set(cfg['human_comparator']) != {'reconciliation', 'kpi_variance', 'evidence_matrix'}:
            raise ValueError('COMPLETE_HUMAN_COMPARATOR_REQUIRED')
        for human in cfg['human_comparator'].values():
            if set(human) != {'hours', 'loaded_usd_hour'} or any(type(v) not in {int, float} or v < 0 for v in human.values()):
                raise ValueError('NONNEGATIVE_EXPLICIT_HUMAN_ASSUMPTIONS_REQUIRED')
    canonical(result)
    return result


def registered_protocol(value, base):
    value = validate(value)
    p = copy.deepcopy(base)
    p.update(edition='registered-' + value['label'], central_seeds=value['seeds'],
             adverse_seeds=value['seeds'] if len(value['configs']) > 1 else [],
             cases=['central'] + sorted(k for k in value['configs'] if k != 'central'),
             arms=value['arms'], control_arm=value['control_arm'], candidate_arm=value['candidate_arm'],
             channel_control_seeds=[], service_cohort_seed=value['service_cohort_seed'], workers=value['workers'])
    p['registration_sha256'] = digest(value)
    p['evidence_role'] = value['evidence_role']
    p['case_design'] = 'All registered seeds cross all registered cases and arms; stop after this fixed finite design. Every business has separate seed capital. Same configuration and keyed exogenous draws within each pair; endogenous paths may differ.'
    p['inference'] = 'Finite authored engineering/comparison design, not calibrated demand, fresh statistical confirmation, annualized profit, actual commerce or lifecycle migration. Exposure/freshness must be established separately. No optional stopping or seed replacement.'
    p['clock'] = 'Registered integer-hour event clock; each case runs its declared planning horizon and drains scheduled settlement events. Existing permanent protection tails remain unchanged.'
    return p
