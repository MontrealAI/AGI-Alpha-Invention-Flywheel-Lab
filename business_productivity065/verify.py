"""Independent read-only replay of all registered native results and delivery hashes."""
import argparse,json,hashlib
from pathlib import Path
from commercial.ledger import digest
from .native import audit_export
from .service import verify_delivery
ARMS=('conditional','no_demand','payment_delay','competitive_imitation','insufficient_earned_cash')

def require(condition):
 if not condition:raise ValueError('PRODUCTIVITY065_RESULT_CHECK_FAILED')

def verify(root,states):
 rows=[]
 for arm in ARMS:
  folder=states/('productivity065-'+arm)
  r=json.loads((folder/'result.json').read_text());e=json.loads((folder/'public-export.json').read_text());m=json.loads((folder/'manifest.json').read_text())
  verdict=audit_export(e,root=root,manifest=m)
  require(verdict['accepted'] and r['public_export_sha256']==digest(e))
  require(e['ledger']['config']['opening']==100000000000)
  require(e['ledger']['summary']==r['summary'])
  require(r['observed_buyers']==0 and r['actual_billing'] is None)
  for d in r['deliveries']:
   if not d['accepted']:
    require(d['production']['funding_before_process'])
    require(r['decision'] in {'FIRST_REJECTED_NO_COLLECTION','SECOND_REJECTED_COST_RETAINED'})
    continue
   job=next(x for x in m['jobs'] if x['id']==d['job']);artifact=json.loads((root/job['delivery_path']).read_text())
   accepted=verify_delivery(root,m,d['job'],artifact)
   require(accepted['accepted'] and digest(artifact)==d['artifact_sha256'])
   require(d['production']['funding_before_process'] and d['production']['exit_code']==0)
  if r['decision'] in {'FIRST_REJECTED_NO_COLLECTION','SECOND_REJECTED_COST_RETAINED'}:
   require(any(not d['accepted'] for d in r['deliveries']))
  elif arm=='conditional':
   require(len(r['deliveries'])==2 and r['summary']['profit']>0)
   funding=r['funding_checks'][0];require(funding['receipt']['funding']=='EARNED')
   require(funding['summary_before']['unrestrictedEarned']>=35000000)
   actions=e['ledger']['actions']
   release=min(i for i,x in enumerate(actions) if x['op']=='event' and x['args'].get('action')=='release')
   reserve=min(i for i,x in enumerate(actions) if x['op']=='reserve')
   require(release<reserve)
  elif arm=='no_demand':
   require(not r['deliveries'] and r['summary']['revenue']==0 and r['summary']['profit']<0)
  else:
   require(len(r['deliveries'])==1 and r['funding_checks'][0]['receipt'] is None)
   require(r['funding_checks'][0]['refusal_unchanged'] is True)
   if arm=='competitive_imitation':require(r['summary']['profit']<0)
  rows.append({'arm':arm,'accepted':True,'profit_microUSD':r['summary']['profit'],'deliveries':len(r['deliveries']),'accepted_deliveries':sum(d['accepted'] for d in r['deliveries']),'decision':r['decision']})
 return {'accepted':True,'scope':'SOURCE_MATCHED_NATIVE_REPLAY_AND_ACTUAL_DELIVERY_ACCEPTANCE_NOT_OBSERVED_COMMERCE','arms':rows}

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--states',type=Path,required=True);a=p.parse_args();print(json.dumps(verify(a.root.resolve(),a.states.resolve()),indent=2))
if __name__=='__main__':main()
