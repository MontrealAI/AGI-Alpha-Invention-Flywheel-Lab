"""Frozen train/calibration/test execution on publisher-hashed physical bytes."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import platform
import tempfile
import time
import urllib.request
from importlib.metadata import version
from pathlib import Path
from .measurement import extract, episodes, read_prefix, inspect_episode
from .prognosis import CUTOFF,ENDPOINTS,METHODS,PRIMARY,SCREEN_THRESHOLD,fit_bank,interval_decision,predict,prefix_features
from .pyprobe_reference import compare_episode
from .cli import readable,screen

ROOT=Path(__file__).parent

class AcquisitionError(RuntimeError):
    def __init__(self, receipt):
        self.receipt=receipt
        super().__init__('Source acquisition failed')

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def save(path,obj):path.write_bytes(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False).encode()+b'\n')

def acquire(entry,manifest,path):
    url=f"https://media.githubusercontent.com/media/{manifest['source_repo']}/{manifest['source_commit']}/{entry['path']}"
    attempts=[]
    for attempt in range(2):
        start=time.perf_counter()
        try:
            with urllib.request.urlopen(url,timeout=120) as r:data=r.read(entry['bytes']+1)
            sha=hashlib.sha256(data).hexdigest()
            if len(data)!=entry['bytes'] or sha!=entry['sha256']:
                raise AcquisitionError({'url':url,'status':'source_identity_mismatch','expected_bytes':entry['bytes'],'observed_bytes':len(data),'expected_sha256':entry['sha256'],'observed_sha256':sha,'attempts':attempts})
            path.write_bytes(data)
            attempts.append({'attempt':attempt+1,'status':'verified','seconds':time.perf_counter()-start})
            return {'url':url,'bytes':len(data),'sha256':sha,'attempts':attempts}
        except (OSError,TimeoutError) as e:
            attempts.append({'attempt':attempt+1,'status':'network_failure','error':type(e).__name__,'seconds':time.perf_counter()-start})
            if attempt==1:raise AcquisitionError({'url':url,'attempts':attempts}) from e
    raise RuntimeError('Unreachable')

def targets(full,prefix):
    return {str(t):full.cycles[t]['capacity_ah']/prefix['reference_capacity_ah'] for t in ENDPOINTS if t in full.cycles}

def reference_checks(path,nominal,accepted):
    checks=[]
    for ep in episodes(read_prefix(path,1000)):
        c=ep[0][3]
        if c not in {1,10,100,500,1000} or c not in accepted.cycles:continue
        e=inspect_episode(ep,nominal)
        if e is not None and not e['errors']:
            try:checks.append(compare_episode(ep))
            except Exception as error:
                checks.append({'cycle':c,'step':ep[0][4],'reference_error':type(error).__name__+': '+str(error)})
    return checks

def measure_record(entry,path,full=False):
    m=extract(path,entry['rated_capacity_ah'],100)
    prefix=prefix_features(m)
    record={'cell':entry['cell'],'group':entry['group'],'role':entry['role'],
            'prefix':prefix,'prefix_quality_flags':m.flags,'prefix_rows':m.observed_rows}
    if full:
        f=extract(path,entry['rated_capacity_ah'],1000)
        record['targets']=targets(f,prefix)
        record['unavailable_target_cycles']=[t for t in ENDPOINTS if t not in f.cycles]
        record['full_quality_flags']=f.flags
        record['accepted_full_cycles']=len(f.cycles)
        record['cycle_capacities_ah']={str(c):e['capacity_ah'] for c,e in f.cycles.items() if c>=1}
        record['reference_checks']=reference_checks(path,entry['rated_capacity_ah'],f)
    return record

def source_identity():
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob('*')) if p.suffix in {'.py','.json','.md','.txt'}}

def run(out,development_only=False):
    out.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();cpu=time.process_time()
    manifest=json.loads((ROOT/'manifest.json').read_text())
    log=[];records=[]
    selected=manifest['cells'] if not development_only else [e for e in manifest['cells'] if e['cell']=='A0067']
    with tempfile.TemporaryDirectory(prefix='physical-battery100-') as temp:
        temp=Path(temp)
        if development_only:
            entry=selected[0];path=temp/'dev.csv'
            receipt=acquire(entry,manifest,path)
            record=measure_record(entry,path,True)
            compact={k:v for k,v in record.items() if k not in {'prefix','cycle_capacities_ah'}}
            compact['prefix']={k:v for k,v in record['prefix'].items() if k!='curve'}
            compact['receipt']=receipt
            save(out/'development.json',compact)
            print('BATTERY100_DEVELOPMENT='+json.dumps(compact,sort_keys=True))
            return
        for entry in selected:
            if entry['role']=='test':continue
            path=temp/'working.csv'
            try:
                receipt=acquire(entry,manifest,path)
                log.append({'cell':entry['cell'],**receipt})
                rec=measure_record(entry,path,True)
                records.append(rec)
            except (ValueError,KeyError,RuntimeError) as e:
                if isinstance(e,AcquisitionError):log.append({'cell':entry['cell'],**e.receipt})
                records.append({'cell':entry['cell'],'group':entry['group'],'role':entry['role'],'error':str(e)})
        training=[x for x in records if x['role']=='train' and 'error' not in x]
        bank=fit_bank(training)
        bank['groups']={e['group']:{'rated_capacity_ah':e['rated_capacity_ah']} for e in selected}
        bank['protocol']='physical-battery100/v1; same-model 1C/35C laboratory schedule'
        bank['scope']='Small empirical residual ranges; no certified coverage or field deployment'
        bank['source_identity']=source_identity()
        calibration=[]
        for method in METHODS:
            errors={str(t):[] for t in ENDPOINTS}
            for record in [r for r in records if r['role']=='calibration']:
                item={'cell':record['cell'],'method':method}
                try:
                    if 'error' in record:raise ValueError(record['error'])
                    predictions=predict(record['prefix'],record['group'],bank,method)
                    for t,p in predictions.items():
                        if t in record['targets']:errors[t].append(abs(p-record['targets'][t]))
                    item.update(predictions=predictions,targets=record['targets'])
                except (ValueError,KeyError) as e:item['error']=str(e)
                calibration.append(item)
            bank['widths'][method]={t:max(vals) for t,vals in errors.items() if len(vals)==9}
        bank['model_identity']=digest(bank)
        save(out/'model.json',bank)
        predictions=[];test_paths={}
        for entry in [e for e in selected if e['role']=='test']:
            path=temp/(entry['cell']+'.csv');test_paths[entry['cell']]=path
            try:
                receipt=acquire(entry,manifest,path);log.append({'cell':entry['cell'],**receipt})
                record=measure_record(entry,path,False)
            except (ValueError,KeyError,RuntimeError) as e:
                if isinstance(e,AcquisitionError):log.append({'cell':entry['cell'],**e.receipt})
                record={'cell':entry['cell'],'group':entry['group'],'error':str(e)}
            for method in METHODS:
                item={'cell':entry['cell'],'group':entry['group'],'method':method}
                try:
                    if 'error' in record:raise ValueError(record['error'])
                    p=predict(record['prefix'],record['group'],bank,method)
                    item['endpoints']=interval_decision(p,bank['widths'][method])
                except (ValueError,KeyError) as e:item['error']=str(e)
                predictions.append(item)
        # The explicit forecast artifact and its hash exist BEFORE parsing test labels.
        seal={'model_identity':bank['model_identity'],'predictions':predictions,'prediction_sha256':digest(predictions)}
        save(out/'sealed_predictions.json',seal)
        print('BATTERY100_PREDICTION_SEAL='+json.dumps({'sha256':seal['prediction_sha256'],'model':bank['model_identity']}),flush=True)
        tests=[]
        for entry in [e for e in selected if e['role']=='test']:
            path=test_paths[entry['cell']]
            try:
                r=measure_record(entry,path,True)
                tests.append(r)
            except (ValueError,KeyError,OSError) as e:tests.append({'cell':entry['cell'],'group':entry['group'],'error':str(e)})
        results=[]
        for item in predictions:
            row=dict(item);truth=next(r for r in tests if r['cell']==item['cell'])
            if 'error' in truth:row['target_error']=truth['error']
            if 'error' not in item and 'error' not in truth:
                row['targets']=truth['targets'];row['unavailable_target_cycles']=truth['unavailable_target_cycles'];row['metrics']={}
                for t,e in item['endpoints'].items():
                    if t not in truth['targets']:continue
                    y=truth['targets'][t]
                    row['metrics'][t]={'absolute_error':abs(e['prediction']-y),'signed_error':e['prediction']-y,
                        'covered':e.get('lower',float('inf'))<=y<=e.get('upper',-float('inf')),
                        'interval_width':e['upper']-e['lower'] if 'lower' in e else None,
                        'correct_decisive':((e['decision']=='SCREEN_PASS' and y>=SCREEN_THRESHOLD) or
                                            (e['decision']=='SCREEN_FAIL' and y<SCREEN_THRESHOLD)) if e['decision']!='CONTINUE_TESTING' else None}
            results.append(row)
        primary=[x for x in results if x['method']==PRIMARY]
        metrics=[m for x in primary for m in x.get('metrics',{}).values()]
        decisive=[x['metrics']['1000']['correct_decisive'] for x in primary if '1000' in x.get('metrics',{}) and x['metrics']['1000']['correct_decisive'] is not None]
        gates={'all_nine_cells_and_two_endpoints':len(metrics)==18,
               'maximum_error_at_most_five_percentage_points':len(metrics)==18 and max(m['absolute_error'] for m in metrics)<=0.05,
               'all_18_endpoint_intervals_cover':len(metrics)==18 and all(m['covered'] for m in metrics),
               'at_least_three_decisive_cycle1000':len(decisive)>=3,
               'no_wrong_decisive_cycle1000':bool(decisive) and all(decisive)}
        report={'kind':'actual_measured_lab_retrospective_prognosis','registered_test_cells':9,'registered_endpoints':18,
                'primary':PRIMARY,'acceptance':gates,'accepted':all(gates.values()),'results':results,
                'calibration':calibration,'training_records':records,'test_records':tests,
                'acquisition_receipts':log,'prediction_seal':seal['prediction_sha256'],'model_identity':bank['model_identity'],
                'versions':{x:version(x) for x in ('numpy','scipy','PyProBE-Data','polars')},'python':platform.python_version(),
                'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,
                'costs':'Actual whole-development/model-session/billing/commercial costs unknown; no zero-cost/profit claim'}
        with (out/'cycle_capacities.csv').open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['cell','group','role','cycle','accepted_capacity_ah'])
            for record in records+tests:
                for c in range(1,1001):
                    writer.writerow([record['cell'],record['group'],record.get('role','test'),c,record.get('cycle_capacities_ah',{}).get(str(c),'')])
        save(out/'evaluation.json',report)
        lines=['# Physical battery laboratory screening result','',f"Finite pilot accepted: {report['accepted']}",
               'Nine untouched test cells, two protocol-specific endpoints each. Actual physical lab data; not field deployment.',
               '', '## Locked primary acceptance']
        lines.extend(f'- {k}: {v}' for k,v in gates.items())
        lines+=['','## Complete forecast comparison','', '| Method | Scorable endpoints / 18 | MAE, percentage points | Max error, percentage points | Covered / scorable |','|---|---:|---:|---:|---:|']
        for method in METHODS:
            ms=[m for x in results if x['method']==method for m in x.get('metrics',{}).values()]
            mae=sum(m['absolute_error'] for m in ms)/len(ms) if ms else None
            maximum=max((m['absolute_error'] for m in ms),default=None)
            lines.append(f"| {method} | {len(ms)} | {100*mae:.3f} | {100*maximum:.3f} | {sum(m['covered'] for m in ms)}/{len(ms)} |" if ms else f'| {method} | 0 | unavailable | unavailable | 0/0 |')
        lines+=['','## Endpoint-specific comparison','', '| Method | Cycle | Scorable / 9 | MAE, percentage points | Covered |','|---|---:|---:|---:|---:|']
        for method in METHODS:
            for endpoint in ENDPOINTS:
                ms=[x['metrics'][str(endpoint)] for x in results if x['method']==method and str(endpoint) in x.get('metrics',{})]
                mae=100*sum(m['absolute_error'] for m in ms)/len(ms) if ms else None
                lines.append(f"| {method} | {endpoint} | {len(ms)} | {mae:.3f} | {sum(m['covered'] for m in ms)}/{len(ms)} |" if ms else f'| {method} | {endpoint} | 0 | unavailable | 0/0 |')
        refs=[r for record in records+tests for r in record.get('reference_checks',[])]
        reference_errors=[r for r in refs if 'reference_error' in r]
        lines+=['','## Direct PyProBE reference',f'{len(refs)-len(reference_errors)}/{len(refs)} selected accepted-episode checks completed. {len(reference_errors)} adapter errors remain explicit in JSON.',
                f"Maximum capacity-range versus terminal-minus-initial discrepancy: {max((r['absolute_delta_disagreement_ah'] for r in refs if 'absolute_delta_disagreement_ah' in r),default=None)} Ah."]
        lines+=['','## Per-cell primary screening','']
        for x in primary:
            lines.append(f"- {x['cell']}: "+(x.get('error') or x.get('target_error') or '; '.join(f"cycle{t}: predicted {100*e['prediction']:.2f}%, observed {100*x['targets'][t]:.2f}%, {e['decision']}" for t,e in x['endpoints'].items() if t in x.get('targets',{}))))
        lines+=['','## Limits','No actual laboratory cycles, time, money or sales were saved. No autonomy, novelty, field-risk or safety claim.',
                'Same-model historical replicate test only. Correlated nine-cell calibration does not establish distribution-free coverage.',
                'Cycle500 regular cycling and cycle1000 post-diagnostic discharge have distinct preparation contexts.',
                'PyProBE agreement is conventional arithmetic consistency on shared sensor values, not independent metrology.',
                f"Prediction seal: {seal['prediction_sha256']}",f"Measured execution: {report['wall_seconds']:.2f}s wall, {report['cpu_seconds']:.2f}s CPU.",report['costs']]
        (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
        # An actual offline user journey, using the same file with future rows present.
        good=next((x for x in manifest['cells'] if x['role']=='test' and test_paths[x['cell']].exists()),None)
        if good:
            demo=screen(test_paths[good['cell']],good['group'],out/'model.json',protocol_confirmed=True)
            truncated=temp/'example-prefix.csv'
            from .measurement import FIELDS
            with truncated.open('w',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(FIELDS)
                writer.writerows(read_prefix(test_paths[good['cell']],100))
            prefix_demo=screen(truncated,good['group'],out/'model.json',protocol_confirmed=True)
            if demo!=prefix_demo:raise AssertionError('Real full-file versus observed-prefix screening differs')
            save(out/'offline_journey.json',{'cell':good['cell'],'full_file_equals_observed_prefix':True,'model_identity':bank['model_identity']})
            save(out/'example_screen.json',demo);(out/'example_screen.txt').write_text(readable(demo))
        print('BATTERY100_RESULT='+json.dumps({'accepted':report['accepted'],'gates':gates,'seal':seal['prediction_sha256'],'rows':len(results),'wall_seconds':report['wall_seconds']},sort_keys=True),flush=True)
        print((out/'REPORT.md').read_text())
        # Compact derived artifact transport, never raw publisher measurements.
        import base64,gzip
        bundle={p.name:p.read_text() for p in out.iterdir() if p.suffix in {'.json','.md','.txt'}}
        encoded=base64.b64encode(gzip.compress(canonical(bundle),mtime=0)).decode()
        chunks=[encoded[i:i+12000] for i in range(0,len(encoded),12000)]
        for index,chunk in enumerate(chunks):print(f'BATTERY100_DERIVED_BUNDLE_PART={index+1}/{len(chunks)}:'+chunk,flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--development-only',action='store_true');args=p.parse_args()
    run(args.output,args.development_only)
if __name__=='__main__':main()
