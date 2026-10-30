from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as F
from itertools import combinations
import hashlib, re, time


@dataclass(frozen=True)
class Q:
    re: F = F(0)
    im: F = F(0)
    def __add__(self, b):
        b = q(b); return Q(self.re+b.re, self.im+b.im)
    __radd__ = __add__
    def __neg__(self): return Q(-self.re, -self.im)
    def __sub__(self, b): return self + -q(b)
    def __rsub__(self, b): return q(b) + -self
    def __mul__(self, b):
        b = q(b); return Q(self.re*b.re-self.im*b.im, self.re*b.im+self.im*b.re)
    __rmul__ = __mul__
    def __truediv__(self, b):
        b = q(b); d = b.re*b.re+b.im*b.im
        if not d: raise ValueError('singular denominator')
        return Q((self.re*b.re+self.im*b.im)/d, (self.im*b.re-self.re*b.im)/d)
    def __bool__(self): return bool(self.re or self.im)
    def json(self): return [str(self.re),str(self.im)]


def q(x): return x if isinstance(x,Q) else Q(F(x))


@dataclass(frozen=True)
class Element:
    name: str
    kind: str
    left: str
    right: str
    value: F


@dataclass(frozen=True)
class Circuit:
    elements: tuple[Element,...]
    input: str
    nodes: tuple[str,...]
    source_sha256: str
    control_block_ignored: bool


def number(s):
    s=s.lower()
    m=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)(meg|[tgkmunpf])?',s)
    if not m: raise ValueError('unsupported component literal '+s)
    powers={'t':12,'g':9,'meg':6,'k':3,'m':-3,'u':-6,'n':-9,'p':-12,'f':-15,None:0}
    return F(m[1])*F(10)**powers[m[2]]


def node(s): return '0' if s.lower() in ('0','gnd') else s.lower()


def parse_netlist(text):
    elements=[]; input_node=None; ignored=False
    for idx,line in enumerate(text.splitlines()):
        s=line.strip()
        if not s or s.startswith('*'): continue
        if idx==0: continue
        parts=s.lower().split(); first=parts[0]
        if first=='.control': ignored=True; break
        if first.startswith('.'):
            if first in ('.global','.ac','.meas','.measure','.end'): continue
            raise ValueError('unsupported directive '+first)
        if first[0] in 'rcl' and len(parts)==4:
            v=number(parts[3])
            if v<=0: raise ValueError('nonpositive passive element')
            elements.append(Element(first,first[0].upper(),node(parts[1]),node(parts[2]),v))
        elif first[0]=='v':
            if input_node is not None or len(parts)<5 or node(parts[2])!='0':
                raise ValueError('requires one grounded independent AC voltage source')
            values=parts[3:]
            if 'ac' not in values or number(values[values.index('ac')+1])!=1:
                raise ValueError('requires unit AC source')
            if 'dc' in values and number(values[values.index('dc')+1])!=0:
                raise ValueError('requires zero DC source')
            consumed=[]
            for k in range(0,len(values),2):
                if k+1>=len(values) or values[k] not in ('ac','dc'): raise ValueError('source expression/phase unsupported')
                consumed.extend(values[k:k+2])
            input_node=node(parts[1])
        else: raise ValueError('unsupported source/nonlinear/active element '+first)
    if not elements or input_node is None: raise ValueError('empty network or missing source')
    if len({x.name for x in elements})!=len(elements): raise ValueError('duplicate element')
    nodes=sorted({z for e in elements for z in (e.left,e.right)}-{'0',input_node})
    if not nodes or len(nodes)>12 or len(elements)>32: raise ValueError('network outside bounded grammar')
    return Circuit(tuple(elements),input_node,tuple(nodes),hashlib.sha256(text.encode()).hexdigest(),ignored)


def admittance(e,omega,value):
    if e.kind=='R': return Q(1/value)
    if e.kind=='C': return Q(F(0),omega*value)
    if e.kind=='L': return Q(F(0),-1/(omega*value))
    raise ValueError('unknown passive law')


def solve(circuit, values, omega):
    omega=F(omega)
    if omega<=0: raise ValueError('nonpositive angular frequency')
    ns=circuit.nodes; indices={n:i for i,n in enumerate(ns)}
    mat=[[Q() for j in ns] for i in ns]; rhs=[Q() for n in ns]
    known={'0':Q(),circuit.input:Q(F(1))}
    for e in circuit.elements:
        y=admittance(e,omega,F(values.get(e.name,e.value)))
        for a,b in ((e.left,e.right),(e.right,e.left)):
            if a in indices:
                i=indices[a];mat[i][i]+=y
                if b in indices: mat[i][indices[b]]-=y
                else: rhs[i]+=y*known[b]
    for k in range(len(ns)):
        p=next((i for i in range(k,len(ns)) if mat[i][k]),None)
        if p is None: raise ValueError('singular disconnected/unbounded network')
        mat[k],mat[p]=mat[p],mat[k];rhs[k],rhs[p]=rhs[p],rhs[k]
        pivot=mat[k][k];mat[k]=[x/pivot for x in mat[k]];rhs[k]=rhs[k]/pivot
        for i in range(len(ns)):
            if i!=k:
                z=mat[i][k];mat[i]=[a-z*b for a,b in zip(mat[i],mat[k])];rhs[i]-=z*rhs[k]
    volts=dict(known,**dict(zip(ns,rhs)))
    current=Q()
    for e in circuit.elements:
        y=admittance(e,omega,F(values.get(e.name,e.value)))
        if e.left==circuit.input: current+=y*(volts[e.left]-volts[e.right])
        elif e.right==circuit.input: current+=y*(volts[e.right]-volts[e.left])
    return volts,current


def response(circuit, values, action):
    v,i=solve(circuit,values,action['omega_rad_s'])
    if action['kind']=='voltage_ratio': return v[action['node']]
    if action['kind']=='input_admittance': return i
    raise ValueError('primitive not in admitted strategy grammar')


def derive_symmetry(circuit):
    laws={'R':{'parameter_exponent':-1,'omega_exponent':0,'unit':'ohm'},
          'C':{'parameter_exponent':1,'omega_exponent':1,'unit':'farad'},
          'L':{'parameter_exponent':-1,'omega_exponent':-1,'unit':'henry'}}
    steps=[];program={}
    for e in circuit.elements:
        law=laws[e.kind]; exponent=F(-1,law['parameter_exponent'])
        program[e.name]=int(exponent)
        steps.append({'element':e.name,'kind':e.kind,'branch_law':law,
            'parameter_scale_exponent':int(exponent),'derived_admittance_scale_exponent':-1})
    return {'schema':'typed-network-symmetry-v1','source_sha256':circuit.source_sha256,
      'authors':'developer supplied passive constitutive laws; algebraic exponent matching and graph coverage executed by program',
      'relations':steps,'program':program,'proof':'Every branch admittance is multiplied by1/a. Entire KCL matrix and source RHS scale1/a, leaving all node voltage ratios unchanged wherever matrix invertible. Input current scales1/a.',
      'applicability':['linear time-invariant passive lumped RCL','positive finite components','single grounded independent input voltage','all circuit branches included','no fixed known load omitted','normalized coherent voltage measurement'],
      'non_applicability':['active/nonlinear components','unknown omitted source impedance/load','unbounded current calibration','unmodeled distributed effects','physical assurance without measured calibration']}


def apply_symmetry(circuit, values, a):
    program=derive_symmetry(circuit)['program'];a=F(a)
    if a<=0: raise ValueError('nonpositive scale')
    return {e.name:str(F(values.get(e.name,e.value))*a**program[e.name]) for e in circuit.elements}


def generate_actions(circuit, protocol, inherited_program=None):
    if inherited_program is not None and inherited_program.get('op')!='derive_flux_observable':
        raise ValueError('retained program outside admitted interpreter')
    freqs=protocol['omega_rad_s'];actions=[];witness_values=apply_symmetry(circuit,{},2)
    witness={'a':'2','original_values':{e.name:str(e.value) for e in circuit.elements},
        'transformed_values':witness_values,'voltage_equal':[],'current_different':[],
        'all_frequency_proof':derive_symmetry(circuit)}
    for omega in freqs:
        v0,i0=solve(circuit,{},omega);v1,i1=solve(circuit,witness_values,omega)
        equal=all(v0[n]==v1[n] for n in circuit.nodes)
        witness['voltage_equal'].append(equal);witness['current_different'].append(i0!=i1)
        if not equal: raise ValueError('failed structural transfer; no current extension admitted')
        for n in circuit.nodes:
            actions.append({'id':'v:'+n+':'+str(omega),'kind':'voltage_ratio','node':n,
               'omega_rad_s':str(omega),'units':'1','relative_acquisition_units':1})
    extension=None
    if protocol.get('allow_flux_extension') and any(witness['current_different']):
        extension={'op':'derive_flux_observable','version':1,
           'generated_from':'executed all-node voltage-equivalence witness plus typed current scaling',
           'source_sha256':circuit.source_sha256,'required_model':derive_symmetry(circuit)['applicability'],
           'rule_authorship':'developer supplied conjugate-observable rule; runtime derives network expression, units and admissibility',
           'units':'siemens','sensor_obligation':'independently calibrated input-current and input-voltage transfer; otherwise abstain',
           'inherited':inherited_program is not None}
        for omega in freqs:
            actions.append({'id':'y:input:'+str(omega),'kind':'input_admittance','node':circuit.input,
                'omega_rad_s':str(omega),'units':'siemens','relative_acquisition_units':2})
    return {'actions':actions,'witness':witness,'generated_extension':extension}


def coordinate_box(z,gain,eps):
    lo,hi=map(F,gain);eps=F(eps)
    if not (0<lo<=hi) or eps<0: raise ValueError('invalid uncertainty envelope')
    return [(min(x*lo,x*hi)-eps,max(x*lo,x*hi)+eps) for x in (z.re,z.im)]


def separated(a,b): return any(x[1]<y[0] or y[1]<x[0] for x,y in zip(a,b))


def compile_plan(circuit,hypotheses,actions,policies,allow_extension=True):
    started=time.process_time(); pairs=set(combinations(range(len(hypotheses)),2)); covers={}; signatures={}
    for action in actions:
        if action['kind']=='input_admittance' and not allow_extension: continue
        p=policies[action['kind']]
        zs=[response(circuit,h['values'],action) for h in hypotheses]
        boxes=[coordinate_box(z,p['gain'],p['absolute_coordinate_error']) for z in zs]
        covers[action['id']]={pair for pair in pairs if separated(boxes[pair[0]],boxes[pair[1]])}
        signatures[action['id']]=[z.json() for z in zs]
    uncovered=set(pairs);selected=[];ancestry=[]
    while uncovered:
        available=[a for a in actions if a['id'] in covers and a['id'] not in selected]
        if not available: break
        best=max(available,key=lambda a:(len(covers[a['id']]&uncovered)/a['relative_acquisition_units'],-actions.index(a)))
        new=covers[best['id']]&uncovered
        if not new: break
        witness=min(uncovered)
        ancestry.append({'revision':len(selected)+1,'parent':selected[-1] if selected else 'voltage-only-v1',
           'consequential_unresolved_pair':[hypotheses[i]['id'] for i in witness],
           'generated_action':best,'newly_separated_pairs':len(new),
           'extension':'flux conjugate input-current observable' if best['kind']=='input_admittance' else None})
        selected.append(best['id']);uncovered-=new
    all_uncovered=pairs-set().union(*covers.values()) if covers else pairs
    return {'schema':'circuit-measurement-strategy-v1','source_sha256':circuit.source_sha256,
       'selected_actions':[a for aid in selected for a in actions if a['id']==aid],
       'generated_ancestry':ancestry,'admitted_pairs':len(pairs),'separated_pairs':len(pairs-uncovered),
       'unresolved_pairs':[[hypotheses[i]['id'],hypotheses[j]['id']] for i,j in sorted(uncovered)],
       'complete_finite_model_acceptance':not uncovered,'strong_full_experiment_unresolved_pairs':len(all_uncovered),
       'exact_responses':signatures,'cpu_seconds':time.process_time()-started,
       'policies':policies,'proof_scope':'Sufficient exact pairwise separation of axis-aligned complex uncertainty rectangles on a finite authored model cohort. Not continuous-tolerance or physical specimen validation.'}


def exhaustive_plan(circuit,hypotheses,actions,policies):
    pairs=set(combinations(range(len(hypotheses)),2));covers=[]
    for a in actions:
        p=policies[a['kind']];boxes=[coordinate_box(response(circuit,h['values'],a),p['gain'],p['absolute_coordinate_error']) for h in hypotheses]
        covers.append({(i,j) for i,j in pairs if separated(boxes[i],boxes[j])})
    full=set().union(*covers);best=None
    for k in range(len(actions)+1):
        for choice in combinations(range(len(actions)),k):
            if set().union(*(covers[i] for i in choice))==full:
                best=choice;break
        if best is not None:break
    return {'method':'ordinary exhaustive finite test-set design using identical model/actions/uncertainty',
      'selected_actions':[actions[i] for i in best],'separated_pairs':len(full),'admitted_pairs':len(pairs),
      'complete_finite_model_acceptance':full==pairs,'unresolved_pairs':len(pairs-full),'minimum_cardinality_to_equal_full_experiment':len(best)}
