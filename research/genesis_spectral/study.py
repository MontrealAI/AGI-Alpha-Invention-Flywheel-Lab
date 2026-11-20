"""Raw measured spectra -> a frozen sparse measurement plan -> cross-substrate test.

Research only. Projecting recorded spectra does not validate a new optical sensor.
No full-spectrum preprocessing is allowed on the sparse prediction path.
"""
from __future__ import annotations
import argparse, collections, csv, hashlib, html, io, json, math, platform, re
import struct, sys, tempfile, time, urllib.request, zipfile
from pathlib import Path
import numpy as np

LABEL = re.compile(r'^(Bu5|W6|TG|C|V|DIW)?_(PE|PET|PLA|PP|PVC|SBR)?_(0X15|0X5|1X5|100|50|15|5|0)_(.+)\.asd$', re.I)
SUBSTRATES = {'bu5':'Bu5','w6':'W6','tg':'TG','c':'C','v':'V','diw':'DIW'}

def save(path, obj):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, sort_keys=True, allow_nan=False); f.write('\n')

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def label(name):
    m = LABEL.fullmatch(Path(name).name)
    if not m: return None
    sub, polymer, concentration, _ = m.groups()
    return SUBSTRATES.get((sub or '').lower(),''), (polymer or '').upper(), float(concentration.upper().replace('X','.'))

def decode_asd(data):
    if len(data) < 484 or data[:3] not in (b'ASD',b'asd',b'as6',b'as7',b'as8'):
        raise ValueError('unsupported/truncated ASD header')
    unit = data[186]
    if unit not in (0,1,2,4): raise ValueError('unsupported spectral measurement type')
    start, step = struct.unpack_from('<ff', data, 191)
    n = struct.unpack_from('<H', data, 204)[0]
    code = data[199]
    if code not in (0,2) or not 2 <= n <= 10000 or not math.isfinite(start) or not math.isfinite(step) or step <= 0:
        raise ValueError('invalid ASD spectral layout')
    size = 4 if code == 0 else 8
    if len(data) < 484 + n*size: raise ValueError('truncated ASD spectrum')
    y = np.frombuffer(data, dtype='<f4' if code == 0 else '<f8', count=n, offset=484).astype(float)
    # Separate standard-library reconstruction checks byte count/order for this record.
    reference = np.array(struct.unpack_from('<'+('f' if code == 0 else 'd')*n, data, 484))
    if not np.array_equal(y,reference) or not np.isfinite(y).all(): raise ValueError('invalid spectral values')
    wave = start + step*np.arange(n)
    take = (wave >= 850) & (wave <= 2400)
    if not take.any(): raise ValueError('no registered wavelength support')
    wave, y = wave[take], y[take]
    # SpecDAL's documented percent-reflectance route uses same-channel target/reference.
    reference_present = False
    if data[:3] in (b'as6',b'as7',b'as8'):
        offset = 484+n*size
        if len(data) < offset+20: raise ValueError('truncated reference header')
        reference_present = bool(data[offset])
        desc_length = struct.unpack_from('<H',data,offset+18)[0]
        ref_start = offset+20+desc_length
        if reference_present:
            if len(data) < ref_start+n*size: raise ValueError('truncated reference data')
            ref = np.frombuffer(data,dtype='<f4' if code==0 else '<f8',count=n,offset=ref_start).astype(float)[take]
            if not np.isfinite(ref).all() or (ref<=0).any(): raise ValueError('invalid reference in registered wavelengths')
            y = y/ref
    if not reference_present and unit != 1: raise ValueError('reflectance requires compatible reference data')
    if not np.isfinite(y).all(): raise ValueError('nonfinite reflectance')
    return wave, y

def band_matrix(wave, centers, halfwidth):
    wave = np.asarray(wave, dtype=float)
    if wave.ndim != 1 or not np.isfinite(wave).all() or not np.all(np.diff(wave)>0): raise ValueError('wavelength order')
    weights=[]
    for c in centers:
        keep=(wave>=c-halfwidth)&(wave<=c+halfwidth)
        if not keep.any() or c-halfwidth<wave[0] or c+halfwidth>wave[-1]: raise ValueError('band outside measured spectrum')
        weights.append(keep.astype(float)/keep.sum())
    return np.asarray(weights)

def fetch(url, target, expected_md5):
    if not url.startswith('https://zenodo.org/records/14419753/files/'):
        raise ValueError('unregistered download')
    md=hashlib.md5(); sha=hashlib.sha256(); count=0
    request=urllib.request.Request(url,headers={'User-Agent':'GENESIS spectral research; public-data reproduction'})
    with urllib.request.urlopen(request,timeout=120) as response, Path(target).open('xb') as f:
        if not response.geturl().startswith('https://zenodo.org/'): raise ValueError('unexpected redirect')
        while block:=response.read(1024*1024):
            count+=len(block)
            if count>350_000_000: raise ValueError('source exceeds declared retrieval envelope')
            md.update(block);sha.update(block);f.write(block)
    if md.hexdigest()!=expected_md5: raise ValueError('publisher checksum mismatch')
    return {'url':url,'bytes':count,'publisher_md5':md.hexdigest(),'sha256':sha.hexdigest()}

def load_means(archive,p):
    sums={};counts=collections.Counter();excluded=collections.Counter();wave=None;members=0
    relevant_subs=set(p['train_substrates']+p['validation_substrates']+p['test_substrates'])
    with zipfile.ZipFile(archive) as z:
        rows=sorted(z.infolist(),key=lambda x:x.filename)
        if len(rows)>30000 or sum(i.file_size for i in rows)>1_500_000_000: raise ValueError('archive bounds')
        names=[i.filename for i in rows]
        if len(names)!=len(set(names)): raise ValueError('duplicate archive names')
        for entry in rows:
            if entry.is_dir() or not entry.filename.lower().endswith('.asd'): continue
            members+=1
            meta=label(entry.filename)
            if meta is None:
                excluded['unparsed_asd']+=1;continue
            sub,poly,conc=meta
            if sub not in relevant_subs or poly not in p['polymers'] or conc not in p['concentrations']:
                excluded['outside_registered_population']+=1;continue
            if entry.file_size>1_000_000: raise ValueError('ASD record bound')
            w,y=decode_asd(z.read(entry))
            take=(w>=850)&(w<=2400);w=w[take];y=y[take]
            if len(w)<100 or w[0]>850 or w[-1]<2400: raise ValueError('incomplete registered wavelength support')
            if wave is None: wave=w
            elif not np.array_equal(w,wave): raise ValueError('different instrument grids require registered handling')
            sums[meta]=sums.get(meta,np.zeros_like(y))+y;counts[meta]+=1
    wanted={(s,pol,float(c)) for s in relevant_subs for pol in p['polymers'] for c in p['concentrations']}
    if set(sums)!=wanted: raise ValueError('missing registered groups: '+str(sorted(wanted-set(sums))))
    ordered=sorted(sums);x=np.array([sums[k]/counts[k] for k in ordered])
    if not np.isfinite(x).all():raise ValueError('nonfinite group mean')
    metadata=[{'id':f'{s}_{pol}_{c:g}','substrate':s,'polymer':pol,'concentration':c,'replicates':counts[(s,pol,c)]} for s,pol,c in ordered]
    return wave,x,metadata,{'asd_members':members,'excluded':dict(excluded),'included_replicates':sum(counts.values()),'group_count':len(ordered),'replicate_count_min':min(counts.values()),'replicate_count_max':max(counts.values()),'note':'Instrumental replicate means, not independent biological or industrial specimens.'}

def metrics(y,pred,classes):
    if len(y)!=len(pred) or len(y)==0:raise ValueError('prediction length')
    index={c:i for i,c in enumerate(classes)};cm=np.zeros((len(classes),len(classes)),dtype=int)
    for a,b in zip(y,pred):
        if a not in index or b not in index:raise ValueError('unknown class')
        cm[index[a],index[b]]+=1
    supports=cm.sum(axis=1)
    if (supports==0).any():raise ValueError('missing class in evaluation')
    return {'n':len(y),'correct':int(np.trace(cm)),'accuracy':float(np.trace(cm)/len(y)),'balanced_accuracy':float(np.mean(np.diag(cm)/supports)),'confusion':cm.tolist(),'classes':list(classes)}

def centroid_predict(train,y,test,classes):
    scale=np.std(train,axis=0);scale=np.where(scale>1e-12,scale,1.)
    means=np.array([train[y==c].mean(axis=0) for c in classes])
    d=((test[:,None,:]-means[None,:,:])/scale[None,None,:])**2
    return np.asarray(classes)[d.sum(axis=2).argmin(axis=1)]

def forward_select(x,y,groups,k,classes):
    selected=[];history=[];fits=0
    for _ in range(k):
        scores=[]
        for j in range(x.shape[1]):
            if j in selected:continue
            cols=selected+[j];correct=0;total=0
            for g in sorted(set(groups)):
                va=groups==g;tr=~va
                pred=centroid_predict(x[tr][:,cols],y[tr],x[va][:,cols],classes)
                correct+=int(np.sum(pred==y[va]));total+=int(va.sum());fits+=1
            scores.append((correct/total,-j,j))
        score,_,best=max(scores);selected.append(best);history.append({'added_index':best,'group_validation_accuracy':score})
    return sorted(selected),history,fits

def estimators(seed):
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    from sklearn.ensemble import ExtraTreesClassifier
    result=[]
    for c in (1,10,100): result.append((f'rbf_svc_C{c}',make_pipeline(StandardScaler(),SVC(C=c,gamma='scale'))))
    for leaf in (1,3):result.append((f'extratrees_leaf{leaf}',ExtraTreesClassifier(n_estimators=400,min_samples_leaf=leaf,random_state=seed,n_jobs=1,max_features=1.0)))
    return result

def choose_plan(x,y,groups,p):
    from sklearn.feature_selection import f_classif
    k=p['sparse_band_count'];n=x.shape[1];classes=p['polymers']
    selected,history,fit_count=forward_select(x,y,groups,k,classes)
    scores=f_classif(x,y)[0];scores=np.nan_to_num(scores,nan=-np.inf)
    plans={'all_bands':list(range(n)),'uniform6':np.rint(np.linspace(0,n-1,k)).astype(int).tolist(),
           'anova6':sorted(np.argsort(-scores,kind='stable')[:k].tolist()),'group_forward6':selected}
    rng=np.random.default_rng(p['seed'])
    for i in range(10):plans[f'random6_{i:02d}']=sorted(rng.choice(n,k,replace=False).tolist())
    return plans,history,fit_count

def run(protocol,output,archive=None):
    from sklearn import __version__ as sklearn_version
    import scipy
    out=Path(output).absolute()
    if any(q.is_symlink() for q in (out,*out.parents)):raise ValueError('regular output required')
    out.mkdir(parents=True,exist_ok=False)
    p=json.loads(Path(protocol).read_text());save(out/'PROTOCOL.json',p)
    start=time.perf_counter();cpu=time.process_time()
    with tempfile.TemporaryDirectory() as temp:
        if archive is None:
            archive=Path(temp)/'source.zip';source=fetch(p['raw_url'],archive,p['publisher_md5'])
        else:
            b=Path(archive).read_bytes()
            if hashlib.md5(b).hexdigest()!=p['publisher_md5']:raise ValueError('source checksum mismatch')
            source={'url':p['raw_url'],'bytes':len(b),'publisher_md5':hashlib.md5(b).hexdigest(),'sha256':hashlib.sha256(b).hexdigest()}
        wave,full,meta,data_info=load_means(archive,p)
    y=np.array([r['polymer'] for r in meta]);groups=np.array([r['substrate'] for r in meta])
    tr=np.isin(groups,p['train_substrates']);va=np.isin(groups,p['validation_substrates']);te=np.isin(groups,p['test_substrates'])
    if np.any(tr&va) or np.any(tr&te) or np.any(va&te) or not np.all(tr|va|te):raise ValueError('split overlap')
    bands=full@band_matrix(wave,p['bands_nm'],p['ideal_band_half_width_nm']).T
    plans,history,selection_fits=choose_plan(bands[tr],y[tr],groups[tr],p)
    matrices={key:bands[:,cols] for key,cols in plans.items()};matrices['full_spectrum']=full
    chosen={};tuning=[]
    for name,x in matrices.items():
        evaluated=[]
        for idx,(method,estimator) in enumerate(estimators(p['seed'])):
            estimator.fit(x[tr],y[tr]);pred=estimator.predict(x[va]);score=metrics(y[va],pred,p['polymers'])
            tuning.append({'plan':name,'method':method,'validation':score});evaluated.append((score['balanced_accuracy'],-idx,method,estimator))
        best=max(evaluated,key=lambda r:r[:2]);chosen[name]=(best[2],best[3],best[0])
    sparse_names=[n for n in matrices if n not in ('all_bands','full_spectrum')]
    selected_sparse=max(sparse_names,key=lambda n:(chosen[n][2],-sparse_names.index(n)))
    ref_names=['full_spectrum','all_bands'];selected_reference=max(ref_names,key=lambda n:(chosen[n][2],-ref_names.index(n)))
    frozen={'schema':'genesis/spectral-frozen-plan/v1','protocol_sha256':digest(p),'source':source,'selected_sparse':selected_sparse,'selected_reference':selected_reference,
            'plans':plans,'chosen_methods':{n:v[0] for n,v in chosen.items()},'tuning':tuning,'forward_search':history,
            'training_ids':[r['id'] for r,keep in zip(meta,tr) if keep],'validation_ids':[r['id'] for r,keep in zip(meta,va) if keep],
            'test_ids':[r['id'] for r,keep in zip(meta,te) if keep],'note':'Written before test scoring. No test result can select a plan or classifier.'}
    save(out/'FROZEN_PLAN.json',frozen);frozen_hash=hashlib.sha256((out/'FROZEN_PLAN.json').read_bytes()).hexdigest()
    results={};predrows=[]
    for name,x in matrices.items():
        pred=chosen[name][1].predict(x[te]);m=metrics(y[te],pred,p['polymers'])
        sub={g:metrics(y[te][groups[te]==g],pred[groups[te]==g],p['polymers']) for g in p['test_substrates']}
        m.update(method=chosen[name][0],inputs=int(x.shape[1]),by_substrate=sub);results[name]=m
        for row,a,b in zip([r for r,keep in zip(meta,te) if keep],y[te],pred):predrows.append({'plan':name,'id':row['id'],'truth':a,'prediction':b})
    limits=p['exploratory_acceptance'];s=results[selected_sparse];r=results[selected_reference]
    accepted=(s['balanced_accuracy']>=limits['sparse_test_balanced_accuracy_min'] and r['balanced_accuracy']-s['balanced_accuracy']<=limits['maximum_loss_vs_validation_chosen_full_reference'] and min(v['accuracy'] for v in s['by_substrate'].values())>=limits['worst_test_substrate_accuracy_min'])
    plan={'schema':'genesis/spectral-band-plan/v1','centers_nm':[p['bands_nm'][j] for j in plans[selected_sparse]],'ideal_band_half_width_nm':p['ideal_band_half_width_nm'],'method':chosen[selected_sparse][0],
          'measurement_model':'Uniform averages of raw instrument reflectance at recorded wavelengths. No detector response, noise or optical feasibility calibration.',
          'status':'COMPUTATIONAL_PREREQUISITE_ONLY' if accepted else 'REJECTED_BY_REGISTERED_COMPUTATIONAL_TEST','physical_qualified':False,'commercial_qualified':False}
    save(out/'BAND_PLAN.json',plan)
    with (out/'PREDICTIONS.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['plan','id','truth','prediction']);w.writeheader();w.writerows(predrows)
    report={'schema':'genesis/spectral-discovery-result/v1','source':source,'data':data_info,'groups':meta,'frozen_plan_sha256':frozen_hash,'results':results,'selected_sparse':selected_sparse,'selected_reference':selected_reference,
            'registered_test_pass':accepted,'band_plan':plan,'actual_measurements_acquired':0,'actual_customer_revenue':0,'hardware_savings_established':False,'ai_superiority_established':False,
            'search':{'forward_fit_count':selection_fits,'classifier_fit_count':len(tuning)},'resources':{'process_cpu_seconds':time.process_time()-cpu,'wall_seconds':time.perf_counter()-start,'billing':None},
            'runtime':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'sklearn':sklearn_version},
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'Previously recorded laboratory reflectance; held-out substrates within one published experiment. Not field validation, a new sensor, real demand, autonomous discovery or improved invention.'}
    save(out/'REPORT.json',report)
    rows=''.join(f'<tr><td>{html.escape(n)}</td><td>{v["inputs"]}</td><td>{v["correct"]}/{v["n"]}</td><td>{100*v["balanced_accuracy"]:.1f}%</td><td>{html.escape(v["method"])}</td></tr>' for n,v in results.items())
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GENESIS — Discovery experiment</title><style>body{{background:#17131f;color:#eee8df;font:17px/1.6 system-ui;max-width:1100px;margin:auto;padding:30px}}h1{{font-size:42px;line-height:1.15}}a{{color:#ebcc88}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:10px;border-bottom:1px solid #534653;text-align:left}}.scroll{{overflow:auto}}.card{{border:1px solid #75604a;border-radius:12px;padding:24px;margin:25px 0}}code{{overflow-wrap:anywhere}}</style><h1>ALPHA GENESIS<br>Design the observation.</h1><p>Can six task-selected spectral bands retain material identification on different substrates?</p><div class="card"><strong>{'Computational prerequisite passes — hardware remains unqualified' if accepted else 'Registered computational target not met — do not promote'}</strong><p>Selected sparse method: {selected_sparse}. Test: {s['correct']}/{s['n']} correct. Reference: {r['correct']}/{r['n']}. These methods were chosen on validation, not test results.</p><p>Proposed band centers (nm): {plan['centers_nm']}.</p></div><p>This experiment uses raw ASD measurements, not published full-spectrum-normalized features. Instrumental repetitions are averaged within a specimen group; they do not inflate the number of independent materials.</p><div class="scroll"><table><tr><th>Plan</th><th>Inputs</th><th>Correct</th><th>Balanced accuracy</th><th>Classifier</th></tr>{rows}</table></div><div class="card"><h2>What this does not establish</h2><p>A projection of recorded spectra is not a new optical instrument. Noise, detector sensitivity, filter availability, illumination, acquisition speed, field shift and complete cost must be tested separately. This is closed-set identification in 5%, 15% and 50% mixtures, not trace microplastic detection.</p></div><p><a href="REPORT.json">Complete results</a> · <a href="FROZEN_PLAN.json">Frozen selection</a> · <a href="BAND_PLAN.json">Band specification</a> · <a href="PREDICTIONS.csv">All test predictions</a> · <a href="PROTOCOL.json">Protocol</a></p><p>Data: Holt, Khan and Rodrigues, DOI 10.5281/zenodo.14419753, CC BY 4.0. New analyses and raw-band projections by the GENESIS project; no endorsement implied.</p></html>'''
    (out/'START_HERE.html').write_text(page,encoding='utf-8')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',default=str(Path(__file__).with_name('PROTOCOL.json')));p.add_argument('--out',required=True);p.add_argument('--archive')
    args=p.parse_args()
    try:
        r=run(args.protocol,args.out,args.archive)
        print(json.dumps({k:r[k] for k in ['selected_sparse','selected_reference','registered_test_pass']},sort_keys=True))
    except Exception as error:
        out=Path(args.out)
        if out.is_dir() and not (out/'FAILURE.json').exists():save(out/'FAILURE.json',{'type':type(error).__name__,'message':str(error),'status':'FAILED_NOT_QUALIFIED'})
        raise
if __name__=='__main__': main()
