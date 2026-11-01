"""Offline cache replay only: no network, credentials, model/API calls or new measurements."""
import csv,json,datetime,zoneinfo,subprocess,sys,hashlib
from pathlib import Path
P=Path(__file__).parent
subprocess.run([sys.executable,str(P/'v2/run_production.py')],cwd=P,check=True,stdout=subprocess.DEVNULL)
subprocess.run([sys.executable,str(P/'v2/normalize_timestamps.py')],cwd=P,check=True,stdout=subprocess.DEVNULL)
man=json.loads((P/'v3_canopy/manifest.json').read_text());n={x['filename']:x for x in json.loads((P/'v3_canopy/native_predictions.json').read_text())};gcc=json.loads((P/'v3_canopy/cached_gcc.json').read_text());out=[]
for x in man:
 if 'error'in x:continue
 raw=x['timestamp'];u=datetime.datetime.strptime(raw,'%Y-%m-%dT%H-%M-%SZ').replace(tzinfo=datetime.timezone.utc);s=n[x['filename']];g=gcc[x['filename']]
 out.append({'timestamp_utc':u.isoformat().replace('+00:00','Z'),'timestamp_local':u.astimezone(zoneinfo.ZoneInfo('US/Central')).isoformat(),'state':s['state'],'green_chromatic_coordinate':g['gcc'],'gcc_baseline_state':g['baseline_state'],'evidence':s['evidence'],'split':'exposed_probe_day' if raw[:10] in ['2024-03-15','2024-04-15','2024-05-15'] else 'heldout_candidate','url':x['url'],'sha256':x['sha256'],'filename':x['filename']})
with (P/'v3_canopy/measurements.csv').open('w') as fp:w=csv.DictWriter(fp,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
expected=json.loads((P/'expected_output_hashes.json').read_text())
for rel,h in expected.items():
 actual=hashlib.sha256((P/rel).read_bytes()).hexdigest();assert actual==h,(rel,actual,h)
print('PASS: offline cache replay exactly reproduced all three primary CSV outputs. No new image or model inference was performed.')
# Reproduce selected GCC view while retaining native uncertainty/disagreement flags.
selected=[{'timestamp_utc':x['timestamp_utc'],'timestamp_local':x['timestamp_local'],'state':x['gcc_baseline_state'],'method':'ordinary_green_chromatic_coordinate','green_chromatic_coordinate':x['green_chromatic_coordinate'],'native_state':x['state'],'quality_flag':'native_uncertain' if x['state']=='unknown' else ('method_disagreement' if x['state']!=x['gcc_baseline_state'] else 'methods_agree'),'url':x['url'],'sha256':x['sha256'],'filename':x['filename']} for x in out]
with (P/'v3_canopy/selected_measurements.csv').open('w') as fp:w=csv.DictWriter(fp,fieldnames=list(selected[0]));w.writeheader();w.writerows(selected)
expected_selected=json.loads((P/'expected_selected_hash.json').read_text())
assert hashlib.sha256((P/'v3_canopy/selected_measurements.csv').read_bytes()).hexdigest()==expected_selected['sha256']
print('PASS: selected GCC canopy view also reproduced exactly, with native uncertainty flags preserved.')
