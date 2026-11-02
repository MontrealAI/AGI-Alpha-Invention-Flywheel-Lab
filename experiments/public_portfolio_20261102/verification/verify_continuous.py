from __future__ import annotations
import argparse, json
from fractions import Fraction as Q
from pathlib import Path
import verify_science as base


def run(benchmark_root=None):
    mu=Q(1,10000);vmax=Q(161,5);horizon=Q(5)
    acceleration=Q(2)+mu*vmax*vmax/2
    lower_velocity=Q(30)-horizon*acceleration
    w_factor=Q(1)-mu*vmax*horizon
    margin=Q(90)-Q(11)-Q(10)-Q(7,5)*Q(151,5)
    initial_relative_velocity_min=Q(32)-Q(151,5)
    checks={
        'acceleration_interval_lower_face_points_inward':2*acceleration-4-mu*vmax*vmax==0,
        'acceleration_interval_upper_face_points_inward':-4<0,
        'velocity_stays_positive':lower_velocity>0,
        'lead_stays_faster_until_five_seconds':initial_relative_velocity_min>0 and w_factor>0,
        'uniform_initial_safety_margin_positive':margin>0}
    proof=[
        'Under equal constant commands uL=uE=-2, each acceleration obeys a_dot=-2a-4-mu*v^2. Starting a=0, the interval[-A,0] is invariant while0<=v<=V: the lower-face derivative is2A-4-mu*v^2>=0 and upper-face derivative is-4-mu*v^2<0.',
        'Velocity cannot increase since a<=0 and cannot reach zero by5s because v>=30-5A>0. This closes the preceding velocity/acceleration invariant bootstrap.',
        'For w=vL-vE and z=aL-aE, z_dot=-2z-mu*(vL+vE)*w, z(0)=0. Before a first zero of w, z<=0 implies0<w<=w0. Variation of constants then gives z>=-mu*V*w0, since vL+vE<=2V and the exponential integral is<=1/2.',
        'Therefore w(t)>=w0*(1-mu*V*t)>0 through5s, contradicting a first zero. The separation grows while ego velocity falls, so d=xL-xE-10-(7/5)*vE is at least its minimum initial margin668/25m.',
        'This is a conditional analytic theorem for a conventional constant-braking controller and the supplied ODE/initial box only. It does not prove the original neural controller, velocity tracking/comfort, actuator or physical-road safety. Those purposes cannot be dropped to promote a full benchmark win.'
    ]
    root=base.BASE/'purpose/continuous'
    protocol=json.loads((root/'PREREGISTRATION.json').read_text())
    source_checks={}
    if benchmark_root is not None:
        for name,expected in protocol['source_input_sha256'].items():
            source_checks[name]=base.digest(Path(benchmark_root)/name)==expected
        checks['external_input_bytes_match_pinned_protocol']=all(source_checks.values())
    return {'schema':'public-portfolio-independent-continuous-property/v1','checker_sha256':base.digest(__file__),
            'protocol_sha256':base.digest(root/'PREREGISTRATION.json'),
            'exact_bounds':{'A_mps2':str(acceleration),'minimum_velocity_mps':str(lower_velocity),'relative_velocity_factor':str(w_factor),'minimum_safe_distance_margin_m':str(margin)},
            'checks':checks,'source_input_hash_checks':source_checks,'source_identity_audit':'supported' if source_checks and all(source_checks.values()) else 'unresolved_not_supplied',
            'passed':all(checks.values()),'independent_derivation':proof,
            'formal_ode_safe_distance_constant_braking':'supported' if all(checks.values()) else 'failed',
            'original_neural_controller_universal_safety':'unresolved','full_speed_tracking_and_comfort':'unresolved',
            'physical_road_safety':'unresolved','blue_sky_admission':'unresolved'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--benchmark-root');args=p.parse_args();output=Path(args.output)
    if output.exists():
        raise ValueError('refuse overwrite of independent property result')
    result=run(args.benchmark_root);output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':result['passed'],'exact_bounds':result['exact_bounds'],'full_tracking_qualified':False}))
    raise SystemExit(0 if result['passed'] else 1)
