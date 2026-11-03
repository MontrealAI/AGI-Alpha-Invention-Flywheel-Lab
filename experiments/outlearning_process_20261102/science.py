"""Reaction-to-process program construction; no network, models or physical actuation.

Species A/B/C are generic. Graph expansion and measurement programs are synthesized
inside the declared grammar, not unrestricted model-generated scientific discovery.
"""
from __future__ import annotations
import itertools, math, time
import numpy as np
from scipy.optimize import least_squares

EDGE_NAMES = ('A_to_B', 'B_to_C', 'A_to_C', 'B_to_A')
INITIAL_GRAPHS = ((1,1,0,0), (1,0,1,0))
EXPANDED_GRAPHS = tuple((1,*bits) for bits in itertools.product((0,1), repeat=3))
TIMES = (.125,.25,.5,1.,2.,4.,8.)
# Mixtures are constructed at runtime from a denominator-four simplex grammar.
# Availability/purity of the intermediate is an assumption, not a physical fact.
def actions():
    return [(float(t),j/4.) for t in TIMES for j in range(5)]


def response(rates, time_s, fraction_b=0.):
    """Closed-form two-state exponential; C is the mass-balance complement."""
    r=np.asarray(rates,float);t=np.asarray(time_s,float);q=np.asarray(fraction_b,float)
    if r.shape!=(4,) or not np.isfinite(r).all() or np.any(r<0):raise ValueError('RATES')
    a=r[0]+r[2]; b=r[3]; c=r[0]; d=r[1]+r[3]
    mid=-(a+d)/2.; delta=math.sqrt(((d-a)/2.)**2+b*c)
    if delta<1e-10:
        h=t*np.exp(mid*t);v=np.exp(mid*t)
    else:
        ep=np.exp((mid+delta)*t);em=np.exp((mid-delta)*t)
        h=(ep-em)/(2*delta);v=(ep+em)/2
    aa=v*(1-q)+h*((d-a)/2*(1-q)+b*q)
    bb=v*q+h*(c*(1-q)+(a-d)/2*q)
    return np.stack((aa,bb,1-aa-bb),axis=-1)


def _predict_records(rates, records):
    return response(rates,np.array([x['time_s'] for x in records]),np.array([x['fraction_b'] for x in records]))


def fit_graph(records, graph):
    idx=np.flatnonzero(graph);target=np.array([x['observed'] for x in records])
    def full(v):
        r=np.zeros(4);r[idx]=v;return r
    def residual(v):return (_predict_records(full(v),records)-target).ravel()
    best=None
    for initial in (.12,.8):
        result=least_squares(residual,np.full(len(idx),initial),bounds=(1e-6,3.),
                             max_nfev=130,ftol=1e-9,xtol=1e-9,gtol=1e-9)
        err=float(np.max(np.abs(residual(result.x))))
        if best is None or np.sum(result.fun**2)<best['sse']:
            best={'graph':list(graph),'rates':full(result.x).tolist(),'max_residual':err,
                  'sse':float(np.sum(result.fun**2)),'nfev':int(result.nfev),'dimension':len(idx)}
    return best


def compatible(records, graphs, noise_bound):
    fits=[fit_graph(records,g) for g in graphs]
    allowed=[f for f in fits if f['max_residual']<=noise_bound+2e-5]
    # Retain all compatible graph explanations, not merely the lowest residual.
    return allowed,fits


def synthesize_probe(models, seen, retained):
    candidates=[a for a in actions() if a not in seen]
    if not candidates:return None,0.
    ranked=[]
    for a in candidates:
        p=np.array([response(m['rates'],*a) for m in models])
        disagreement=float(np.max(np.ptp(p,axis=0))) if len(p)>1 else 0.
        priority=1. if list(a) in retained.get('prefix',[]) else 0.
        # Scores only use fitted explanations and public inputs.
        ranked.append((disagreement,priority,-a[0],-a[1],a))
    best=max(ranked)
    return best[-1],best[0]


def produce(observe, *, arm, retained, noise_bound, budget):
    if arm not in ('initial','retained','ordinary','equal_content'):raise ValueError('ARM')
    records=[];trace=[];seen=set();graphs=INITIAL_GRAPHS if arm in ('initial','retained') else EXPANDED_GRAPHS
    start=time.process_time();expansions=0
    if noise_bound>.04:
        return {'status':'UNRESOLVED_NOISE','records':[],'models':[],'trace':[{'decision':'STOP','reason':'noise exceeds commissioned predictive tolerance'}],
                'queries':0,'expansions':0,'cpu_seconds':time.process_time()-start}
    prefix=[(.25,0.),(2.,0.)]
    if arm in ('retained','ordinary','equal_content'):
        prefix+= [tuple(a) for a in retained['prefix'] if tuple(a) not in prefix]
    if arm=='initial':prefix +=[(.5,0.),(1.,0.)]
    fitting=[];models=[]
    for step in range(budget):
        if prefix: action=prefix.pop(0);reason='retained_experiment_program' if step>=2 and arm!='initial' else 'initial_observation'
        else:
            action,info=synthesize_probe(models or fitting,seen,retained);reason='max_model_disagreement'
            if action is None:break
        if action in seen:raise ValueError('DUPLICATE_QUERY')
        observed=observe(*action);seen.add(action)
        records.append({'time_s':action[0],'fraction_b':action[1],'observed':[float(v) for v in observed]})
        if (abs(sum(observed)-1)>3*noise_bound+1e-5 or min(observed)<-noise_bound or max(observed)>1+noise_bound):
            trace.append({'step':step,'action':list(action),'reason':reason,'decision':'ABSTAIN','evidence':'mass or calibration contradiction'})
            return {'status':'UNRESOLVED_CALIBRATION','records':records,'models':[],'trace':trace,'queries':len(records),'expansions':expansions,'cpu_seconds':time.process_time()-start}
        models,fitting=compatible(records,graphs,noise_bound)
        if len(records)>=2 and not models and graphs==INITIAL_GRAPHS:
            graphs=EXPANDED_GRAPHS;expansions+=1
            models,fitting=compatible(records,graphs,noise_bound)
            trace.append({'step':step,'decision':'EXPAND','from':[list(g) for g in INITIAL_GRAPHS],
                          'to':[list(g) for g in EXPANDED_GRAPHS], 'reason':'neither initial explanation fits bounded observations'})
        trace.append({'step':step,'action':list(action),'reason':reason,'compatible_graphs':len(models),
                      'minimum_residual':min(f['max_residual'] for f in fitting),'decision':'CONTINUE'})
        # Require an actual intervention involving B and two post-fit validation observations.
        # These are protocol rules, shared by all arms, not claimed learned intelligence.
        enough=len(records)>=6 and any(x['fraction_b']>.2 for x in records)
        if enough and models:
            next_action,disagreement=synthesize_probe(models,seen,retained)
            if disagreement<=.015:
                return {'status':'MODEL_CANDIDATE','records':records,'models':models,'trace':trace,
                        'queries':len(records),'expansions':expansions,'cpu_seconds':time.process_time()-start}
    return {'status':'MODEL_CANDIDATE' if models and len(records)>=6 and any(x['fraction_b']>.2 for x in records) else 'UNRESOLVED_BUDGET_OR_MODEL',
            'records':records,'models':models,'trace':trace,'queries':len(records),'expansions':expansions,'cpu_seconds':time.process_time()-start}


DESIGNS=tuple((t,s,f) for t in (.25,.5,1.,2.,4.,8.) for s in (.25,.5,1.,2.,4.,8.) for f in (0.,.5,1.))


def design_response(rates, design):
    t,s,f=design;first=response(rates,t);removed=f*first[1]
    feed=first.copy();feed[1]*=1-f
    kab,kbc,kac,kba=rates
    matrix=np.array([[-kab-kac,kba,0],[kab,-kbc-kba,0],[kac,kbc,0.]])
    second=np.linalg.solve(np.eye(3)-s*matrix,feed)
    product=removed+second[1]
    # Separator purity, zero holdup and linear kinetics are commissioned assumptions.
    score=product-.02*(t+s)-.10*f
    return float(product),float(score),second.tolist()


def construct_process(k1):
    if k1['status']!='MODEL_CANDIDATE' or not k1['models']:
        return {'status':'NO_DEPLOY','reason':k1['status'],'design':None}
    candidates=[]
    for d in DESIGNS:
        values=[design_response(m['rates'],d) for m in k1['models']]
        lo=min(v[0] for v in values);score=min(v[1] for v in values)
        if lo>=.40:candidates.append((score,-sum(d[:2]),d,lo))
    if not candidates:return {'status':'NO_DEPLOY','reason':'no robust design reaches product-yield contract','design':None}
    score,_,design,lo=max(candidates)
    return {'status':'DESIGN_CANDIDATE','design':list(design),'predicted_min_yield':lo,'predicted_min_score':score,
            'candidate_count':len(DESIGNS),'operating_scope':'SIMULATED_FIRST_ORDER_PFR_SEPARATOR_CSTR_NOT_MANUFACTURED'}
