"""Asset/incentive admission for the EXISTING finite planner; never a payment engine.

Receipts must be independently rederived before context_from_rederived is called.
Digest consistency is not authentication. Role/source labels do not prove independence.
"""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import re
import sys
from .preflight import benefit_members, same_canonical
from .readout import (EvidenceError, _invoke, _plain_directory, canonical, sha,
                      snapshot_from_rederived, strict_json)

SCHEMA = 'agi-alpha/economic-coupling/v1'
CONTEXT = 'agi-alpha/coupling-context/v1'
BASELINE_ALLOCATOR_BLOB = '465e752db419b5077314b91136e2b4e8e8784226'
ROLES = {
    'verifier': 'completed_check',
    'challenger': 'adjudicated_counterexample',
    'builder': 'accepted_outcome',
    'originator': 'collected_incremental_surplus',
}


def require(ok, reason):
    if not ok:
        raise EvidenceError(reason)


def exact(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), 'EXACT_' + label + '_FIELDS_REQUIRED')


def ident(value):
    require(type(value) is str and re.fullmatch(r'[a-z][a-z0-9_.-]{0,79}', value), 'BOUNDED_IDENTIFIER_REQUIRED')
    return value


def money(value):
    require(type(value) is int and 0 <= value <= 10**18, 'BOUNDED_NONNEGATIVE_INTEGER_AMOUNT_REQUIRED')
    return value


def digest_id(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'CONTENT_DIGEST_REQUIRED')
    return value


def index(rows, label):
    require(type(rows) is list and len(rows) <= 32, 'BOUNDED_' + label + '_LIST_REQUIRED')
    result = {}
    for row in rows:
        require(type(row) is dict, 'OBJECT_REQUIRED')
        name = ident(row.get('id'))
        require(name not in result, 'DUPLICATE_' + label + '_ID')
        result[name] = row
    return result


def refs(values):
    require(type(values) is list and len(values) <= 32, 'BOUNDED_REFERENCE_LIST_REQUIRED')
    require(all(type(x) is str for x in values), 'STRING_REFERENCES_REQUIRED')
    require(len(set(values)) == len(values), 'DUPLICATE_REFERENCE')
    for value in values:
        ident(value)
    return values


def context_from_rederived(audit, report, scoreboard, world):
    """Select ONE complete native world; do not pool independent scenario balances."""
    snapshot_from_rederived(audit, report, scoreboard)
    matches = [b for b in scoreboard['businesses'] if b['business_reference'] == world]
    require(len(matches) == 1, 'ONE_EXISTING_NATIVE_WORLD_REQUIRED')
    b = matches[0]
    summary = b['financial_state_microUSD']
    for key in ('available', 'unrestrictedEarned'):
        require(type(summary.get(key)) is int, 'NATIVE_FUNDING_FIELD_REQUIRED:' + key)
    require(type(summary.get('investmentStopped')) is bool, 'NATIVE_STOP_STATE_REQUIRED')
    require(type(b.get('executed_hours')) is int and b['executed_hours'] >= 0, 'NATIVE_EVENT_HORIZON_REQUIRED')
    digest_id(b.get('native_actions_sha256'))
    return {
        'schema': CONTEXT, 'scope': 'SIMULATED', 'world': world,
        'source_sha256': scoreboard['source_sha256'], 'freeze_sha256': scoreboard['frozen_sha256'],
        'report_sha256': scoreboard['report_sha256'], 'scoreboard_sha256': sha(scoreboard),
        'audit_sha256': sha(audit), 'actions_sha256': b['native_actions_sha256'],
        'summary_sha256': sha(summary), 'available': max(0, summary['available']),
        'unrestrictedEarned': max(0, summary['unrestrictedEarned']),
        'investmentStopped': summary['investmentStopped'], 'observed_hour': b['executed_hours'],
        'proof_scope': 'REQUIRES_CANONICAL_REDERIVATION_NOT_JSON_SELF_ATTESTATION',
        'funding_authority': False,
    }


def live_context(enterprise, world, *, timeout=600):
    """Only for explicitly trusted frozen source; no account mutation is requested."""
    root = _plain_directory(enterprise)
    src = _plain_directory(root / 'source')
    require(type(timeout) is int and 1 <= timeout <= 900, 'FINITE_AUDIT_TIMEOUT_REQUIRED')
    for name in ('FROZEN.json', 'REPORT.json', 'COMPLETE.json'):
        require((root / name).is_file() and not (root / name).is_symlink(), 'COMPLETE_ENTERPRISE_REQUIRED')
    command = [sys.executable, '-m', 'connected_enterprise']
    audit = _invoke(command + ['audit', '--output', str(root)], src, timeout)
    report = strict_json((root / 'REPORT.json').read_bytes())
    board = _invoke(command + ['scoreboard', '--output', str(root)], src, timeout)
    return context_from_rederived(audit, report, board, world)


def check_context(context):
    exact(context, {'schema', 'scope', 'world', 'source_sha256', 'freeze_sha256', 'report_sha256',
                    'scoreboard_sha256', 'audit_sha256', 'actions_sha256', 'summary_sha256',
                    'available', 'unrestrictedEarned', 'investmentStopped', 'observed_hour',
                    'proof_scope', 'funding_authority'}, 'CONTEXT')
    require(context['schema'] == CONTEXT and context['scope'] == 'SIMULATED', 'SIMULATION_ONLY')
    require(context['funding_authority'] is False, 'NO_FUNDING_AUTHORITY')
    require(context['proof_scope'] == 'REQUIRES_CANONICAL_REDERIVATION_NOT_JSON_SELF_ATTESTATION', 'CONTEXT_PROOF_SCOPE')
    require(type(context['world']) is str and 0 < len(context['world']) <= 160, 'WORLD_REQUIRED')
    for key in ('source_sha256', 'freeze_sha256', 'report_sha256', 'scoreboard_sha256',
                'audit_sha256', 'actions_sha256', 'summary_sha256'):
        digest_id(context[key])
    for key in ('available', 'unrestrictedEarned', 'observed_hour'):
        money(context[key])
    require(type(context['investmentStopped']) is bool, 'NATIVE_STOP_STATE_REQUIRED')


def assess(request, context, universe):
    """Cost and filter proposals, then reuse portfolio_scale.transformational.choose.

    Input asset qualifications, contracts and returns remain declared premises.
    Even valid proposals require fresh independent mission proof and a native commit.
    """
    from portfolio_scale.transformational import choose
    check_context(context)
    exact(request, {'schema', 'expected_context_sha256', 'planning_cap_microUSD', 'allocation',
                    'assets', 'incentives', 'shared_costs', 'attachments'}, 'COUPLING')
    require(request['schema'] == SCHEMA, 'COUPLING_SCHEMA')
    require(request['expected_context_sha256'] == sha(context), 'STALE_OR_CROSS_WORLD_CONTEXT')
    cap = money(request['planning_cap_microUSD'])
    base = copy.deepcopy(request['allocation'])
    exact(base, {'schema', 'scope', 'currency', 'scenarios', 'actions', 'synergies', 'max_states',
                 'worst_loss_limit', 'downside_penalty_bps'}, 'ALLOCATION_WITHOUT_FUNDING')
    require(type(base['max_states']) is int and 1 <= base['max_states'] <= 65536, 'BOUNDED_PLANNING_SEARCH')
    require(type(base['actions']) is list and len(base['actions']) <= 16, 'BOUNDED_ACTION_SHORTLIST')
    require(type(base['scenarios']) is dict and 1 <= len(base['scenarios']) <= 32, 'BOUNDED_SCENARIOS')
    actions = index(base['actions'], 'ACTION')
    benefit_members(base['synergies'], set(actions))
    assets = index(request['assets'], 'ASSET')
    rewards = index(request['incentives'], 'INCENTIVE')
    shared = index(request['shared_costs'], 'SHARED_COST')
    attachments = request['attachments']
    require(type(attachments) is dict and set(attachments) == set(actions), 'ONE_ATTACHMENT_PER_ACTION')
    for row in shared.values():
        exact(row, {'id', 'kind', 'amount_microUSD'}, 'SHARED_COST')
        require(row['kind'] in {'maintenance', 'revalidation', 'integration'}, 'SHARED_COST_KIND')
        money(row['amount_microUSD'])
    for asset in assets.values():
        exact(asset, {'id', 'artifact_sha256', 'scope', 'qualification', 'rights', 'expires_hour',
                      'evidence_ref', 'shared_cost_ids'}, 'ASSET')
        digest_id(asset['artifact_sha256'])
        ident(asset['scope']); ident(asset['evidence_ref']); money(asset['expires_hour'])
        require(asset['qualification'] in {'QUALIFIED_IN_SCOPE', 'CANDIDATE', 'INVALIDATED', 'UNKNOWN'}, 'ASSET_QUALIFICATION')
        require(asset['rights'] in {'PERMITTED', 'UNKNOWN', 'DENIED'}, 'ASSET_RIGHTS')
        require(set(refs(asset['shared_cost_ids'])) <= set(shared), 'UNKNOWN_SHARED_COST')
    for reward in rewards.values():
        exact(reward, {'id', 'role', 'payee', 'adjudicator', 'basis', 'cap_microUSD', 'evidence_ref'}, 'INCENTIVE')
        require(reward['role'] in ROLES and reward['basis'] == ROLES[reward['role']], 'INCENTIVE_MUST_REWARD_DEFINED_WORK_NOT_FAVORABLE_VERDICT')
        ident(reward['payee']); ident(reward['adjudicator']); ident(reward['evidence_ref'])
        require(reward['payee'] != reward['adjudicator'], 'SELF_ADJUDICATED_REWARD')
        money(reward['cap_microUSD'])
    blocked, expanded, cost_nodes, normalized = {}, [], {}, {}
    zero = dict.fromkeys(base['scenarios'], 0)
    for name, action in actions.items():
        require(not name.startswith('wheel-cost-'), 'RESERVED_ACTION_PREFIX')
        att = attachments[name]
        exact(att, {'scope', 'asset_ids', 'incentive_ids', 'shared_cost_ids', 'producer', 'checker',
                    'fresh_mission_check', 'base_excludes_declared_extras'}, 'ATTACHMENT')
        ident(att['scope']); ident(att['producer']); ident(att['checker'])
        require(att['fresh_mission_check'] is True, 'FRESH_MISSION_CHECK_REQUIRED')
        require(att['base_excludes_declared_extras'] is True, 'EXPLICIT_NONOVERLAPPING_COST_CONTRACT_REQUIRED')
        require(att['producer'] != att['checker'], 'BUILDER_CHECKER_ROLE_COLLISION')
        require(set(refs(att['asset_ids'])) <= set(assets), 'UNKNOWN_ASSET')
        require(set(refs(att['incentive_ids'])) <= set(rewards), 'UNKNOWN_INCENTIVE')
        require(set(refs(att['shared_cost_ids'])) <= set(shared), 'UNKNOWN_SHARED_COST')
        require(type(action.get('authorized')) is bool, 'EXPLICIT_PLANNING_PERMISSION_REQUIRED')
        require(set(refs(action.get('requires'))) <= set(actions), 'ACTION_DEPENDENCIES_REQUIRED')
        money(action.get('cost'))
        why, item_ids = [], set(att['shared_cost_ids'])
        for aid in att['asset_ids']:
            asset = assets[aid]
            if asset['qualification'] != 'QUALIFIED_IN_SCOPE': why.append('ASSET_NOT_QUALIFIED:' + aid)
            if asset['rights'] != 'PERMITTED': why.append('ASSET_RIGHTS_UNAVAILABLE:' + aid)
            if asset['scope'] != att['scope']: why.append('ASSET_SCOPE_CHANGED:' + aid)
            if asset['expires_hour'] <= context['observed_hour']: why.append('ASSET_REVALIDATION_DUE:' + aid)
            item_ids.update(asset['shared_cost_ids'])
        dependencies = list(action['requires'])
        for item in sorted(item_ids):
            key = 'wheel-cost-shared-' + item
            cost_nodes[key] = (shared[item]['amount_microUSD'], 'shared:' + item)
            dependencies.append(key)
        for rid in sorted(att['incentive_ids']):
            reward = rewards[rid]
            require(reward['adjudicator'] != att['producer'], 'PRODUCER_CANNOT_ADJUDICATE_REWARD')
            if reward['role'] in {'verifier', 'challenger'}:
                require(reward['payee'] != att['producer'], 'PRODUCER_CANNOT_REVIEW_OWN_REWARD')
            # The whole cap is provisioned once, not spent and not counted as actual income.
            key = 'wheel-cost-reward-' + rid
            cost_nodes[key] = (reward['cap_microUSD'], 'incentive:' + rid)
            dependencies.append(key)
        if context['investmentStopped']: why.append('NATIVE_INVESTMENT_STOPPED')
        if not action['authorized']: why.append('ACTION_NOT_ALLOWED_BY_PLANNING_ENVELOPE')
        if why: blocked[name] = sorted(set(why))
        action['authorized'] = action['authorized'] and not why
        action['requires'] = sorted(set(dependencies))
        normalized[name] = action
        expanded.append(action)
    for name, (amount, category) in sorted(cost_nodes.items()):
        expanded.append({'id': name, 'lane': 'instrument', 'catalog_id': None, 'cost': amount,
                         'requires': [], 'exclusive_group': None, 'cash_returns': zero,
                         'evidence': category, 'authorized': not context['investmentStopped']})
    require(len(expanded) <= 32, 'EXPANDED_COST_GRAPH_LIMIT')
    base['actions'] = expanded
    base['funding'] = {'source': context['actions_sha256'], 'available': context['available'],
                       'unrestrictedEarned': context['unrestrictedEarned'],
                       'authorized_allocation': 0 if context['investmentStopped'] else cap}
    result = choose(base, universe)
    selected = [x for x in result['selected'] if x in actions]
    # Remove unattached zero-cost dependency nodes from the presentation only.
    needed = {d for name in selected for d in normalized[name]['requires'] if d in cost_nodes}
    costs = [{'id': name, 'category': cost_nodes[name][1], 'amount_microUSD': cost_nodes[name][0]} for name in sorted(needed)]
    cost = sum(actions[x]['cost'] for x in selected) + sum(x['amount_microUSD'] for x in costs)
    require(cost == result['cost'], 'ALLOCATOR_COST_RECONCILIATION_FAILED')
    return {
        'schema': 'agi-alpha/economic-coupling-proposal/v1', 'scope': 'SIMULATED_SHADOW_PLANNING_ONLY',
        'request_sha256': sha(request), 'context_sha256': sha(context), 'world': context['world'],
        'source_sha256': context['source_sha256'], 'expected_native_actions_sha256': context['actions_sha256'],
        'catalog_sha256': sha(universe), 'compiled_allocation_sha256': sha(base),
        'decision': result['decision'], 'selected_actions': sorted(selected), 'blocked_actions': blocked,
        'shared_and_incentive_provisions': costs, 'total_proposed_commitment_microUSD': cost,
        'planning_budget_microUSD': result.get('budget'), 'allocator': result,
        'incentive_status': 'CAPS_PROVISIONED_IN_PLAN_NOT_PAYABLE_OR_PAID',
        'asset_market_value_microUSD': None, 'execution_authority': False, 'funding_authority': False,
        'current_proof': None, 'authority': [], 'reaudit_before_native_commit': True,
        'limitations': [
            'Native context is valid only when produced by a freshly rederived canonical audit; JSON hashes are not authentication.',
            'Planning permission, asset qualification, reuse rights, role separation and scenario returns are declared inputs, not externally verified by this adapter.',
            'No reserved funds, payouts, collected income, licenses, causal invention benefit or physical capacity are created.',
            'Caps and shared costs consume proposed budget once; actual contingent payment still requires its own contract, evidence and native authorization.',
            'The existing finite allocator is reused. No global market equilibrium or autonomous recursive improvement is claimed.',
        ],
    }


def verify_proposal(proposal, request, context, universe):
    require(type(proposal) is dict and same_canonical(proposal, assess(request, context, universe)), 'PROPOSAL_OR_NATIVE_STATE_CHANGED')
    return {'accepted': True, 'scope': 'RECOMPUTED_PLANNING_CONTRACT_ONLY',
            'context_sha256': sha(context), 'funding_authority': False}
