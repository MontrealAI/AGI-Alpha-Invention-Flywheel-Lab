"""Read-only exact-main gate for a separately manually dispatched bridge release."""
import argparse,json,re,subprocess
REQUIRED={'campaign.yml','consequential007.yml','consequential009.yml','adaptive012.yml','commercial010.yml',
          'genesis-execution-bridge.yml','genesis-bridge-package.yml','connected014-release.yml'}
def decide(source,main,runs):
 if re.fullmatch('[0-9a-f]{40}',source or '') is None or main!=source:raise ValueError('exact current main required')
 relevant=[r for r in runs if r.get('head_sha')==source and r.get('event')=='push' and r.get('head_branch')=='main']
 latest={}
 for r in relevant:
  path=r.get('path','')
  if re.fullmatch(r'\.github/workflows/[a-zA-Z0-9_.-]+\.ya?ml',path) is None:raise ValueError('workflow identity')
  key=path.split('/')[-1]
  if key not in latest or (r['id'],r.get('run_attempt',1))>(latest[key]['id'],latest[key].get('run_attempt',1)):latest[key]=r
 missing=REQUIRED-set(latest)
 if missing:raise ValueError('missing required main workflows: '+','.join(sorted(missing)))
 incomplete={k:r.get('conclusion') or r.get('status') for k,r in latest.items() if r.get('status')!='completed' or r.get('conclusion')!='success'}
 if incomplete:raise ValueError('main workflows not successful: '+json.dumps(incomplete,sort_keys=True))
 return {'accepted':True,'source_commit':source,'event':'push','main_workflows':{k:{'id':r['id'],'run_attempt':r.get('run_attempt',1),'conclusion':r['conclusion']} for k,r in sorted(latest.items())}}
def fetch(repo,path):
 p=subprocess.run(['gh','api','repos/'+repo+'/'+path],capture_output=True,text=True,check=True)
 return json.loads(p.stdout)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',required=True);p.add_argument('--source-commit',required=True);a=p.parse_args()
 if re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',a.repository) is None:raise ValueError('repository syntax')
 rows=[];page=1
 while True:
  result=fetch(a.repository,'actions/runs?head_sha='+a.source_commit+'&event=push&per_page=100&page='+str(page))
  rows+=result['workflow_runs']
  if len(rows)>=result['total_count']:break
  if not result['workflow_runs'] or page>=20:raise ValueError('incomplete workflow enumeration')
  page+=1
 branch=fetch(a.repository,'branches/main')
 print(json.dumps(decide(a.source_commit,branch['commit']['sha'],rows),sort_keys=True))
if __name__=='__main__':main()
