"""Read-only erratum for the published controller checker; native audit unchanged.

The original checker attributed native fees to release/refund, although the native
engine incurs the registered fee at offer. This correction preserves the frozen
operator, source files, account, queue, original failure and monetary results.
"""
from __future__ import annotations
import argparse, copy, hashlib, importlib, json, sys, time
from pathlib import Path

ORIGINAL_REVIEW_SHA256='228a6a97244a423f4a96449527fe3aa671bada75571ed5517be101db8f1ebfdd'
NEEDLE="""    fees=sum(a['after']['expenses']-a['before']['expenses'] for a in tape['actions']
             if a['op']=='event' and a['args'].get('action') in ('release','refund'))
"""
REPLACEMENT="    fees=native_offer_fees(tape,replay['orders'],p['payment_fee_basis_points'])\n"

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def native_offer_fees(tape,orders,basis_points):
    total=0;seen=set()
    for action in tape['actions']:
        if action['op']!='offer':continue
        ident=action['args']['id']
        if ident not in orders or ident in seen:raise ValueError('UNMATCHED_OFFER_FEE')
        seen.add(ident)
        expected=orders[ident]['price']*basis_points//10000
        if action['after']['expenses']-action['before']['expenses']!=expected:
            raise ValueError('OFFER_FEE_TIMING_OR_AMOUNT_MISMATCH')
        total+=expected
    if seen!=set(orders):raise ValueError('MISSING_NATIVE_OFFER_FEE')
    return total

def tests():
    orders={'a':{'price':12000000000}}
    tape={'actions':[{'op':'offer','args':{'id':'a'},'before':{'expenses':0},'after':{'expenses':300000000}}]}
    assert native_offer_fees(tape,orders,250)==300000000
    assert native_offer_fees({'actions':[]},{},250)==0
    bad=[]
    changed=copy.deepcopy(tape);changed['actions'][0]['op']='event';bad.append(changed)
    changed=copy.deepcopy(tape);changed['actions'][0]['after']['expenses']+=1;bad.append(changed)
    changed=copy.deepcopy(tape);changed['actions']*=2;bad.append(changed)
    changed=copy.deepcopy(tape);changed['actions'][0]['args']['id']='other';bad.append(changed)
    for changed in bad:
        try:native_offer_fees(changed,orders,250)
        except ValueError:pass
        else:raise AssertionError('INVALID_FEE_ACCEPTED')
    return 6

def replay(source,case):
    source=Path(source).resolve();case=Path(case).resolve()
    identity=json.loads((source/'SOURCE.json').read_text())
    for name,expected in identity['files'].items():
        path=source/name
        if path.is_symlink() or not path.is_file() or sha(path)!=expected:raise ValueError('ORIGINAL_SOURCE_MISMATCH:'+name)
    original=source/'enterprise078_scale/review.py'
    if sha(original)!=ORIGINAL_REVIEW_SHA256:raise ValueError('ERRATUM_ONLY_APPLIES_TO_NAMED_CHECKER')
    code=original.read_text()
    if code.count(NEEDLE)!=1:raise ValueError('EXACT_CORRECTION_LOCATION_REQUIRED')
    files={str(p):sha(p) for p in case.iterdir() if p.is_file()}
    sys.path.insert(0,str(source))
    module=importlib.import_module('enterprise078_scale.review')
    if Path(module.__file__).resolve()!=original:raise ValueError('WRONG_IMPORTED_FROZEN_CHECKER')
    from commercial.ledger import digest
    if digest(identity['files'])!=identity['sha256']:raise ValueError('SOURCE_MANIFEST_DIGEST_MISMATCH')
    cpu=time.process_time();wall=time.perf_counter()
    try:
        module.review(case);prior='PASSED_NO_FEE_DIFFERENCE'
    except ValueError as exc:
        if str(exc)!='COMPLETE_MODELED_COST_RECONCILIATION_FAILED':raise
        prior='ORIGINAL_COMPLETE_MODELED_COST_RECONCILIATION_FAILED_PRESERVED'
    corrected=code.replace(NEEDLE,REPLACEMENT)
    namespace={'__name__':'enterprise078_scale.fee_erratum','__package__':'enterprise078_scale',
               '__file__':str(original),'native_offer_fees':native_offer_fees}
    exec(compile(corrected,str(original)+'#offer-fee-erratum','exec'),namespace)
    result=namespace['review'](case)
    if {str(p):sha(p) for p in case.iterdir() if p.is_file()}!=files:raise ValueError('EVIDENCE_MUTATED')
    for name,expected in identity['files'].items():
        if sha(source/name)!=expected:raise ValueError('SOURCE_MUTATED')
    result.update(original_checker_verdict=prior,original_checker_sha256=ORIGINAL_REVIEW_SHA256,
                  corrected_checker_sha256=hashlib.sha256(corrected.encode()).hexdigest(),
                  erratum_script_sha256=sha(__file__),financial_history_changed=False,
                  native_verifier_changed=False,regression_checks=tests(),input_files_sha256=files,
                  measured_replay_cpu_seconds=time.process_time()-cpu,measured_replay_wall_seconds=time.perf_counter()-wall,
                  qualification='CORRECTED_READ_ONLY_REPRODUCTION_NOT_NEW_FINANCIAL_EXECUTION')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path);p.add_argument('--case',type=Path);p.add_argument('--test',action='store_true');a=p.parse_args()
    if a.test:print(json.dumps({'fee_regression_checks_passed':tests()}));return
    if a.source is None or a.case is None:p.error('--source and --case are required')
    print(json.dumps(replay(a.source,a.case),sort_keys=True))
if __name__=='__main__':main()
