"""Independent replay, execute only after coordinator final-public-freeze receipt."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
from check_n3b import *

def main(base,receipt):
    b=Path(base);a=b/'artifact';r=json.loads((a/'results.json').read_text());dec=json.loads((a/'decisions_before_truth.json').read_text())
    assert receipt==r['public_freeze']==dec['public_final_freeze']
    assert r['test_count']==300 and r['independent_test_slides']==1
    assert r['newmask_physical_acceptance'] is False and r['commercial_acceptance'] is False
    lineage=json.loads((b/'test_lineage.json').read_text());verify_lineage(lineage,Path(__file__).parent/'N3B_SPLIT.json','test')
    names=[x['name'] for x in lineage];d=np.load(b/'test.npz');truth=d['height'].astype(float)*HEIGHT_MAX/255
    train=np.load(b/'train.npz')['mask'];dev=np.load(b/'val_train.npz')['mask'];test=d['mask'];audit=audit_masks(train,dev,test)
    ps=np.load(a/'frozen_predictions.npz');fitted=json.loads((b/'fitted_models.json').read_text());checks=0;largest=0.
    assert dec['fitted_model_file_sha256']==hashlib.sha256((b/'fitted_models.json').read_bytes()).hexdigest()
    for label in ps.files:
        p=ps[label];assert mask_digest(p)==dec['predictions_sha256'][label]
        for i in range(300):
            z=metrics(truth[i],p[i]);reported=r['models'][label]['per_patch'][i]
            for key in ('active_rmse_um','fullfield_rmse_um'):
                err=abs(z[key]-reported[key]);largest=max(largest,err);assert err<1e-8
            checks+=1
        for tid,t in targets().items():
            chosen=select(names,p,t);old=dec['choices'][label][tid];assert chosen['name']==old['selected_member'];assert chosen['index']==old['selected_index']
            actual=truth[chosen['index']];m=metrics(actual,t);reported=r['models'][label]['inverse_exact_archived_recipe'][tid]
            for key in ('active_rmse_um','fullfield_rmse_um','target_feature_mae_um'):
                err=abs(m[key]-reported[key]);largest=max(largest,err);assert err<1e-8
            assert abs(m['zero_target_positive_excess_mean_um']-reported['zero_target_excess_mean_um'])<1e-8
            checks+=1
    raw_baselines=np.load(b/'baseline_raw_arrays.npz');bindings={}
    for label in ('pix2pix','L1','MSE'):
        br=raw_baselines[label+'_real'];bf=raw_baselines[label+'_fake']
        try:
            binding=baseline_binding(br,test,bf)
        except ValueError as error:
            assert 'author_'+label not in ps.files
            bindings[label]={'status':'UNQUALIFIED','reason':str(error)}
        else:
            assert 'author_'+label in ps.files
            expected=(bf.astype(float)*HEIGHT_MAX/255).astype(np.float32)
            assert np.array_equal(expected,ps['author_'+label])
            bindings[label]=binding
    generated=[];allmasks=np.concatenate((train,dev,test))
    for recipe in json.loads((a/'generated_recipes.json').read_text()):
        name=recipe['id'];path=a/(name+'_native8.png');rec=new_mask(path,recipe);native=np.asarray(Image.open(path));expected=independent_forward(fitted['models'][recipe['model']],native.astype(float)/255);saved=np.load(a/(name+'_predicted_height64.npy'))
        gap=float(np.max(abs(expected-saved)));assert gap<1e-8
        pad=np.asarray(Image.open(a/(name+'_padded16.png')));assert np.array_equal(pad,np.pad(native,4))
        rec.update({'id':name,'numerical_max_abs_gap_um':gap,**mask_novelty(native,allmasks)});generated.append(rec)
    out={'receipt':receipt,'replayed_metric_and_choice_cases':checks,'max_reported_metric_difference_um':largest,'source_masks':audit,'generated_artifacts':generated,'status':'software/retrospective metrics verified; newmask physical acceptance NOT established','baseline_raw_binding':bindings,'independent_test_slides':1}
    print(json.dumps(out,indent=2));(Path(__file__).parent/'N3B_REPLAY.json').write_text(json.dumps(out,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--receipt',required=True);x=p.parse_args();main(x.base,x.receipt)
