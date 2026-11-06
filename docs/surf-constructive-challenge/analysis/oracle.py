"""Separate finite oracle: subset-capacity inequalities, not producer max flow.

Shares the declared mathematical problem, not the producer functions. This is
implementation diversity under common authorship, not institutional independence.
"""
from itertools import combinations, product


def require(ok, reason):
    if not ok:raise ValueError(reason)


def oracle(case, financial=True):
    # Reconstruct strategy space and pricing independently.
    candidates=[]
    scenarios=[((),()),(('A',),()),(('B',),()),(('A','B'),())]
    if case.include_q_failure:scenarios.append((('A','B'),('Q',)))
    for bits in product((0,1),repeat=5):
        t,a,p,q,r=bits
        if t>case.adapter_available or a>case.pooling_available:continue
        if q and (not t or not case.supplier_q_accepted):continue
        reserved=tuple(s for s,on in zip(('P','Q','R'),(p,q,r)) if on)
        price=4+t*case.adapter_cost+a+4*p+9*r+q*(case.pooled_q_cost if a else 8)
        if financial and (price>case.cash or price>=case.price_per_buyer*2):continue
        valid=True
        for clients,failures in scenarios:
            for size in range(1,len(clients)+1):
                for subset in combinations(clients,size):
                    available=set()
                    for s in reserved:
                        if s in failures:continue
                        if s in ('P','R') or ('B' in subset and t):available.add(s)
                    if 4*size>4*len(available):valid=False
        if valid:candidates.append((price,(t,a,reserved)))
    if not candidates:return None
    price,choice=min(candidates)
    return {'cost':price,'key':choice,'surplus':case.price_per_buyer*2-price}


def check_witness(case,result):
    """Direct check of actual returned allocations and pricing against all scenarios."""
    expected=oracle(case)
    if expected is None:
        require(result['decision']=='DECLINE' and result['strategy'] is None,'FALSE_ADMISSION')
        require(result['cost'] is None and result['surplus'] is None,'FALSE_VALUE')
        require(result['witnesses']==[],'FALSE_WITNESS')
        return True
    require(result['decision']=='ADMIT_MODEL','MISSED_FEASIBLE_CONSTRUCTION')
    s=result['strategy'];key=(int(s['adapter']),int(s['pooling']),tuple(s['reserved']))
    require(key==expected['key'] and result['cost']==expected['cost'] and
            result['surplus']==expected['surplus'],'NOT_EXACT_BEST_CONSTRUCTION')
    demand_worlds=[((),()),(('A',),()),(('B',),()),(('A','B'),())]
    if case.include_q_failure:demand_worlds.append((('A','B'),('Q',)))
    got=[(tuple(w['world']['active']),tuple(w['world']['failed'])) for w in result['witnesses']]
    require(got==demand_worlds,'MISSING_OR_CHANGED_SCENARIO')
    for w in result['witnesses']:
        used={x:0 for x in s['reserved']}; served={x:0 for x in w['world']['active']}
        seen=set()
        for row in w['allocation']:
            c,p,n=row['client'],row['supplier'],row['units']
            require(c in served and p in used and p not in w['world']['failed'],'BAD_EDGE')
            require(p!='Q' or (c=='B' and s['adapter']),'UNQUALIFIED_INTERFACE')
            require(type(n) is int and 0<n<=4 and (c,p) not in seen,'BAD_FLOW')
            seen.add((c,p));used[p]+=n;served[c]+=n
        require(all(n==4 for n in served.values()) and all(n<=4 for n in used.values()),'PROMISE_OR_CAPACITY_VIOLATION')
        require(w['feasible'] is True and w['required_units']==4*len(served)
                and w['delivered_units']==sum(served.values()),'MISSTATED_FLOW')
    return True


def source_check(required, presented, fulfilled):
    """A declared finite obligation set, not a semantic judge of natural books."""
    missing_from_summary=set(required)-set(presented)
    missing_from_outcome=set(required)-set(fulfilled)
    return {'accepted':not(missing_from_summary or missing_from_outcome),
            'missing_from_summary':sorted(missing_from_summary),
            'missing_from_outcome':sorted(missing_from_outcome)}


def classify_criticism(required, source_ids, presented, claim):
    """Adjudicate against source and output, not the critic's self-reported facts.

    The finite source labels and material requirements are authored. A critic can
    supply a false 'present' field; it is deliberately ignored. Natural semantic
    coverage and source authenticity are outside this finite model.
    """
    item = claim['source_id']
    if item not in source_ids:return 'UNSUPPORTED'
    if item not in required:return 'IMMATERIAL_TO_THIS_CHARTER'
    if item in presented:return 'FALSE_CRITICISM'
    return 'MATERIAL_OMISSION'
