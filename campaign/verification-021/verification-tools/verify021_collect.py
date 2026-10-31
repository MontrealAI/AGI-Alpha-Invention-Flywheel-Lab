import datetime,hashlib,json,pathlib,shutil,subprocess,sys,tempfile,zipfile
BASE=pathlib.Path('/workspace/scratch/8ae627a67fcf');REPO=BASE/'p0-native'
PUBLIC=REPO/'campaign/verification-021';CONTROL=BASE/'verification021-control'
SNAPSHOT=REPO/'campaign/verification-021-work/source'
sys.path.insert(0,str(REPO))
from connected_enterprise.runner import identity
from connected_enterprise.finance import source_identity

def copy(source,target):
 target=PUBLIC/target;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)

def main():
 before=json.loads((PUBLIC/'SOURCE_VERIFICATION.json').read_text())
 assert identity(REPO)==before['source_identity']==identity(SNAPSHOT)
 assert source_identity(REPO)==before['financial_source']==source_identity(SNAPSHOT)
 for name,value in before['original_failed_evidence_sha256'].items():
  assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==value
 for name,value in before['prepared_test_sha256'].items():
  assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==value
  assert hashlib.sha256((SNAPSHOT/name).read_bytes()).hexdigest()==value
 before['post_verification_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 before['all_selected_source_bytes_unchanged']=True
 before['all_prepared_test_bytes_unchanged']=True
 before['original_failure_and_prior_ledger_bytes_unchanged']=True
 (PUBLIC/'SOURCE_VERIFICATION.json').write_text(json.dumps(before,indent=2)+'\n')
 for p in (SNAPSHOT/'campaign/native-capital-020/qualification').glob('verification021-legacy.*'):
  copy(p,pathlib.Path('qualification')/p.name)
 for name in ['maturity_successor_receipt.json','maturity_successor_public_record.json',
              'ordinary_portable_upgrade_receipt.json','ordinary_portable_upgrade_public_record.json']:
  copy(SNAPSHOT/'campaign/native-capital-020/independent'/name,pathlib.Path('proofs')/name)
 for p in CONTROL.glob('*.receipt.json'):copy(p,pathlib.Path('jobs')/p.name)
 for p in CONTROL.glob('*.log'):copy(p,pathlib.Path('jobs')/p.name)
 for name in ['verify021_meter.py','verify021_operations.py','verify021_setup.py','verify021_control_probe.py','verify021_collect.py']:
  copy(BASE/name,pathlib.Path('verification-tools')/name)
 for name in before['prepared_test_sha256']:
  copy(REPO/name,pathlib.Path('verification-inputs')/pathlib.Path(name).name)
 operating=CONTROL/'operating';members=[]
 archive=PUBLIC/'RAW_OPERATING_RECORDS.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as out:
  for p in sorted(operating.rglob('*')):
   if not p.is_file():continue
   name=p.relative_to(operating).as_posix()
   if ('.adaptive-simulation-key' in p.name or 'account.sqlite' in p.name
       or p.name=='STATE.json' or p.name.endswith('.lock') or '__pycache__' in p.parts):continue
   raw=p.read_bytes();out.writestr(name,raw)
   members.append({'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
 with tempfile.TemporaryDirectory(prefix='public-export-audit-',dir=CONTROL/'tmp') as temp:
  temp=pathlib.Path(temp)
  with zipfile.ZipFile(archive) as z:
   for info in z.infolist():
    assert not pathlib.PurePosixPath(info.filename).is_absolute() and '..' not in pathlib.PurePosixPath(info.filename).parts
   z.extractall(temp)
  checks=[]
  for name in ['central-comparison','provider_default','outside_choice']:
   target=temp/name
   assert identity(target/'source')==before['source_identity']
   assert not list(target.rglob('*.adaptive-simulation-key')) and not list(target.rglob('*.sqlite'))
   done=subprocess.run([sys.executable,'-m','connected_enterprise','audit','--output',str(target)],
                       cwd=target/'source',capture_output=True,text=True)
   check={'name':name,'returncode':done.returncode,'stdout':done.stdout,'stderr':done.stderr}
   checks.append(check);assert done.returncode==0,check
   assert json.loads(done.stdout)['accepted']
 (PUBLIC/'PUBLIC_EXPORT_AUDIT.json').write_text(json.dumps({'accepted':True,'checks':checks,
  'scope':'Actual extracted public copies, without SQLite accounts or private simulation keys, passed the unchanged canonical frozen audit.'},indent=2)+'\n')
 (PUBLIC/'RAW_OPERATING_INDEX.json').write_text(json.dumps({'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
  'archive_bytes':archive.stat().st_size,'members':members,'private_material_included':False,
  'reproduction':'Extract ZIP into a new directory, then run python3 -m connected_enterprise audit --output ABSOLUTE_RUN_DIRECTORY with cwd=RUN_DIRECTORY/source. Public copies permit audit, not owned-account resume.'},indent=2)+'\n')
 report=json.loads((operating/'central-comparison/COMPARISON.json').read_text())
 copy(operating/'central-comparison/COMPARISON.json','COMPARISON.json')
 for name in ['provider_default','outside_choice']:
  a=json.loads((operating/name/'CAPITAL_AUDIT.json').read_text())
  (PUBLIC/(name.upper()+'.json')).write_text(json.dumps({'accepted':a['accepted'],'scoreboard':a['scoreboard']},indent=2)+'\n')
 summary={'schema':'native021-verification-results/v1','status':'VERIFICATION_COMPLETE_ON_UNCHANGED_CANDIDATE',
  'candidate_commit':before['candidate_commit'],'runtime_source_sha256':before['source_identity']['sha256'],
  'financial_source_sha256':before['financial_source']['sha256'],
  'corrected_launcher':json.loads((PUBLIC/'qualification/verification021-legacy.json').read_text()),
  'maturity_successor':{k:v for k,v in json.loads((PUBLIC/'proofs/maturity_successor_receipt.json').read_text()).items() if k!='service_receipts'},
  'ordinary_portable_upgrade':json.loads((PUBLIC/'proofs/ordinary_portable_upgrade_receipt.json').read_text()),
  'comparison':{'settled_orders':{k:v['settled_orders'] for k,v in report['arms'].items()},
    'profit_microUSD':{k:v['native_summary']['profit'] for k,v in report['arms'].items()},
    'profitable_earned_continuations':{k:v['profitable_earned_continuations'] for k,v in report['arms'].items()},
    'settled_order_delta':report['settled_order_delta'],'profit_delta_microUSD':report['profit_delta_microUSD'],
    'control_limit':'No-receipt-financing ablation, not the strongest conventional financing policy.'},
  'retained_new_harness_failures':[
   {'job':'ordinary-portable-upgrade','reason':'Git archive inherited the nested working-directory prefix. Unchanged test passed after setting GIT_DIR and GIT_WORK_TREE to the isolated root; both outcomes retained.'},
   {'job':'central-canonical-completion','reason':'Precondition rejected incomplete comparison after 36 events, with only final maturity at hour 48 outstanding. Continued the same account/key for that event, then completed canonical comparison/audits; both outcomes retained.'}],
  'prior_failure':'Original recursive-launcher failure, 435.256672077 CPU seconds against its 300-second cap, and original failed resource qualification remain unchanged.',
  'historical_native_suite':'22 tests passed previously on identical runtime; not rerun or counted as new tests.',
  'limitations':['All buyers, money, provider observations and complete-resource prices are authored simulation assumptions.',
    'Deterministic synthetic reconciliation jobs and checker executed; no paid frontier-model calls or observed customers.',
    'Actual host/model billing unknown; no actual annual profit, general market superiority or capability-compounding claim.',
    'Financial Account/Journal source transition is verified. Full legacy operating queue/STATE migration remains unimplemented and guarded.',
    'Local same-model/host verification, not independent external certification.'],
  'actions':{'hosted_ci':0,'external_spending':0,'runtime_changes':0,'merged':False,'released':False,'automatic_renewal':False}}
 assert summary['corrected_launcher']['accepted'] and summary['corrected_launcher']['tests']==70
 assert summary['maturity_successor']['accepted'] and summary['ordinary_portable_upgrade']['accepted']
 (PUBLIC/'RESULTS.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({'accepted':True,'archive_bytes':archive.stat().st_size,'archive_members':len(members),'comparison':summary['comparison']}))

if __name__=='__main__':main()
