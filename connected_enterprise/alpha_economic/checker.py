"""Host-owned immutable acceptance; models cannot modify this checker or its cases."""
from .core import contract, digest, harness


def check(c,instrument,groups=('training','confirmation')):
    c=contract(c); results=[]
    if not isinstance(instrument,dict) or instrument.get('inputs')!=c['inputs']:
        return {'accepted':False,'reason':'INPUT_CONTRACT_CHANGED','cases':[]}
    evaluator=harness('instruments')
    for group in groups:
        if group not in ('training','confirmation'): raise ValueError('UNKNOWN_ACCEPTANCE_GROUP')
        for case in c[group]:
            try:
                observed=evaluator.evaluate(instrument,case['input'],max_operations=c['max_operations'])
                passed=evaluator._json_equal(observed['output'],case['expected'])
                results.append({'group':group,'case_sha256':digest(case),'passed':passed,'operations':observed['operations']})
            except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
                results.append({'group':group,'case_sha256':digest(case),'passed':False,'operations':None})
    return {'accepted':bool(results) and all(r['passed'] for r in results), 'cases':results,
            'scope':'FINITE_CUSTOMER_DECLARED_CASES_NOT_GENERAL_CORRECTNESS_OR_EXTERNAL_CERTIFICATION',
            'instrument_sha256':digest(instrument),'contract_sha256':digest(c)}


def verify(c,artifact):
    if not isinstance(artifact,dict) or set(artifact)!={'schema','contract_sha256','instrument','provenance'} or artifact['schema']!='alpha-economic/artifact/v1':
        raise ValueError('EXACT_INSTRUMENT_ARTIFACT_REQUIRED')
    if artifact['contract_sha256']!=digest(contract(c)): raise ValueError('ARTIFACT_CONTRACT_BINDING_FAILED')
    ordinary=check(c,c['ordinary'])
    result=check(c,artifact['instrument'])
    if not ordinary['accepted']: raise ValueError('ORDINARY_CONTROL_NOT_QUALIFIED')
    return {**result,'artifact_sha256':digest(artifact),'ordinary':ordinary,
            'algorithmic_superiority_established':False}
