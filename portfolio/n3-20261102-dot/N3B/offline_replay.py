"""Additive portable replay adapter: no network, fitting or new optimization."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
import numpy as np

def main(source,out):
 source=Path(source).resolve();out=Path(out).resolve()
 if source==out or source in out.parents:raise ValueError('output must be outside source tree')
 out.mkdir(parents=True,exist_ok=True);work=out/'evidence'
 shutil.copytree(source,work,dirs_exist_ok=True,ignore=shutil.ignore_patterns('frozen_predictions.npz','__pycache__'))
 # Assemble only hash-bound compact local evidence; no network or source mutations.
 chunk_manifest=work/'EVIDENCE_CHUNKS.json'
 if chunk_manifest.exists():
  import io,zipfile
  manifest=json.loads(chunk_manifest.read_text());parts=[]
  for entry in manifest['chunks']:
   part=(work/entry['path']).read_bytes()
   if len(part)!=entry['bytes'] or hashlib.sha256(part).hexdigest()!=entry['sha256']:raise ValueError('evidence chunk mismatch')
   parts.append(part)
  payload=b''.join(parts)
  if len(payload)!=manifest['payload_bytes'] or hashlib.sha256(payload).hexdigest()!=manifest['payload_sha256']:raise ValueError('evidence payload mismatch')
  with zipfile.ZipFile(io.BytesIO(payload)) as archive:
   expected={e['path']:e for e in manifest['members']}
   if len(archive.namelist())!=len(expected) or set(archive.namelist())!=set(expected):raise ValueError('evidence member set mismatch')
   for name,entry in expected.items():
    target=(work/name).resolve()
    if work.resolve() not in target.parents:raise ValueError('unsafe evidence member path')
    data=archive.read(name)
    if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('evidence member hash mismatch')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  derivation=json.loads((work/'DATA_DERIVATION.json').read_text())
  for tag,entry in derivation.items():
   file=work/(tag+'.npz')
   if hashlib.sha256(file.read_bytes()).hexdigest()!=entry['derived_mask_only_npz_sha256']:raise ValueError('derived mask file mismatch')
   array=np.load(file)['mask']
   if list(array.shape)!=entry['shape'] or str(array.dtype)!=entry['dtype'] or hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()!=entry['mask_array_sha256']:raise ValueError('derived mask array mismatch')
 # Evidence may be distributed as deterministic gzip to keep the public package compact.
 import gzip
 for p in work.rglob('*.json.gz'):
  target=p.with_suffix('')
  if not target.exists():target.write_bytes(gzip.decompress(p.read_bytes()))
 decision=json.loads((work/'artifact/decisions_before_truth.json').read_text());fitted=json.loads((work/'fitted_models.json').read_text());receipt=decision['public_final_freeze']
 sys.path.insert(0,str(work));from model import predict;from produce import upsample128
 masks=np.load(work/'test.npz')['mask'];inputs=masks.astype(float).reshape(300,64,2,64,2).mean((2,4))/255
 raw=np.load(work/'baseline_raw_arrays.npz');predictions={}
 for label,expected in decision['predictions_sha256'].items():
  if label.startswith('author_'):
   a=(raw[label.removeprefix('author_')+'_fake'].astype(float)*280.83/255).astype(np.float32)
  else:
   continuous=np.stack([upsample128(predict(fitted['models'][label],a)) for a in inputs])
   a=np.clip(continuous/280.83*255,0,255).astype(np.uint8).astype(np.float32)*np.float32(280.83/255)
  actual=hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
  if actual!=expected:raise ValueError(f'frozen prediction hash mismatch for {label}')
  predictions[label]=a
 np.savez_compressed(work/'artifact/frozen_predictions.npz',**predictions)
 candidates=list(work.rglob('replay_n3b.py'))
 if len(candidates)!=1:raise ValueError('exactly one frozen independent replay required')
 replay=candidates[0]
 split=replay.parent/'N3B_SPLIT.json'
 if not split.exists():
  candidates=list(work.rglob('SPLIT.json'))
  if len(candidates)!=1:raise ValueError('independent split absent or ambiguous')
  shutil.copyfile(candidates[0],split)
 subprocess.run([sys.executable,str(replay),'--base',str(work),'--receipt',receipt],check=True)
 shutil.copyfile(replay.parent/'N3B_REPLAY.json',out/'N3B_REPLAY.json')
 (out/'OFFLINE_RECEIPT.json').write_text(json.dumps({'public_freeze':receipt,'mode':'offline reconstruction and unchanged independent verification','network_calls':0,'retraining':False,'new_optimization':False,'models_reconstructed':list(predictions),'test_cases':300},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',default=str(Path(__file__).parent));p.add_argument('--out',required=True);a=p.parse_args();main(a.base,a.out)
