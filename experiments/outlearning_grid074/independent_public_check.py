"""Portable independent review. Does not import retained_symmetry or evaluator.

Exact rank uses the Faddeev-LeVerrier characteristic polynomial of A^T A,
not the retained algorithm's row-reduction/nullspace implementation.
This wrapper was authored after the negative result for public reproduction.
"""
import copy
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
from thermal_k1 import ThermalSession, development_worlds, self_test as thermal_test

ROOT=Path(__file__).parent

def load(name):return json.loads((ROOT/name).read_text())

def constraints(card,reference=False):
    names=card['variables'];rows=[]
    for terms in card['equations']:
        weights=[[F(str(term.get(name,0))) for name in names] for term in terms]
        rows += [[b-a for a,b in zip(weights[0],term)] for term in weights[1:]]
    rows += [[F(int(name==fixed)) for name in names] for fixed in card['fixed']]
    if reference:
        rows += [[F(str(card['allowed_references'][0]['monomial'].get(name,0))) for name in names]]
    return rows

def multiply(a,b):
    return [[sum((x*y for x,y in zip(row,col)),F(0)) for col in zip(*b)] for row in a]

def exact_rank(rows,n):
    gram=multiply(list(map(list,zip(*rows))),rows)
    B=[[F(int(i==j)) for j in range(n)] for i in range(n)]
    coefficients=[F(1)]
    for k in range(1,n+1):
        AB=multiply(gram,B)
        c=-sum((AB[i][i] for i in range(n)),F(0))/k
        coefficients.append(c)
        B=[[AB[i][j]+(c if i==j else 0) for j in range(n)] for i in range(n)]
    nullity=0
    for coefficient in reversed(coefficients):
        if coefficient:break
        nullity+=1
    return {'rank':n-nullity,'nullity':nullity,'columns':n,
            'algorithm':'exact rational Faddeev-LeVerrier characteristic polynomial of Gram matrix'}

def two_bus(r,x,p,q,E=1.):
    a=E*E+2*(r*p+x*q);b=(r*r+x*x)*(p*p+q*q)
    D=a*a-4*b
    assert D>0
    v=(a+math.sqrt(D))/2
    V=complex(v-r*p-x*q,x*p-r*q)/E
    I=(E-V)/complex(r,x)
    injection=-V*I.conjugate()
    assert abs(injection-complex(p,q))<1e-12
    return {'voltage':math.sqrt(v),'current':abs(I),'v':v,'ell':abs(I)**2,
            'power_residual':abs(injection-complex(p,q))}

def fixed_q0_ray(r,x,cap,E):
    # Exact concavity permits endpoint maximum when derivative(cap)>0.
    v0=E*E;D=v0*v0+4*v0*r*cap-4*x*x*cap*cap
    derivative=r+(v0*r-2*x*x*cap)/math.sqrt(D)
    assert derivative>0
    endpoint=two_bus(r,x,cap,0.,E)
    # Current is monotone on the positive high-voltage branch; see SOURCES.md.
    safe=(.95<=E and endpoint['voltage']<=1.05 and endpoint['current']<=.90)
    return {'safe':safe,'max_voltage':endpoint['voltage'],'max_current':endpoint['current'],'min_voltage':E}

def run():
    freeze=load('K1_FREEZE.json')
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in freeze['files'].items())
    k1=load('k1_card.json');k2=load('k2_card.json');cf=copy.deepcopy(k2);cf['fixed'].remove('u')
    matrices={}
    for name,card in [('K1',k1),('K2_fixed_source',k2),('K2_unanchored_counterfactual',cf)]:
        matrices[name]=exact_rank(constraints(card),len(card['variables']))
        matrices[name]['with_reference']=exact_rank(constraints(card,True),len(card['variables']))
    assert [matrices[k]['nullity'] for k in matrices]==[1,0,1]
    assert all(d['with_reference']['nullity']==0 for d in matrices.values())
    for card,gauge in [(k1,{'theta':-1,'C':1,'loss':1,'gain':1}),
                       (cf,{'v':2,'u':2,'ell':-2,'r':2,'x':2,'gain':-1})]:
        v=[gauge.get(n,0) for n in card['variables']]
        assert all(sum(a*b for a,b in zip(row,v))==0 for row in constraints(card))
    observed=load('K1_OBSERVATIONS.json')
    replayed=[];total_cost=0.
    for record,w in zip(observed,development_worlds()[:2]):
        ses=ThermalSession(w)
        outputs=[ses.observe(t['power'],t['time'],t['kind']) for t in record['observations']]
        assert outputs==record['observations']
        total_cost+=sum(t['cost'] for t in outputs)
        result=ses.evaluate({'cap':2.5,'hypothesis':'abstain'})
        replayed.append({'cap_safe':not result['unsafe_claim'],'true_max_rise':result['true_max_rise'],'unsafe_probes':result['unsafe_probe_count']})
    assert total_cost==22 and [x['cap_safe'] for x in replayed]==[False,True]
    assert all(x['unsafe_probes']==0 for x in replayed)
    r,x,g,b,scale=.08,.09,.83,.17,1.02
    error=0.;held_source_mismatch=0.;branch_residual=0.
    for p,q in [(.1,.12),(.3,-.1),(.5,.2),(.6,-.25)]:
        s=two_bus(r,x,p,q)
        t=two_bus(scale*scale*r,scale*scale*x,p,q,scale)
        wrong=two_bus(scale*scale*r,scale*scale*x,p,q,1.)
        error=max(error,abs(g*s['voltage']+b-((g/scale)*t['voltage']+b)))
        held_source_mismatch=max(held_source_mismatch,abs(g*s['voltage']+b-((g/scale)*wrong['voltage']+b)))
        assert abs(t['voltage']-scale*s['voltage'])<1e-12
        assert abs(t['current']-s['current']/scale)<1e-12
        ell=s['ell'];P=r*ell-p;Q=x*ell-q
        residuals=[P+p-r*ell,Q+q-x*ell,s['v']-1+2*(r*P+x*Q)-(r*r+x*x)*ell,ell-P*P-Q*Q]
        branch_residual=max(branch_residual,*map(abs,residuals))
    assert error<1e-12 and held_source_mismatch>1e-3 and branch_residual<1e-12
    base=fixed_q0_ray(r,x,.5,1.)
    scaled=fixed_q0_ray(r*scale*scale,x*scale*scale,.5,scale)
    assert base['safe'] and not scaled['safe']
    return {'passed':True,'candidate_imported':False,'frozen_files_unchanged':True,
            'exact_rank_checks':matrices,'K1_observations_exactly_reproduced':True,'K1_acquisition_units':total_cost,
            'K1_physical_cap_2_5_witness':replayed,'thermal_independent_ode_test':thermal_test(),
            'K2_counterfactual_meter_error':error,'K2_held_source_mismatch':held_source_mismatch,
            'K2_signed_equation_residual':branch_residual,'K2_base_cap_0_5':base,'K2_scaled_source_counterfactual_cap_0_5':scaled,
            'scope':'negative multiplicative-scaling transfer test only; counterfactual source change excluded from actual K2; no blind confirmation or economics'}

if __name__=='__main__':print(json.dumps(run(),indent=2))
