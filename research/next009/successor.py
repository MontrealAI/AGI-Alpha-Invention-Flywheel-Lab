import argparse, hashlib, itertools, json, math, time
from fractions import Fraction
from pathlib import Path
import numpy as np
from flywheel import retention
from inventions.measurement009 import compiler

DRIFT_GRID = ('0', '1', '5', '10', '25')

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, value):
    with Path(path).open('xb') as stream: stream.write(canonical(value)+b'\n')

def source_identity(root):
    return {'path':'inventions/measurement009/compiler.py','sha256':sha(Path(root)/'inventions/measurement009/compiler.py')}

def verified_parent(root, plan_path, receipt_path, verifier_path, protocol_path, expected):
    for key, path in [('plan',plan_path),('receipt',receipt_path),('verifier',verifier_path),('protocol',protocol_path)]:
        if sha(path) != expected[key]: raise ValueError('FROZEN_IDENTITY_'+key)
    plan, receipt = json.loads(Path(plan_path).read_bytes()), json.loads(Path(receipt_path).read_bytes())
    if receipt.get('schema') != 'agi-alpha/next009-delivery-acceptance/v1' or receipt.get('accepted') is not True or receipt.get('scope')!='model-based-water-observation-plan': raise ValueError('PARENT_NOT_ACCEPTED')
    if receipt.get('artifact_sha256') != expected['plan'] or receipt.get('verifier_source_sha256') != expected['verifier'] or receipt.get('protocol_sha256') != expected['protocol']: raise ValueError('PARENT_RECEIPT_BINDING')
    if source_identity(root)['sha256']!=expected['candidate'] or receipt.get('candidate_source_sha256')!=expected['candidate']:raise ValueError('PARENT_GENERATOR_SOURCE_NOT_VERIFIED')
    if plan.get('operator') != 'known-zero-reference' or plan.get('status') != 'CONSTRUCTED_MODEL_PLAN': raise ValueError('PARENT_OPERATOR_SCOPE')
    return {'instrument':source_identity(root),
        'applicability':{'schema_version':1,'conditions':{'units':'source_contribution_percentage_points','reference_available':True,'nuisance':'additive_sensor_offset'},
            'assumptions':['Known-zero same-sensor reference','Constant offset across primary reference and samples','Bounded read error; reference error shared over time'],
            'uncertainty':'Finite authored model; physical bias stationarity and error bounds not established.',
            'failures':[{'conditions':{'reference_drift_nonzero':True},'reason':'Primary constant-offset acceptance does not qualify time-varying drift; a separately verified extension is required.'},
                        {'conditions':{'known_zero_valid':False},'reason':'Subtraction cannot certify an unknown reference signal.'}]},
        'generative_operator':{'language':'reference-contrast009','program':{'expression':plan['generated_expression']['ast'],'noise_bound_pp':plan['noise_bound_pp'],'max_sensor_erasures':plan['max_sensor_erasures'],'generator':'interval-constraint-composition','proposal_origin':'Model-authored mathematical interval rule; no claim of independent autonomous theorem discovery.'}},
        'provenance':{'primary_plan_sha256':expected['plan'],'primary_protocol_sha256':expected['protocol'],'verification_source_sha256':expected['verifier'],'source_corpus_sha256':plan['corpus_sha256']},
        'verification':{'status':'verified-in-scope','receipt_sha256':expected['receipt']},
        'costs':{'observed_parent_construction':plan['construction_cost'],'parent_acquisition_charged_once':True,'total_parent_and_enterprise_cost':'UNKNOWN','funding':'Explicit research allocation; no earned funding claimed'},
        'exposure':['EPA Net1 development corpus; source-pinned primary artifacts; no Net2 contents used to author this successor'], 'supersedes':[]}

def derive_drift_program(parent_program, drift_bound_pp):
    eps, drift = Fraction(parent_program['noise_bound_pp']), Fraction(str(drift_bound_pp))
    if eps <= 0 or drift < 0: raise ValueError('INTERVAL_DOMAIN')
    return {'schema':'agi-alpha/generated-reference-drift009/v1','parent_expression':parent_program['expression'],
        'parameters':{'noise_bound_pp':str(eps),'reference_to_sample_drift_bound_pp':str(drift)},
        'interval_composition':{'reference_pair_error_bound':str(2*eps),'sample_pair_error_bound':str(2*(eps+drift)),
            'shared_reference_required':True,'rule':'Intersect reference pair-error interval with every sample pair-error interval; empty intersection separates hypotheses.'},
        'ancestry':{'parent_program_sha256':hashlib.sha256(canonical(parent_program)).hexdigest(),'extension':'Minkowski addition of bounded time-varying drift to sample-read interval','generated_values':['reference_pair_error_bound','sample_pair_error_bound'],'rule_author':'root session model; known interval arithmetic, not a novelty claim'},
        'scope':'Independently bounded arbitrary time-varying sample drift; no field calibration or probabilistic independence assumption.'}

def drift_relations(corpus, program):
    nodes, sources = corpus['nodes'], corpus['sources']
    sample = Fraction(program['interval_composition']['sample_pair_error_bound'])
    ref = Fraction(program['interval_composition']['reference_pair_error_bound'])
    rows, records = [], []
    for i,j in itertools.combinations(range(len(sources)),2):
        row=[]
        for k in range(len(nodes)):
            differences=[Fraction(str(x[k]))-Fraction(str(y[k])) for x,y in zip(corpus['signal'][i],corpus['signal'][j])]
            low=max([-ref,*[-d-sample for d in differences]])
            high=min([ref,*[-d+sample for d in differences]])
            row.append(int(low>high))
        rows.append(row);records.append({'sources':[sources[i],sources[j]],'separating_sensors':[nodes[k] for k,v in enumerate(row) if v]})
    return np.asarray(rows,dtype=np.int8),records

def compile_drift(corpus, parent_program, drift_bound_pp, algorithm='milp'):
    start, own=time.monotonic(),time.process_time()
    program=derive_drift_program(parent_program,drift_bound_pp)
    matrix,relations=drift_relations(corpus,program)
    selected,solver=compiler.solve_relations(matrix,parent_program['max_sensor_erasures']+1,algorithm)
    ids=[corpus['nodes'][k] for k in selected]
    return {'schema':'agi-alpha/drift-observation-plan009/v1','corpus_sha256':compiler.digest(corpus),
        'network':corpus['network'],'sensors':ids,'operator':'bounded-reference-drift','generated_program':program,
        'noise_bound_pp':parent_program['noise_bound_pp'],'drift_bound_pp':str(drift_bound_pp),'max_sensor_erasures':parent_program['max_sensor_erasures'],
        'status':'CONSTRUCTED_MODEL_PLAN' if solver['status'] in ['OPTIMAL','FEASIBLE_HEURISTIC','FEASIBLE_UNPROVEN'] else solver['status'],
        'solver':solver,'pair_certificates':[{'sources':x['sources'],'separating_selected_sensors':[s for s in x['separating_sensors'] if s in ids]} for x in relations],
        'construction_cost':{'wall_seconds':time.monotonic()-start,'process_cpu_seconds':time.process_time()-own,'complete_monetary_cost':None},
        'scope':'Research-funded, finite model-based adaptation; independent acceptance required.'}

def query(drift=False, valid=True):
    return {'schema_version':1,'conditions':{'units':'source_contribution_percentage_points','reference_available':True,'nuisance':'additive_sensor_offset','reference_drift_nonzero':drift,'known_zero_valid':valid}}

class DriftInterpreter:
    def __init__(self, corpus, plan):
        if compiler.digest(corpus)!=plan['corpus_sha256'] or plan['operator']!='bounded-reference-drift': raise ValueError('DRIFT_SOURCE_OR_OPERATOR')
        self.plan=json.loads(canonical(plan));self.nodes=tuple(corpus['nodes']);self.sources=tuple(corpus['sources'])
        self.values=tuple(tuple(tuple(Fraction(str(v)) for v in row) for row in source) for source in corpus['signal'])
        self.count=len(corpus['times_seconds']);self.eps=Fraction(plan['noise_bound_pp']);self.drift=Fraction(plan['drift_bound_pp'])
        self.expression=plan['generated_program']['parent_expression']
    def diagnose(self, observations):
        if observations.get('known_zero_valid') is not True or observations.get('drift_bound_qualified') is not True: return {'status':'ASSUMPTIONS_UNQUALIFIED','sources':[]}
        if Fraction(str(observations.get('drift_bound_pp', '-1')))!=self.drift: return {'status':'DRIFT_ENVELOPE_MISMATCH','sources':[]}
        erased=set(observations.get('outages',[]))&set(self.plan['sensors'])
        if len(erased)>self.plan['max_sensor_erasures']:return {'status':'OUTAGE_ENVELOPE_EXCEEDED','sources':[]}
        selected=[s for s in self.plan['sensors'] if s not in erased]
        for sensor in selected:
            if sensor not in observations.get('reference',{}) or sensor not in observations.get('trace',{}) or len(observations['trace'][sensor])!=self.count:return {'status':'INCOMPLETE_OBSERVATIONS','sources':[]}
        corrected={s:[compiler.evaluate_expression(self.expression,observations,s,t) for t in range(self.count)] for s in selected}
        compatible=[]
        for i,source in enumerate(self.sources):
            valid=True
            for sensor in selected:
                k=self.nodes.index(sensor);residual=[v-self.values[i][t][k] for t,v in enumerate(corrected[sensor])]
                low=max([-self.eps,*[-self.eps-self.drift-r for r in residual]])
                high=min([self.eps,*[self.eps+self.drift-r for r in residual]])
                if low>high:valid=False;break
            if valid:compatible.append(source)
        return {'status':'UNIQUE' if len(compatible)==1 else 'ABSTAIN' if compatible else 'MODEL_INCONSISTENT','sources':compatible,'scope':'Declared bounded-drift model only; all supplied required observations checked.'}

def run(args):
    root, output=Path(args.root).resolve(),Path(args.output)
    output.mkdir(parents=True,exist_ok=False)
    expected=json.loads(Path(args.parent_freeze).read_bytes())
    parent=verified_parent(root,args.primary_plan,args.primary_receipt,args.verifier_source,args.primary_protocol,expected)
    record_dir=output/'retained_records';identity=retention.store(record_dir,parent)
    initial=retention.retrieve(record_dir,query(),root)
    if len(initial['records'])!=1 or initial['records'][0]['id']!=identity: raise ValueError('REAL_RETRIEVAL_FAILED')
    refusal=retention.retrieve(record_dir,query(drift=True),root)
    invalid=retention.retrieve(record_dir,query(valid=False),root)
    if refusal['records'] or invalid['records']:raise ValueError('SCOPED_NEGATIVE_KNOWLEDGE_FAILED')
    write(output/'RETRIEVAL.json',{'record_id':identity,'in_scope':initial,'drift_scope':refusal,'invalid_reference':invalid,'scope':'Refused target approval supplies a construction obligation; no inherited verification grants target acceptance.'})
    corpus=json.loads(Path(args.corpus).read_bytes())
    if corpus['network']!='Net2':raise ValueError('PRESPECIFIED_SUCCESSOR_NET2_ONLY')
    if corpus['times_seconds']!=list(range(0,86400,3600)) or corpus['sources']!=corpus['nodes']:raise ValueError('PRESPECIFIED_COHORT_OR_HORIZON_CHANGED')
    base=compiler.compile_plan(corpus,noise_bound_pp='1',max_sensor_erasures=1,algorithm='milp',operator='known-zero-reference')
    write(output/'old_zero_drift_plan.json',base)
    rows=[]
    for d in DRIFT_GRID:
        for arm in ['retained','equal-content-ordinary-reuse','reset-full-toolbox']:
            start,own=time.monotonic(),time.process_time()
            if arm=='retained':
                read=retention.retrieve(record_dir,query(),root)
                p=read['records'][0]['record']['generative_operator']['program']
            elif arm=='equal-content-ordinary-reuse':
                record=json.loads((record_dir/(identity+'.json')).read_bytes());retention.validate(record)
                if record['instrument']!=source_identity(root):raise ValueError('ORDINARY_SOURCE_MISMATCH')
                p=record['generative_operator']['program']
            else:
                p={'expression':compiler.synthesize_operator()['ast'],'noise_bound_pp':'1','max_sensor_erasures':1,'generator':'interval-constraint-composition','proposal_origin':'Independent algorithmic rebuild from same disclosed service assumptions and full toolbox; not independent frontier-model design.'}
            plan=compile_drift(corpus,p,d)
            matrix,_=drift_relations(corpus,plan['generated_program'])
            old_indices=[corpus['nodes'].index(x) for x in base['sensors']]
            old_failed=int(np.sum(matrix[:,old_indices].sum(axis=1)<2)) if old_indices else int(len(matrix))
            name='drift_'+d+'_'+arm+'.json';write(output/name,plan)
            elapsed={'wall_seconds':time.monotonic()-start,'process_cpu_seconds':time.process_time()-own,'monetary_cost':None}
            rows.append({'drift_bound_pp':d,'arm':arm,'plan':name,'plan_sha256':sha(output/name),'status':plan['status'],'sensors':plan['sensors'],'old_plan_failed_pair_obligations':old_failed,'whole_path_cost':elapsed})
    report={'schema':'agi-alpha/successor009-comparison/v1','cohort':{'network':'Net2','all_source_cases':len(corpus['sources']),'pairs':math.comb(len(corpus['sources']),2),'times':len(corpus['times_seconds']),'drift_grid_pp':list(DRIFT_GRID),'max_sensor_erasures':1},
        'corpus_sha256':compiler.digest(corpus),'inherited_record_id':identity,'rows':rows,
        'funding':{'route':'explicit_research_allocation','qualified_unrestricted_simulated_earned_funding':0,'earned_funded_construction':False},
        'controls':{'old_policy_new_toolbox':'standard multicover accepts generated drift relations, independent verifier provides conventional reference','new_policy_old_toolbox':'typed scope rejects drift transfer; no false approval','ordinary_reuse':'identical parent information and solver','reset':'rebuilds expression/rules algorithmically with identical full toolbox; does not measure independent model rediscovery'},
        'claims':{'fresh_model_transfer':'PENDING_INDEPENDENT_CHECK','causal_successor_benefit':'Requires old-plan failing pair plus accepted revised plan under same drift obligation','discovery_advantage':'NOT_ESTABLISHED; methods share known rule and solver','after_cost_discovery_advantage':'UNKNOWN_COMPLETE_COST_AND_NO_SUPERIORITY','real_or_qualified_simulated_earnings':0},
        'cost_treatment':'Every arm includes actual retrieval/reconstruction, relation construction and solving. Parent acquisition reported once separately; measured CPU is not money. Research/LLM/session costs remain unknown. All five drift levels and all source pairs retained.'}
    write(output/'SUCCESSOR.json',report)
    print(json.dumps({'rows':len(rows),'sources':len(corpus['sources']),'record_id':identity,'qualified_earned':0}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--output',required=True);p.add_argument('--corpus',required=True);p.add_argument('--primary-plan',required=True);p.add_argument('--primary-receipt',required=True);p.add_argument('--verifier-source',required=True);p.add_argument('--primary-protocol',required=True);p.add_argument('--parent-freeze',required=True)
    run(p.parse_args())
