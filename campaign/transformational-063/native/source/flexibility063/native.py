"""Small operating seam over the canonical owned native account.

No schedule is computed here and no parallel money ledger exists.  The caller
chooses economics, funds production, constructs the plan, and invokes completion.
"""
from __future__ import annotations

import copy
from pathlib import Path
from commercial.ledger import amount as validate_amount
from connected_enterprise.finance import JournalAccount, audit_journal
from . import service

OPENING = 100_000_000_000


class BusinessAccount:
    def __init__(self, root, manifest, path, *, opening=OPENING, working=0, contract='flexibility063'):
        self.root = Path(root).resolve()
        self.manifest = copy.deepcopy(manifest)
        service.load_contracts(self.root, self.manifest)
        self.account = JournalAccount(self.root, self.manifest, Path(path).absolute(),
                                      opening=opening, working=working, contract=contract)

    def spend(self, ident, kind, amount, day, work, expected_net=0, allow_seed=False):
        return self.account.spend(ident, kind, amount, day, work, expected_net, allow_seed=allow_seed)

    def cost(self, ident, amount, day):
        return self.account.cost(ident, amount, day)

    def begin_order(self, job_id, order_id, buyer_id, price, buyer_budget, day, deadline, terms=None):
        service.has_request(self.root, self.manifest, job_id)
        for ident in (order_id, buyer_id):
            if not isinstance(ident, str) or not ident.strip() or len(ident) > 140:
                raise ValueError('FLEXIBILITY063_BOUNDED_ORDER_AND_BUYER_IDS_REQUIRED')
        validate_amount(price, positive=True)
        if type(buyer_budget) is not int or buyer_budget < price:
            raise ValueError('FLEXIBILITY063_BUYER_BUDGET_REQUIRED')
        validate_amount(buyer_budget)
        if type(day) is not int or type(deadline) is not int or day < 0 or deadline < day:
            raise ValueError('FLEXIBILITY063_EXPLICIT_ORDER_INTERVAL_REQUIRED')
        extra = {}
        if self.manifest['native_engine'] == 'exact-prospective-v2':
            if not isinstance(terms, dict) or terms.get('order_id') != order_id or terms.get('price_microUSD') != price:
                raise ValueError('FLEXIBILITY063_EXPLICIT_BUYER_CHOSEN_TERMS_REQUIRED')
            from commercial.terms_exact_v2 import validate_terms
            validate_terms(terms, registered_at=day)
            extra['terms_id'] = order_id + '-terms'
        elif terms is not None:
            raise ValueError('FLEXIBILITY063_PERMANENT_ACCOUNT_CANNOT_REGISTER_PROSPECTIVE_TERMS')
        provision = [a for a in self.account.export()['ledger']['actions']
                     if a['op'] == 'wallet' and a['args']['buyer'] == buyer_id]
        if not provision:
            self.account.execute('wallet', {'buyer': buyer_id, 'amount': buyer_budget}, day)
        elif len(provision) != 1:
            raise ValueError('FLEXIBILITY063_UNIQUE_BUYER_PROVISION_REQUIRED')
        if terms is not None:
            self.account.execute('register_terms', {'id': order_id + '-terms', 'terms': terms}, day)
        self.account.execute('offer', {'id': order_id, 'buyer': buyer_id, 'price': price,
                                      'job_id': job_id, 'deadline': deadline, **extra}, day)
        for action in ('consent', 'fund'):
            self.account.execute('event', {'id': order_id, 'action': action,
                                          'event_id': order_id + '-' + action}, day)
        return self.snapshot()

    def complete_order(self, order_id, job_id, artifact, day):
        rows = [r for r in self.account.export()['ledger']['orders'] if r['id'] == order_id]
        if len(rows) != 1 or rows[0]['state'] not in {'funded', 'verified', 'released'}:
            raise ValueError('FLEXIBILITY063_OUTPUT_REQUIRES_FUNDED_ORDER')
        offers = [a for a in self.account.export()['ledger']['actions']
                  if a['op'] == 'offer' and a['args']['id'] == order_id]
        if len(offers) != 1 or offers[0]['args']['job_id'] != job_id:
            raise ValueError('FLEXIBILITY063_FUNDED_REQUEST_CHANGED')
        receipt = service.write_delivery(self.root, self.manifest, job_id, artifact)
        if not receipt['accepted']:
            return receipt
        self.account.execute('event', {'id': order_id, 'action': 'prepare',
                                      'event_id': order_id + '-prepare',
                                      'artifact_sha256': receipt['artifact_sha256']}, day)
        return receipt

    def release(self, order_id, day):
        return self.account.execute('event', {'id': order_id, 'action': 'release',
                                            'event_id': order_id + '-release'}, day)

    def refund(self, order_id, day):
        return self.account.execute('event', {'id': order_id, 'action': 'refund',
                                            'event_id': order_id + '-refund'}, day)

    def advance(self, day):
        return self.account.advance_financial(day)

    def snapshot(self):
        return self.account.snapshot()

    def export(self):
        return self.account.export()

    def audit(self):
        return audit_journal(self.export(), root=self.root, manifest=self.manifest)

    def seal_checkpoint(self, state):
        return self.account.seal_checkpoint(state)

    def verify_checkpoint(self, envelope):
        return self.account.verify_checkpoint(envelope)

    def close(self):
        return self.account.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def audit_export(record, *, root, manifest):
    return audit_journal(record, root=root, manifest=manifest)


def main():
    """Independently replay an exported native account; never create a trade."""
    import argparse
    import json
    from commercial.ledger import strict_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['audit'])
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--record', required=True, type=Path)
    args = parser.parse_args()
    verdict = audit_export(strict_json(args.record.read_bytes()), root=args.source,
                           manifest=strict_json(args.manifest.read_bytes()))
    print(json.dumps(verdict, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
