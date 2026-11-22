"""Fresh native fixture only; never pass an original account directory."""
import copy
import json
import shutil
import tempfile
from pathlib import Path
import enterprise078

# The process starts in exact staged science. Only this additive package is
# found in current source; original native imports remain from staged science.
CURRENT = Path(__file__).resolve().parents[2]
enterprise078.__path__.append(str(CURRENT/'enterprise078'))
from enterprise078.native import BusinessAccount
from enterprise078.service import prepare_manifest
from commercial.ledger import digest
from enterprise078.transactional_data.operator import ingest, project, export_csv
from enterprise078.transactional_data.run import fixture
from enterprise078.transactional_admission.contract import request
from enterprise078.transactional_admission.catalog import prepare, recover, location, source_identity


def run():
    checks=[]
    def refused(call):
        try: call()
        except (ValueError, FileExistsError): return
        raise AssertionError('INVALID_PROPOSAL_ACCEPTED')
    with tempfile.TemporaryDirectory(prefix='catalog-TEST-ONLY-') as tmp:
        tmp=Path(tmp);root=Path.cwd();path=tmp/'private'/'account'
        candidate=tmp/'candidate-source'
        for name in source_identity(CURRENT):
            p=candidate/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(CURRENT/name,p)
        manifest=prepare_manifest(root,[{'id':'dev-K1','delivery_path':'enterprise078/deliveries/catalog-test.json'}])
        kwargs=dict(opening=25000000000,working=0,contract='CATALOG_TEST_NOT_CONTINUATION')
        events=fixture(257);db=tmp/'output.sqlite';csv=tmp/'output.csv'
        ingest(db,events);project(db);export_csv(db,csv)
        contract=request('sql-csv-catalog-fixture',events)
        with BusinessAccount(root,manifest,path,**kwargs) as a:
            a.cost('fixture-incurred-failure',100000000,0)
            before=digest(a.export())
            code=candidate/'enterprise078/transactional_admission/catalog.py'
            raw=code.read_bytes();code.write_bytes(raw+b'\n# substituted candidate before first proposal\n')
            refused(lambda:prepare(a,candidate,None,contract,events,db,csv))
            assert not location(a).exists() and digest(a.export())==before
            code.write_bytes(raw)
            checks.append('candidate_must_match_executing_source_before_append')
            first=prepare(a,candidate,None,contract,events,db,csv)
            assert not first['native_catalog_admitted'] and first['financial_export_sha256']==before
            assert len(recover(a,candidate,first['head']))==1
            assert digest(a.export())==before
            checks.append('accepted_typed_proposal_no_financial_mutation')
            refused(lambda:prepare(a,candidate,None,contract,events,db,csv))
            checks.append('stale_head_cannot_overwrite')
            bad=copy.deepcopy(contract);bad['type']='preparation'
            refused(lambda:prepare(a,candidate,first['head'],bad,events,db,csv))
            checks.append('lab_relabel_refused')
            p=location(a)/'00000000.json';original=p.read_bytes()
            e=json.loads(original);e['body']['state']['status']='ACTIVE';p.write_text(json.dumps(e,sort_keys=True,separators=(',',':'))+'\n')
            refused(lambda:recover(a,candidate,first['head']));p.write_bytes(original)
            checks.append('tampered_activation_refused')
            code=candidate/'enterprise078/transactional_admission/catalog.py';raw=code.read_bytes()
            code.write_bytes(raw+b'\n');refused(lambda:recover(a,candidate,first['head']));code.write_bytes(raw)
            checks.append('changed_candidate_source_refused')
            second=prepare(a,candidate,first['head'],request('sql-csv-second',events),events,db,csv)
            p=location(a)/'00000001.json';raw=p.read_bytes();p.unlink()
            refused(lambda:recover(a,candidate,second['head']));p.write_bytes(raw)
            checks.append('removed_tail_refused_with_expected_head')
            a.cost('zero-value-followup',0,1)
            assert len(recover(a,candidate,second['head']))==2
            checks.append('native_append_preserves_prior_prefix_binding')
            after=digest(a.export());assert a.audit()['accepted']
        with BusinessAccount(root,manifest,path,**kwargs) as a:
            assert len(recover(a,candidate,second['head']))==2
            assert digest(a.export())==after
            assert a.snapshot()['summary']['profit']==-100000000
            assert a.audit()['accepted']
            checks.append('same_authority_reopen_preserves_loss')
    return {'accepted':True,'checks':checks,'fixture_loss_microUSD':100000000,
            'proposals':2,'activation_implemented':False,'native_catalog_admitted':False,
            'original_account_touched':False,'scope':'fresh test account only; no signed envelope or key exported'}


if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
