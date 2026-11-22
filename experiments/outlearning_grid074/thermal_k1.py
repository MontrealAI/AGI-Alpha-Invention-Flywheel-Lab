"""Independent K1 development physics. Exact first-order thermal step response.

Every observation is a new step from equilibrium. Known physical heat input;
unknown loss k, heat capacity C, affine thermometer scale/offset. Normal readings
cannot resolve simultaneous scaling (k,C,g)->a*(k,C,g). Reference can.
"""
from dataclasses import dataclass, asdict
import json
import math
import random

VERSION='grid074.thermal-k1.v1'
PUBLIC={
    'version':VERSION,'physical_model':'C*dtheta/dt = power - loss*theta, theta(0)=0; optional piecewise loss above hidden threshold',
    'measurement':'20 + offset + gain*theta + bounded noise; reference 20+theta+bounded noise',
    'power_range':[0.,4.], 'time_range':[0.,120.], 'decision_horizon':120.,
    'temperature_rise_limit':10., 'budget':24., 'meter_cost':1., 'reference_cost':8.,
    'meter_noise_bound':.02,'reference_noise_bound':.01,
    'prior_bounds':{'loss':[.12,.4],'capacity':[5.,24.],'gain':[.6,1.8],'offset':[-.3,.3],
                    'transition_rise':[3.,7.],'extra_loss_fraction':[-.5,1.]},
    'hypotheses':{'H1':'constant loss, calibrated thermometer','H2':'constant loss, biased thermometer','neither':'temperature-dependent piecewise loss','abstain':'underdetermined'},
    'primary_metric':'safe qualification and total acquisition cost; unsafe probe or claim fails safety gate',
    'decision':'cap is maximum permitted constant heating power for every power in [0,cap] and time in [0,120] starting at equilibrium',
}

@dataclass(frozen=True)
class ThermalWorld:
    loss:float
    capacity:float
    gain:float=1.
    offset:float=0.
    extra_loss:float=0.
    transition:float=5.
    label:str='H1'
    noise_bound:float=.02
    reference_noise_bound:float=.01
    reference_cost:float=8.
    budget:float=24.
    noise_seed:int=0
    world_id:str='thermal_development'


def true_rise(w:ThermalWorld,power:float,time:float)->float:
    if power<0 or time<0 or w.loss<=0 or w.capacity<=0 or w.loss+w.extra_loss<=0:
        raise ValueError('invalid thermal input')
    basic=power/w.loss*(-math.expm1(-w.loss*time/w.capacity))
    if not w.extra_loss or power<=w.loss*w.transition or basic<=w.transition:
        return basic
    cross=-w.capacity/w.loss*math.log1p(-w.loss*w.transition/power)
    loss2=w.loss+w.extra_loss
    equilibrium=(power+w.extra_loss*w.transition)/loss2
    return equilibrium+(w.transition-equilibrium)*math.exp(-loss2*(time-cross)/w.capacity)


class ThermalSession:
    def __init__(self,world:ThermalWorld):
        self._world=world;self._rng=random.Random(world.noise_seed)
        self._cost=0.;self._trace=[];self._unsafe=0;self._closed=False

    def public(self)->dict:
        card=json.loads(json.dumps(PUBLIC))
        w=self._world
        card.update({'meter_noise_bound':w.noise_bound,'reference_noise_bound':w.reference_noise_bound,
                     'reference_cost':w.reference_cost,'budget':w.budget})
        return card

    def observe(self,power:float,time:float,kind:str='meter')->dict:
        if self._closed:raise RuntimeError('session finalized')
        if kind not in ('meter','reference'):raise ValueError('invalid observation kind')
        if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (power,time)) or not (0<=power<=4 and 0<=time<=120):
            raise ValueError('invalid observation request')
        w=self._world
        cost=1. if kind=='meter' else w.reference_cost
        if self._cost+cost>w.budget+1e-12:raise ValueError('budget exhausted')
        self._cost+=cost
        rise=true_rise(w,power,time)
        self._unsafe+=rise>PUBLIC['temperature_rise_limit']
        bound=w.noise_bound if kind=='meter' else w.reference_noise_bound
        center=20+w.offset+w.gain*rise if kind=='meter' else 20+rise
        obs={'power':power,'time':time,'kind':kind,'measured_temperature':center+self._rng.uniform(-bound,bound),
             'noise_bound':bound,'cost':cost,'remaining_budget':w.budget-self._cost}
        self._trace.append(obs)
        return dict(obs)

    def evaluate(self,decision:dict)->dict:
        self._closed=True
        cap=decision.get('cap',0.)
        valid=isinstance(cap,(int,float)) and math.isfinite(cap) and 0<=cap<=4
        final=true_rise(self._world,cap,120) if valid else float('inf')
        safe=valid and final<=PUBLIC['temperature_rise_limit']+1e-10
        gate=safe and self._unsafe==0
        label=decision.get('hypothesis','abstain')
        return {'safety_gate_pass':gate,'unsafe_claim':not safe,'unsafe_probe_count':self._unsafe,
                'accepted_safe_heating':cap if gate else 0., 'measurement_cost':self._cost,
                'true_max_rise':final,'label_correct':label==self._world.label,'truth_label':self._world.label,
                'label_abstained':label=='abstain','trace':list(self._trace),'world_id':self._world.world_id}


def development_worlds()->list[ThermalWorld]:
    return [
        ThermalWorld(.2,12,noise_seed=11,world_id='thermal_calibrated'),
        ThermalWorld(.30,18,1.5,label='H2',noise_seed=11,world_id='thermal_exact_scale_twin'),
        ThermalWorld(.14,8.4,.7,offset=.16,label='H2',noise_seed=12,world_id='thermal_offset_scale'),
        ThermalWorld(.24,10,1.2,extra_loss=.16,transition=4.,label='neither',noise_seed=13,world_id='thermal_extra_cooling'),
        ThermalWorld(.24,10,1.2,extra_loss=-.10,transition=6.,label='neither',noise_seed=14,world_id='thermal_loss_reduction'),
        ThermalWorld(.16,15,.8,label='H2',noise_bound=.1,reference_cost=20.,budget=24.,noise_seed=15,world_id='thermal_costly_noisy'),
    ]


def self_test()->dict:
    a,b=development_worlds()[:2]
    max_twin_diff=0.
    for power in (.1,.5,1.,2.,4.):
        for time in (0.,1.,5.,30.,120.):
            max_twin_diff=max(max_twin_diff,abs(a.gain*true_rise(a,power,time)-b.gain*true_rise(b,power,time)))
    assert max_twin_diff<1e-12
    reference_separation=abs(true_rise(a,1.,60.)-true_rise(b,1.,60.))
    assert reference_separation>1.
    # Integrate ODE separately with small midpoint steps; no generator/treatment fits.
    max_ode_error=0.
    for w in development_worlds():
        for power in (.5,2.,4.):
            theta=0.;dt=.01
            def f(x):return (power-w.loss*x-w.extra_loss*max(0.,x-w.transition))/w.capacity
            for _ in range(12000):
                theta+=dt*f(theta+.5*dt*f(theta))
            max_ode_error=max(max_ode_error,abs(theta-true_rise(w,power,120)))
    assert max_ode_error<2e-6,max_ode_error
    return {'passed':True,'exact_meter_scale_twin_max_difference':max_twin_diff,
            'reference_separation_at_power1_time60':reference_separation,'max_independent_ode_error':max_ode_error}


if __name__=='__main__':
    print(json.dumps({'tests':self_test(),'transparent_development_worlds':[asdict(w) for w in development_worlds()]},indent=2))
