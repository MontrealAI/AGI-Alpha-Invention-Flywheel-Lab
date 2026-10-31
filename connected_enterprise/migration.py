"""Authenticated continuation of a connected business across source versions."""
from __future__ import annotations
from connected_enterprise.transition_evidence import ticket_body, scoped_business, business_evidence

import copy
import hashlib
import hmac
from pathlib import Path

from commercial.ledger import canonical, digest, strict_json, operating_state_digest
from commercial.persistence import atomic_bytes

POLICY_SCHEMA = 'agi-alpha/connected-prospective-policy/v2'
CALENDAR_POLICY_SCHEMA='agi-alpha/connected-prospective-policy/v3-calendar'
INTENT_SCHEMA = 'agi-alpha/connected-operating-upgrade-intent/v1'


def default_policy():
    return {'schema': POLICY_SCHEMA, 'mode': 'prospective', 'protection_hours': 48,
            'upgrade_cost_microUSD': 1_000_000,
            'residual_microUSD': 0, 'premium_microUSD': 0, 'coverage_limit_microUSD': 0,
            'deductible_microUSD': 0, 'payout_delay_hours': 0, 'exclusions': [],
            'jurisdiction': 'Authored synthetic jurisdiction; no legal finality established',
            'counterparty_obligations': 'Buyer pays modeled price; producer supplies independently accepted artifact; claims remain producer obligations'}


def validate_policy(raw):
    if isinstance(raw,dict) and raw.get('schema')==CALENDAR_POLICY_SCHEMA:
        if set(raw)!=set(default_policy())|{'calendar_until_day'} or type(raw['calendar_until_day']) is not int or not 1<=raw['calendar_until_day']<=365:
            raise ValueError('EXACT_FINITE_CALENDAR_POLICY_REQUIRED')
        base={k:v for k,v in raw.items() if k!='calendar_until_day'};base['schema']=POLICY_SCHEMA
        validate_policy(base)
        return copy.deepcopy(raw)
    current_fields = set(default_policy())
    if not isinstance(raw, dict) or set(raw) not in [current_fields, current_fields - {'upgrade_cost_microUSD'}]:
        raise ValueError('EXACT_PROSPECTIVE_OPERATING_POLICY_REQUIRED')
    p = copy.deepcopy(raw)
    legacy = p.get('schema') == 'agi-alpha/connected-prospective-policy/v1' and set(p) == current_fields - {'upgrade_cost_microUSD'}
    if not (legacy or p.get('schema') == POLICY_SCHEMA and set(p) == current_fields) or p['mode'] not in {'permanent', 'prospective'}:
        raise ValueError('REGISTERED_OPERATING_LIABILITY_POLICY_REQUIRED')
    for key in ['protection_hours', 'residual_microUSD', 'premium_microUSD',
                'coverage_limit_microUSD', 'deductible_microUSD', 'payout_delay_hours']:
        if type(p[key]) is not int or not 0 <= p[key] <= 10**12:
            raise ValueError('BOUNDED_OPERATING_POLICY_INTEGER_REQUIRED')
    if not legacy and (type(p['upgrade_cost_microUSD']) is not int or not 0 <= p['upgrade_cost_microUSD'] <= 10**12):
        raise ValueError('BOUNDED_DECLARED_SOURCE_UPGRADE_INVOICE_REQUIRED')
    if not 1 <= p['protection_hours'] <= 24 * 365:
        raise ValueError('FINITE_POSITIVE_OPERATING_PROTECTION_REQUIRED')
    from commercial.terms import prospective_terms
    prospective_terms('policy-validation', max(1_000_000, p['residual_microUSD']),
                      1 + p['protection_hours'], 1, residual=p['residual_microUSD'],
                      premium=p['premium_microUSD'], coverage_limit=p['coverage_limit_microUSD'],
                      deductible=p['deductible_microUSD'], exclusions=p['exclusions'],
                      payout_delay_hours=p['payout_delay_hours'], jurisdiction=p['jurisdiction'],
                      counterparty_obligations=p['counterparty_obligations'])
    if p['mode'] == 'permanent' and any(p[k] for k in ['residual_microUSD', 'premium_microUSD', 'coverage_limit_microUSD', 'deductible_microUSD', 'payout_delay_hours']):
        raise ValueError('PERMANENT_CONTROL_HAS_NO_PROSPECTIVE_CHARGES_OR_COVERAGE')
    return p


def effective_horizon(state):
    horizon=state['config']['horizon_days']
    for row in state.get('calendar_extensions',[]):
        if (not isinstance(row,dict) or set(row)!={'from_day','until_day','ticket_sha256','prior_checkpoint_sha256'}
            or type(row['from_day']) is not int or row['from_day']!=horizon
            or type(row['until_day']) is not int or not horizon<row['until_day']<=365):
            raise ValueError('APPEND_ONLY_FINITE_CALENDAR_REQUIRED')
        horizon=row['until_day']
    return horizon


def _calendar_authority(op,state):
    if op['policy']['schema']!=CALENDAR_POLICY_SCHEMA:return None
    old=effective_horizon(state);new=op['policy']['calendar_until_day']
    if state['queue'] or state['current'] is not None or not (old-1)*24<=state['last_time']<24*old or new<=old:
        raise ValueError('COMPLETED_CALENDAR_PREFIX_REQUIRED')
    days=[e['time']//24 for e in state['events'] if e['kind']=='BUSINESS_DECISION']
    if days!=list(range(old)) or any(e['time']%24 for e in state['events'] if e['kind']=='BUSINESS_DECISION'):
        raise ValueError('EXACT_COMPLETED_CALENDAR_PREFIX_REQUIRED')
    prior=copy.deepcopy(state.get('prospective_policy'))
    if not isinstance(prior,dict):raise ValueError('EXISTING_TERMS_REQUIRED_FOR_CALENDAR_EXTENSION')
    proposed=copy.deepcopy(op['policy'])
    for policy in [prior,proposed]:
        policy.pop('calendar_until_day',None);policy['schema']=POLICY_SCHEMA
    if prior!=proposed:raise ValueError('CALENDAR_EXTENSION_MUST_PRESERVE_TERMS')
    return old,new


def terms_for(order_id, price, collection, policy, fee, *, deadline=None):
    from commercial.terms import prospective_terms
    p = validate_policy(policy)
    if p['mode'] == 'permanent':
        return None
    return prospective_terms(order_id, price, max(collection, deadline or collection) + p['protection_hours'], collection,
                             residual=p['residual_microUSD'], premium=p['premium_microUSD'], fee=fee,
                             coverage_limit=p['coverage_limit_microUSD'], deductible=p['deductible_microUSD'],
                             exclusions=p['exclusions'], payout_delay_hours=p['payout_delay_hours'],
                             jurisdiction=p['jurisdiction'], counterparty_obligations=p['counterparty_obligations'])


def _read(path):
    path = Path(path).absolute()
    if not path.is_file() or any(p.is_symlink() for p in [path, *path.parents]) or path.stat().st_size > 64_000_000:
        raise ValueError('BOUNDED_REGULAR_OPERATING_UPGRADE_FILE_REQUIRED')
    return strict_json(path.read_bytes())


def _write(path, value):
    atomic_bytes(Path(path), canonical(value) + b'\n')


def validate_operating_authority(ticket, *, key=None, root=None):
    body = ticket_body(ticket)
    op = body.get('operating')
    if not isinstance(op, dict) or set(op) != {'schema', 'prior_checkpoint', 'from_runtime', 'to_runtime', 'policy'} or op['schema'] != 'agi-alpha/connected-operating-transition/v1':
        raise ValueError('EXACT_OPERATING_TRANSITION_AUTHORITY_REQUIRED')
    validate_policy(op['policy'])
    envelope = op['prior_checkpoint']
    if not isinstance(envelope, dict) or set(envelope) != {'body', 'signature'}:
        raise ValueError('ORIGINAL_SIGNED_OPERATING_CHECKPOINT_REQUIRED')
    checkpoint = envelope['body']
    expected = {'schema', 'scope', 'contract', 'source_sha256', 'manifest_sha256',
                'native_sequence', 'native_actions_sha256', 'state'}
    if not isinstance(checkpoint, dict) or set(checkpoint) != expected:
        raise ValueError('EXACT_PRIOR_OPERATING_CHECKPOINT_REQUIRED')
    if key is not None:
        signature = hmac.new(key, b'connected014-operating-state\n' + canonical(checkpoint), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(envelope['signature']), signature):
            raise ValueError('PRIOR_OPERATING_CHECKPOINT_SIGNATURE_MISMATCH')
    prior = body['prior_record']['ledger']; state = checkpoint['state']
    if prior['summary']['available'] < op['policy'].get('upgrade_cost_microUSD', 0):
        raise ValueError('OPERATING_UPGRADE_INVOICE_EXCEEDS_UNCOMMITTED_CASH')
    n = checkpoint['native_sequence']
    if (checkpoint['schema'] != 'agi-alpha/connected014-operating-checkpoint/v1'
            or checkpoint['scope'] != 'SIMULATED_LOCAL_POSIX'
            or checkpoint['contract'] != prior['config']['contract']
            or checkpoint['manifest_sha256'] != prior['config']['manifest_sha256']
            or checkpoint['source_sha256'] != body['from_source']['sha256']
            or type(n) is not int or not 0 <= n <= len(prior['actions'])
            or checkpoint['native_actions_sha256'] != digest(prior['actions'][:n])):
        raise ValueError('OPERATING_UPGRADE_ORIGINAL_NATIVE_PREFIX_CHANGED')
    if not isinstance(state, dict) or state.get('schema') != 'agi-alpha/connected014-live/v1' or state.get('source') != op['from_runtime']:
        raise ValueError('OPERATING_UPGRADE_SOURCE_OR_STATE_CHANGED')
    if type(state.get('processed_events')) is not int or not isinstance(state.get('queue'), list) or not isinstance(state.get('orders'), list):
        raise ValueError('OPERATING_UPGRADE_QUEUE_AND_PROVENANCE_REQUIRED')
    if body['day'] < state['last_time'] or state['queue'] and body['day'] > state['queue'][0]['time']:
        raise ValueError('OPERATING_UPGRADE_CLOCK_PAST_QUEUED_WORK')
    extension=_calendar_authority(op,state)
    if extension is not None and body['day']!=state['last_time']:raise ValueError('CALENDAR_EXTENSION_CLOCK_CHANGED')
    for runtime, finance in [(op['from_runtime'], body['from_source']), (op['to_runtime'], body['to_source'])]:
        if (not isinstance(runtime, dict) or set(runtime) != {'files', 'sha256'}
                or digest(runtime['files']) != runtime['sha256']
                or any(runtime['files'].get(name) != sha for name, sha in finance['files'].items())):
            raise ValueError('OPERATING_AND_FINANCIAL_SOURCE_VERSIONS_DIFFER')
    if root is not None:
        from .verify import check_source
        check_source(root, op['to_runtime'])
    return op


def migrated_state(ticket):
    op = validate_operating_authority(ticket)
    state = copy.deepcopy(op['prior_checkpoint']['body']['state'])
    history = state.get('operating_upgrades', [])
    if any(row['id'] == ticket_body(ticket)['id'] for row in history):
        raise ValueError('OPERATING_TRANSITION_REPLAY_OR_FORK')
    state.setdefault('origin_source', copy.deepcopy(state['source']))
    state['source'] = copy.deepcopy(op['to_runtime'])
    state['prospective_policy'] = copy.deepcopy(op['policy'])
    extension=_calendar_authority(op,op['prior_checkpoint']['body']['state'])
    if extension is not None:
        old,new=extension
        state['calendar_extensions']=copy.deepcopy(state.get('calendar_extensions',[]))+[{'from_day':old,'until_day':new,'ticket_sha256':digest(ticket),'prior_checkpoint_sha256':digest(op['prior_checkpoint'])}]
        from .engine import _schedule
        for day in range(old,new):_schedule(state,day*24,'plan',f'plan-{day:04d}')
    state['operating_upgrades'] = copy.deepcopy(history) + [{
        'id': ticket_body(ticket)['id'], 'ticket_sha256': digest(ticket),
        'prior_checkpoint_sha256': digest(op['prior_checkpoint']),
        'from_runtime_sha256': op['from_runtime']['sha256'],
        'to_runtime_sha256': op['to_runtime']['sha256'], 'policy': copy.deepcopy(op['policy'])}]
    invoice = op['policy'].get('upgrade_cost_microUSD', 0)
    if invoice:
        state['costs'].append({'id': 'source-upgrade-' + ticket_body(ticket)['id'], 'amount': invoice,
                               'category': 'source_upgrade_integration', 'time': ticket_body(ticket)['day'],
                               'funding_receipt': {'funding': 'OPERATING_CASH', 'authorization_sha256': digest(ticket),
                                                   'scope': 'Declared modeled upgrade invoice; actual engineering/host/model billing unknown'}})
    return state


def _receipt(ticket, record, account_path):
    body = ticket_body(ticket); original = body['operating']['prior_checkpoint']; expected = migrated_state(ticket)
    transitions = [e for e in record['ledger']['actions'] if e['op'] == 'source_transition' and e['args']['id'] == body['id']]
    if len(transitions) != 1 or transitions[0]['before'] != transitions[0]['after']:
        raise ValueError('EXACT_MONETARY_CONTINUITY_TRANSITION_REQUIRED')
    return {'schema': 'agi-alpha/connected-operating-migration/v1', 'accepted': True,
            'id': body['id'], 'ticket_sha256': digest(ticket), 'account_path': str(account_path),
            'original_checkpoint_sha256': digest(original), 'migrated_state_sha256': digest(expected),
            'transition_sequence': transitions[0]['seq'], 'monetary_summary_before': transitions[0]['before'],
            'monetary_summary_after': transitions[0]['after'],
            'preserved_queue_sha256': digest(original['body']['state']['queue']),
            'preserved_current_sha256': digest(original['body']['state']['current']),
            'preserved_order_provenance_sha256': digest(original['body']['state']['orders']),
            'original_signed_journal_sha256': digest(body['prior_envelope']),
            'modeled_upgrade_cost_microUSD': body['operating']['policy'].get('upgrade_cost_microUSD', 0),
            'scope': 'Authenticated local synthetic business continuation; no external account authority',
            **({'appended_calendar_queue_sha256':digest(expected['queue']),
                'prior_queue_is_preserved_prefix':expected['queue'][:len(original['body']['state']['queue'])]==original['body']['state']['queue'],
                'calendar_until_day':effective_horizon(expected)} if body['operating']['policy']['schema']==CALENDAR_POLICY_SCHEMA else {})}


def _preserve(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and _read(path) != value:
        raise ValueError('IMMUTABLE_OPERATING_UPGRADE_HISTORY_CHANGED')
    if not path.exists():
        _write(path, value)


@scoped_business
def recover_upgrade(root, manifest, output, *, failpoint=None):
    from .finance import JournalAccount
    output = Path(output).absolute()
    intent = _read(output / 'MIGRATION_INTENT.json')
    if set(intent) != {'schema', 'ticket', 'manifest_sha256'} or intent['schema'] != INTENT_SCHEMA or intent['manifest_sha256'] != digest(manifest):
        raise ValueError('OPERATING_UPGRADE_INTENT_AUTHORITY_CHANGED')
    ticket = intent['ticket']; body = ticket_body(ticket); cfg = body['prior_record']['ledger']['config']
    from .upgrades import validate_ticket
    validate_ticket(ticket, root=root, path=output / 'account.sqlite')
    expected = migrated_state(ticket)
    original = body['operating']['prior_checkpoint']
    with JournalAccount.upgrade_source(root, manifest, output / 'account.sqlite', opening=cfg['opening'],
                                     working=cfg['working'], contract=cfg['contract'], authorization=ticket) as account:
        validate_ticket(ticket, key=account._account._key, root=root, path=account.path)
        current = _read(output / 'STATE.json')
        if failpoint:
            failpoint('after_financial_transition', account)
        if current == original:
            tape = account.export()['ledger']; markers = [e for e in tape['actions'] if e['op'] == 'operating_checkpoint' and e['seq'] >= len(body['prior_record']['ledger']['actions'])]
            if markers and markers[-1]['args']['state_sha256'] != operating_state_digest(expected):
                raise ValueError('OPERATING_HISTORY_REWIND_FORBIDDEN')
            if not markers:
                tail = tape['actions'][len(body['prior_record']['ledger']['actions']):]
                allowed_cost = 'source-upgrade-' + body['id']
                if any(e['op'] != 'source_transition' and not (e['op'] == 'cost' and e['args']['id'] == allowed_cost) for e in tail):
                    raise ValueError('OPERATING_HISTORY_REWIND_FORBIDDEN')
            invoice = body['operating']['policy'].get('upgrade_cost_microUSD', 0)
            if invoice:
                account.cost('source-upgrade-' + body['id'], invoice, body['day'])
            account.save_checkpoint(output / 'STATE.json', expected)
        else:
            state = account.verify_checkpoint(current)
            history = state.get('operating_upgrades', [])
            if not any(row == expected['operating_upgrades'][-1] for row in history):
                raise ValueError('OPERATING_UPGRADE_CHECKPOINT_CONFLICT_NO_REWIND')
        if failpoint:
            failpoint('after_operating_checkpoint', account)
        record = account.export()
        receipt = _receipt(ticket, record, account.path)
        path = output / 'MIGRATION_RECEIPT.json'
        if path.exists() and _read(path) != receipt:
            prior = _read(path); previous = record.get('source_transitions', {}).get(prior.get('id'))
            archived = output / 'MIGRATION_HISTORY' / (str(prior.get('ticket_sha256')) + '.receipt.json')
            if (previous is None or ticket_body(previous)['counter'] >= body['counter']
                    or prior != _receipt(previous, record, account.path)
                    or not archived.exists() or _read(archived) != prior):
                raise ValueError('OPERATING_MIGRATION_RECEIPT_CHANGED')
        _write(path, receipt)
        return receipt


def _upgrade_world(root, historical_root, manifest, output, *, policy, expected_checkpoint_sha256, ident, failpoint=None):
    from enterprise.runner import RunLock
    from .runner import identity
    from .upgrades import authorize_upgrade
    from .verify import check_source
    output = Path(output).absolute(); root = Path(root).absolute()
    with RunLock(output):
        intent_path = output / 'MIGRATION_INTENT.json'
        policy = validate_policy(policy)
        if policy['schema'] not in {POLICY_SCHEMA,CALENDAR_POLICY_SCHEMA}:
            raise ValueError('NEW_OPERATING_UPGRADE_REQUIRES_CURRENT_COSTED_POLICY')
        predecessor = None
        if intent_path.exists():
            predecessor = _read(intent_path); prior = ticket_body(predecessor['ticket'])
            if prior['id'] == ident:
                if (prior['operating']['policy'] != policy
                        or digest(prior['operating']['prior_checkpoint']) != expected_checkpoint_sha256):
                    raise ValueError('OPERATING_UPGRADE_RETRY_AUTHORITY_CHANGED')
                return recover_upgrade(root, manifest, output, failpoint=failpoint)
            if digest(prior['operating']['prior_checkpoint']) == expected_checkpoint_sha256:
                raise ValueError('OPERATING_UPGRADE_RETRY_AUTHORITY_CHANGED')
        checkpoint = _read(output / 'STATE.json')
        if digest(checkpoint) != expected_checkpoint_sha256:
            raise ValueError('STALE_OPERATING_UPGRADE_CHECKPOINT')
        state = checkpoint['body']['state']; cfg = state['config']
        check_source(historical_root, state['source'])
        origin = state.get('origin_source', state['source'])
        contract = 'connected014/' + digest({'config': cfg, 'seed': state['seed'], 'arm': state['arm'], 'source': origin, 'manifest': manifest})
        day = max(state['last_time'], state['current']['event']['time'] if state['current'] else state['last_time'])
        operating = {'schema': 'agi-alpha/connected-operating-transition/v1', 'prior_checkpoint': checkpoint,
                     'from_runtime': state['source'], 'to_runtime': identity(root), 'policy': policy}
        ticket = authorize_upgrade(historical_root=historical_root, target_root=root, manifest=manifest,
                                   path=output / 'account.sqlite', opening=cfg['opening'], working=cfg['working'],
                                   contract=contract, expected_state_digest=None, ident=ident, day=day, operating=operating, evidence_dir=output/'transition-evidence')
        if _read(output / 'STATE.json') != checkpoint:
            raise ValueError('OPERATING_CHECKPOINT_ADVANCED_DURING_AUTHORIZATION')
        with business_evidence(output):
            validate_operating_authority(ticket, root=root)
        if predecessor is not None:
            previous = predecessor['ticket']; previous_body = ticket_body(previous); record = ticket_body(ticket)['prior_record']
            if (record.get('source_transitions', {}).get(previous_body['id']) != previous
                    or ticket_body(ticket)['counter'] != previous_body['counter'] + 1
                    or ticket_body(ticket)['from_source'] != previous_body['to_source']):
                raise ValueError('OPERATING_PREDECESSOR_INTENT_NOT_AUTHENTICATED')
            previous_receipt = _receipt(previous, record, output / 'account.sqlite')
            receipt_path = output / 'MIGRATION_RECEIPT.json'
            if receipt_path.exists() and _read(receipt_path) != previous_receipt:
                raise ValueError('OPERATING_MIGRATION_RECEIPT_CHANGED')
            sha = digest(previous)
            _preserve(output / 'MIGRATION_HISTORY' / (sha + '.intent.json'), predecessor)
            _preserve(output / 'MIGRATION_HISTORY' / (sha + '.receipt.json'), previous_receipt)
        _write(intent_path, {'schema': INTENT_SCHEMA, 'ticket': ticket, 'manifest_sha256': digest(manifest)})
        if failpoint:
            failpoint('after_upgrade_intent', None)
        return recover_upgrade(root, manifest, output, failpoint=failpoint)


def check_lineage(result, manifest):
    history = result.get('operating_upgrades', [])
    if not history and any(k in result for k in ['origin_source', 'prospective_policy', 'operating_upgrades']):
        raise ValueError('OPERATING_ORIGIN_OR_POLICY_WITHOUT_AUTHENTICATED_TRANSITION')
    transitions = result['owned_account'].get('source_transitions', {})
    expected = [];expected_calendar=[]
    previous = None
    for native in result['owned_account']['ledger']['actions']:
        if native['op'] != 'source_transition':
            continue
        ticket = transitions[native['args']['id']]
        if 'operating' not in ticket_body(ticket):
            raise ValueError('OPERATING_HISTORY_REQUIRES_QUEUE_TRANSITION_AUTHORITY')
        op = validate_operating_authority(ticket)
        state = migrated_state(ticket)
        if previous is not None and op['from_runtime'] != previous:
            raise ValueError('OPERATING_RUNTIME_VERSION_CHAIN_BROKEN')
        old = op['prior_checkpoint']['body']['state']
        if old.get('calendar_extensions',[])!=expected_calendar:raise ValueError('CALENDAR_PREFIX_AUTHORITY_CHANGED')
        expected_calendar=state.get('calendar_extensions',[])
        if any(old[k] != result[k] for k in ['config', 'seed', 'arm']):
            raise ValueError('OPERATING_TRANSITION_BUSINESS_IDENTITY_CHANGED')
        expected.append(state['operating_upgrades'][-1]); previous = op['to_runtime']
        for key in ['orders', 'costs', 'events', 'decisions', 'investments']:
            if result[key][:len(old[key])] != old[key]:
                if key == 'orders' and op['policy']['schema']!=CALENDAR_POLICY_SCHEMA:
                    immutable = ['id', 'customer_id', 'job_id', 'offer', 'price', 'qualified_time', 'production_time', 'complete_cost', 'funding_receipt']
                    if len(result[key]) >= len(old[key]) and all(all(a.get(k) == b.get(k) for k in immutable) for a, b in zip(old[key], result[key])):
                        continue
                raise ValueError('OPERATING_TRANSITION_LOST_OR_REWROTE_HISTORY:' + key)
    if history != expected or history and (result['source'] != previous or result.get('prospective_policy') != history[-1]['policy']):
        raise ValueError('OPERATING_SOURCE_HISTORY_NOT_AUTHORIZED')
    if result.get('calendar_extensions',[])!=expected_calendar:raise ValueError('CALENDAR_EXTENSION_NOT_AUTHENTICATED')
    origin = result.get('origin_source', result['source'])
    if history:
        first = ticket_body(transitions[history[0]['id']])['operating']['prior_checkpoint']['body']['state']
        if origin != first.get('origin_source', first['source']):
            raise ValueError('OPERATING_ORIGINAL_SOURCE_OR_IDENTITY_CHANGED')
    contract = 'connected014/' + digest({'config': result['config'], 'seed': result['seed'], 'arm': result['arm'], 'source': origin, 'manifest': manifest})
    if result['owned_account']['ledger']['config']['contract'] != contract:
        raise ValueError('FROZEN_SOURCE_CONFIG_SEED_ARM_ACCOUNT_BINDING_CHANGED')
    return {'operating_source_transitions_checked':len(history),'original_contract':contract,'calendar_extensions_checked':len(expected_calendar),'effective_horizon_days':effective_horizon(result)}


def upgrade_world(root,historical_root,manifest,output,**kwargs):
    output=Path(output).absolute();store=output/'transition-evidence'
    if any(p.is_symlink() for p in [store,*store.parents]):raise ValueError('EVIDENCE_DIRECTORY_SYMLINK_REFUSED')
    store.mkdir(mode=0o700,exist_ok=True)
    with business_evidence(output):return _upgrade_world(root,historical_root,manifest,output,**kwargs)
