"""Owned simulation seam. All money and capacity commitments use JournalAccount."""
from __future__ import annotations
from pathlib import Path
from commercial.ledger import digest
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.finance import JournalAccount, audit_journal
from . import service

OPENING = 100_000_000_000
SCHEMA = 'genesis-commitment001/native-services/v1'


def capacity_rows(export):
    """Successful paid commitments, never a separately mutable capacity book."""
    rows = []
    for entry in export['connected_journal']['entries']:
        request = entry['request']
        if entry['status'] == 'COMPLETE' and request['operation'] == 'spend':
            if not isinstance(request['work'], dict):
                raise ValueError('OBJECT_RESOURCE_WORK_REQUIRED')
            capacity = request['work'].get('capacity')
            if capacity is not None:
                rows.append({'id': request['id'], **capacity})
    return rows


def validate_capacity(capacity, suppliers):
    if not isinstance(capacity, dict) or set(capacity) != {'supplier', 'start', 'end', 'units'}:
        raise ValueError('EXACT_CAPACITY_COMMITMENT_REQUIRED')
    if capacity['supplier'] not in suppliers:
        raise ValueError('REGISTERED_SUPPLIER_REQUIRED')
    if any(type(capacity[k]) is not int for k in ('start','end','units')):
        raise ValueError('INTEGER_CAPACITY_INTERVAL_REQUIRED')
    if not 0 <= capacity['start'] < capacity['end'] or capacity['units'] <= 0:
        raise ValueError('POSITIVE_CAPACITY_INTERVAL_REQUIRED')
    supplier = suppliers[capacity['supplier']]
    if supplier['consent'] != 'AUTHORED_SIMULATED_ACCEPTANCE' or type(supplier['units']) is not int or supplier['units'] <= 0:
        raise ValueError('EXPLICIT_SIMULATED_SUPPLIER_ACCEPTANCE_REQUIRED')


def capacity_available(export, ident, capacity, suppliers):
    validate_capacity(capacity, suppliers)
    rows = capacity_rows(export)
    own = [r for r in rows if r['id'] == ident]
    if own:
        if len(own) != 1 or own[0] != {'id': ident, **capacity}:
            raise ValueError('IDEMPOTENT_CAPACITY_CHANGED')
        return True
    relevant = [r for r in rows if r['supplier'] == capacity['supplier']]
    points = {capacity['start'], capacity['end']}
    for row in relevant:
        points.update((row['start'], row['end']))
    for point in sorted(points):
        if capacity['start'] <= point < capacity['end']:
            used = sum(r['units'] for r in relevant if r['start'] <= point < r['end'])
            if used + capacity['units'] > suppliers[capacity['supplier']]['units']:
                return False
    return True


class BusinessAccount:
    def __init__(self, root, manifest, path, *, contract, suppliers):
        self.root, self.manifest, self.suppliers = Path(root), manifest, suppliers
        service.load_contracts(root, manifest)
        self.account = JournalAccount(root, manifest, path, opening=OPENING, working=0, contract=contract)
        try:
            rows=capacity_rows(self.account.export())
            for row in rows:
                validate_capacity({k:v for k,v in row.items() if k!='id'},suppliers)
            for supplier,grant in suppliers.items():
                own=[r for r in rows if r['supplier']==supplier]
                for point in {t for r in own for t in (r['start'],r['end'])}:
                    if sum(r['units'] for r in own if r['start']<=point<r['end'])>grant['units']:
                        raise ValueError('RECOVERED_CAPACITY_OVERCOMMITTED')
        except BaseException:
            self.account.close()
            raise

    def reserve_delivery(self, ident, amount, hour, work, *, allow_seed):
        # The mandatory native account owns a process-level exclusive lease.
        # Its reentrant mutex also covers this check plus the durable spend.
        with self.account._mutex:
            if type(hour) is not int or hour < 0 or work['capacity']['start'] < hour:
                raise ValueError('FUTURE_CAPACITY_RESERVATION_REQUIRED')
            if set(work) != {'capacity','costs','expected_net','job','order','buyer'} or any(type(v) is not int or v < 0 for v in work['costs'].values()) or sum(work['costs'].values()) != amount:
                raise ValueError('EXACT_PREPAID_DELIVERY_WORK_REQUIRED')
            self.account.audit()
            if not capacity_available(self.account.export(), ident, work['capacity'], self.suppliers):
                return None
            return self.account.spend(ident, 'committed_delivery', amount, hour, work,
                                      expected_net=work['expected_net'], allow_seed=allow_seed)

    def begin(self, job, order, buyer, price, budget, hour, collect, maturity):
        commitments = [e for e in self.account.export()['connected_journal']['entries']
                       if e['status'] == 'COMPLETE' and e['request']['operation'] == 'spend'
                       and e['request']['id'] == 'capacity-' + order]
        if len(commitments) != 1:
            raise ValueError('FUNDED_CAPACITY_REQUIRED_BEFORE_PROMISE')
        work = commitments[0]['request']['work']
        if (work.get('job'), work.get('order'), work.get('buyer')) != (job, order, buyer):
            raise ValueError('PROMISE_CAPACITY_BINDING_CHANGED')
        if commitments[0]['request']['day'] > hour or sum(work['costs'].values()) != commitments[0]['request']['amount']:
            raise ValueError('PREPAID_PRODUCTION_REQUIRED_BEFORE_PROMISE')
        if not commitments[0]['request']['day'] <= hour <= work['capacity']['start']:
            raise ValueError('PROMISE_MUST_PRECEDE_RESERVED_SERVICE')
        service.has_request(self.root, self.manifest, job)
        terms = prospective_terms(order, price, maturity, collect, residual=50_000_000)
        self.account.execute('wallet', {'buyer': buyer, 'amount': budget}, hour)
        self.account.execute('register_terms', {'id': order+'-terms', 'terms': terms}, hour)
        self.account.execute('offer', {'id': order, 'buyer': buyer, 'price': price,
            'job_id': job, 'deadline': collect+1, 'terms_id': order+'-terms'}, hour)
        for action in ('consent','fund'):
            self.event(order, action, hour)

    def event(self, order, action, hour, artifact_sha256=None):
        args = {'id': order, 'action': action, 'event_id': order+'-'+action}
        if artifact_sha256 is not None:
            args['artifact_sha256'] = artifact_sha256
        return self.account.execute('event', args, hour)

    def deliver(self, job, order, artifact, hour):
        commitments = [e for e in self.account.export()['connected_journal']['entries']
                       if e['status'] == 'COMPLETE' and e['request']['operation'] == 'spend'
                       and e['request']['id'] == 'capacity-' + order]
        if len(commitments) != 1 or commitments[0]['request']['work']['job'] != job:
            raise ValueError('DELIVERY_CAPACITY_BINDING_REQUIRED')
        capacity = commitments[0]['request']['work']['capacity']
        if not capacity['start'] <= hour < capacity['end']:
            raise ValueError('DELIVERY_OUTSIDE_RESERVED_CAPACITY')
        receipt = service.write_delivery(self.root, self.manifest, job, artifact)
        if receipt['accepted']:
            self.event(order, 'prepare', hour, digest(artifact))
        return receipt

    def close(self):
        self.account.close()

    def __enter__(self): return self
    def __exit__(self, *_): self.close()
