"""Opt in to the native verifier's existing Enterprise078 prefix support.

This holds no balance and introduces no financial transition. Every request uses
JournalAccount and the original adaptive account. The private cache rebinds all
bytes, prepared artifacts, proofs and ownership, and is discarded on reopen.
Public final audits always replay from the original account opening.
"""
from pathlib import Path
import copy
from commercial.ledger import _NativePrefixReplay, digest
from connected_enterprise.finance import JournalAccount, _audit_journal
from enterprise078.native import BusinessAccount
from enterprise078.service import load_contracts

class ScaleJournalAccount(JournalAccount):
    def _audit_incremental(self):
        if self.manifest.get('schema') != 'enterprise078/native-services/v1':
            return super()._audit_incremental()
        with self._mutex:
            try:
                self._assert_current()
                if self._native_prefix is None:
                    self._native_prefix = _NativePrefixReplay(self._prefix_identity)
                return _audit_journal(self.export(), root=self.root, manifest=self.manifest,
                                      _native_session=self._native_prefix)
            except BaseException:
                if self._native_prefix is not None:
                    self._native_prefix.close()
                raise

class ScaleBusinessAccount(BusinessAccount):
    def __init__(self,root,manifest,path,*,opening,working=0,contract='enterprise078-scale'):
        self.root=Path(root).resolve();self.manifest=copy.deepcopy(manifest)
        load_contracts(self.root,self.manifest)
        self.account=ScaleJournalAccount(self.root,self.manifest,Path(path).absolute(),
                                        opening=opening,working=working,contract=contract)


def expected_requests(cmd,known_wallets):
    op=cmd['op'];a=cmd['args'];hour=a['day']
    def ex(kind,args):return {'operation':'execute','op':kind,'args':args,'day':hour}
    if op=='cost':return [ex('cost',{'id':a['ident'],'amount':a['amount']})]
    if op=='spend':return [{'operation':'spend','id':a['ident'],'kind':a['kind'],'amount':a['amount'],
                           'day':hour,'work':a['work'],'expected_net':a['expected_net'],'allow_seed':a['allow_seed']}]
    if op=='begin':
        rows=[]
        if a['buyer_id'] not in known_wallets:
            rows.append(ex('wallet',{'buyer':a['buyer_id'],'amount':a['buyer_budget']}));known_wallets.add(a['buyer_id'])
        tid=a['order_id']+'-terms'
        rows += [ex('register_terms',{'id':tid,'terms':a['terms']}),
                 ex('offer',{'id':a['order_id'],'buyer':a['buyer_id'],'price':a['price'],'job_id':a['job_id'],
                             'deadline':a['deadline'],'terms_id':tid}),
                 ex('event',{'id':a['order_id'],'action':'consent','event_id':a['order_id']+'-consent'}),
                 ex('event',{'id':a['order_id'],'action':'fund','event_id':a['order_id']+'-fund'})]
        return rows
    if op=='deliver':
        if not a['expected_accepted']:return []
        return [ex('event',{'id':a['order_id'],'action':'prepare','event_id':a['order_id']+'-prepare',
                           'artifact_sha256':digest(a['artifact'])})]
    if op in ('release','refund'):
        return [ex('event',{'id':a['order_id'],'action':op,'event_id':a['order_id']+'-'+op})]
    raise ValueError('UNKNOWN_OPERATION_IN_REPLAY')
