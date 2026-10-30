import argparse
import copy
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from connected_enterprise import engine as old


def candidate(source):
    before="cfg['clearing_hours']>cfg['payment_deadline_hours']"
    after="cfg['production_hours']+cfg['acceptance_hours']+cfg['clearing_hours']>cfg['payment_deadline_hours']"
    if source.count(before)!=1:raise ValueError('EXACT_DEADLINE_PATCH_CONTEXT_REQUIRED')
    source=source.replace(before,after)
    before="slots=cfg['initial_slots']+sum(i['kind']=='capacity' and i['activation_time']<=t<i['expiry_time'] for i in state['investments'])"
    after="production_time=t+cfg['production_hours']\n    usable_capacity=[i for i in state['investments'] if i['kind']=='capacity' and i['activation_time']<=t and production_time<i['expiry_time']]\n    slots=cfg['initial_slots']+len(usable_capacity)"
    if source.count(before)!=1:raise ValueError('EXACT_CAPACITY_PATCH_CONTEXT_REQUIRED')
    source=source.replace(before,after)
    before="[i['plan_id'] for i in state['investments'] if i['kind']=='capacity' and i['activation_time']<=t<i['expiry_time']]"
    if source.count(before)!=1:raise ValueError('EXACT_CAPACITY_ASSIGNMENT_CONTEXT_REQUIRED')
    source=source.replace(before,"[i['plan_id'] for i in usable_capacity]")
    return source


def orders(module,expiry):
    cfg=module.default_config();cfg.update(horizon_days=2,arrival_bps=10000,customer_pool=4)
    state=module._initial(cfg,1,'baseline',{})
    state['queue']=[{'id':'day-one','time':24,'kind':'plan'}]
    state['investments']=[{'kind':'capacity','activation_time':24,'expiry_time':expiry,'plan_id':'paid-capacity'}]
    class Account:
        def snapshot(self):return {'summary':{'unrestrictedEarned':0,'available':1000*module.MICRO}}
    def offer(jobs,s,b,c):
        return {'job':{'id':b['id'],'work_keys':[]}}, {'price_microUSD':3*module.MICRO},100*module.MICRO
    with patch.object(module,'_offer',side_effect=offer),patch.object(module,'draw',return_value=.5):
        return module._prepare_plan(state,Account(),{})['orders']


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():raise ValueError('NEW_EVIDENCE_DIRECTORY_REQUIRED')
    original=(ROOT/'connected_enterprise/engine.py').read_text()
    expected='2194e2d005a715f9e5957c51bb69b920fbd500e7'
    raw=original.encode()
    if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=expected:raise ValueError('EXACT_ENGINE_BLOB_REQUIRED')
    fixed=candidate(original)
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader('connected_enterprise._timing_candidate',loader=None))
    exec(compile(fixed,'<isolated-timing-candidate>','exec'),module.__dict__)
    cfg=old.default_config();cfg['clearing_hours']=cfg['payment_deadline_hours'];old.validate_config(cfg)
    try:module.validate_config(cfg)
    except ValueError:pass
    else:raise AssertionError('INFEASIBLE_DEADLINE_ADMITTED')
    boundary=[]
    for clearing,valid in [(236,True),(237,True),(238,False),(240,False)]:
        cfg=module.default_config();cfg['clearing_hours']=clearing
        try:module.validate_config(cfg);admitted=True
        except ValueError:admitted=False
        assert admitted==valid
        boundary.append({'production_hours':2,'acceptance_hours':1,'clearing_hours':clearing,'deadline_hours':240,'admitted':admitted})
    assert len(orders(old,25))==2
    capacity=[]
    for expiry,count in [(25,1),(26,1),(27,2)]:
        result=orders(module,expiry);assert len(result)==count
        assert all(o['capacity_source_plan_id'] is None or o['production_time']<expiry for o in result)
        capacity.append({'activation':24,'production':26,'expiry':expiry,'orders':len(result)})
    with tempfile.TemporaryDirectory() as tmp:
        output=Path(tmp)/'never-committed';cfg=module.default_config();cfg['clearing_hours']=240
        try:module.run_world(ROOT,{},cfg,1,'baseline',output)
        except ValueError:pass
        else:raise AssertionError('INFEASIBLE_RUN_ADMITTED')
        assert not output.exists()
    a.output.mkdir(parents=True)
    diff=''.join(difflib.unified_diff(original.splitlines(True),fixed.splitlines(True),fromfile='a/connected_enterprise/engine.py',tofile='b/connected_enterprise/engine.py'))
    (a.output/'ENGINE_TIMING.patch').write_text(diff)
    result={'base_head':'3d53f63283723c1a28a224277493aadffd5af5b9','base_engine_git_blob':expected,
        'candidate_engine_sha256':hashlib.sha256(fixed.encode()).hexdigest(),
        'deadline_boundaries':boundary,'capacity_boundaries':capacity,
        'invalid_config_rejected_before_output_or_financial_commitment':True,
        'prior_capacity_expiry_failure_reproduced':True,
        'scope':'ISOLATED_FUNCTIONAL_ENGINEERING_REPAIR; not integrated or full composed/native/release qualification',
        'release_qualified':False,'canonical_source_modified':False}
    (a.output/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
