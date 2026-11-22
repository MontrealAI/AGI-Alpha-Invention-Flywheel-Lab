"""Fresh disposable account only: no input account path or copied balance."""
import copy,json,tempfile
from pathlib import Path
from commercial.ledger import digest
from connected_enterprise.finance import JournalAccount,audit_journal
from commercial.terms_exact_v2 import prospective_terms
from enterprise078.transactional_data.run import fixture
from enterprise078.transactional_data.operator import ingest,project,export_csv
from . import service


def run():
    root=Path.cwd();events=fixture(257);ident='sql-csv-native-test'
    m=service.manifest(root,ident,events)
    db='enterprise078/sql-deliveries/output.sqlite';csv='enterprise078/sql-deliveries/output.csv'
    (root/db).parent.mkdir(parents=True,exist_ok=True)
    ingest(root/db,events);project(root/db);export_csv(root/db,root/csv)
    artifact=service.write_delivery(root,m,ident,db,csv)
    checks=[]
    with tempfile.TemporaryDirectory(prefix='SQL-NATIVE-TEST-NOT-CONTINUATION-') as tmp:
        path=Path(tmp)/'account';kwargs=dict(opening=1000000000,working=0,contract='SQL_TEST_NOT_CONTINUATION')
        with JournalAccount(root,m,path,**kwargs) as a:
            a.cost('prior-failed-work',20000000,0);a.cost('complete-declared-delivery',100000000,1)
            a.execute('wallet',{'buyer':'buyer','amount':400000000},1)
            for order,day in [('collected',2),('refund',6)]:
                terms=prospective_terms(order,200000000,day+10,day+2,residual=10000000,fee=200000)
                a.execute('register_terms',{'id':order+'-terms','terms':terms},day)
                a.execute('offer',{'id':order,'buyer':'buyer','price':200000000,'job_id':ident,'deadline':day+3,'terms_id':order+'-terms'},day)
                for event in ('consent','fund'):
                    a.execute('event',{'id':order,'action':event,'event_id':order+'-'+event},day)
                if order=='collected':
                    a.execute('event',{'id':order,'action':'prepare','event_id':order+'-prepare','artifact_sha256':digest(artifact)},day+1)
                    a.execute('event',{'id':order,'action':'release','event_id':order+'-release'},day+2)
                else:a.execute('event',{'id':order,'action':'refund','event_id':order+'-refund'},day+1)
            a.advance_financial(8760)
            record=a.export();assert audit_journal(record,root=root,manifest=m)['accepted']
            checks.append('typed_native_collection_and_refund_full_replay')
            raw=(root/csv).read_bytes();(root/csv).write_text('corrupt')
            try:
                try: verdict=audit_journal(record,root=root,manifest=m)
                except (ValueError,AssertionError):verdict={'accepted':False}
                assert not verdict['accepted']
            finally:(root/csv).write_bytes(raw)
            checks.append('actual_output_tamper_rejected')
        with JournalAccount(root,m,path,**kwargs) as a:
            assert digest(a.export())==digest(record)
            assert audit_journal(a.export(),root=root,manifest=m)['accepted']
            checks.append('same_account_authenticated_reopen')
        changed=copy.deepcopy(m);changed['jobs'][0]['request']['type']='preparation'
        try:
            with JournalAccount(root,changed,path,**kwargs):pass
        except ValueError:checks.append('changed_manifest_refused_no_reseed')
        else:raise AssertionError('CHANGED_MANIFEST_ACCEPTED')
    return {'checks':checks,'accepted':True,'scope':'fresh native engineering fixture; not original continuation or market calibration',
            'summary':record['ledger']['summary'],'orders':[{k:r[k] for k in ('id','state')} for r in record['ledger']['orders']],
            'actions_sha256':record['ledger']['actions_sha256'],'actual_records':257,'original_mutations':0,
            'original_catalog_transition':False,'whole_development_host_model_cost':'UNKNOWN','horizon_hours':[0,8760]}

if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
