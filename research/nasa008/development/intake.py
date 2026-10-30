from pathlib import Path
import json,struct,zipfile,time,hashlib,resource
import numpy as np
from PIL import Image
root=Path(__file__).resolve().parent
start=time.process_time()
record={}
with Image.open(root/'TTT_AM_315400_low_res.tif') as im:
 record['ct']={'dimensions':list(im.size),'frames':im.n_frames,'mode':im.mode,'tags':{str(k):str(v)for k,v in im.tag_v2.items()}}
 arr=np.empty((im.n_frames,im.height,im.width),dtype=np.uint8)
 for i in range(im.n_frames):
  im.seek(i);arr[i]=np.asarray(im)
 np.save(root/'ct.npy',arr,allow_pickle=False)
 record['ct']['shape']=list(arr.shape)
 record['ct']['histogram']=np.bincount(arr.ravel(),minlength=256).tolist()
 Image.fromarray(arr.max(0)).save(root/'ct_max_axis0.png')
 Image.fromarray(arr.max(1)).save(root/'ct_max_axis1.png')
 Image.fromarray(arr.max(2)).save(root/'ct_max_axis2.png')
with zipfile.ZipFile(root/'TTT_AM_315400_profilometry.zip') as z:
 name='disk_profilometry_top_height_image.tif'
 b=z.read(name);order='<' if b[:2]==b'II'else'>';magic,offset=struct.unpack_from(order+'HI',b,2);assert magic==42
 n=struct.unpack_from(order+'H',b,offset)[0];tags={}
 for i in range(n):
  tag,kind,count,value=struct.unpack_from(order+'HHII',b,offset+2+12*i)
  size={1:1,2:1,3:2,4:4,5:8}.get(kind)
  if tag in (256,257,258,259,273,277,278,279,339):
   assert kind in (3,4)and count<100
   vstart=offset+2+12*i+8 if size*count<=4 else value
   tags[tag]=struct.unpack_from(order+str(count)+('H'if kind==3 else'I'),b,vstart)
 assert tags[258]==(64,)and tags[339]==(3,)and tags[259]==(1,)and tags[277]==(1,)
 height,width=tags[257][0],tags[256][0]
 assert tags[279][0]==width*height*8
 profile=np.frombuffer(b,dtype=order+'f8',count=height*width,offset=tags[273][0]).reshape(height,width).copy()
 np.save(root/'profile.npy',profile,allow_pickle=False)
 finite=profile[np.isfinite(profile)]
 record['profile']={'byte_order':order,'shape':list(profile.shape),'tags':{str(k):v for k,v in tags.items()},'finite_count':int(len(finite)),'quantiles':np.quantile(finite,[0,.001,.01,.1,.5,.9,.99,.999,1]).tolist(),'documentation_mismatch':'Source description says single precision but actual TIFF is float64.'}
 with z.open('disk_profilometry_top_optical_image.tif')as f:
  im=Image.open(f);im.thumbnail((1100,1100));im.save(root/'profile_texture.png')
record['cpu_seconds']=time.process_time()-start;record['peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
(root/'INTAKE.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
