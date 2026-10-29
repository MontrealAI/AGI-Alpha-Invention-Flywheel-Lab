"""Exact known-code and gate-synthesis controls. No candidate import or search.

Outer: arXiv2510.20728v3, AppendixE equations22–23.
Inner: standard Steane code from the binary [7,3,4] simplex code and its complement.
"""
import hashlib,itertools,json,time
from pathlib import Path

R=Path(__file__).resolve().parent


def paulis(n,weight):
    for sites in itertools.combinations(range(n),weight):
        for letters in itertools.product('XYZ',repeat=weight):
            flip=z=ny=0
            for j,p in zip(sites,letters):
                b=1<<(n-1-j)
                if p in 'XY':flip|=b
                if p in 'YZ':z|=b
                if p=='Y':ny+=1
            yield flip,z,ny,''.join(f'{p}{j}' for j,p in zip(sites,letters))


def gaussian_integer(real_coefficient,ipower):
    return [(real_coefficient,0),(0,real_coefficient),(-real_coefficient,0),(0,-real_coefficient)][ipower%4]


def matrix(states,flip,z,ny):
    return [[gaussian_integer(sum(c*left.get(x^flip,0)*(-1 if (x&z).bit_count()%2 else 1) for x,c in right.items()),ny)
             for right in states] for left in states]


def scalar_matrix(m):
    return all(m[i][j] == (m[0][0] if i==j else (0,0)) for i in range(len(m)) for j in range(len(m)))


def audit(states,n,den,maxweight,weights,logical_phases):
    k=len(states);gram=matrix(states,0,0,0)
    assert all(gram[i][j] == ((den,0) if i==j else (0,0)) for i in range(k) for j in range(k))
    count=1
    for w in range(1,maxweight+1):
        for flip,z,ny,label in paulis(n,w):
            m=matrix(states,flip,z,ny);assert scalar_matrix(m),(label,m);count+=1
    for state,phase in zip(states,logical_phases):
        assert all(sum(a for a,bit in zip(weights,format(x,f'0{n}b')) if bit=='1')%4 == phase for x in state)
    next_witness=None
    for flip,z,ny,label in paulis(n,maxweight+1):
        m=matrix(states,flip,z,ny)
        if not scalar_matrix(m):
            next_witness=dict(Pauli=label,numerator_matrix=m,common_denominator=den);break
    return dict(n=n,K=k,orthonormal=True,Pauli_weight_detection=maxweight,
                exact_operators_checked=count,logical_phase_exponents=logical_phases,
                first_next_weight_KL_failure=next_witness)


outer=[{} for _ in range(4)]
for t in itertools.product(range(2),repeat=3):
    par=t[0]^t[1]^t[2];phi=''.join(map(str,(*t,par)));psi=''.join(map(str,(*t,par^1)))
    signs=[1,(-1)**(t[0]+t[1]),(-1)**(t[0]+t[2])]
    for j,s in enumerate(signs):
        for prefix in ['00','11']:outer[j][int(prefix+phi,2)]=s
    for prefix,suffix in [('10',phi),('01',psi)]:outer[3][int(prefix+suffix,2)]=(-1)**t[2]
outer_weights=[1,3,2,2,2,2]
outer_result=audit(outer,6,16,1,outer_weights,[0,0,0,1])

dual={0}
for g in [0b1111000,0b1100110,0b1010101]:dual|={x^g for x in list(dual)}
inner=[{x:1 for x in dual},{x^127:1 for x in dual}]
assert sorted(x.bit_count() for x in dual)==[0,4,4,4,4,4,4,4]
inner_result=audit(inner,7,8,2,[3]*7,[0,1])

decomposition=[]
for a,b in itertools.product(range(2),repeat=2):
    phase=a+b;after_first_cx=b^a;phase-=after_first_cx;after_second_cx=after_first_cx^a
    assert after_second_cx==b and phase%8==(2*a*b)%8
    decomposition.append(dict(input_bits=[a,b],output_bits=[a,after_second_cx],T_phase_exponent_mod8=phase%8))

result=dict(completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),candidate_read=False,
    outer_paper_code=outer_result,Steane_inner=inner_result,
    composed_known_methods_control=dict(n=42,K=4,quantum_distance_lower_bound=6,quantum_distance_exact=6,
        method='six outer physical qubits each replaced by one7-qubit Steane block',
        physical_weights=[(-w)%4 for w in outer_weights for _ in range(7)],
        logical_phase_exponents=[0,0,0,1],local_phase_gate_locations=42,
        distance_upper_bound_witness=dict(physical_X_sites=[0,1,6,7,8,13],weight=6,
            compressed_logical_matrix='diag(1,1,1,0)',
            reason='Steane X0X1X6 acts as inner logical X; two blocks lift the outer X0X1 witness'),
        expanded42qubit_state_not_materialized=True,
        certification='exact component checks above plus standard distance-product and gate-composition argument',
        encoder_syndrome_decoder_device_costs='UNKNOWN'),
    ordinary_logical_CS_synthesis=dict(sequence=['T(a)','T(b)','CNOT(a,b)','T_dagger(b)','CNOT(a,b)'],
        T_or_Tdagger_count=3,CNOT_count=2,truth_table=decomposition,
        fault_tolerant_T_resources='requires implementation, e.g. prepared magic states; complete costs UNKNOWN'))
(R/'KNOWN_BASELINE_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='ordinary_logical_CS_synthesis'},indent=2))
