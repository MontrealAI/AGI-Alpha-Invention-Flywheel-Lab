#!/usr/bin/env python3
"""Independent, fail-closed audit of Ω ALPHA's first public-record asset.

Recomputes the complete selected fresh-task cohort using a separate mathematical
oracle and re-executes the exported declarative instrument; it never infers cash,
market fit, frontier parity or economic savings from retrospective arithmetic.
Run in the existing HARNESS environment, without API calls or credentials.
"""
from __future__ import annotations
import argparse
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=lambda x: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def exact_equal(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(exact_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(exact_equal(x, y) for x, y in zip(a, b))
    return a == b


def _integer(row, field):
    value = row.get(field)
    if type(value) is not int:
        raise ValueError('NONINTEGER_'+field.upper())
    return value


def oracle_window(row):
    lo, hi = _integer(row, 'ready'), _integer(row, 'until')
    if not (0 <= lo <= hi <= 6):
        raise ValueError('INVALID_WINDOW_INTERVAL')
    measurements = [_integer(row, 'c'+str(i)) for i in range(6)]
    best = None
    for start in range(6):
        if start < lo or start + 2 > hi:
            continue
        a, b = measurements[start], measurements[start+1]
        if a < 0 or b < 0:
            continue
        candidate = (a+b, start)
        if best is None or candidate < best:
            best = candidate
    return {'start': -1, 'total': -1} if best is None else {'start': best[1], 'total': best[0]}


def oracle_quote(row):
    offers = []
    for rank, name in enumerate(('cad','usd','eur','gbp')):
        amount = _integer(row, name)
        if amount < 0:
            continue
        factor = 10000 if name == 'cad' else _integer(row, name+'_rate')
        if factor < 0:
            raise ValueError('NEGATIVE_EXCHANGE_FACTOR')
        offers.append((Decimal(amount)*Decimal(factor), rank, name.upper()))
    if not offers:
        return {'currency': 'NONE', 'scaled_cad': -1}
    chosen = sorted(offers)[0]
    return {'currency': chosen[2], 'scaled_cad': int(chosen[0])}


def oracle_catalogue(row):
    m, error, threshold = (_integer(row, n) for n in ('m','error','floor'))
    if type(row.get('reviewed')) is not bool:
        raise ValueError('REVIEWED_BOOLEAN_REQUIRED')
    if not row['reviewed'] or error < 0:
        return {'status':'defer'}
    lower, upper = Fraction(m-error), Fraction(m+error)
    target = Fraction(threshold)
    return {'status': 'include' if lower >= target else 'exclude' if upper < target else 'defer'}


ORACLES = {'window':oracle_window,'quote':oracle_quote,'catalogue':oracle_catalogue}
SOURCE_BY_CONTRACT = {'window':'electricity','quote':'exchange-rates','catalogue':'seismic-archive'}


def source_cohort(sources, contract):
    """Build the entire cohort independently from the preserved source bytes.

    Uses a separate implementation from the generator and never trusts its
    recorded expected answers. No public API network access is needed.
    """
    obj=json.loads(sources[SOURCE_BY_CONTRACT[contract]]['snapshot']['body'])
    rows=[]
    if contract=='window':
        source=obj['data']
        if len(source)<84:
            raise ValueError('SOURCE_HAS_TOO_FEW_INTENSITIES')
        for a,b in zip(source,source[1:]):
            if a['to'] != b['from']:
                raise ValueError('NONCONTINUOUS_SOURCE_INTERVALS')
        for j in range(14):
            segment=source[j*6:j*6+6]
            values=[r['intensity']['actual'] for r in segment]
            if any(type(x) not in (int,type(None)) for x in values):
                raise ValueError('SOURCE_INTENSITY_TYPE')
            rows.append({**{'c'+str(i): (-1 if x is None else x) for i,x in enumerate(values)},
                         'ready':j%3,'until':6-j%2})
    elif contract=='quote':
        for i,rec in enumerate(obj['observations']):
            conversion={}
            for c in ('USD','EUR','GBP'):
                rate=Decimal(rec['FX'+c+'CAD']['v'])*Decimal(10000)
                conversion[c.lower()+'_rate']=int(rate)  # declared decimal-to-integer truncation
            rows.append({'cad':182+(7*i)%16,'usd':132-i%6,
                         'eur':-1 if i%4==0 else 111+i%9,'gbp':100-i%5,**conversion})
    else:
        for i,event in enumerate(obj['features']):
            record=event['properties']
            mag=record['mag']
            if mag is None: continue
            error=record.get('magError')
            rows.append({'m':int(Decimal(str(mag))*1000),
                         'error':-1 if error is None else int(Decimal(str(error))*1000),
                         'floor':(6000,6250,6500)[i%3],
                         'reviewed':record['status']=='reviewed'})
    unique={}
    for row in rows:
        identity=json.dumps(row,sort_keys=True,separators=(',',':'))
        unique.setdefault(identity,row)
    if len(unique)<7:
        raise ValueError('SOURCE_HAS_TOO_FEW_DISTINCT_CASES')
    return list(unique.values())


def audit_sources(sources):
    if not isinstance(sources, dict) or not sources:
        raise ValueError('PRIMARY_SOURCE_MAP_REQUIRED')
    audits=[]
    for ident, row in sorted(sources.items()):
        url = row['url']
        loc = urlsplit(url)
        if loc.scheme != 'https' or not loc.hostname or loc.username or loc.password or loc.fragment:
            raise ValueError('INVALID_PRIMARY_SOURCE_URL')
        snap = row.get('snapshot',{})
        raw = snap.get('body','')
        if type(raw) is not str or not raw:
            raise ValueError('SOURCE_BYTES_NOT_PRESERVED')
        digest=sha(raw.encode('utf-8'))
        if digest != snap.get('sha256'):
            raise ValueError('SOURCE_SHA256_MISMATCH')
        json.loads(raw,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_SOURCE')))
        audits.append({'id':ident,'uri':url,'sha256':digest,'bytes':len(raw.encode('utf-8'))})
    return audits


def window_proxy(cases):
    """Only a counterfactual emissions-intensity proxy for one notional 1kWh job."""
    matched=0
    savings=Fraction(0)
    for case in cases:
        data=case['input']
        chosen=oracle_window(data)
        if chosen['start'] < 0: continue
        earliest=None
        for start in range(data['ready'],data['until']-1):
            pair=(data['c'+str(start)],data['c'+str(start+1)])
            if pair[0]>=0 and pair[1]>=0:
                earliest=sum(pair)
                break
        if earliest is None: continue
        improvement=Fraction(earliest-chosen['total'],2)
        if improvement < 0: raise ValueError('OPTIMIZER_WORSE_THAN_EARLIEST')
        matched+=1
        savings+=improvement
    return {'compared_cases':matched,'counterfactual_total_gco2_per_notional_kwh':str(savings),
            'units':'gCO2/kWh per retrospective notional constant-power job',
            'not_observed':'No workload was scheduled, no energy measured, and no monetary value or emissions reduction was realized.'}


def audit(work:Path):
    source_file=work/'SOURCES.json'
    result_file=work/'RESULT.json'
    sources=read_json(source_file)
    result=read_json(result_file)
    source_audit=audit_sources(sources)
    conclusion={'schema':'omega-alpha/independent-first-asset-review/v1',
        'source_inputs_sha256':sha(source_file.read_bytes()),
        'producer_receipt_sha256':sha(result_file.read_bytes()),
        'primary_sources':source_audit,
        'real_customers_verified':False,'collected_money_verified':False,
        'complete_cost_profit_verified':False,'economic_crossing_verified':False,
        'frontier_parity_verified':False,'inventor_improvement_verified':False,
        'observed_monetization':'NOT_ESTABLISHED',
        'scope':'Independent review of generated executable and fresh source-derived cases, not real-world asset deployment.'}
    if result.get('status')!='complete':
        return {**conclusion,'status':'NO_QUALIFIED_ARTIFACT','producer_status':result.get('status'),
                'reason':'The model-led economic mission did not deliver a completed qualifying artifact.'}
    choice=result.get('choice') or {}
    contract=choice.get('contract')
    if contract not in ORACLES:
        raise ValueError('UNSUPPORTED_OR_UNDECLARED_CONTRACT')
    if result.get('verification',{}).get('passed') is not True:
        raise ValueError('PRODUCER_CLAIMS_COMPLETE_WITHOUT_QUALIFICATION')
    asset=read_json(work/'asset.json')
    archive=read_json(work/'ARCHIVE.json')
    registration=read_json(work/'REGISTRATION.json')
    mission=read_json(work/'MISSION.json')
    if mission.get('economic_mission',{}).get('sources') != sources:
        raise ValueError('MISSION_SOURCE_SNAPSHOT_MISMATCH')
    from bridge.workflows import digest
    if digest(mission)!=registration.get('spec_sha256') or result.get('spec_sha256')!=registration.get('spec_sha256'):
        raise ValueError('REGISTRATION_SOURCE_CONTRACT_MISMATCH')
    if result.get('successor_sha256')!=registration.get('successor_sha256'):
        raise ValueError('REGISTRATION_SUCCESSOR_MISMATCH')
    frozen=result.get('frozen') or {}
    if sha((work/'asset.json').read_bytes()) != frozen.get('sha256'):
        raise ValueError('FROZEN_EXECUTABLE_HASH_MISMATCH')
    if archive.get('files',{}).get('asset.json') != (work/'asset.json').read_text(encoding='utf-8'):
        raise ValueError('EXPORTED_ASSET_DIFFERS_FROM_SEALED_CANDIDATE')
    from bridge.instruments import evaluate
    spec=archive.get('state',{}).get('spec',{})
    max_operations=spec.get('max_operations')
    if type(max_operations) is not int or max_operations <= 0:
        raise ValueError('EXECUTION_BUDGET_MISSING')
    fields=('qualification_comparison','fresh_transfer')
    full_source=source_cohort(sources,contract)
    expected_inputs={
        'qualification_comparison':full_source[3:-2],
        'fresh_transfer':full_source[-2:]}
    details={}
    all_cases=[]
    case_identity=set()
    for group in fields:
        record=result.get(group)
        if not isinstance(record,dict) or not isinstance(record.get('cases'),list) or not record['cases']:
            raise ValueError('FRESH_CASES_MISSING_'+group.upper())
        if len(record['cases'])!=len(expected_inputs[group]):
            raise ValueError('SOURCE_COHORT_INCOMPLETE_'+group.upper())
        success=0
        digest_set=set()
        for case,source_input in zip(record['cases'],expected_inputs[group]):
            if not exact_equal(case['input'],source_input):
                raise ValueError('SOURCE_COHORT_INPUT_MUTATED_OR_REORDERED')
            data=case['input']
            identity=sha(json.dumps(data,sort_keys=True,separators=(',',':')).encode())
            if identity in digest_set:
                raise ValueError('DUPLICATE_INPUT_'+group.upper())
            digest_set.add(identity)
            if identity in case_identity:
                raise ValueError('QUALIFICATION_AND_TRANSFER_INPUT_OVERLAP')
            case_identity.add(identity)
            reference=ORACLES[contract](data)
            if not exact_equal(reference,case['expected']):
                raise ValueError('EXPECTED_ANSWER_NOT_INDEPENDENTLY_SUPPORTED')
            actual=evaluate(asset,data,max_operations)['output']
            if exact_equal(actual,reference): success+=1
            all_cases.append(case)
        details[group]={'total':len(record['cases']),'independent_passes':success,
                        'passed':success==len(record['cases'])}
    if not all(x['passed'] for x in details.values()):
        status='REJECTED_FRESH_QUALIFICATION'
    else:
        status='VERIFIED_BOUNDED_ARITHMETIC_ASSET'
    benefit=window_proxy(all_cases) if contract=='window' else {
        'status':'NOT_ESTABLISHED',
        'reason':'Registered quotes are hypothetical or catalogue decisions lack an independently measured beneficiary outcome.'}
    return {**conclusion,'status':status,'contract':contract,
            'independent_execution':details,'operating_benefit':benefit,
            'comparison_to_strong_specialist':'PARITY_OR_UNMEASURED; direct ordinary specialist performs same registered function',
            'economic_usefulness':'NOT_ESTABLISHED_WITHOUT_REAL_WORKFLOW_AND_COMPLETE_COST',
            'causal_invention_advantage':'NOT_ESTABLISHED'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    report=audit(args.work)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists(): raise SystemExit('REFUSE_EXISTING_RECEIPT')
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'economic_usefulness':report.get('economic_usefulness','NOT_ESTABLISHED')}))

if __name__=='__main__': main()
