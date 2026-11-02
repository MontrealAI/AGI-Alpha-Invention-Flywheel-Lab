from __future__ import annotations
import argparse,json,time
from pathlib import Path
import verify_finance as frozen
import verify_science as base
from r2_stream_audit import case_inputs
from connected_enterprise.finance import audit_journal,source_identity


def run(public_root,receipt_root):
    public_root=Path(public_root).resolve();receipt_root=Path(receipt_root).resolve()
    protocol=frozen.read(Path(__file__).with_name('FINANCIAL_VERIFICATION_PROTOCOL.json'))
    selected=protocol['native_full_replay_subset'];rows=[]
    if len(selected)!=10 or len(set(selected))!=10:
        raise ValueError('ORIGINAL_TEN_RETAINED_NATIVE_REPLAY_CASES_REQUIRED')
    for ident in selected:
        row={'case_id':ident,'passed':False,'arithmetic_rechecked':False,'native_rechecked':False}
        try:
            loaded=case_inputs(public_root,ident)
            if loaded is None:raise ValueError('RETAINED_PUBLIC_CASE_FILES_REQUIRED')
            parsed,hashes=loaded;receipt=frozen.read(receipt_root/(ident+'.json'));meta=receipt['metadata']
            if meta['case_id']!=ident or meta['input_hashes']!=hashes or meta['primary_checker_sha256']!=base.digest(frozen.__file__) or not meta['native_replay_required']:
                raise ValueError('EXACT_ORIGINAL_INDEPENDENT_AUDIT_RECEIPT_REQUIRED')
            manifest=parsed['manifest.json'];record=parsed['account.public.json'];state=parsed['RESULT.json']
            current=source_identity(base.ROOT,manifest)
            if record['connected_journal']['source']!=current or current['sha256']!=meta['financial_source_sha256']:
                raise ValueError('ORIGINAL_FINANCIAL_SOURCE_IDENTITY_REQUIRED')
            checked=frozen.check_case(public_root/ident,state,manifest,record,26280)
            native=audit_journal(record,root=base.ROOT,manifest=manifest)
            row.update({'passed':bool(checked['passed'] and native['accepted']),'arithmetic_rechecked':True,
                        'native_rechecked':bool(native['accepted']),'input_hashes':hashes,
                        'original_audit_receipt_sha256':base.digest(receipt_root/(ident+'.json')),
                        'independent_trailing365_profit_microUSD':checked['independent_trailing365_profit_microUSD']})
        except Exception as exc:
            row['error_type']=type(exc).__name__;row['error']=str(exc)[:2000]
        rows.append(row)
        print('RETAINED_RECHECK '+ident+' passed='+str(row['passed']),flush=True)
    return {'schema':'public-portfolio/retained-ten-public-native-recheck/v1','checker_sha256':base.digest(__file__),
            'primary_predicate_sha256':base.digest(frozen.__file__),'original_registered_cases':110,'retained_cases_expected':10,
            'retained_cases_rechecked':sum(r['arithmetic_rechecked'] and r['native_rechecked'] for r in rows),
            'passed':len(rows)==10 and all(r['passed'] for r in rows),'cases':rows,
            'original110_audit_reperformed':False,
            'scope':'Exact-hash recheck of the original ten predeclared retained key-free native exports using unchanged predicates. The other100 original cases are represented by their saved independent audit receipts; this command does not recheck their omitted input exports or claim a new110-case reproduction.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--public-root',required=True);p.add_argument('--audit-receipts',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    output=Path(args.output)
    if output.exists():raise ValueError('refuse overwrite of retained export recheck')
    started=time.time();result=run(args.public_root,args.audit_receipts);result['wall_seconds']=time.time()-started
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({'passed':result['passed'],'retained_rechecked':result['retained_cases_rechecked'],'original110_reperformed':False}))
    raise SystemExit(0 if result['passed'] else 1)
