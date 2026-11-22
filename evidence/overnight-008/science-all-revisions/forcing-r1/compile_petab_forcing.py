import argparse, ast as pyast, csv, hashlib, itertools, json, math, time
from fractions import Fraction as F
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.integrate import solve_ivp
import gauge_probe as gp

def math_ast(e):
    kind=gp.local(e)
    if kind=='csymbol':
        if not e.attrib.get('definitionURL','').endswith('/time'):raise ValueError('UNKNOWN_CSYMBOL')
        return ('symbol','__sbml_time__')
    if kind=='math':return math_ast(e[0])
    if kind=='ci':return ('symbol',e.text.strip())
    if kind=='cn':return ('number',F(e.text.strip()))
    if kind!='apply' or gp.local(e[0]) not in {'times','divide','plus','minus','power','ln','exp'}:raise ValueError('UNSUPPORTED_MATHML')
    return (gp.local(e[0]),*[math_ast(x) for x in e[1:]])
def eval_value(e,env):
    k=e[0]
    if k=='number':return float(e[1])
    if k=='symbol':return env[e[1]]
    a=[eval_value(x,env) for x in e[1:]]
    if k=='times':return math.prod(a)
    if k=='divide':return a[0]/a[1]
    if k=='plus':return sum(a)
    if k=='minus':return a[0]-sum(a[1:]) if len(a)>1 else -a[0]
    if k=='ln':return math.log(a[0])
    if k=='exp':return math.exp(a[0])
    if k=='power':return a[0]**a[1]
    raise ValueError('UNSUPPORTED_OPERATOR')

def table(source,name):
    with (source/name).open() as h:return list(csv.DictReader(h,delimiter='\t'))
def formula(text):
    tree=pyast.parse(text,mode='eval')
    if sum(1 for _ in pyast.walk(tree))>2048:raise ValueError('FORMULA_NODE_LIMIT')
    def go(x):
        if isinstance(x,pyast.Name):return ('symbol',x.id)
        if isinstance(x,pyast.Constant) and type(x.value) in (int,float):return ('number',F(str(x.value)))
        if isinstance(x,pyast.UnaryOp) and isinstance(x.op,pyast.USub):return ('minus',go(x.operand))
        if isinstance(x,pyast.BinOp):
            op={pyast.Add:'plus',pyast.Sub:'minus',pyast.Mult:'times',pyast.Div:'divide',pyast.Pow:'power'}.get(type(x.op))
            if op:return (op,go(x.left),go(x.right))
        raise ValueError('UNSUPPORTED_OBSERVABLE_FORMULA')
    return go(tree.body)
def substituted(expr,aliases):
    if expr[0]=='symbol':return aliases.get(expr[1],expr)
    if expr[0]=='number':return expr
    return (expr[0],*[substituted(x,aliases) for x in expr[1:]])
def load(source):
    root=ET.parse(source/'model.xml').getroot()
    if any(gp.local(x) in {'rateRule','algebraicRule','event','functionDefinition'} for x in root.iter()):raise ValueError('UNSUPPORTED_SBML_RULE_EVENT_FUNCTION')
    if sum(1 for _ in root.iter())>20000:raise ValueError('SBML_NODE_LIMIT')
    parameter_rows=table(source,'parameters.tsv')
    parameters={x['parameterId']:float(x['nominalValue']) for x in parameter_rows}
    estimated=[x['parameterId'] for x in parameter_rows if x['estimate']=='1']
    if any(parameters[x]<=0 for x in estimated):raise ValueError('POSITIVE_ESTIMATED_PARAMETER_REQUIRED_FOR_SCALING')
    constants={x.attrib['id']:float(x.attrib.get('size','1')) for x in root.iter() if gp.local(x)=='compartment'}
    if any(x!=1. for x in constants.values()):raise ValueError('UNIT_COMPARTMENT_ONLY')
    constants.update({x.attrib['id']:float(x.attrib['value']) for x in root.iter() if gp.local(x)=='parameter' and x.attrib['id'] not in estimated})
    constants.update({x['parameterId']:float(x['nominalValue']) for x in parameter_rows if x['estimate']=='0'})
    if '__sbml_time__' in constants or '__sbml_time__' in parameters:raise ValueError('RESERVED_TIME_SYMBOL')
    constants['__sbml_time__']=0.
    rule_sources={x.attrib['variable']:math_ast(next(y for y in x if gp.local(y)=='math')) for x in root.iter() if gp.local(x)=='assignmentRule'}
    if len(rule_sources)>32:raise ValueError('ASSIGNMENT_RULE_LIMIT')
    if any(x in estimated for x in rule_sources):raise ValueError('ASSIGNMENT_TARGET_CANNOT_BE_ESTIMATED_PARAMETER')
    rule_cache={}
    def expand(e,trail=()):
        if e[0]=='number':return e
        if e[0]=='symbol':
            name=e[1]
            if name not in rule_sources:return e
            if name in trail:raise ValueError('ASSIGNMENT_CYCLE')
            if name not in rule_cache:rule_cache[name]=expand(rule_sources[name],trail+(name,))
            return rule_cache[name]
        return (e[0],*[expand(x,trail) for x in e[1:]])
    for name in rule_sources:expand(('symbol',name))
    species_rows=[x for x in root.iter() if gp.local(x)=='species']
    if any(x.attrib.get('boundaryCondition','false')=='true' or x.attrib.get('constant','false')=='true' for x in species_rows):raise ValueError('DYNAMIC_SPECIES_ONLY')
    species=[x.attrib['id'] for x in species_rows]
    if any(x in species for x in rule_sources):raise ValueError('ALGEBRAIC_SPECIES_NOT_IMPLEMENTED')
    assignments={x.attrib['symbol']:expand(math_ast(next(y for y in x if gp.local(y)=='math'))) for x in root.iter() if gp.local(x)=='initialAssignment'}
    initial={x.attrib['id']:assignments.get(x.attrib['id'],('number',F(x.attrib.get('initialConcentration',x.attrib.get('initialAmount','0'))))) for x in species_rows}
    reactions=[]
    for r in root.iter():
        if gp.local(r)!='reaction':continue
        rhs=expand(math_ast(next(x for x in r.iter() if gp.local(x)=='math')));changes={}
        for group in r:
            sign=-1 if gp.local(group)=='listOfReactants' else 1 if gp.local(group)=='listOfProducts' else 0
            if sign:
                for s in group:changes[s.attrib['species']]=changes.get(s.attrib['species'],0.)+sign*float(s.attrib.get('stoichiometry','1'))
        reactions.append((r.attrib['id'],rhs,changes))
    conditions=table(source,'conditions.tsv')
    if any(v for x in conditions for k,v in x.items() if k not in {'conditionId','conditionName'}):raise ValueError('CONDITION_OVERRIDES_NOT_IMPLEMENTED')
    observations={x['observableId']:x for x in table(source,'observables.tsv')}
    measured=table(source,'measurements.tsv');contracts=[];seen=set()
    def alias_value(s):
        try:return ('number',F(s))
        except ValueError:return ('symbol',s)
    for measurement in measured:
        key=measurement['observableId'];obs=observations[key];aliases={}
        for field,prefix in [('observableParameters','observableParameter'),('noiseParameters','noiseParameter')]:
            text=measurement.get(field,'')
            for j,s in enumerate(text.split(';') if text else [],1):aliases[f'{prefix}{j}_{key}']=alias_value(s)
        observed=expand(substituted(formula(obs['observableFormula']),aliases))
        noise=expand(substituted(formula(obs['noiseFormula']),aliases))
        contract=(observed,noise)
        if contract not in seen:contracts.append(contract);seen.add(contract)
    return {'parameters':parameters,'estimated':estimated,'constants':constants,'species':species,'initial':initial,'reactions':reactions,'contracts':contracts,'observations':observations,'measurements':measured,'parameter_rows':parameter_rows,'expanded_assignment_rules':rule_cache}
def constraints(model):
    names=model['species']+model['estimated'];n=len(names);index={s:i for i,s in enumerate(names)};rows=[]
    def zero():return [F(0)]*n
    def unit(s):
        x=zero()
        if s in index:x[index[s]]=F(1)
        elif s not in model['constants']:raise ValueError('UNKNOWN_SYMBOL '+s)
        return x
    def sub(a,b):return [x-y for x,y in zip(a,b)]
    exponents=set()
    def power_scan(e,inside=False):
        if e[0] in {'number','symbol'}:return
        variable=e[0]=='power' and e[2][0]=='symbol'
        if variable:
            if inside:raise ValueError('NESTED_VARIABLE_POWER_NOT_IMPLEMENTED')
            exponents.add(e[2][1])
        for x in e[1:]:power_scan(x,inside or variable)
    expressions=list(model['initial'].values())+[e for _,e,_ in model['reactions']]+[e for c in model['contracts'] for e in c]
    for e in expressions:power_scan(e)
    if len(exponents)>4:raise ValueError('EXPONENT_PARAMETER_LIMIT')
    exponents=sorted(exponents)
    def wt(e,exponent):
        k=e[0]
        if k=='number':return None if e[1]==0 else zero()
        if k=='symbol':return unit(e[1])
        a=[wt(x,exponent) for x in e[1:]]
        if k in {'plus','minus'}:
            a=[x for x in a if x is not None]
            if not a:return None
            for x in a[1:]:rows.append(sub(x,a[0]))
            return a[0]
        if k=='times':return None if any(x is None for x in a) else [sum(x) for x in zip(*a)]
        if k=='divide':
            if a[1] is None:raise ValueError('ZERO_DENOMINATOR')
            return None if a[0] is None else sub(a[0],a[1])
        if k=='power':
            if e[2][0]=='number':v=e[2][1]
            elif e[2][0]=='symbol':v=F(exponent[e[2][1]]);rows.append(unit(e[2][1]))
            else:raise ValueError('UNSUPPORTED_POWER_EXPONENT')
            if not v:return zero()
            if a[0] is None:
                if v<=0:raise ValueError('ZERO_POWER_DOMAIN')
                return None
            return [v*x for x in a[0]]
        if k in {'ln','exp'}:
            if a[0] is None:raise ValueError('LOG_ZERO')
            rows.append(a[0]);return None if e[1]==('number',F(1)) else zero()
        raise ValueError('UNSUPPORTED_OPERATOR '+k)
    zero_initials=[]
    for values in itertools.product([2,3],repeat=len(exponents)):
        values=dict(zip(exponents,values))
        for s,e in model['initial'].items():
            w=wt(e,values)
            if w is None:zero_initials.append(s)
            else:rows.append(sub(unit(s),w))
        for _,e,changes in model['reactions']:
            w=wt(e,values)
            if w is not None:
                for s,c in changes.items():
                    if c:rows.append(sub(w,unit(s)))
        for contract in model['contracts']:
            for e in contract:
                w=wt(e,values)
                if w is not None:rows.append(w)
    unique=[];seen=set()
    for row in rows:
        key=tuple(row)
        if any(row) and key not in seen:unique.append(row);seen.add(key)
    if len(names)>48 or len(unique)>512:raise ValueError('INTERPRETER_SIZE_LIMIT')
    return names,unique,unit,sorted(set(zero_initials))
def numeric(model,source):
    species=model['species'];env=dict(model['constants'],**model['parameters'])
    initial=[eval_value(model['initial'][s],env) for s in species]
    observed=model['measurements'];times=sorted(set(float(x['time']) for x in observed))
    mat=np.array([[c.get(s,0.) for _,_,c in model['reactions']] for s in species])
    def fun(t,y):
        values=dict(env,**dict(zip(species,y)));values['__sbml_time__']=t
        return mat@np.array([eval_value(e,values) for _,e,_ in model['reactions']])
    sol=solve_ivp(fun,(0.,max(times)),initial,method='LSODA',t_eval=times,rtol=1e-9,atol=1e-11)
    if not sol.success:raise ValueError('NUMERICAL_INTEGRATION_FAILED '+sol.message)
    values=[];reference=table(source,'simulations.tsv')
    if len(reference)!=len(observed):raise ValueError('REFERENCE_LENGTH')
    for row,ref in zip(observed,reference):
        if row['observableId']!=ref['observableId'] or row['time']!=ref['time']:raise ValueError('REFERENCE_ALIGNMENT')
        obs=model['observations'][row['observableId']];vals=dict(env,**dict(zip(species,sol.y[:,times.index(float(row['time']))])))
        vals['__sbml_time__']=float(row['time'])
        vals.update({name:eval_value(expr,vals) for name,expr in model['expanded_assignment_rules'].items()})
        for j,s in enumerate(row.get('observableParameters','').split(';') if row.get('observableParameters','') else [],1):
            vals[f"observableParameter{j}_{row['observableId']}"]=float(s) if s not in env else env[s]
        values.append(eval_value(formula(obs['observableFormula']),vals))
    ref=np.array([float(x['simulation']) for x in reference]);pred=np.array(values)
    absolute=float(np.max(abs(pred-ref)));scale=max(1.,float(np.max(abs(ref))));passed=absolute<=1e-5+1e-4*scale
    if not passed:raise ValueError('REFERENCE_TRAJECTORY_VALIDATION_FAILED '+str(absolute))
    return {'maximum_absolute_error':absolute,'relative_to_max_reference':absolute/scale,'tolerance_absolute':1e-5,'tolerance_relative_to_max_reference':1e-4,'passed':passed,'solver_calls':sol.nfev,'scope':'Digital SBML interpretation at supplied PEtab nominal parameters; physical validity and model adequacy untested','times':times,'states':sol.y.tolist(),'observable_values':values,'reference_values':ref.tolist()}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    source=Path(args.source).resolve();output=Path(args.output).resolve()
    if output.exists():raise FileExistsError('Refusing overwrite '+str(output))
    output.mkdir(parents=True);begin=time.monotonic();model=load(source);names,rows,unit,zeros=constraints(model);n=len(names);basis=gp.nullspace(rows,n)
    measured=[{'id':s,'row':[str(x) for x in unit(s)],'calibrated':True,'cost_units':1} for s in model['species']]
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()}
    program={'language':'linear-ambiguity-plan/v1','dimension':n,'constraints':[[str(x) for x in row] for row in rows],'measurements':measured,'requires_absolute_calibration':True,'max_plans':min(2048,2**len(measured)),'names':names,'known_scaling_directions':[{names[i]:str(x) for i,x in enumerate(v) if x} for v in basis],'provenance':{'source_sha256':files,'compiler_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'dependency_gauge_probe_sha256':hashlib.sha256(Path(gp.__file__).read_bytes()).hexdigest(),'physical_calibration_acquired':False,'cost_units':'Dimensionless measurement count, no financial claim','exposure':'Development transfer; no protected confirmation or scientific superiority claim'}}
    validation=numeric(model,source)
    report={'source':str(source),'states':len(model['species']),'estimated_parameters':len(model['estimated']),'observation_contracts':len(model['contracts']),'measured_rows':len(model['measurements']),'known_scale_directions':len(basis),'expanded_assignment_rules':{k:str(v) for k,v in model['expanded_assignment_rules'].items()},'zero_initials_correctly_not_constrained_as_known_nonzero':zeros,'global_or_practical_identifiability_established':False,'numeric_validation':{k:v for k,v in validation.items() if k not in {'times','states','observable_values','reference_values'}},'runtime_seconds':time.monotonic()-begin,'decision':'Development transfer executed; no claim of new capability over strong methods'}
    for name,data in [('model_constraints.json',program),('TRANSFER_RESULT.json',report),('RAW_NUMERIC.json',validation)]:
        (output/name).write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
