"""Self-contained public-synthetic proof of one source-aware successor transformation."""
import argparse
import copy
import json
from pathlib import Path

from commercial import service, verified_delta as delta
from scripts.run_verified_delta044 import example

SCHEMA = 'agi-alpha/verified-delta-demo/v1'
FILES = ('BEFORE_INPUT.json','BEFORE_CERT.json','AFTER_INPUT.json','AFTER_CERT.json','DEMO.json')


def safe(path):
    path=Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('SYMLINK_OR_UNTRUSTED_PATH_REFUSED')
    return path


def strict_json(path):
    raw=safe(path).read_bytes()
    if len(raw)>2_000_000:raise ValueError('BOUND_PUBLIC_PROOF_BYTES_EXCEEDED')
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('DUPLICATE_JSON_FIELD')
            result[k]=v
        return result
    return json.loads(raw,object_pairs_hook=pairs,
                      parse_constant=lambda value:(_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def expected(before, earlier, after, later):
    pin=delta.digest(earlier)
    p=delta.verify(before,earlier,full=True)
    q=delta.verify(after,later,earlier,expected_previous_sha256=pin,full=True)
    if not p['current_complete_outcome_accepted'] or not q['current_complete_outcome_accepted']:
        raise ValueError('CURRENT_COMPLETE_OUTCOME_NOT_VERIFIED')
    if later['report'] != service.reconcile(after):
        raise ValueError('TRANSFORMED_OUTPUT_CHANGED')
    return {'schema':SCHEMA,'source':delta.sources(),
            'before_input_sha256':delta.digest(before), 'after_input_sha256':delta.digest(after),
            'before_proof_sha256':pin,'after_proof_sha256':delta.digest(later),
            'full_rows':len(after['invoices'])+len(after['payments']),
            'rows_semantically_rechecked':later['semantic_rows_rechecked'],
            'reused_groups':later['reused_groups'], 'fresh_groups':later['fresh_groups'],
            'independent_full_current_check':True,
            'all_current_outcomes_accepted':True,
            'actual_customers':0,'actual_collections':0,'actual_profit':None,
            'scope':'BOUNDED_PUBLIC_SYNTHETIC_PRODUCTIVE_MECHANISM_NOT_BEYOND_HUMAN_EVIDENCE'}


def build(path):
    path=safe(path)
    if path.exists():raise FileExistsError('CREATE_ONLY_DEMO_REQUIRED')
    before=example(100,5)
    earlier=delta.execute(before)
    after=copy.deepcopy(before)
    after['invoices'][0]['amount_cents']+=19
    after['payments'][0]['amount_cents']+=19
    later=delta.execute(after,earlier,expected_previous_sha256=delta.digest(earlier))
    result=expected(before,earlier,after,later)
    if (result['reused_groups'],result['fresh_groups'],result['rows_semantically_rechecked'])!=(99,1,10):
        raise ValueError('UNEXPECTED_BOUND_DEMO_CAUSAL_EFFECT')
    path.mkdir(parents=True)
    for name,value in zip(FILES,(before,earlier,after,later,result)):
        (path/name).write_bytes(delta.canonical(value))
    return verify(path)


def verify(path):
    path=safe(path)
    if not path.is_dir() or {p.name for p in path.iterdir()}!=set(FILES):
        raise ValueError('EXACT_PUBLIC_DEMO_FILE_CLOSURE_REQUIRED')
    rows=[strict_json(path/name) for name in FILES]
    checked=expected(*rows[:4])
    if rows[4]!=checked or (rows[4]['reused_groups'],rows[4]['fresh_groups'],rows[4]['rows_semantically_rechecked'])!=(99,1,10):
        raise ValueError('CURRENT_DEMO_RECEIPT_DOES_NOT_REDERIVE')
    return {'verified':True,'demo':checked,'files':list(FILES)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    for name in ('build','verify'):
        sub.add_parser(name).add_argument('--path',required=True)
    args=parser.parse_args()
    result=build(args.path) if args.action=='build' else verify(args.path)
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
