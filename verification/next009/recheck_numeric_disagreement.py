import importlib.util,json
from fractions import Fraction
from pathlib import Path

root=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('independent_resolved_checker',Path(__file__).with_name('verify.py'))
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
base=root/'evidence/next009/verification'
original=json.loads((base/'runtime-adversary-v1/artifacts/COUNTEREXAMPLES.json').read_text())
resolved=json.loads((base/'net1-canonical-final-development/artifacts/DEVELOPMENT_CASES.json').read_text())['cases']
by_id={c['case']:c for c in resolved}
corpus=json.loads((root/'evidence/next009/construction/networks-v2/artifacts/Net1/model/corpus.json').read_text())
data=checker.corpus_values(corpus);nodes=corpus['nodes'];sources=corpus['sources'];rows=[]
for item in original:
    case=item['case'];observed={nodes.index(s):[Fraction(v) for v in values] for s,values in case['observations'].items()};reference={nodes.index(s):Fraction(v) for s,v in case['reference'].items()}
    compatible=[sources[i] for i in range(len(sources)) if checker.compatible_source(data,i,observed,reference,list(observed),Fraction(1))]
    violations=[];source=sources.index(case['true_source'])
    for s,values in observed.items():
        offset=Fraction(case['offsets'][nodes[s]])
        if abs(reference[s]-offset)>1:violations.append({'sensor':nodes[s],'kind':'reference'})
        for t,value in enumerate(values):
            error=value-offset-data[source][t][s]
            if abs(error)>1:violations.append({'sensor':nodes[s],'time':t,'kind':'read','error':str(error)})
    replacement=by_id[case['case']]
    same_latents=all(case[k]==replacement[k] for k in ('true_source','erased','offsets','reference'))
    rows.append({'case':case['case'],'original_candidate_status':item['candidate_result']['status'],'original_candidate_sources':item['candidate_result']['sources'],'same_original_observations_canonical_model_compatible':compatible,'candidate_and_resolved_checker_agree':compatible==item['candidate_result']['sources'],'violates_resolved_bound_for_recorded_latents':bool(violations),'violations':violations,'canonical_counterpart_same_offsets_reference_and_erasures':same_latents,'canonical_counterpart_passed':replacement['passed']})
report={'schema':'agi-alpha/next009-numeric-spec-disagreement-adjudication/v1','original_binary_cases':len(rows),'original_cases_reclassified_as_passed':0,'resolved_checker_agrees_with_original_candidate_count':sum(r['candidate_and_resolved_checker_agree'] for r in rows),'original_observations_outside_resolved_latent_error_bounds_count':sum(r['violates_resolved_bound_for_recorded_latents'] for r in rows),'same_latents_canonical_counterparts_passed':sum(r['canonical_counterpart_same_offsets_reference_and_erasures'] and r['canonical_counterpart_passed'] for r in rows),'rows':rows,'scope':'Preserves original 19 failures under different numeric specifications. The candidate already used canonical decimal semantics; this is pre-freeze specification resolution, not a demonstrated algorithmic repair.'}
out=base/'numeric-spec-adjudication/RECHECK.json'
with out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
