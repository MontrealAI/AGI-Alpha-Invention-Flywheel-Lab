from __future__ import annotations
import argparse,copy,fcntl,hashlib,json,os,time,uuid
from pathlib import Path
import verify_finance as frozen
import verify_science as base
from commercial.ledger import canonical,strict_json
from connected_enterprise.finance import source_identity,audit_journal

HERE=Path(__file__).resolve().parent
AMENDMENT=HERE/'r2_audit_execution_amendment.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def immutable_save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.pending-'+str(os.getpid())+'-'+uuid.uuid4().hex)
    with temporary.open('xb') as stream:
        stream.write(canonical(value)+b'\n');stream.flush();os.fsync(stream.fileno())
    os.link(temporary,path)
    temporary.unlink()


def public_read(public_root,path):
    path=Path(path)
    if path.is_symlink() or not path.resolve().is_relative_to(public_root):
        raise ValueError('PUBLIC_EXPORT_SCOPE_REQUIRED')
    raw=path.read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('PUBLIC_EXPORT_NOT_YET_COMPLETE')
    value=strict_json(raw)
    if canonical(value)+b'\n'!=raw:
        raise ValueError('IMMUTABLE_CANONICAL_PUBLIC_EXPORT_REQUIRED')
    return value,sha(raw)


def case_inputs(public_root,ident):
    folder=public_root/ident
    paths={name:folder/name for name in ('account.public.json','manifest.json','RESULT.json')}
    if not all(p.is_file() for p in paths.values()):
        return None
    parsed={};hashes={}
    for name,path in paths.items():
        value,checksum=public_read(public_root,path);parsed[name]=value;hashes[name]=checksum
    return parsed,hashes


def derived_metadata(parsed,audit):
    state=parsed['RESULT.json'];summary=parsed['account.public.json']['ledger']['summary']
    return {'route':state['route'],'scenario':state['scenario']['id'],'opening_microUSD':state['opening_microUSD'],
            'profit_microUSD':summary['profit'],'cash_microUSD':summary['cash'],'available_microUSD':summary['available'],
            'payables_microUSD':summary['payables'],'tail_reserve_microUSD':summary['tailReserve'],
            'revenue_microUSD':summary['revenue'],'expenses_microUSD':summary['expenses'],
            'trailing_365_profit_microUSD':audit['independent_trailing365_profit_microUSD'],
            'accepted_and_collected_orders':state['accepted_and_collected_orders']}


def authority_negative_checks():
    from experiments.public_portfolio_20261102 import service
    checks=base.Checks()
    candidate=copy.deepcopy(frozen.read(base.ROOT/'experiments/public_portfolio_20261102/PRODUCTS.json')[0])
    candidate['delivery_path']=service.PREFIX+'deliveries/independent-negative-test/'+candidate['id']+'.json'
    forged=copy.deepcopy(candidate);forged['approval_path']=service.PREFIX+'producer-chosen-approval.json'
    checks.reject('producer_selected_approval_trust_anchor_refused',lambda:service._product(base.ROOT,forged))
    forged=copy.deepcopy(candidate);forged['product_path']=service.PREFIX+'producer-chosen-product.json'
    checks.reject('noncanonical_product_path_refused',lambda:service._product(base.ROOT,forged))
    return checks.rows


def run(public_root,cache_root):
    public_root=Path(public_root).resolve();cache_root=Path(cache_root).resolve()
    cache_root.mkdir(parents=True,exist_ok=True)
    amendment=frozen.read(AMENDMENT);expected_source=amendment['expected_native_financial_source_sha256']
    if base.digest(frozen.__file__)!=amendment['frozen_primary_checker_sha256'] or base.digest(HERE/'FINANCIAL_VERIFICATION_PROTOCOL.json')!=amendment['frozen_protocol_sha256']:
        raise ValueError('FROZEN_AUDIT_PREDICATE_CHANGED')
    protocol=frozen.read(HERE/'FINANCIAL_VERIFICATION_PROTOCOL.json')
    operating=frozen.read(base.BASE/'ECONOMICS_PROTOCOL.json')
    public_protocol,public_protocol_hash=public_read(public_root,public_root/'protocol.json')
    if public_protocol!=operating:
        raise ValueError('ORIGINAL_REGISTERED_ECONOMIC_PROTOCOL_REQUIRED')
    planned=[r+'-'+s['id'] for r in ('purpose','interface','complementarity','arrangement','foundry') for s in operating['registered_scenarios']]
    replay_required=set(protocol['native_full_replay_subset'])
    if len(planned)!=110 or len(set(planned))!=110 or len(replay_required)!=10 or not replay_required<=set(planned):
        raise ValueError('ORIGINAL_110_ACCOUNT_10_REPLAY_DENOMINATORS_REQUIRED')
    lock=(cache_root/'AUDITOR.lock').open('a+')
    try:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close();raise ValueError('READ_ONLY_AUDITOR_ALREADY_RUNNING')
    receipts=[];new_count=0;cached_count=0;incomplete=[];input_mismatches=[]
    try:
        for ident in planned:
            try:
                loaded=case_inputs(public_root,ident)
            except ValueError as exc:
                if str(exc)=='PUBLIC_EXPORT_NOT_YET_COMPLETE':
                    incomplete.append(ident);continue
                raise
            if loaded is None:
                incomplete.append(ident);continue
            parsed,hashes=loaded;record=parsed['account.public.json'];manifest=parsed['manifest.json'];state=parsed['RESULT.json']
            actual=source_identity(base.ROOT,manifest)
            if actual['sha256']!=expected_source or record['connected_journal']['source']!=actual:
                raise ValueError('ORIGINAL_FINANCIAL_SOURCE_MUST_REMAIN_BB74:'+ident)
            metadata={'case_id':ident,'input_hashes':hashes,'financial_source_sha256':expected_source,
                      'primary_checker_sha256':amendment['frozen_primary_checker_sha256'],
                      'audit_protocol_sha256':amendment['frozen_protocol_sha256'],'native_replay_required':ident in replay_required}
            receipt_path=cache_root/'receipts'/(ident+'.json')
            if receipt_path.exists():
                receipt=frozen.read(receipt_path)
                if receipt.get('metadata')!=metadata:
                    input_mismatches.append(ident);continue
                cached_count+=1
                print('AUDIT_CACHE_VERIFIED '+ident,flush=True)
            else:
                started=time.time()
                try:
                    audit=frozen.check_case(public_root/ident,state,manifest,record,operating['operating_end_hour_exclusive'])
                    if ident in replay_required:
                        audit['native_audit']=audit_journal(record,root=base.ROOT,manifest=manifest)
                        audit['native_full_replay']=True
                except Exception as exc:
                    audit={'case_id':ident,'passed':False,'native_full_replay':False,'error_type':type(exc).__name__,'error':str(exc)[:2000]}
                second=case_inputs(public_root,ident)
                if second is None or second[1]!=hashes or source_identity(base.ROOT,manifest)!=actual:
                    raise ValueError('AUDIT_INPUT_OR_SOURCE_CHANGED_DURING_CHECK:'+ident)
                receipt={'schema':'public-portfolio/immutable-readonly-audit-receipt/v1','metadata':metadata,
                         'audit':audit,'driver_sha256':base.digest(__file__),'amendment_sha256':base.digest(AMENDMENT),
                         'wall_seconds':time.time()-started,'operating_accounts_or_balances_mutated':False}
                if 'independent_trailing365_profit_microUSD' in audit:
                    receipt['derived_metadata']=derived_metadata(parsed,audit)
                immutable_save(receipt_path,receipt);new_count+=1
                print('AUDITED '+ident+' passed='+str(audit['passed'])+' native='+str(audit['native_full_replay']),flush=True)
            receipts.append({'case_id':ident,'receipt_path':str(receipt_path),'receipt_sha256':base.digest(receipt_path),'receipt':receipt})
        all_results_path=public_root/'RESULTS.json';complete=False;summary_binding=[];summary_hash=None
        if all_results_path.exists():
            summary,summary_hash=public_read(public_root,all_results_path)
            case_map={r['case_id']:r for r in summary['cases']}
            complete=(summary.get('status','COMPLETE')=='COMPLETE' and summary.get('failed_businesses')==0 and set(case_map)==set(planned) and
                      len(summary['cases'])==110 and summary.get('registered_businesses')==110 and summary.get('completed_businesses')==110)
            for item in receipts:
                compact=case_map.get(item['case_id']);derived=item['receipt'].get('derived_metadata')
                if compact is None or derived is None or any(compact.get(k)!=v for k,v in derived.items()):
                    summary_binding.append(item['case_id'])
        checked=len(receipts);native_count=sum(bool(r['receipt']['audit'].get('native_full_replay')) for r in receipts)
        cases_pass=all(r['receipt']['audit'].get('passed') for r in receipts)
        authority_checks=authority_negative_checks()
        final_qualified=complete and checked==110 and native_count==10 and cases_pass and all(c['passed'] for c in authority_checks) and not input_mismatches and not summary_binding
        return {'schema':'public-portfolio/streamed-independent-financial-audit/v1',
                'status':'COMPLETE_110_ACCOUNT_10_NATIVE_REPLAY' if final_qualified else 'PARTIAL_OR_FAILED_AUDIT',
                'driver_sha256':base.digest(__file__),'amendment_sha256':base.digest(AMENDMENT),
                'financial_source_sha256':expected_source,'economic_public_protocol_sha256':public_protocol_hash,
                'planned_accounts':110,'planned_independent_native_replays':10,'case_artifacts_audited':checked,
                'canonical_native_replays_completed':native_count,'new_audits_this_invocation':new_count,'immutable_cache_receipts_reused':cached_count,
                'all_checked_predicates_passed':cases_pass,'producer_campaign_complete':complete,'complete_110_10_qualified':final_qualified,
                'authority_negative_checks':authority_checks,
                'missing_case_artifacts':incomplete,'immutable_input_mismatches':input_mismatches,
                'producer_summary_binding_mismatches':summary_binding,'producer_summary_sha256':summary_hash,
                'audit_receipts':[{'case_id':r['case_id'],'receipt_sha256':r['receipt_sha256'],
                                   'passed':r['receipt']['audit'].get('passed'),
                                   'native_full_replay':r['receipt']['audit'].get('native_full_replay')} for r in receipts],
                'scope':'Read-only financial predicates and original ten full native replays; no private account/key reads, cash operations, R1 relabeling, market calibration or actual commerce.'}
    finally:
        fcntl.flock(lock.fileno(),fcntl.LOCK_UN);lock.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--public-root',required=True);p.add_argument('--cache-root',required=True);p.add_argument('--report',required=True);args=p.parse_args()
    report=Path(args.report)
    if report.exists():raise ValueError('refuse overwrite of prior audit progress report')
    started=time.time();result=run(args.public_root,args.cache_root);result['wall_seconds']=time.time()-started
    immutable_save(report,result)
    print(json.dumps({k:result[k] for k in ('status','case_artifacts_audited','canonical_native_replays_completed','all_checked_predicates_passed','complete_110_10_qualified')}))
    raise SystemExit(0 if result['all_checked_predicates_passed'] and all(c['passed'] for c in result['authority_negative_checks']) and not result['immutable_input_mismatches'] and not result['producer_summary_binding_mismatches'] else 1)
