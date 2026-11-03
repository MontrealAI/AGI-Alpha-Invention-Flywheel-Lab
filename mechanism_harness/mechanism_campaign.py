"""Registered end-to-end mechanism-construction comparison, not market evidence."""
from __future__ import annotations
import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import time

import scipy
from commercial.ledger import canonical,digest,strict_json
from . import market_program as v
from .mechanism_synthesis import synthesize,retain
from .market_cases import market

CASES=((391101,'complementary'),(391102,'substitute'),(391103,'competitive'))
SOURCE_NAMES=('mechanism_harness/market_program.py','mechanism_harness/mechanism_synthesis.py',
              'mechanism_harness/market_cases.py','mechanism_harness/mechanism_campaign.py')


def source_identity():
    root=Path(__file__).resolve().parents[1];result={}
    for name in SOURCE_NAMES:
        path=root/name
        if not path.is_file() or any(x.is_symlink() for x in (path,*path.parents)):
            raise ValueError('REGULAR_SOURCE_REQUIRED')
        result[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def logical(x):
    if isinstance(x,dict):return {k:logical(value) for k,value in x.items() if k not in ('construction_cpu_ns','solver_cpu_ns')}
    if isinstance(x,list):return [logical(value) for value in x]
    return x


def execute(cases=CASES):
    memory=None;rows=[];history_cost=0
    for seed,family in cases:
        memory_before=copy.deepcopy(memory)  # freeze inherited means before fresh market creation
        m=market(seed,family)
        inherited=synthesize(m,memory=memory_before)
        cold=synthesize(m)
        full=synthesize(m,mode='full')
        separate=synthesize(m,mode='full',restriction='separate')
        bundle=synthesize(m,mode='full',restriction='bundle')
        runs={'inherited':inherited,'cold':cold,'full_control':full,'separate':separate,'bundle':bundle}
        all_valid=all(r['program'] is not None and v.verify(m,r['program'])['accepted'] for r in runs.values())
        if not all_valid:
            rows.append({'market':m,'runs':runs,'status':'UNRESOLVED','memory_before':memory_before})
            # A failed game remains in the denominator; do not create false inheritance.
            continue
        contribution=lambda name:Fraction(runs[name]['verification']['expected_contribution_cents'])
        best_standard=max(('separate','bundle'),key=lambda name:(contribution(name),name=='bundle'))
        choices=[]
        for t,r in zip(m['types'],inherited['program']['rules']):
            observed=v.buyer_choose(m,inherited['program'],{k:t[k] for k in ('values','budget_cents','outside_utility')})
            if observed['outcome_id']!=r['outcome_id'] or observed['price_cents']!=r['price_cents']:
                raise ValueError('DECLARED_INCENTIVE_DOES_NOT_SURVIVE_ACTUAL_BUYER_CHOICE')
            choices.append(observed)
        # A copied menu is a genuine competitor option: buyer can refuse us for it.
        copycat=[]
        for t in m['types']:
            private={k:copy.deepcopy(t[k]) for k in ('values','budget_cents','outside_utility')}
            best_gross=max([private['outside_utility']]+[private['values'][next(j for j,o in enumerate(m['outcomes']) if o['id']==r['outcome_id'])]-r['price_cents'] for r in inherited['program']['rules'] if r['outcome_id']!='outside' and r['price_cents']<=private['budget_cents']])
            private['outside_utility']=best_gross
            copycat.append(v.buyer_choose(m,inherited['program'],private))
        memory=retain(m,inherited,memory_before)
        rows.append({'market':m,'runs':runs,'status':'VERIFIED','memory_before':memory_before,
                     'memory_after':memory,'best_standard':best_standard,
                     'expected_gain_over_standard_cents':str(contribution('inherited')-contribution(best_standard)),
                     'expected_gain_over_full_control_cents':str(contribution('inherited')-contribution('full_control')),
                     'actual_supported_buyer_choices':choices,'copycat_choices':copycat,
                     'all_exact_checks_pass':all_valid,'equal_optimum_to_full_control':contribution('inherited')==contribution('full_control'),
                     'prior_discovery_rows':history_cost,
                     'inherited_vs_cold_rows_saved':cold['total_rows_built']-inherited['total_rows_built']})
        history_cost+=inherited['total_rows_built']
    valid=[r for r in rows if r['status']=='VERIFIED']
    totals={key:sum(r['runs'][key]['total_rows_built'] for r in valid) for key in ('inherited','cold','full_control','separate','bundle')}
    checks={key:sum(r['runs'][key]['deviation_checks'] for r in valid) for key in totals}
    cpu={key:sum(r['runs'][key]['construction_cpu_ns'] for r in valid) for key in totals}
    return {'schema':'omega/private-mechanism-campaign/v3','cases':rows,
            'registered_cases':len(cases),'completed_cases':len(valid),'total_rows_built':totals,
            'total_deviation_checks':checks,'construction_cpu_ns':cpu,
            'all_synthesized_programs_verified':len(valid)==len(rows),
            'registered_template_advantage_cases':sum(Fraction(r['expected_gain_over_standard_cents'])>0 for r in valid),
            'beats_strong_full_solver':any(Fraction(r['expected_gain_over_full_control_cents'])>0 for r in valid),
            'constraint_transfer_rows_saved':totals.get('cold',0)-totals.get('inherited',0),
            'actual_revenue_usd':0,'scope':'Finite synthetic private-information mechanism construction, independent integer checks and causal constraint transfer. No empirical demand or universal game-invention claim.',
            'runtime':{'python':platform.python_version(),'scipy':scipy.__version__}}


def audit(report):
    if report.get('source')!=source_identity():raise ValueError('SOURCE_CHANGED')
    if report.get('actual_revenue_usd')!=0 or report['registered_cases']!=len(CASES):raise ValueError('UNSUPPORTED_CLAIM_OR_DENOMINATOR')
    memory=None
    for row,(seed,family) in zip(report['cases'],CASES):
        m=market(seed,family)
        if m!=row['market'] or row['memory_before']!=memory:raise ValueError('MARKET_OR_INHERITANCE_CHANGED')
        for name,run in row['runs'].items():
            if run['program'] is None:continue
            checked=v.verify(m,run['program'])
            if checked!=run['verification'] or not checked['accepted']:raise ValueError('UNVERIFIED_MECHANISM')
        if row['status']=='VERIFIED':
            memory=retain(m,row['runs']['inherited'],memory)
            if memory!=row['memory_after']:raise ValueError('UNSUPPORTED_LEARNING')
    # Numerical solver choices can have tied optima; exact bound/check records and
    # this source-matched deterministic replay establish only the declared model.
    actual=execute()
    if logical({k:x for k,x in report.items() if k!='source'})!=logical(actual):
        raise ValueError('CAMPAIGN_REPLAY_CHANGED')
    return {'accepted':True,'report_logical_sha256':digest(logical(report)),
            'scope':'Exact program checks and source-matched numerical replay; no external certification.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--audit',action='store_true')
    a=p.parse_args(argv)
    if any(x.is_symlink() for x in (a.output,*a.output.absolute().parents)):raise ValueError('NO_SYMLINKS')
    if a.audit:print(json.dumps(audit(strict_json(a.output.read_bytes())),indent=2));return
    if a.output.exists():raise FileExistsError('PRESERVE_EXISTING_EVIDENCE')
    before=source_identity();r=execute()
    if before!=source_identity():raise ValueError('SOURCE_CHANGED_DURING_RUN')
    r['source']=before;a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('xb') as f:f.write(canonical(r)+b'\n')
    print(json.dumps({k:x for k,x in r.items() if k not in ('cases','source')},indent=2))

if __name__=='__main__':main()
