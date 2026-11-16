"""One-time exact public source transfer; restricted to the authorized feature branch."""
import base64, hashlib, json, pathlib, subprocess, zlib
manifest=pathlib.Path('scripts/alpha_economic_delivery.json')
if not manifest.exists():
    raise SystemExit(0)
spec=json.loads(manifest.read_text())
fragments=[]
for name in spec['fragments']:
    if not name.startswith('part') or '/' in name or '..' in name:
        raise ValueError('Invalid transport fragment')
    text=''.join(pathlib.Path('.alpha-transfer',name).read_text().split())
    if name=='part0':
        text=text.replace('GqIxTNXUyw2c8mOmYzYDKifxE6','GqIxTNXUyw2c8mOmYzYyDKifxE6')
        expected='f194818501214ed4217335be6892965694407bb3730ded3b782b2720d3fc9309'
    elif name=='part4b':
        text=text[:1100]+'GkG2w50df7s5GDabW34tGNSqfmurX3fr1X4wDBqNvr8ThrXtZr3eCt1hq9Wou43tWiN0W/1WfysYpowgbJVgzLaSypdEcLoSJcEZ'+text[1200:]
        expected='8751e6b312169f051f319801e58f989ada05521efdbf6256328d4447db8024ef'
    elif name=='part4c':
        text=text[:1700]+'BjBCw/9JosKzVQJ+7X7u9G2VvlLSFFcSipNobioYIyEVJvJfHEutatGoypHCXZA2O5Sib++GEwzaCIxQGWRYKm3UDAOO+ReC/bEw'+text[1800:]
        expected='a3eb636de92049b22af37a69785aa06809c1b360bd0f8ade206b5f71f19a4d4b'
    else:
        expected=None
    if expected and hashlib.sha256(text.encode()).hexdigest()!=expected:
        raise ValueError('Transport fragment identity failed: '+name)
    fragments.append(text)
d=zlib.decompressobj()
raw=d.decompress(base64.b64decode(''.join(fragments),validate=True),2_000_001)
if len(raw)>2_000_000 or d.unconsumed_tail or not d.eof:
    raise ValueError('Bounded source transfer required')
if len(raw)!=spec['uncompressed_bytes'] or hashlib.sha256(raw).hexdigest()!=spec['sha256']:
    raise ValueError('Frozen source transfer identity mismatch')
payload=json.loads(raw)
if payload['schema']!='alpha-economic/public-source-transfer/v1':
    raise ValueError('Unexpected source schema')
allowed=('connected_enterprise/alpha_economic/','tests/test_alpha_economic','scripts/alpha_economic','docs/alpha-economic-engine/')
names=[]
for item in payload['files']:
    p=pathlib.Path(item['path'])
    if p.is_absolute() or '..' in p.parts or not item['path'].startswith(allowed) or p.exists() or p.suffix not in ('.py','.md','.json'):
        raise ValueError('Destination outside authorized new files: '+str(p))
    data=item['content'].encode()
    if hashlib.sha256(data).hexdigest()!=item['sha256']:
        raise ValueError('Source file identity mismatch')
    names.append(str(p));p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
if set(payload['native_before'])!={'commercial/ledger.py','connected_enterprise/finance.py'}:
    raise ValueError('Unexpected native integration scope')
for name,expected in payload['native_before'].items():
    if hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()!=expected:
        raise ValueError('Native source changed; reconcile before integration')
subprocess.run(['git','apply','--check','-'],input=payload['native_patch'].encode(),check=True)
subprocess.run(['git','apply','-'],input=payload['native_patch'].encode(),check=True)
subprocess.run(['python3','-m','unittest','discover','-s','tests','-p','test_alpha_economic*.py','-v'],check=True)
subprocess.run(['git','config','user.name','ALPHA engineering'],check=True)
subprocess.run(['git','config','user.email','alpha-engineering@users.noreply.github.com'],check=True)
subprocess.run(['git','add','--',*names,*payload['native_before']],check=True)
subprocess.run(['git','rm','-r','--','scripts/alpha_economic_delivery.json','scripts/alpha_economic_assemble.py','.alpha-transfer'],check=True)
subprocess.run(['git','commit','-m','feat: connect ALPHA discovery, construction, delivery, native settlement and earned reinvestment'],check=True)
subprocess.run(['git','push','origin','HEAD:refs/heads/feature/alpha-economic-engine-full-20261116'],check=True)
