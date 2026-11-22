"""Independent N3B metrics/target/artifact checker. No fitting, network or actuation.
Physics scope: source instrument-scaled PNG height; one test slide only.
"""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
HEIGHT_MAX=280.83

def targets():
    r,c=np.indices((8,8)); ridge=np.where((c==3)|(c==4),50.,0.)
    wall=np.where((((r==1)|(r==6))&(c>=1)&(c<=6))|(((c==1)|(c==6))&(r>=1)&(r<=6)),100.,0.)
    terrace=np.where((r>=2)&(r<=5)&(c>=1)&(c<=3),50.,0.)+np.where((r>=2)&(r<=5)&(c>=4)&(c<=6),100.,0.)
    result={}
    for key,a in zip(('continuous_ridge50','annular_wall100','two_level_terrace'),(ridge,wall,terrace)):
        b=np.zeros((16,16));b[4:12,4:12]=a
        result[key]=np.repeat(np.repeat(b,8,axis=0),8,axis=1)
    return result

def field(a):
    a=np.asarray(a,float)
    if a.shape!=(128,128) or not np.isfinite(a).all():raise ValueError('finite128x128 field required')
    return a

def metrics(actual,target):
    a=field(actual);t=field(target);e=a-t;active=e[32:96,32:96];positive=t>0;zero=t==0
    return {'fullfield_rmse_um':float(np.sqrt(np.mean(e**2))), 'active_rmse_um':float(np.sqrt(np.mean(active**2))), 'target_feature_mae_um':float(np.mean(np.abs(e[positive]))) if positive.any() else None, 'zero_target_positive_excess_mean_um':float(np.mean(np.maximum(a[zero],0))), 'zero_target_positive_excess_max_um':float(np.max(np.maximum(a[zero],0)))}

def select(names,predictions,target):
    if len(names)!=300 or len(set(names))!=300 or len(predictions)!=300:raise ValueError('all300 unique test names required')
    t=field(target)[32:96,32:96]
    scores=[float(np.mean((field(p)[32:96,32:96]-t)**2)) for p in predictions]
    i=min(range(300),key=lambda k:(scores[k],names[k]))
    return {'name':names[i],'index':i,'predicted_active_mse_um2':scores[i]}

def mask_digest(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def canonical(a):
    a=np.asarray(a)
    return min(mask_digest(np.rot90(x,k)) for x in (a,np.fliplr(a)) for k in range(4))
def audit_masks(train,dev,test):
    groups=[np.asarray(x) for x in (train,dev,test)]
    for a,n in zip(groups,(1030,114,300)):
        if a.shape!=(n,128,128) or a.dtype!=np.uint8:raise ValueError('source mask denominator/dtype/shape')
    known=np.concatenate(groups[:2]);exact=set(map(mask_digest,known));dihedral=set(map(canonical,known))
    a=groups[2]
    return {'test_exact_matches_calibration_indices':[i for i,x in enumerate(a) if mask_digest(x) in exact], 'test_dihedral_matches_calibration_indices':[i for i,x in enumerate(a) if canonical(x) in dihedral], 'test_fullwhite_active_indices':[i for i,x in enumerate(a) if np.all(x[32:96,32:96]==255)], 'test_unique_mask_count':len(set(map(mask_digest,a))), 'scope':'same source/testslide; duplicate masks are reported, never outcome-excluded'}

def verify_lineage(records,splitfile,split):
    entries=json.loads(Path(splitfile).read_text())['members'];want={e['name']:e for e in entries if e['split']==split}
    if len(records)!=len(want) or len({r['name'] for r in records})!=len(want) or set(r['name'] for r in records)!=set(want):raise ValueError('incomplete/duplicated source lineage')
    for r in records:
        e=want[r['name']]
        if r['crc32']!=e['crc32'] or r['size']!=e['size'] or len(r['sha256'])!=64:raise ValueError('source lineage mismatch')
    return {'member_count':len(records),'scope':'manifest identity; raw member CRC must be checked by source reader; partial ranges do not verify whole archive SHA'}

def new_mask(path,recipe):
    a=np.asarray(Image.open(path))
    if a.shape!=(8,8) or a.dtype!=np.uint8:raise ValueError('new mask must be8x8uint8 grayscale')
    if recipe.get('exposure_s')!=5 or recipe.get('native_pitch_um')!=80:raise ValueError('source exposure/pitch mismatch')
    if recipe.get('physical_acceptance') is not False:raise ValueError('unprinted mask cannot claim physical acceptance')
    return {'mask_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'gray_min':int(a.min()),'gray_max':int(a.max()),'physical_status':'MODEL ONLY; not manufactured','native_shape':[8,8]}

def source_roundtrip(a):
    # Author base_dataset ToTensor/Normalize(.5,.5), util.tensor2im float32.
    # Exact precommitted image transformation, NOT per-pixel +/-1 tolerance.
    x=np.asarray(a,dtype=np.float32)/np.float32(255)
    normalized=(x-np.float32(.5))/np.float32(.5)
    return ((normalized+np.float32(1))/np.float32(2)*np.float32(255)).astype(np.uint8)

def baseline_binding(baseline_masks,source_masks,predictions):
    b=np.asarray(baseline_masks);s=np.asarray(source_masks);p=np.asarray(predictions)
    if b.shape!=(300,128,128) or s.shape!=b.shape or p.shape!=b.shape:raise ValueError('all300 aligned baseline shapes required')
    raw=np.all(b==s,axis=(1,2));mapped=np.all(b==source_roundtrip(s),axis=(1,2))
    mismatch=np.flatnonzero(~(raw|mapped)).tolist()
    if mismatch:raise ValueError('published baseline input mismatch at '+str(mismatch))
    if not np.isfinite(p).all():raise ValueError('nonfinite baseline')
    return {'aligned':300,'raw_exact':int(raw.sum()),'roundtrip_only':int((mapped&~raw).sum()),'source_binding':'same basename source index; author_real mask equals raw or exact float32 source roundtrip of paired LEFT; actual height is paired RIGHT; repeated fiducials preserved'}


def independent_forward(model, native):
    """Separate direct polynomial evaluator; shares scipy Gaussian convention,
    not independent physical truth. Return64² source-unit field."""
    from scipy.ndimage import gaussian_filter
    a=np.asarray(native,float)
    if a.shape!=(8,8) or not np.isfinite(a).all() or (a<0).any() or (a>1).any():raise ValueError('native finite8x8 fraction')
    padded=np.pad(a,4);m=np.kron(padded,np.ones((4,4)))
    fields=[m]+[gaussian_filter(m,x,mode='constant',cval=0) for x in (.5,1.,2.,4.)]
    if model['kind'] in ('point','blur'):fields=[fields[model['scale']]]
    cols=[np.ones_like(m)]+fields+[x**2 for x in fields]+[x**3 for x in fields]
    if model['kind']=='spatial':cols += [fields[0]*x for x in fields[1:]]
    coeff=np.asarray(model['coef'],float)
    if len(coeff)!=len(cols) or not np.isfinite(coeff).all():raise ValueError('coefficient mismatch')
    return np.clip(sum(c*x for c,x in zip(coeff,cols)),0,HEIGHT_MAX)

def mask_novelty(native, archive_masks):
    a=np.asarray(native)
    if a.shape!=(8,8) or a.dtype!=np.uint8:raise ValueError('native8bit mask required')
    full=np.kron(np.pad(a,4),np.ones((8,8),dtype=np.uint8))
    return {'exact_existing_mask_indices':[i for i,m in enumerate(archive_masks) if np.array_equal(full,m)], 'claim':'genuinely new only if no exact archived match; otherwise existing recipe'}

def selftest():
    ts=targets();assert [int(np.count_nonzero(a)) for a in ts.values()]==[1024,1280,1536]
    for t in ts.values():assert metrics(t,t)['active_rmse_um']==0
    bad=np.zeros((128,128));bad[0,0]=np.nan
    try:metrics(bad,next(iter(ts.values())))
    except ValueError:pass
    else:raise AssertionError('NaN accepted')
    names=[f'{i:04d}' for i in reversed(range(300))];ps=np.zeros((300,128,128));assert select(names,ps,np.zeros((128,128)))['name']=='0000'
    try:select(names[:-1],ps[:-1],np.zeros((128,128)))
    except ValueError:pass
    else:raise AssertionError('partial denominator accepted')
    return {'tests':'target counts/identity,NaN rejection,lexicographic tie,incomplete denominator rejection','status':'pass','scope':'analytic software controls only; noN3Bsource outcomes'}
if __name__=='__main__':print(json.dumps(selftest(),indent=2))
