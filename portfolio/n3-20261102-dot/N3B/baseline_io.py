"""Source-bound author200epoch outputs. Never used during training/model selection."""
import io,json,hashlib,re
import numpy as np
from PIL import Image
from data_io import BASE,fetch_range,extract_members
URL='https://data.nist.gov/od/ds/mds2-2950/modified_pix2pix.zip';SIZE=993046483

def gray(raw):
 a=np.asarray(Image.open(io.BytesIO(raw)))
 if a.ndim==3:
  if not np.all(a[:,:,:3]==a[:,:,:1]):raise ValueError('RGBchannels differ')
  a=a[:,:,0]
 if a.shape!=(128,128):raise ValueError('baseline128² required')
 return a

def normalization_roundtrip(a):
 #Source ToTensor/Normalize(.5,.5), then tensor2im float32 arithmetic anduint8cast.
 x=a.astype(np.float32)/np.float32(255);x=(x-np.float32(.5))/np.float32(.5)
 return (((x+np.float32(1))/np.float32(2))*np.float32(255)).astype(np.uint8)

def load_baselines(test_masks,receipt):
 if not receipt:raise ValueError('requires finalpublicfreeze receipt')
 entries=json.loads((BASE/'baseline_entries.json').read_text());result={};lineage=[];binding={};raw_arrays={}
 for label in ['pix2pix','L1','MSE']:
  a=[e for e in entries if '/'+label+'netD1L_refs200epoch/test_200/images/' in e['name']]
  if len(a)!=600:raise ValueError('baseline requires600members')
  start=min(e['offset'] for e in a);end=max(e['offset']+30+len(e['name'].encode())+e['compressed'] for e in a)-1
  block=fetch_range(URL,SIZE,start,end);decoded=extract_members(block,start,a);fake={};real={}
  for e,b in decoded:
   i=int(e['name'].split('/')[-1].split('_')[0]);which=fake if '_fake.png' in e['name'] else real
   if i in which:raise ValueError('duplicate authoroutput')
   which[i]=gray(b);lineage.append({'name':e['name'],'sha256':hashlib.sha256(b).hexdigest(),'crc32':e['crc32'],'receipt':receipt})
  if set(real)!=set(range(300)) or set(fake)!=set(range(300)):raise ValueError('baselineindex mismatch')
  stats={'exact_raw':0,'exact_source_roundtrip':0,'mismatches':[]}
  for i in range(300):
   if np.array_equal(real[i],test_masks[i]):stats['exact_raw']+=1
   elif np.array_equal(real[i],normalization_roundtrip(test_masks[i])):stats['exact_source_roundtrip']+=1
   else:stats['mismatches'].append(i)
  binding[label]=stats
  raw_arrays[label+'_real']=np.stack([real[i] for i in range(300)])
  raw_arrays[label+'_fake']=np.stack([fake[i] for i in range(300)])
  if not stats['mismatches']:result[label]=np.stack([fake[i] for i in range(300)]).astype(float)*280.83/255
 np.savez_compressed(BASE/'baseline_raw_arrays.npz',**raw_arrays)
 (BASE/'baseline_lineage.json').write_text(json.dumps(lineage,indent=2));(BASE/'baseline_binding.json').write_text(json.dumps(binding,indent=2))
 return result,binding
