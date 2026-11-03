"""Offline, conditional archival-event certificate; no image, key, API or account access."""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from datetime import datetime, timezone
from pathlib import Path

STATES = {'water_contact', 'no_water_contact', 'unknown'}
TARGETS = ('road', 'sidewalk')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def ingest(csv_bytes, manifest_bytes):
    rows = list(csv.DictReader(csv_bytes.decode('utf-8').splitlines()))
    manifest = json.loads(manifest_bytes)
    sources = {r['filename']: r for r in manifest}
    if len(sources) != len(manifest) or not sources:
        raise ValueError('SOURCE_DUPLICATE_OR_EMPTY')
    grid = {}
    for r in rows:
        f, q, state = r['filename'], r['query'], r['state']
        if q not in TARGETS or state not in STATES or f not in sources:
            raise ValueError('UNREGISTERED_TARGET_STATE_OR_SOURCE')
        m = sources[f]
        if r['timestamp'] != m['timestamp'] or r['sha256'] != m['sha256'] or r['url'] != m['url']:
            raise ValueError('IMAGE_PROVENANCE_DISAGREEMENT')
        if len(m['sha256']) != 64 or len(bytes.fromhex(m['sha256'])) != 32:
            raise ValueError('INVALID_IMAGE_HASH')
        key = (f,q)
        if key in grid:
            raise ValueError('DUPLICATE_SOURCE_QUERY')
        grid[key] = state
    frames = sorted(sources.values(), key=lambda x:(x['timestamp'], x['filename']))
    if len(grid) != len(frames)*len(TARGETS):
        raise ValueError('INCOMPLETE_SOURCE_QUERY_GRID')
    return frames, grid

class Observations:
    def __init__(self, frames, grid, budget):
        self.frames, self.grid, self.budget = frames, grid, budget
        self.seen = {}
        if type(budget) is not int or budget < 0:
            raise ValueError('INVALID_REVIEW_BUDGET')
    def observe(self, index):
        if not 0 <= index < len(self.frames):
            raise ValueError('INDEX_OUTSIDE_ARCHIVE')
        if index not in self.seen:
            if len(self.seen) >= self.budget:
                return False
            f = self.frames[index]['filename']
            self.seen[index] = {q:self.grid[(f,q)] for q in TARGETS}
        return True

def uniform_indices(n, count):
    if n == 0 or count == 0:
        return []
    if count == 1:
        return [0]
    return sorted({(i*(n-1))//(count-1) for i in range(count)})

def edges(seen, query):
    wet = sorted(i for i, row in seen.items() if row[query]=='water_contact')
    if not wet:
        return []
    first, last = wet[0], wet[-1]
    left = [i for i,row in seen.items() if i < first and row[query]=='no_water_contact']
    right = [i for i,row in seen.items() if i > last and row[query]=='no_water_contact']
    return [(max(left),first,'onset')] * bool(left) + [(last,min(right),'exit')] * bool(right)

def certificate(frames, obs, query):
    ee = {k:(a,b) for a,b,k in edges(obs.seen,query)}
    if set(ee)!={'onset','exit'}:
        return {'status':'ABSTAIN_MISSING_DRY_WET_DRY_WITNESSES'}
    a,b = ee['onset']; c,d=ee['exit']
    ts = lambda i:frames[i]['timestamp']
    dt = lambda i:datetime.strptime(ts(i), '%Y-%m-%dT%H-%M-%SZ').replace(tzinfo=timezone.utc)
    return {'status':'CONDITIONAL_SINGLE_EPISODE','onset':{'after':ts(a),'at_or_before':ts(b),'width_hours':round((dt(b)-dt(a)).total_seconds()/3600,6)},'exit':{'at_or_after':ts(c),'before':ts(d),'width_hours':round((dt(d)-dt(c)).total_seconds()/3600,6)},'witness_indices':[a,b,c,d]}

def ordinary(obs):
    n=len(obs.frames)
    for i in uniform_indices(n,min(12,obs.budget)):
        obs.observe(i)
    turn=0
    while len(obs.seen)<obs.budget:
        moves=[]
        for q in TARGETS:
            spans=[(b-a,(a+b)//2) for a,b,_ in edges(obs.seen,q) if b-a>1 and (a+b)//2 not in obs.seen]
            if spans:
                width,m=max(spans)
                moves.append((q,width,m))
        if not moves:break
        q,w,m=sorted(moves,key=lambda row:(-row[1],(TARGETS.index(row[0])-turn)%len(TARGETS),row[2]))[0]
        obs.observe(m)
        turn=(TARGETS.index(q)+1)%len(TARGETS)
    return obs

def joint(obs):
    n=len(obs.frames)
    for i in uniform_indices(n,min(12,obs.budget)):
        obs.observe(i)
    while len(obs.seen)<obs.budget:
        scores={}
        for q in TARGETS:
            for a,b,_ in edges(obs.seen,q):
                if b-a<2: continue
                m=(a+b)//2
                if m in obs.seen: continue
                scores[m]=scores.get(m,0.0)+math.log2(b-a)
        if not scores: break
        obs.observe(min(scores, key=lambda i:(-scores[i],i)))
    return obs

def evaluate(frames, grid, seen, query):
    states=[grid[(f['filename'],query)] for f in frames]
    wet=[i for i,s in enumerate(states) if s=='water_contact']
    report={'oracle_label_scope':'RECORDED_SEMANTIC_PREDICTIONS_NOT_PHYSICAL_TRUTH','positive_frames':len(wet),'unknown_frames':states.count('unknown')}
    c=certificate(frames,seen,query)
    if not wet:
        return {**report,'status':'NO_RECORDED_POSITIVE','certificate':c}
    violations=sum(s=='no_water_contact' for s in states[wet[0]:wet[-1]+1])
    report['interior_recorded_dry_violations']=violations
    report['conditional_episode_consistent_on_exposed_record']=violations==0
    if c['status']=='CONDITIONAL_SINGLE_EPISODE':
        ee={k:(a,b) for a,b,k in edges(seen.seen,query)}
        a,b=ee['onset']; d,e=ee['exit']
        report['archive_wet_extrema_bracketed']=a < wet[0] <= b and d <= wet[-1] < e
        report['eligible_for_conditional_interval']=report['conditional_episode_consistent_on_exposed_record'] and report['archive_wet_extrema_bracketed']
    else:
        report['archive_wet_extrema_bracketed']=False
        report['eligible_for_conditional_interval']=False
    report['certificate']=c
    return report

def run(csv_bytes,manifest_bytes,budget=32):
    frames,grid=ingest(csv_bytes,manifest_bytes)
    if budget>len(frames):
        budget=len(frames)
    methods={'no_deploy':Observations(frames,grid,0),'uniform':Observations(frames,grid,budget),'ordinary_bisection':Observations(frames,grid,budget),'joint_adaptive':Observations(frames,grid,budget),'exhaustive_upper_bound':Observations(frames,grid,len(frames))}
    for i in uniform_indices(len(frames),budget): methods['uniform'].observe(i)
    ordinary(methods['ordinary_bisection']);joint(methods['joint_adaptive'])
    for i in range(len(frames)): methods['exhaustive_upper_bound'].observe(i)
    summaries={}
    for name,obs in methods.items():
        summaries[name]={'image_reads':len(obs.seen),'target_assessments':2*len(obs.seen),'observed_image_sha256':[frames[i]['sha256'] for i in sorted(obs.seen)],'queries':{q:evaluate(frames,grid,obs,q) for q in TARGETS}}
    return {'schema':'agi-alpha/historical-event-contract001/v1','status':'EXPOSED_ARCHIVE_EXPERIMENT_NOT_NEW_CONFIRMATION','source_csv_sha256':sha(csv_bytes),'source_manifest_sha256':sha(manifest_bytes),'frames':len(frames),'budget_images':budget,'distinct_targets':list(TARGETS),'methods':summaries,'limitations':['All labels were produced in the historical 2024 study; evaluation is exposed engineering replay, not a fresh blinded or physical validation.','A single wet episode cannot be established from sparse frames or unknowns; intervals are explicitly conditional and not exact onset/reopening dates.','No buyer, willingness-to-pay, outreach, price, native account, collection, measured AI billing or complete delivery cost.','Both queries concern one existing camera and event; no scalable demand, historical economic impossibility, newly qualified scientific method or recursive discovery is established.']}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--measurements',type=Path,default=Path(__file__).parents[2]/'research/historical_measurement/v2/production_measurements.csv')
    p.add_argument('--manifest',type=Path,default=Path(__file__).parents[2]/'research/historical_measurement/manifest.json')
    p.add_argument('--budget',type=int,default=32)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    result=run(args.measurements.read_bytes(),args.manifest.read_bytes(),args.budget)
    rendered=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output:args.output.write_text(rendered)
    else:print(rendered)

if __name__=='__main__':main()
