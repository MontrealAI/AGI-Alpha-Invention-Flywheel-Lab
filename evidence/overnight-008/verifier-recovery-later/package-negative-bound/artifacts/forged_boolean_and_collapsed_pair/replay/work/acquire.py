"""Bounded acquisition of the public CC-BY-4.0 walnut data. No code is fetched."""
import hashlib, json, pathlib, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
FILES = {
    'Data82.mat': (8083003, '03a35c57ae52026f980ffcf540a4243a02f198b3fcdd8dff72cb251f70b067cc'),
    'GroundTruthReconstruction.mat': (9671701, '88cc17c0b9706a9cf88f615e490d0254e59e89ee88740d293d06c16a1d6005bd'),
}
records=[]
for name,(size,digest) in FILES.items():
    destination=DATA/name
    url=f'https://zenodo.org/records/1254206/files/{name}?download=1'
    for attempt in range(1,3):
        if destination.exists() and destination.stat().st_size == size and hashlib.sha256(destination.read_bytes()).hexdigest()==digest:
            records.append({'file':name,'status':'ALREADY_VERIFIED','bytes':size,'sha256':digest});break
        partial=DATA/f'{name}.attempt{attempt}.partial'
        t=time.monotonic()
        rec={'file':name,'url':url,'attempt':attempt}
        try:
            with urllib.request.urlopen(url,timeout=60) as response, partial.open('xb') as target:
                count=0
                while True:
                    block=response.read(min(1<<18,size+1-count))
                    if not block:break
                    count+=len(block)
                    if count>size:raise ValueError('size ceiling exceeded')
                    target.write(block)
            actual=hashlib.sha256(partial.read_bytes()).hexdigest()
            rec.update(bytes=partial.stat().st_size,sha256=actual)
            if partial.stat().st_size!=size or actual!=digest:raise ValueError('size/hash mismatch')
            partial.rename(destination)
            rec['status']='VERIFIED'
            records.append(rec)
            (ROOT/'ACQUISITION.json').write_text(json.dumps(records,indent=2)+'\n')
            break
        except Exception as error:
            rec.update(status='FAILED_PRESERVED',error=repr(error),wall_seconds=time.monotonic()-t)
            records.append(rec)
            (ROOT/'ACQUISITION.json').write_text(json.dumps(records,indent=2)+'\n')
            if attempt==2:raise
    else:raise RuntimeError(name)
(ROOT/'ACQUISITION.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records))
