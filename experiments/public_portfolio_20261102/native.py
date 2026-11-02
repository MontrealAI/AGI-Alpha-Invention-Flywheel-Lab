from __future__ import annotations
import copy
from pathlib import Path
from commercial.ledger import amount
from connected_enterprise.finance import JournalAccount, audit_journal
from commercial.terms_exact_v2 import prospective_terms
from . import service

class BusinessAccount:
    def __init__(self, root, manifest, path, *, opening, working=0, contract):
        self.root, self.manifest = Path(root).resolve(), copy.deepcopy(manifest)
        service.load_contracts(self.root, self.manifest)
        self.account = JournalAccount(self.root, self.manifest, path, opening=opening, working=working, contract=contract)

    def begin(self, job, order, buyer, price, budget, hour, collection_hour, warranty_hour, residual):
        service.load_contracts(self.root, self.manifest)
        if job not in {j['id'] for j in self.manifest['jobs']}:
            raise ValueError('PORTFOLIO_REGISTERED_LICENSE_REQUIRED')
        amount(price, positive=True); amount(budget)
        if budget < price:
            raise ValueError('PORTFOLIO_VOLUNTARY_BUYER_BUDGET_REQUIRED')
        terms = prospective_terms(order, price, warranty_hour, collection_hour, residual=residual, fee=200_000,
            counterparty_obligations='NONEXCLUSIVE computational design/evidence package and costed checking/support only; no physical, flight, safety, industrial or market qualification. Synthetic buyer may refuse. No actual contract.')
        provisions = [a for a in self.export()['ledger']['actions'] if a['op'] == 'wallet' and a['args']['buyer'] == buyer]
        if not provisions:
            self.account.execute('wallet', {'buyer': buyer, 'amount': budget}, hour)
        elif len(provisions) != 1 or provisions[0]['args']['amount'] != budget:
            raise ValueError('PORTFOLIO_BUYER_WALLET_TOPUP_REFUSED')
        self.account.execute('register_terms', {'id': order + '-terms', 'terms': terms}, hour)
        self.account.execute('offer', {'id': order, 'buyer': buyer, 'price': price, 'job_id': job,
            'deadline': collection_hour + 1, 'terms_id': order + '-terms'}, hour)
        for action in ('consent', 'fund'):
            self.account.execute('event', {'id': order, 'action': action, 'event_id': order + '-' + action}, hour)

    def deliver(self, order, job, artifact, hour):
        rows = [r for r in self.export()['ledger']['orders'] if r['id'] == order]
        offers = [r for r in self.export()['ledger']['actions'] if r['op'] == 'offer' and r['args']['id'] == order]
        if len(rows) != 1 or rows[0]['state'] not in {'funded', 'verified', 'released'} or len(offers) != 1 or offers[0]['args']['job_id'] != job:
            raise ValueError('PORTFOLIO_MATCHED_FUNDED_ORDER_REQUIRED')
        receipt = service.write_delivery(self.root, self.manifest, job, artifact)
        if receipt['accepted']:
            self.account.execute('event', {'id': order, 'action': 'prepare', 'event_id': order + '-prepare',
                'artifact_sha256': receipt['artifact_sha256']}, hour)
        return receipt

    def event(self, order, action, hour):
        return self.account.execute('event', {'id': order, 'action': action, 'event_id': order + '-' + action}, hour)

    def spend(self, ident, kind, cost, hour, work, expected_net=0, allow_seed=False):
        return self.account.spend(ident, kind, cost, hour, work, expected_net, allow_seed=allow_seed)

    def cost(self, ident, cost, hour): return self.account.cost(ident, cost, hour)
    def advance(self, hour): return self.account.advance_financial(hour)
    def export(self): return self.account.export()
    def snapshot(self): return self.account.snapshot()
    def audit(self): return audit_journal(self.export(), root=self.root, manifest=self.manifest)
    def close(self): return self.account.close()
    def __enter__(self): return self
    def __exit__(self, *_): self.close()
