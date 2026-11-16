"""Actual continuous controller + actual native accounting, with synthetic buyers/costs."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import threading
import time
from .agents import AuthoredFixtureAgent
from .commerce import SimulatedBuyer
from .core import SCHEMA,digest,identifier,save,sign
from .runtime import Engine,default_policy


def instrument():
    return {'name':'Capacity fulfillment','inputs':['demand','capacity','reserve','unit_value'],
            'bindings':{'usable':{'formula':'max(0, capacity-reserve)'},'served':{'formula':'min(demand, usable)'}},
            'outputs':{'served':{'ref':'served'},'unserved':{'formula':'demand-served'},'delivered_value':{'formula':'served*unit_value'}}}


def ordinary():
    return {'inputs':['demand','capacity','reserve','unit_value'],
            'outputs':{'served':{'formula':'min(demand, max(0, capacity-reserve))'},
                       'unserved':{'formula':'demand-min(demand, max(0, capacity-reserve))'},
                       'delivered_value':{'formula':'min(demand, max(0, capacity-reserve))*unit_value'}}}


def example(number=1,*,buyer='buyer-demo',outside=25_000_000):
    def case(d,c,r,v):
        served=min(d,max(0,c-r))
        return {'input':{'demand':d,'capacity':c,'reserve':r,'unit_value':v},
                'expected':{'served':served,'unserved':d-served,'delivered_value':served*v}}
    shift=number*7
    return {'schema':SCHEMA,'buyer':buyer,'purpose':'Construct a reusable bounded digital instrument computing served demand, unmet demand and value after a capacity reserve.',
            'domain':'bounded-json-instrument','inputs':['demand','capacity','reserve','unit_value'],
            'training':[case(100+shift,90,10,2),case(12+shift,100,0,3)],
            'confirmation':[case(150+shift,110,20,4),case(30+shift,20,40,5),case(0,shift,0,9)],
            'ordinary':ordinary(),'price_microUSD':12_000_000,'buyer_budget_microUSD':20_000_000,
            'outside_option_microUSD':outside,'costs_microUSD':{'acquisition':200_000,'research':300_000,
            'construction_per_attempt':500_000,'verification':200_000,'delivery':100_000,'support':400_000,
            'maintenance':200_000,'tax_provision':800_000},'reinvestment_microUSD':1_000_000,
            'reuse_benefit_microUSD':2_000_000,'max_attempts':3,'max_operations':1000,'scope_key':'capacity-fulfillment-v1',
            'conditions':'Inputs are nonnegative numbers; the declared finite cases are the acceptance boundary. No physical device is controlled.',
            'rights':'Synthetic example inputs; recipient may use the generated JSON instrument. Supplied evaluator retains Apache-2.0.',
            'residual_microUSD':400_000,'claim_window_hours':24,'expires_at':int(time.time())+86400,'nonce':'request-'+str(number)}


def wait_job(engine,job,expected,thread,deadline):
    while time.monotonic()<deadline:
        state=engine.state.get(job)['state']
        if state in expected:return state
        if not thread.is_alive():raise RuntimeError('CONTROLLER_STOPPED_BEFORE_REQUEST_COMPLETION')
        time.sleep(.02)
    raise TimeoutError('DEMONSTRATION_OBSERVATION_WINDOW_EXCEEDED')


def run(output):
    output=Path(output).absolute()
    if output.exists():raise ValueError('NEW_DEMO_DIRECTORY_REQUIRED')
    keys={'buyer-demo':b'alpha-test-buyer-not-a-real-customer-key-2026'}
    agent=AuthoredFixtureAgent({'capacity-fulfillment-v1':instrument()},fail_first=True)
    engine=Engine(output,default_policy(),agent,SimulatedBuyer(keys),keys)
    stop=threading.Event();errors=[];result=[]
    def worker():
        try:result.append(engine.run(watch=True,poll=.01,stop=stop))
        except BaseException as exc:errors.append(repr(exc))
    thread=threading.Thread(target=worker,name='alpha-economic-continuous-controller')
    thread.start();deadline=time.monotonic()+180
    ids=[]
    try:
        for number,outside in ((1,25_000_000),(2,25_000_000),(3,10_000_000)):
            c=example(number,outside=outside)
            envelope=sign({'kind':'request','buyer':c['buyer'],'expires_at':c['expires_at'],'contract':c},keys[c['buyer']])
            job=engine.submit(envelope);ids.append(job)
            wait_job(engine,job,{'COMPLETE','DECLINED','REFUNDED'},thread,deadline)
    except BaseException:
        if errors:raise RuntimeError('; '.join(errors)) from None
        raise
    finally:
        stop.set();thread.join(30)
    if thread.is_alive():raise RuntimeError('DEMO_WORKER_DID_NOT_STOP')
    if errors:raise RuntimeError('; '.join(errors))
    report=result[0]
    report['demonstration']={'single_continuous_controller':True,'successive_requests_same_native_account':ids,
                           'worker_stopped':True,'counterparties':'SYNTHETIC','costs':'DECLARED_PREPAID_SIMULATION_ENVELOPES',
                           'actual_model_inference':False,'actual_model_calls':0,'fixture_construction_calls':agent.calls,
                           'first_attempts':len(engine.state.attempts(ids[0])),'successor_attempts':len(engine.state.attempts(ids[1])),
                           'successor_provenance':engine.state.get(ids[1])['data']['artifact']['provenance'],
                           'no_purchase_preserved':engine.state.get(ids[2])['state']=='DECLINED'}
    save(output/'RESULTS.json',report)
    save(output/'REQUEST-example.json',example(10))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();print(json.dumps(run(args.output),indent=2))

if __name__=='__main__':main()
