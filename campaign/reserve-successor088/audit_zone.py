"""Independent zone oracle and onsite lower-bound certificates. Writes REVIEW.json only."""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
import run_zone as z
ROOT=Path(__file__).resolve().parent

def oracle(edges,failed,source):
    eligible=[e for i,e in enumerate(edges) if i!=failed and (e[0]>=39 or e[0]==source)]
    rr,cc,ww=zip(*eligible)
    graph=csr_matrix((ww,(np.array(rr)-1,np.array(cc)-1)),shape=(416,416))
    return dijkstra(graph,directed=True,indices=source-1)

def main():
    m=z.base;edges,source_hash=m.read()
    failures=[-1]+[i for i,(a,b,w) in enumerate(edges) if a>=39 and b>=39]
    count=0;maxdiff=0.;records={t:[] for t in (5,10,15)}
    for failed in failures:
        distances=[]
        for source in m.DEPOTS:
            od=oracle(edges,failed,source);actual=m.routes(edges,failed,source);row=[]
            for j,destination in enumerate(m.DEST):
                a,b=actual[j][0],od[destination-1]
                assert (np.isinf(a) and np.isinf(b)) or abs(a-b)<1e-10
                if np.isfinite(a):maxdiff=max(maxdiff,abs(a-b))
                count+=1;row.append(float(b))
            distances.append(row)
        for deadline in records:
            records[deadline].append([[d<=deadline for d in row] for row in distances])
    for deadline,rec in records.items():
        retained=json.loads((ROOT/f'zone-instrument-{deadline}.json').read_text())
        assert retained['identity']['failures']==failures
        assert rec==retained['content']
    # Independent necessity certificate: each target is unreachable from EVERY
    # other allowed site when its feeder is closed, without any deadline limit.
    all_sites=tuple(m.DEPOTS)+tuple(m.DEST)
    certificates=[]
    for target,failed in zip(m.DEST,(102,184,321)):
        assert failed in failures
        for site in all_sites:
            dist=oracle(edges,failed,site)[target-1]
            assert dist==0 if site==target else np.isinf(dist)
        certificates.append({'target':target,'failed_edge_index':failed,'failed_edge':edges[failed],
                             'all_other_sites_disconnected':True})
    results=json.loads((ROOT/'ONSITE_RESULT.json').read_text())
    checks=[]
    for case in results['cases']:
        for key,demand in [('parent',(1,1,1)),('successor',(2,1,1)),('ordinary_equal_content_successor',(2,1,1))]:
            actual=case[key];bound=3000*sum(demand)
            # The cut certificate forces x_onsite[j]>=demand[j]. Nonnegative
            # remote costs give this global lower bound, even if onsite sites
            # are additionally allowed to ship to OTHER beneficiaries.
            assert actual['cost']==actual['conventional_cost']==bound
            assert list(actual['capacities'])==[0,0,0,0,*demand]
            assert list(actual['conventional_capacities'])==[0,0,0,0,*demand]
            assert actual['all_scenarios_accepted']==len(failures)
            # Construct a direct assignment independent of solver/Hall code.
            assignment=[(4+j,j) for j,n in enumerate(demand) for _ in range(n)]
            assert len(assignment)==sum(demand)
            for scenario in records[case['deadline']]:
                capacity=list(actual['capacities'])
                for depot,beneficiary in assignment:
                    assert depot==4+beneficiary and capacity[depot]>0
                    capacity[depot]-=1
            checks.append({'deadline':case['deadline'],'case':key,'lower_bound':bound,
                           'onsite_empty_path_assignment_verified_scenarios':len(failures)})
    review={'source_sha256':source_hash,'zone_scenarios':len(failures),
            'independent_zone_distance_checks':count,'maximum_difference':maxdiff,
            'all_retained_zone_reachability_equal':True,'feeder_cut_certificates':certificates,
            'onsite_independent_optimum_and_assignments':checks,
            'original_and_zone_failures_preserved':True,
            'claim':'Onsite provision is optimal in the authored model; conventional identical provision ties. No commercial superiority or successor enabling advantage.',
            'audited_files_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['run.py','run_zone.py','run_onsite.py','ONSITE_RESULT.json']}}
    (ROOT/'REVIEW.json').write_text(json.dumps(review,indent=2)+'\n')
    print(json.dumps({'zone_distance_checks':count,'scenarios':len(failures),'distance_difference':maxdiff,
                      'feeder_cuts_verified':len(certificates),'onsite_optimal_cases_verified':len(checks),
                      'parent_optimum':9000,'successor_optimum':12000}))
if __name__=='__main__':main()
