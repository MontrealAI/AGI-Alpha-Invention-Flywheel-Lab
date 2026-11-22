"""Construct actual quantized masks and fixed-target source-recipe decisions."""
import json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
from model import inverse,predict,mask_from_native
BASE=Path(__file__).parent

def targets(res=128):
 a=np.zeros((8,8));a[:,3:5]=50
 b=np.zeros((8,8));b[1,1:7]=100;b[6,1:7]=100;b[1:7,1]=100;b[1:7,6]=100
 c=np.zeros((8,8));c[2:6,1:4]=50;c[2:6,4:7]=100
 out={}
 for name,n in [('continuous_ridge50',a),('annular_wall100',b),('two_level_terrace',c)]:
  field=np.zeros((16,16));field[4:12,4:12]=n
  out[name]=np.repeat(np.repeat(field,res//16,0),res//16,1)
 return out

def upsample128(a):
 return np.asarray(Image.fromarray(np.asarray(a,np.float32)).resize((128,128),Image.Resampling.BILINEAR),float)

def make_new_masks():
 fitted=json.loads((BASE/'fitted_models.json').read_text());out=BASE/'artifact';out.mkdir(exist_ok=True);records=[]
 for label in ['spatial0','point0',fitted['best_blur']]:
  model=fitted['models'][label]
  for target_id,target in targets(64).items():
   mask,pred,diag=inverse(model,target,maxiter=100);name=label+'_'+target_id
   Image.fromarray(mask).save(out/f'{name}_native8.png')
   padded=np.zeros((16,16),dtype=np.uint8);padded[4:12,4:12]=mask;Image.fromarray(padded).save(out/f'{name}_padded16.png')
   cells=''.join(f'<rect x="{(c+4)*80}" y="{(r+4)*80}" width="80" height="80" fill="rgb({int(mask[r,c])},{int(mask[r,c])},{int(mask[r,c])})"/>' for r in range(8) for c in range(8))
   (out/f'{name}.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1.28mm" height="1.28mm" viewBox="0 0 1280 1280"><metadata>MODEL ONLY, unprinted, source-specific5s recipe; not manufacturing release.</metadata><rect width="1280" height="1280" fill="black"/>'+cells+'</svg>')
   np.save(out/f'{name}_predicted_height64.npy',pred)
   record={'id':name,'target_id':target_id,'model':label,'native_pitch_um':80,'exposure_s':5,'input_levels':'8bit grayscale; sourceengine/resinonly','field_native_pixels':[16,16],'active_native_pixels':[8,8],'black_border_native_pixels':4,'mask_raw64bytes_sha256':hashlib.sha256(mask.tobytes()).hexdigest(),'mask_png_sha256':hashlib.sha256((out/f'{name}_native8.png').read_bytes()).hexdigest(),'new_mask_physical_truth':None,**diag}
   records.append(record);print(name,diag,flush=True)
 (out/'generated_recipes.json').write_text(json.dumps(records,indent=2))
 return records

def select_archived(predictions,names):
 #This function has no physicalheight input. Freeze output before evaluating truth.
 if len(names)!=300 or len(set(names))!=300 or predictions.shape!=(300,128,128) or not np.all(np.isfinite(predictions)):raise ValueError('requires300unique masks and finite128² predictions')
 out={}
 for tid,target in targets(128).items():
  errors=np.mean((predictions[:,32:96,32:96]-target[None,32:96,32:96])**2,axis=(1,2))
  i=min(range(len(names)),key=lambda i:(float(errors[i]),names[i]))
  out[tid]={'selected_member':names[i],'selected_index':i,'predicted_active_rmse_um':float(np.sqrt(errors[i]))}
 return out
if __name__=='__main__':make_new_masks()
