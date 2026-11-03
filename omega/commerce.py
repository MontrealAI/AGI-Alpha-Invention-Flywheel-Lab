"""Offline seller workflow fixtures; no payment network and no financial ledger.

Receipts are deliberately synthetic and cannot be posted as native product sales.
The existing JournalAccount remains the sole financial authority. A missing
original account is a recovery dependency, never permission to replace its seed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from omega.seller import MICRO, OFFERS, declared_registration, replay_audit

SCOPE = 'AUTHORED_WORKFLOW_FIXTURE_NOT_DEMAND_OR_NATIVE_REVENUE'
PAID = ('self_hosted', 'group_webinar', 'founder_private')
BASE = Path(__file__).resolve().parents[1]
TERMS = {
    'self_hosted': {'purpose': 'Defined self-hosted Genesis edition and its documentation.',
        'prerequisites': 'Compatible buyer hardware, chosen model resources and setup ability.',
        'deliverable': 'Versioned bytes, setup guide, first workflow and diagnostics.',
        'exclusions': 'No continuing updates, personal support, earnings or unlimited AI promise.'},
    'group_webinar': {'purpose': 'Optional product orientation and bounded group questions.',
        'prerequisites': 'Compatible Zoom client; Eventbrite and licensed Zoom arrangements unresolved.',
        'deliverable': 'One authored 90-minute session; maximum 500 attendees.',
        'exclusions': 'No deployment, individual implementation or continuing advice.'},
    'founder_private': {'purpose': 'A bounded decision review of one buyer-supplied question.',
        'prerequisites': 'Brief, desired decision, relevant evidence and permission to discuss it.',
        'deliverable': '30-minute conversation and a concise decision/next-test note.',
        'exclusions': 'No complete deployment, earnings guarantee or continuing follow-up.'},
}
COST_POLICY = {
    'scope': 'AUTHORED_USD_COST_ENVELOPE_NOT_PROVIDER_QUOTE_OR_INVOICE',
    'processing_bps': 350, 'processing_fixed_microUSD': 300_000,
    'event_ticket_bps': 700, 'event_ticket_fixed_microUSD': 2 * MICRO,
    'dispute_fee_microUSD': 20 * MICRO,
    'acquisition_microUSD': {'self_hosted': 25 * MICRO, 'group_webinar': 15 * MICRO,
                            'founder_private': 500 * MICRO},
    'delivery_microUSD': {'self_hosted': MICRO, 'group_webinar': 2 * MICRO,
                         'founder_private': 10 * MICRO},
    'founder_opportunity_microUSD_per_hour': 2000 * MICRO,
    'webinar_minutes': {'preparation': 180, 'presentation': 90, 'administration': 60},
    'private_minutes': {'prerequisite_review': 15, 'preparation': 45,
                        'conversation': 30, 'deliverable_and_administration': 15},
    'exception_minutes': 12, 'dispute_review_minutes': 20,
    'unknown_complete_costs': ['actual acquisition/conversion', 'hosting at scale',
        'documentation and maintenance allocation', 'security incidents and mandatory obligations',
        'actual payment/FX fees and payout delays', 'fraud losses beyond these fixtures',
        'applicable indirect and income taxes', 'legal/platform requirements',
        'actual model/host billing', 'buyer adoption and operating effort'],
    'capex_policy': 'No asset purchase modeled; software/research expensed in original native arm.',
    'depreciation_policy': 'No capitalized asset in this fixture; not a claim that real depreciation is zero.',
    'financing_policy': 'No financing, reinvestment, account creation or seed in workflow fixtures.',
}


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('NONNEGATIVE_INTEGER_REQUIRED:' + name)
    return value


def _identifier(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError('BOUNDED_NONEMPTY_IDENTIFIER_REQUIRED')
    return value


def offer(ident):
    if ident not in PAID:
        raise ValueError('KNOWN_OPTIONAL_OFFER_REQUIRED')
    return {'id': ident, 'price_microUSD': OFFERS[ident]['price_usd'] * MICRO,
            'currency': 'USD', 'currency_status': 'model convention, commercial currency unconfirmed',
            'scope': SCOPE, 'terms': TERMS[ident], 'ongoing_support': False,
            'license_status': 'ROOT_REDISTRIBUTION_LICENSE_UNRESOLVED',
            'outside_options': ['do_not_purchase', 'free_core_if_rights_resolved',
                                'competent_conventional_tools', 'other_autonomous_products'],
            'cost_policy_sha256': digest(COST_POLICY)}


def documentation_help(code):
    path = BASE / 'omega/README.md'
    document = path.read_text()
    searches = {'MODEL_UNAVAILABLE': 'default path is entirely local deterministic',
                'INSUFFICIENT_RESOURCES': 'Python 3.12.',
                'INPUT_UNCLEAR': 'Edit the request, construct/check'}
    needle = searches.get(code)
    match = next((line.strip() for line in document.splitlines()
                  if needle and needle in line), None)
    return {'resolved': False, 'known_diagnostic': bool(match),
            'guidance': match or 'No documented resolution found; stop and retain the diagnostic.',
            'document': 'omega/README.md', 'document_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'scope': 'DETERMINISTIC_DOCUMENT_LOOKUP_NOT_MODEL_ASSISTANT',
            'next': 'Review documented local path and resources; no automatic external transfer.' if match
                    else 'Unresolved exception requires bounded founder review or withdrawal.'}


class CommerceFixture:
    """Atomic, replayed workflow commands. No cash balance or ledger is stored."""
    def __init__(self, path, artifact, *, founder_budget_minutes=600):
        self.path, self.artifact = Path(path).absolute(), Path(artifact).absolute()
        _integer(founder_budget_minutes, 'founder_budget_minutes')
        if any(p.is_symlink() for p in [self.path, self.artifact, *self.path.parents, *self.artifact.parents]):
            raise ValueError('REGULAR_LOCAL_WORKFLOW_PATH_REQUIRED')
        if not self.artifact.is_file() or self.artifact.stat().st_size > 16_000_000:
            raise ValueError('BOUNDED_ACTUAL_ARTIFACT_REQUIRED')
        with self.artifact.open('rb') as stream:
            initial_artifact = stream.read(16_000_001)
        if len(initial_artifact) > 16_000_000:
            raise ValueError('BOUNDED_ACTUAL_ARTIFACT_REQUIRED')
        self.meta = {'schema': 'omega/commerce-fixture/v1', 'scope': SCOPE,
                     'artifact_sha256': hashlib.sha256(initial_artifact).hexdigest(),
                     'artifact_bytes': len(initial_artifact),
                     'founder_budget_minutes': founder_budget_minutes,
                     'terms_sha256': digest(TERMS), 'cost_policy_sha256': digest(COST_POLICY),
                     'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        self.db = None
        try:
            if self.path.exists():
                if not self.path.is_file():
                    raise ValueError('EXISTING_OWNED_WORKFLOW_REQUIRED')
                self.db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, isolation_level=None)
                self._check_identity()
                self.audit()
                self.db.close()
                self.db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, isolation_level=None)
                self._check_identity()
                self.audit()
            else:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                self.db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, isolation_level=None)
                self.db.execute('BEGIN IMMEDIATE')
                self.db.execute('CREATE TABLE metadata (id INTEGER PRIMARY KEY, value BLOB NOT NULL)')
                self.db.execute('CREATE TABLE commands (seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, request BLOB NOT NULL, receipt BLOB NOT NULL)')
                self.db.execute('INSERT INTO metadata VALUES (1,?)', (canonical(self.meta),))
                self.db.execute('COMMIT')
            self.db.execute('PRAGMA synchronous=FULL')
        except BaseException:
            if self.db is not None:
                self.db.close()
            raise

    def _check_identity(self):
        tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables != {'metadata', 'commands'}:
            raise ValueError('EXISTING_OWNED_WORKFLOW_REQUIRED')
        if self.db.execute('SELECT id,value FROM metadata ORDER BY id').fetchall() != [(1, canonical(self.meta))]:
            raise ValueError('WORKFLOW_SOURCE_TERMS_OR_ARTIFACT_CHANGED')
        if [r[1:3] for r in self.db.execute('PRAGMA table_info(commands)')] != [('seq', 'INTEGER'), ('id', 'TEXT'), ('request', 'BLOB'), ('receipt', 'BLOB')]:
            raise ValueError('EXACT_WORKFLOW_COMMAND_SCHEMA_REQUIRED')

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _state(self):
        state = {'orders': {}, 'sessions': {}, 'founder_reserved_minutes': 0,
                 'founder_required_minutes': 0, 'exceptions': [], 'last_hour': 0}
        for seq, raw, receipt in self.db.execute('SELECT seq,request,receipt FROM commands ORDER BY seq'):
            request = strict_json(raw)
            derived = self._apply(state, request, verify_bytes=False)
            if canonical(derived) != receipt:
                raise ValueError('WORKFLOW_REPLAY_RECEIPT_CHANGED:' + str(seq))
        return state

    def _apply(self, state, request, *, verify_bytes):
        op, ident, payload, hour = (request[k] for k in ('operation', 'order_id', 'payload', 'hour'))
        if hour < state['last_hour']:
            raise ValueError('WORKFLOW_TIME_REGRESSION')
        state['last_hour'] = hour
        orders = state['orders']
        if op == 'discover':
            if ident in orders or set(payload) != {'offer_id', 'session_id'}:
                raise ValueError('NEW_ORDER_WITH_EXACT_OFFER_INPUT_REQUIRED')
            quote = offer(payload['offer_id'])
            if quote['id'] != 'self_hosted':
                _identifier(payload['session_id'])
            elif payload['session_id'] is not None:
                raise ValueError('DOWNLOAD_HAS_NO_FOUNDER_SESSION')
            orders[ident] = {'offer': quote, 'state': 'explained', 'session_id': payload['session_id'],
                            'captured': False, 'settled': False, 'payout_held': False,
                            'refunded': False, 'disputed': False, 'active_dispute': False,
                            'dispute_lost': False, 'entitled': False, 'delivered': False,
                            'download_requested': False,
                            'onboarded': False, 'processing_microUSD': 0, 'dispute_fee_microUSD': 0}
            return {'scope': SCOPE, 'state': 'explained', 'offer': quote}
        if ident not in orders:
            raise ValueError('EXPLAINED_ORDER_REQUIRED')
        row = orders[ident]
        if op == 'choose':
            if set(payload) != {'consent'} or type(payload['consent']) is not bool or row['state'] != 'explained':
                raise ValueError('EXPLICIT_ONCE_ONLY_CHOICE_REQUIRED')
            row['state'] = 'selected' if payload['consent'] else 'declined'
        elif op == 'payment':
            if set(payload) != {'status', 'provider'} or payload['provider'] != 'TEST_DOUBLE' or payload['status'] not in {'succeeded', 'failed', 'unavailable'}:
                raise ValueError('EXPLICIT_SIMULATED_PROVIDER_RESULT_REQUIRED')
            if row['state'] not in {'selected', 'payment_failed'}:
                raise ValueError('CONSENTED_UNPAID_ORDER_REQUIRED')
            if payload['status'] != 'succeeded':
                row['state'] = 'payment_failed'
            else:
                self._reserve_session(state, row)
                row['captured'], row['state'] = True, 'payment_captured'
                kind = row['offer']['id']
                bps = COST_POLICY['event_ticket_bps'] if kind == 'group_webinar' else COST_POLICY['processing_bps']
                fixed = COST_POLICY['event_ticket_fixed_microUSD'] if kind == 'group_webinar' else COST_POLICY['processing_fixed_microUSD']
                row['processing_microUSD'] = (row['offer']['price_microUSD'] * bps + 9999) // 10000 + fixed
        elif op == 'settle':
            if set(payload) != {'status', 'provider'} or payload['provider'] != 'TEST_DOUBLE' or payload['status'] not in {'settled', 'held'} or not row['captured'] or row['settled']:
                raise ValueError('EXPLICIT_UNSETTLED_TEST_PAYMENT_REQUIRED')
            row['settled'] = payload['status'] == 'settled'
            row['payout_held'] = not row['settled']
        elif op == 'entitle':
            if payload or row['state'] != 'payment_captured':
                raise ValueError('CAPTURED_PAYMENT_REQUIRED_FOR_ENTITLEMENT')
            row['entitled'], row['state'] = True, 'entitled'
        elif op in {'download', 'download_complete', 'deliver_session'}:
            if not row['entitled'] or row['delivered'] or row['active_dispute']:
                raise ValueError('ACTIVE_UNDELIVERED_ENTITLEMENT_REQUIRED')
            if op == 'download':
                if payload or row['offer']['id'] != 'self_hosted' or row['download_requested']:
                    raise ValueError('DOWNLOAD_OFFER_REQUIRED')
                if verify_bytes:
                    self._read_artifact()
                row['download_requested'], row['state'] = True, 'download_ready'
            elif op == 'download_complete':
                if set(payload) != {'destination', 'artifact_sha256', 'artifact_bytes'} or not row['download_requested'] or row['offer']['id'] != 'self_hosted' or payload['artifact_sha256'] != self.meta['artifact_sha256'] or type(payload['artifact_bytes']) is not int or payload['artifact_bytes'] != self.meta['artifact_bytes']:
                    raise ValueError('VERIFIED_DOWNLOAD_COMPLETION_REQUIRED')
                destination = Path(payload['destination'])
                if not destination.is_absolute() or destination in {self.artifact, self.path}:
                    raise ValueError('SEPARATE_ABSOLUTE_DOWNLOAD_DESTINATION_REQUIRED')
                if verify_bytes:
                    self._verify_destination(destination)
                row['delivered'], row['state'] = True, 'delivered'
                row['download_receipt'] = payload
            else:
                if row['offer']['id'] == 'self_hosted' or payload != {'founder_supplied': 'SIMULATED_RECEIPT'}:
                    raise ValueError('EXPLICIT_FOUNDER_DELIVERY_TEST_DOUBLE_REQUIRED')
                session = state['sessions'][row['session_id']]
                if not session['delivered']:
                    state['founder_required_minutes'] += session['minutes']
                    session['delivered'] = True
                row['delivered'], row['state'] = True, 'delivered'
        elif op == 'onboard':
            if payload or not row['delivered'] or not row['entitled'] or row['onboarded']:
                raise ValueError('ACTIVE_DELIVERED_ORDER_REQUIRED')
            row['onboarded'], row['state'] = True, 'onboarded'
        elif op == 'help':
            if set(payload) != {'code'} or not row['entitled']:
                raise ValueError('ACTIVE_ENTITLEMENT_AND_DIAGNOSTIC_REQUIRED')
            result = documentation_help(payload['code'])
            if not result['known_diagnostic']:
                state['exceptions'].append({'order_id': ident, 'cause': payload['code'], 'minutes': COST_POLICY['exception_minutes']})
                state['founder_required_minutes'] += COST_POLICY['exception_minutes']
            return {'scope': SCOPE, 'state': row['state'], **result}
        elif op == 'refund':
            if payload or not row['captured'] or row['refunded'] or row['active_dispute'] or row['dispute_lost']:
                raise ValueError('CAPTURED_UNREFUNDED_UNDISPUTED_ORDER_REQUIRED')
            row['refunded'], row['entitled'], row['state'] = True, False, 'refunded'
        elif op == 'dispute':
            if payload or not row['captured'] or row['disputed']:
                raise ValueError('CAPTURED_UNDISPUTED_ORDER_REQUIRED')
            row['disputed'], row['active_dispute'], row['entitled'], row['state'] = True, True, False, 'disputed'
            row['dispute_fee_microUSD'] = COST_POLICY['dispute_fee_microUSD']
            state['founder_required_minutes'] += COST_POLICY['dispute_review_minutes']
            state['exceptions'].append({'order_id': ident, 'cause': 'payment_dispute', 'minutes': COST_POLICY['dispute_review_minutes']})
        elif op == 'resolve_dispute':
            if set(payload) != {'result'} or payload['result'] not in {'seller_wins', 'buyer_wins'} or row['state'] != 'disputed':
                raise ValueError('EXPLICIT_DISPUTE_RESULT_REQUIRED')
            row['dispute_lost'] = payload['result'] == 'buyer_wins'
            row['active_dispute'] = False
            row['entitled'] = not row['dispute_lost'] and not row['refunded']
            row['state'] = 'dispute_lost' if row['dispute_lost'] else 'dispute_won'
        else:
            raise ValueError('KNOWN_WORKFLOW_OPERATION_REQUIRED')
        return {'scope': SCOPE, 'state': row['state'], 'order_id': ident,
                'artifact_sha256': self.meta['artifact_sha256'] if op in {'download', 'download_complete'} else None,
                'artifact_bytes': self.meta['artifact_bytes'] if op in {'download', 'download_complete'} else None}

    def _reserve_session(self, state, row):
        kind, ident = row['offer']['id'], row['session_id']
        exception_minutes = sum(item['minutes'] for item in state['exceptions'])
        if state['founder_reserved_minutes'] + exception_minutes > self.meta['founder_budget_minutes']:
            raise ValueError('FOUNDER_EXCEPTION_BUDGET_EXHAUSTED_BEFORE_PAYMENT')
        if kind == 'self_hosted':
            return
        minutes = sum(COST_POLICY['webinar_minutes' if kind == 'group_webinar' else 'private_minutes'].values())
        session = state['sessions'].get(ident)
        if session is None:
            if state['founder_reserved_minutes'] + exception_minutes + minutes > self.meta['founder_budget_minutes']:
                raise ValueError('FOUNDER_CAPACITY_EXHAUSTED_BEFORE_PAYMENT')
            session = state['sessions'][ident] = {'kind': kind, 'seats': 0, 'minutes': minutes, 'delivered': False}
            state['founder_reserved_minutes'] += minutes
        limit = 500 if kind == 'group_webinar' else 1
        if session['kind'] != kind or session['seats'] >= limit or session['delivered']:
            raise ValueError('SESSION_FULL_CLOSED_OR_WRONG_TYPE')
        session['seats'] += 1

    def act(self, action_id, operation, order_id, *, hour=0, **payload):
        _identifier(action_id); _identifier(order_id); _identifier(operation); _integer(hour, 'hour')
        if operation == 'download_complete':
            raise ValueError('ACTUAL_COPY_ENTRYPOINT_REQUIRED')
        request = {'operation': operation, 'order_id': order_id, 'hour': hour, 'payload': payload}
        if len(canonical(request)) > 8192:
            raise ValueError('BOUNDED_WORKFLOW_COMMAND_REQUIRED')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            state = self._state()
            old = self.db.execute('SELECT request,receipt FROM commands WHERE id=?', (action_id,)).fetchone()
            if old:
                if old[0] != canonical(request):
                    raise ValueError('IDEMPOTENT_WORKFLOW_PAYLOAD_CHANGED')
                result = strict_json(old[1])
            else:
                result = self._apply(state, request, verify_bytes=True)
                self.db.execute('INSERT INTO commands(id,request,receipt) VALUES (?,?,?)',
                                (action_id, canonical(request), canonical(result)))
            self.db.execute('COMMIT')
            return result
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def _verify_destination(self, destination):
        if any(p.is_symlink() for p in [destination, *destination.parents]) or not destination.is_file():
            raise ValueError('REGULAR_LOCAL_DOWNLOAD_DESTINATION_REQUIRED')
        if destination.stat().st_size != self.meta['artifact_bytes']:
            raise ValueError('EXISTING_DOWNLOAD_DESTINATION_DIFFERS')
        with destination.open('rb') as stream:
            raw = stream.read(self.meta['artifact_bytes'] + 1)
        if len(raw) != self.meta['artifact_bytes'] or hashlib.sha256(raw).hexdigest() != self.meta['artifact_sha256']:
            raise ValueError('EXISTING_DOWNLOAD_DESTINATION_DIFFERS')

    def _read_artifact(self):
        if self.artifact.is_symlink() or not self.artifact.is_file() or self.artifact.stat().st_size != self.meta['artifact_bytes']:
            raise ValueError('ACTUAL_DOWNLOAD_BYTES_CHANGED')
        with self.artifact.open('rb') as stream:
            raw = stream.read(self.meta['artifact_bytes'] + 1)
        if len(raw) != self.meta['artifact_bytes'] or hashlib.sha256(raw).hexdigest() != self.meta['artifact_sha256']:
            raise ValueError('ACTUAL_DOWNLOAD_BYTES_CHANGED')
        return raw

    def _copy_bytes(self, destination):
        raw = self._read_artifact()
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.omega-download-', delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                    try:
                        os.link(temporary, destination)
                    except FileExistsError:
                        pass
                    descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                finally:
                    temporary.unlink()
        self._verify_destination(destination)

    def download_copy(self, order_id, destination, *, action_id=None, hour=0):
        _identifier(order_id); _integer(hour, 'hour')
        action_id = action_id or 'download-copy:' + order_id
        _identifier(action_id)
        destination = Path(destination).absolute()
        if destination in {self.artifact, self.path} or any(p.is_symlink() for p in [destination, *destination.parents]):
            raise ValueError('REGULAR_LOCAL_DOWNLOAD_DESTINATION_REQUIRED')
        request = {'operation': 'download_complete', 'order_id': order_id, 'hour': hour,
                   'payload': {'destination': str(destination), 'artifact_sha256': self.meta['artifact_sha256'],
                               'artifact_bytes': self.meta['artifact_bytes']}}
        self.db.execute('BEGIN IMMEDIATE')
        try:
            state = self._state()
            row = state['orders'].get(order_id, {})
            if not row.get('download_requested') or not row.get('entitled') or row.get('active_dispute') or row['offer']['id'] != 'self_hosted':
                raise ValueError('ACTIVE_STAGED_DOWNLOAD_REQUIRED')
            old = self.db.execute('SELECT request,receipt FROM commands WHERE id=?', (action_id,)).fetchone()
            if old and old[0] != canonical(request):
                raise ValueError('IDEMPOTENT_WORKFLOW_PAYLOAD_CHANGED')
            if not old and row.get('delivered'):
                raise ValueError('ORIGINAL_DOWNLOAD_COMPLETION_ID_REQUIRED')
            if not old and hour < state['last_hour']:
                raise ValueError('WORKFLOW_TIME_REGRESSION')
            self._copy_bytes(destination)
            result = strict_json(old[1]) if old else self._apply(state, request, verify_bytes=True)
            if not old:
                self.db.execute('INSERT INTO commands(id,request,receipt) VALUES (?,?,?)',
                                (action_id, canonical(request), canonical(result)))
            self.db.execute('COMMIT')
            return result
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def audit(self):
        state = self._state()
        return {'accepted': True, 'scope': SCOPE, 'commands': self.db.execute('SELECT COUNT(*) FROM commands').fetchone()[0],
                'state_sha256': digest(state), 'integrity_limit': 'Replay consistency; no hostile-operator authentication or payment authority.'}

    def report(self):
        state, audit = self._state(), self.audit()
        rows = list(state['orders'].values())
        captured = sum(r['offer']['price_microUSD'] for r in rows if r['captured'])
        settled = sum(r['offer']['price_microUSD'] for r in rows if r['settled'])
        refunded = sum(r['offer']['price_microUSD'] for r in rows if r['refunded'] or r['dispute_lost'])
        unresolved = sum(r['offer']['price_microUSD'] for r in rows if r['state'] == 'disputed' and not r['refunded'])
        recognized = sum(r['offer']['price_microUSD'] for r in rows
                         if r['delivered'] and not r['refunded'] and not r['dispute_lost'] and r['state'] != 'disputed')
        undelivered = sum(r['offer']['price_microUSD'] for r in rows
                         if r['captured'] and not r['delivered'] and not r['refunded'] and not r['dispute_lost'])
        processing = sum(r['processing_microUSD'] + r['dispute_fee_microUSD'] for r in rows)
        acquisition = sum(COST_POLICY['acquisition_microUSD'][r['offer']['id']] for r in rows)
        delivery = sum(COST_POLICY['delivery_microUSD'][r['offer']['id']] for r in rows if r['delivered'])
        founder = (state['founder_required_minutes'] * COST_POLICY['founder_opportunity_microUSD_per_hour'] + 59) // 60
        return {'schema': 'omega/commerce-fixture-report/v1', 'scope': SCOPE, 'audit': audit,
            'metadata': self.meta, 'offers': [offer(i) for i in PAID], 'cost_policy': COST_POLICY,
            'funnel_counts': {'explained': len(rows), 'declined': sum(r['state'] == 'declined' for r in rows),
                'simulated_captures': sum(r['captured'] for r in rows), 'delivered': sum(r['delivered'] for r in rows),
                'onboarded': sum(r['onboarded'] for r in rows), 'refunded': sum(r['refunded'] for r in rows),
                'disputes': sum(r['disputed'] for r in rows)},
            'receipt_reconciliation_microUSD': {'synthetic_captures': captured,
                'synthetic_gross_settlements': settled,
                'unsettled_capture_receivables_before_refunds': captured - settled,
                'unfulfilled_order_liability': undelivered,
                'fixture_recognition_after_delivery_and_reversals': recognized,
                'refunds_and_lost_disputes': refunded, 'unresolved_dispute_principal': unresolved,
                'processing_and_dispute_fee_envelope': processing,
                'net_captured_value_before_other_costs_not_cash': captured - refunded - unresolved - processing,
                'acquisition_envelope': acquisition, 'delivery_envelope': delivery,
                'noncash_founder_opportunity_cost': founder,
                'conditional_fixture_contribution_before_unknown_complete_costs':
                    recognized - processing - acquisition - delivery - founder},
            'founder': {'budget_minutes': self.meta['founder_budget_minutes'],
                'reserved_service_minutes': state['founder_reserved_minutes'],
                'modeled_required_minutes': state['founder_required_minutes'],
                'actual_observed_human_minutes': None, 'exception_count': len(state['exceptions']),
                'unresolved_exception_minutes': sum(e['minutes'] for e in state['exceptions']),
                'modeled_capacity_shortfall_minutes': max(0, state['founder_reserved_minutes'] + sum(e['minutes'] for e in state['exceptions']) - self.meta['founder_budget_minutes']),
                'actual_human_work_completed': None,
                'exceptions': state['exceptions'], 'autonomous_claim': False,
                'new_service_capacity_status': 'DEFER' if state['founder_reserved_minutes'] + sum(e['minutes'] for e in state['exceptions']) >= self.meta['founder_budget_minutes'] else 'WITHIN_AUTHORED_BUDGET'},
            'native_account_postings': 0, 'native_product_sales_added': 0,
            'complete_cost_profit_microUSD': None, 'trailing_365_day_profit_microUSD': None,
            'next_action': 'Retain tested mechanics; restore authenticated original account before any native continuation. Product license, demand, complete costs and live obligations remain unresolved.'}


def inspect_continuation(output):
    """Read-only fail-closed preflight; never create an account, key or balance."""
    output = Path(output).absolute()
    needed = ('registration.json', 'manifest.json', 'result.json', 'native-public-export.json',
              'account.sqlite.actions.jsonl', 'account.sqlite.connected-journal.json',
              'account.sqlite.adaptive-simulation-key')
    missing = [name for name in needed if not (output / name).is_file()]
    if missing or not (output / 'source').is_dir():
        return {'status': 'BLOCKED_ORIGINAL_RECOVERY_STATE_MISSING', 'missing': missing,
                'source_directory_present': (output / 'source').is_dir(),
                'native_account_modified': False, 'new_account_created': False}
    if any(p.is_symlink() for name in needed for p in [output / name, *(output / name).parents]):
        raise ValueError('ORIGINAL_REGULAR_RECOVERY_STATE_REQUIRED')
    registration = strict_json((output / 'registration.json').read_bytes())
    if canonical(registration) != canonical(declared_registration()):
        raise ValueError('ORIGINAL_OMEGA_POLICY_REQUIRED')
    checked = replay_audit(output)
    record = strict_json((output / 'native-public-export.json').read_bytes())
    journal = strict_json((output / 'account.sqlite.connected-journal.json').read_bytes())
    key_path = output / 'account.sqlite.adaptive-simulation-key'
    key_info = key_path.stat()
    if not stat.S_ISREG(key_info.st_mode) or key_info.st_nlink != 1 or stat.S_IMODE(key_info.st_mode) & 0o077:
        raise ValueError('PRIVATE_ORIGINAL_RECOVERY_KEY_REQUIRED')
    if key_info.st_size != 32:
        raise ValueError('RECOVERY_KEY_FILE_SIZE_MISMATCH')
    if canonical(journal['body']) != canonical(record['connected_journal']):
        raise ValueError('PUBLIC_EXPORT_NOT_CURRENT_ORIGINAL_JOURNAL')
    raw_tape = (output / 'account.sqlite.actions.jsonl').read_bytes()
    if len(raw_tape) > 64_000_000 or not raw_tape.endswith(b'\n'):
        raise ValueError('CANDIDATE_RECOVERY_TAPE_INCOMPLETE_OR_OVERSIZED')
    tape = [strict_json(line) for line in raw_tape.splitlines()]
    expected_header = {'schema': 'agi-alpha/commercial010-durable-actions/v1', 'config': record['ledger']['config']}
    if not tape or canonical(tape[0]) != canonical(expected_header):
        raise ValueError('CANDIDATE_RECOVERY_TAPE_HEADER_MISMATCH')
    if canonical(tape[1:]) != canonical(record['ledger']['actions']):
        raise ValueError('ORIGINAL_ACTION_TAPE_PREFIX_MISMATCH')
    return {'status': 'CANDIDATE_RECOVERY_CONSISTENT_REQUIRES_ORIGINAL_CUSTODY_PROVENANCE', 'audit': checked,
            'contract': record['ledger']['config']['contract'],
            'native_actions_sha256': record['ledger']['actions_sha256'],
            'native_account_modified': False, 'new_account_created': False,
            'private_key_contents_read': False,
            'private_authority_validation': 'NOT_PERFORMED_NO_INDEPENDENT_ORIGINAL_CUSTODY_ANCHOR',
            'continuation_authorized': False,
            'product_posting_status': 'BLOCKED_PRODUCT_SPECIFIC_NATIVE_ACCEPTANCE_ADAPTER_NOT_IMPLEMENTED'}


def reinvestment_view(summary, amount, expected_net):
    """Read-only projection of JournalAccount.spend's earned-cash prerequisite."""
    _integer(amount, 'amount', 1)
    if type(expected_net) is not int or type(summary.get('profit')) is not int:
        raise ValueError('INTEGER_NET_AND_NATIVE_PROFIT_REQUIRED')
    available = min(_integer(summary['available'], 'available'),
                    _integer(summary['unrestrictedEarned'], 'unrestrictedEarned'))
    reason = 'INVESTMENT_STOPPED' if summary.get('investmentStopped') else (
        'NONPOSITIVE_EXPECTED_NET' if expected_net <= 0 else (
        'INSUFFICIENT_UNRESTRICTED_CASH' if available < amount else 'CASH_PREREQUISITE_ONLY'))
    return {'decision': 'MAY_REQUEST_NATIVE_RESERVATION' if reason == 'CASH_PREREQUISITE_ONLY' else 'DEFER',
            'reason': reason, 'recorded_profit_microUSD_unchanged': summary['profit'],
            'unrestricted_cash_microUSD': available, 'spending_authority': False}


def run_fixture(output, artifact):
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    workflow = output / 'workflow.sqlite'
    with CommerceFixture(workflow, artifact) as shop:
        for ident, kind, session, consent in [('download', 'self_hosted', None, True),
                ('refund', 'self_hosted', None, True), ('dispute', 'self_hosted', None, True),
                ('decline', 'self_hosted', None, False), ('webinar', 'group_webinar', 'group-1', True),
                ('private', 'founder_private', 'private-1', True)]:
            shop.act(ident + ':discover', 'discover', ident, offer_id=kind, session_id=session)
            shop.act(ident + ':choice', 'choose', ident, consent=consent)
            if not consent:
                continue
            shop.act(ident + ':payment', 'payment', ident, provider='TEST_DOUBLE', status='succeeded')
            shop.act(ident + ':settle', 'settle', ident, provider='TEST_DOUBLE', status='settled')
            shop.act(ident + ':entitle', 'entitle', ident)
            if kind == 'self_hosted':
                shop.act(ident + ':download', 'download', ident)
                shop.download_copy(ident, output / (ident + '-delivered-artifact.bin'))
            else:
                shop.act(ident + ':session', 'deliver_session', ident, founder_supplied='SIMULATED_RECEIPT')
            shop.act(ident + ':onboard', 'onboard', ident)
        shop.act('download:help', 'help', 'download', code='MODEL_UNAVAILABLE')
    with CommerceFixture(workflow, artifact) as shop:
        shop.act('download:payment', 'payment', 'download', provider='TEST_DOUBLE', status='succeeded')
        shop.act('download:unknown', 'help', 'download', code='UNKNOWN_DIAGNOSTIC')
        shop.act('refund:refund', 'refund', 'refund')
        shop.act('dispute:open', 'dispute', 'dispute')
        shop.act('dispute:resolve', 'resolve_dispute', 'dispute', result='buyer_wins')
        report = shop.report()
    report['profit_cash_separation_fixture'] = reinvestment_view(
        {'profit': 1000 * MICRO, 'available': 50 * MICRO, 'unrestrictedEarned': 50 * MICRO},
        100 * MICRO, 200 * MICRO)
    atomic_bytes(output / 'report.json', canonical(report) + b'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    simulate = sub.add_parser('simulate-test')
    simulate.add_argument('--output', required=True)
    simulate.add_argument('--artifact', required=True)
    inspect = sub.add_parser('inspect-continuation')
    inspect.add_argument('--account-directory', required=True)
    args = parser.parse_args()
    result = run_fixture(args.output, args.artifact) if args.command == 'simulate-test' else inspect_continuation(args.account_directory)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
