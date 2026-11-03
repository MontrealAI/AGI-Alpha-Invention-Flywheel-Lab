from __future__ import annotations
from pathlib import Path
from commercial.ledger import digest
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.finance import JournalAccount, audit_journal
from . import service


class BusinessAccount:
    def __init__(self, root, manifest, path, opening):
        self.root, self.manifest = Path(root).resolve(), manifest
        service.load_contracts(self.root, manifest)
        self.account = JournalAccount(self.root, manifest, Path(path).absolute(),
                                      opening=opening, working=0, contract='outlearning-906c4f4d')

    def spend(self, ident, amount, hour, work, expected_net=0, allow_seed=True):
        return self.account.spend(ident, 'registered_interoperation_resource', amount, hour,
                                  work, expected_net, allow_seed=allow_seed)

    def snapshot(self):
        return self.account.snapshot()['summary']

    def begin_order(self, job_id, ident, price, budget, hour, clearing_delay, support_hours):
        service._bound(self.root, self.manifest, job_id)
        buyer = ident + '-buyer'
        collection = hour + 2 + clearing_delay
        maturity = collection + support_hours
        terms = prospective_terms(ident, price, maturity, collection)
        self.account.execute('wallet', {'buyer': buyer, 'amount': budget}, hour)
        self.account.execute('register_terms', {'id': ident + '-terms', 'terms': terms}, hour)
        self.account.execute('offer', {'id': ident, 'buyer': buyer, 'price': price,
                                     'job_id': job_id, 'deadline': collection + 2, 'terms_id': ident + '-terms'}, hour)
        for op in ('consent', 'fund'):
            self.account.execute('event', {'id': ident, 'action': op, 'event_id': ident + '-' + op}, hour)
        return {'collection_hour': collection, 'maturity_hour': maturity}

    def produce(self, ident, job_id, program, hour):
        row = service._bound(self.root, self.manifest, job_id)
        artifact = {'request_sha256': digest(row['request']), 'program': program}
        receipt = service.write_delivery(self.root, self.manifest, job_id, artifact)
        if receipt['accepted']:
            self.account.execute('event', {'id': ident, 'action': 'prepare', 'event_id': ident + '-prepare',
                                         'artifact_sha256': receipt['artifact_sha256']}, hour)
        return receipt

    def settle(self, ident, accepted, hour):
        op = 'release' if accepted else 'refund'
        return self.account.execute('event', {'id': ident, 'action': op, 'event_id': ident + '-' + op}, hour)

    def advance(self, hour):
        return self.account.advance_financial(hour)

    def export(self):
        return self.account.export()

    def audit(self):
        return audit_journal(self.export(), root=self.root, manifest=self.manifest)

    def seal(self, state):
        return self.account.seal_checkpoint(state)

    def verify(self, envelope):
        return self.account.verify_checkpoint(envelope)

    def close(self):
        self.account.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
