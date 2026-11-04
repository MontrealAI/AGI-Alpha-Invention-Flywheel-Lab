import copy
import json
import math
import random
import unittest
from .direct import analyze


def make(r=10,c=2,g=1,f=.5,ev=1e-9,ei=0):
    return {'records':[{'current':i,'v2':g*i*(r+c)+.012,'v4':g*i*f*r-.008} for i in [.01,-.01,.02,-.02]],
            'voltage_error':ev,'current_error':ei,'gain_range':[g,g], 'sense_fraction_range':[f,f]}


class TestDirect(unittest.TestCase):
    def test_exact_changes(self):
        out=analyze({'baseline':make(),'after':make(12,2)})
        self.assertEqual(out['classifications'],{'sample':'changed','contact':'unchanged'})
        out=analyze({'baseline':make(),'after':make(10,3)})
        self.assertEqual(out['classifications'],{'sample':'unchanged','contact':'changed'})

    def test_offsets(self):
        a,b=make(),make()
        for row in b['records']:
            row['v2']+=400
            row['v4']-=12
        out=analyze({'baseline':a,'after':b})
        self.assertEqual(set(out['classifications'].values()),{'unchanged'})

    def test_fail_closed(self):
        for mutate in [lambda s:s.update(voltage_error=-1),lambda s:s.update(gain_range=[0,1]),
                       lambda s:s.update(sense_fraction_range=[1,0]),lambda s:s['records'][0].update(v4=None),
                       lambda s:s['records'][0].update(current=0),lambda s:s.update(current_error=.02),
                       lambda s:s['records'][0].update(v2=float('nan')),
                       lambda s:s['records'][2].update(v2=99),lambda s:s.update(records=[])]:
            s=make();mutate(s)
            out=analyze({'baseline':make(),'after':s})
            self.assertEqual(out['after'],{'bulk':None,'contact':None})
            self.assertEqual(set(out['classifications'].values()),{'ambiguous'})
            json.dumps(out,allow_nan=False)
        self.assertEqual(set(analyze(None)['classifications'].values()),{'ambiguous'})

    def test_outside_rod_and_tiny_gain_abstain(self):
        for changes in [{'sense_fraction_range':[1.1,1.2]},
                        {'sense_fraction_range':[.9,1.1]},
                        {'gain_range':[1e-320,1e-320]}]:
            s=make();s.update(changes)
            out=analyze({'baseline':make(),'after':s})
            self.assertEqual(out['after'],{'bulk':None,'contact':None})
            self.assertEqual(out['difference'],{'bulk':None,'contact':None})
            self.assertEqual(set(out['classifications'].values()),{'ambiguous'})
            json.dumps(out,allow_nan=False)

    def test_geometry_uncertainty(self):
        s=make();s['sense_fraction_range']=[.2,.8]
        self.assertEqual(set(analyze({'baseline':s,'after':s})['classifications'].values()),{'ambiguous'})

    def test_threshold_boundaries(self):
        def exact(r,c):
            return {'records':[{'current':i,'v2':i*(r+c),'v4':i*r} for i in [1,-1]],
                    'voltage_error':0,'current_error':0,'gain_range':[1,1],
                    'sense_fraction_range':[1,1]}
        for sign in [-1,1]:
            out=analyze({'baseline':exact(10,2),'after':exact(10+sign*.5,2+sign*.25)})
            self.assertEqual(set(out['classifications'].values()),{'unchanged'})
            out=analyze({'baseline':exact(10,2),'after':exact(10+sign*.501,2+sign*.251)})
            self.assertEqual(set(out['classifications'].values()),{'changed'})

    def test_serialized_threshold_neighbors(self):
        def exact(value, key):
            return {'records':[{'current':i,'v2':i*value,
                                'v4':i*value if key == 'bulk' else 0} for i in [1,-1]],
                    'voltage_error':0,'current_error':0,'gain_range':[1,1],
                    'sense_fraction_range':[1,1]}
        for key,label,t in [('bulk','sample',.5),('contact','contact',.25)]:
            for value in [math.nextafter(t,-math.inf),t,math.nextafter(t,math.inf)]:
                for sign in [-1,1]:
                    zero, changed = exact(0,key),exact(value,key)
                    before, after = (zero,changed) if sign == 1 else (changed,zero)
                    out=json.loads(json.dumps(analyze({'baseline':before,'after':after}),allow_nan=False))
                    lo,hi=out['difference'][key]
                    expected=('changed' if lo > t or hi < -t else
                              'unchanged' if lo >= -t and hi <= t else 'ambiguous')
                    self.assertEqual(out['classifications'][label],expected)
                    if value <= t:
                        self.assertEqual(expected,'unchanged')
                    else:
                        self.assertIn(expected,('changed','ambiguous'))

    def test_truth_flags_ignored(self):
        a={'baseline':make(),'after':make()}
        b=copy.deepcopy(a)
        b.update(sample_changed=True,contact_changed=True,truth={'bulk':999})
        self.assertEqual(analyze(a),analyze(b))

    def test_random_enclosure(self):
        rng=random.Random(923)
        accepted=0
        for _ in range(2000):
            r,c=rng.uniform(.1,100),rng.uniform(0,10)
            g,f=rng.uniform(.8,1.2),rng.uniform(.2,.9)
            ev,ei=1e-5,1e-8
            s=make(r,c,g,f,ev,ei)
            s['gain_range']=[g*.99,g*1.01]
            s['sense_fraction_range']=[f*.98,f*1.02]
            for row in s['records']:
                delta=rng.uniform(-ei,ei)
                row['v2']+=g*(r+c)*delta+rng.uniform(-ev,ev)
                row['v4']+=g*f*r*delta+rng.uniform(-ev,ev)
            out=analyze({'baseline':s,'after':s})['baseline']
            if out['bulk'] is None:continue
            accepted+=1
            for key, truth in [('bulk',r),('contact',c)]:
                self.assertLessEqual(out[key][0],truth)
                self.assertGreaterEqual(out[key][1],truth)
        self.assertGreater(accepted,1800)

if __name__=='__main__':unittest.main()
