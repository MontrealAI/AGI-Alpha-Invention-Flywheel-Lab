import json,hashlib,urllib.request
from pathlib import Path

root=Path(__file__).resolve().parent
rows=json.loads((root/'retrieval.json').read_text())
base='https://raw.githubusercontent.com/NineAbyss/OR-License/2bda4b8d6ddd4bd1cb62b89acee0c7c2f1914d47/tasks/'
for row in rows:
    target=root/'inputs'/row['task']/Path(row['path']).name
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256']:continue
    with urllib.request.urlopen(base+row['task']+'/'+row['path'],timeout=30) as response:data=response.read(1048577)
    if len(data)>1048576 or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('PINNED_SOURCE_BYTES_DIFFER')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
print(json.dumps({'pinned_public_files_ready':len(rows),'hidden_grader_or_expert_reference_access':False}))
