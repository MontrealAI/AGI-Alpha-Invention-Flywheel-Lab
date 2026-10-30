from fractions import Fraction as F
from itertools import product
from pathlib import Path
import argparse, hashlib, json, resource, time
from .circuit import parse_netlist, derive_symmetry, apply_symmetry, generate_actions, compile_plan, exhaustive_plan


ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'research/consequential009/analog'


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')


def hypotheses(circuit,names):
    out=[]
    for bits in product(('9/10','11/10'),repeat=len(names)):
        raw={e.name:str(e.value) for e in circuit.elements}
        for name,m in zip(names,bits): raw[name]=str(F(raw[name])*F(m))
        for scale in ('1/2','1','2'):
            out.append({'id':'t'+''.join('0' if x=='9/10' else '1' for x in bits)+'-a'+scale.replace('/','_'),
                'tolerance_multipliers':dict(zip(names,bits)),'impedance_scale':scale,
                'values':apply_symmetry(circuit,raw,scale)})
    return out


def default_protocol():
    return {'schema':'consequential009-analog-development-v1','status':'DEVELOPMENT; all cases exposed; no statistical confirmation',
      'source_commit':'032b1c32c4dbad45ff132bcfac1dbecadbd8abb0',
      'sources':{'rc-meas-ac.sp':'2d464ba58ee46f4f88cb319debe5e90d396e06ad','MonteCarlo.sp':'608dc4cfdda5d168952a6319d87a9d63f4f6cb84'},
      'omega_rad_s':['100000','300000','1000000','3000000'],
      'successor_omega_rad_s':['300000','1000000','3000000','10000000'],
      'source_supply_gain':['4/5','6/5'],
      'supply_treatment':'Simultaneous coherent ratios to measured input cancel a common source amplitude; no physical gain/phase calibration has been measured.',
      'allow_flux_extension':True,
      'policies':{'voltage_ratio':{'gain':['1','1'],'absolute_coordinate_error':'1/10000'},
        'input_admittance':{'gain':['999/1000','1001/1000'],'absolute_coordinate_error':'1/10000000'}},
      'unknown_current_gain_stress':['1/2','2'],
      'tolerance_scope':'Finite authored +/-10percent component grid, then derived scale1/2,1,2. Not a continuous-tolerance guarantee; no measured specimen truth.',
      'original_tolerance_elements':['r1','c1','c2','r2'],
      'successor_tolerance_elements':['c1','c2','l3'],
      'endpoint':'All unordered pairs in full admitted finite cohort must be separated by at least one exact nonoverlapping complex response rectangle. Otherwise output unresolved pairs and abstain, with full denominator.',
      'comparator':'All-node voltage at every admitted frequency, ordinary exhaustive design over identical extended VI observations, full VI experiment, and reset/ordinary reuse controls.',
      'claim_limits':['known network laws and impedance scaling are not claimed novel','synthetic circuit responses are not physical measurements','calibration bounds are conditional authored envelopes, not measured guarantees','all simulation model errors and out-of-family loads remain unbounded','resource and monetary costs are distinct']}


def run(output,protocol_path=None):
    started=time.perf_counter();cpu=time.process_time();out=Path(output);out.mkdir(parents=True,exist_ok=True)
    protocol=json.loads(Path(protocol_path).read_text()) if protocol_path else default_protocol()
    write(out/'PROTOCOL.json',protocol)
    protocol_hash=hashlib.sha256((out/'PROTOCOL.json').read_bytes()).hexdigest()
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'inventions/consequential009/circuit.py']}
    results={}
    for edition,filename,names,omegas in [('primary','rc-meas-ac.sp',protocol['original_tolerance_elements'],protocol['omega_rad_s']),
             ('fresh_successor','MonteCarlo.sp',protocol['successor_tolerance_elements'],protocol['successor_omega_rad_s'])]:
        raw=(SOURCE/filename).read_text();c=parse_netlist(raw);hs=hypotheses(c,names)
        p=dict(protocol,omega_rad_s=omegas)
        write(out/(edition+'-COHORT.json'),{'source_sha256':c.source_sha256,'hypotheses':hs,
              'scope':'finite model-derived; nominal extraction before control block; raw ngspice control/Monte Carlo not executed'})
        gen=generate_actions(c,p);actions=gen['actions']
        write(out/(edition+'-GENERATED.json'),gen)
        old=compile_plan(c,hs,actions,protocol['policies'],allow_extension=False)
        candidate=compile_plan(c,hs,actions,protocol['policies'])
        ordinary=exhaustive_plan(c,hs,actions,protocol['policies'])
        stress_p=json.loads(json.dumps(protocol['policies']));stress_p['input_admittance']['gain']=protocol['unknown_current_gain_stress']
        stress=compile_plan(c,hs,actions,stress_p)
        for arm,data in [('voltage-only',old),('constructed',candidate),('ordinary-exhaustive',ordinary),('unknown-gain-stress',stress)]:
            write(out/(edition+'-'+arm+'.json'),data)
        results[edition]={'cohort':len(hs),'pairs':candidate['admitted_pairs'],
          'voltage_only_separated':old['separated_pairs'],'constructed_separated':candidate['separated_pairs'],
          'constructed_complete_acceptance':candidate['complete_finite_model_acceptance'],
          'constructed_actions':len(candidate['selected_actions']),
          'ordinary_separated':ordinary['separated_pairs'],'ordinary_actions':len(ordinary['selected_actions']),
          'strong_technical_advantage':candidate['separated_pairs']>ordinary['separated_pairs'],
          'unknown_gain_stress_unresolved':len(stress['unresolved_pairs']),
          'truth_scope':'model-derived exact linear RCL responses; no physical calibration'}
    results.update({'protocol_sha256':protocol_hash,'source_hashes':before,
        'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.perf_counter()-started,
        'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'scientific_novelty':'NOT_ESTABLISHED','physical_capability':'NOT_VALIDATED',
        'retention_benefit':'Root retention experiment separate; possession of better tools not discovery improvement',
        'monetary_cost':'UNKNOWN; measured CPU not complete money','commerce':'No buyer, payment or earned funds created by this run'})
    write(out/'REPORT.json',results);return results


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--protocol')
    args=p.parse_args();print(json.dumps(run(args.output,args.protocol),indent=2))
