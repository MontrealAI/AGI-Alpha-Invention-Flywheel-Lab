"""Independent arithmetic/count reader; does not invoke the simulation."""
import argparse,json
from pathlib import Path

def audit_row(r):
 cum=rev=coll=0.;accepted=orders=contacts=0
 assert len(r['trace'])==26
 for q,x in enumerate(r['trace'],1):
  assert x['quarter']==q
  cum+=x['profit'];rev+=x['revenue'];coll+=x['collected']
  tol=max(1e-5,r['capital']*1e-10)
  assert abs(x['revenue']-x['expense']-x['profit'])<tol
  assert abs(rev-coll-x['receivables'])<tol
  assert abs(x['cash']+x['receivables']-x['tax_payable']-r['capital']-cum)<tol
  assert x['cash']+tol>=x['reserved'] and x['reserved']>=-tol and x['tax_payable']>=-tol
  assert accepted<=x['accepted']<=x['orders']<=x['contacts']
  assert orders<=x['orders'] and contacts<=x['contacts']
  assert x['orders']-orders==x['new_orders']
  if q>20:assert x['new_orders']==0
  if r['mode']=='human_only' and x['selected_variant']:assert x['selected_variant']=='human'
  accepted=x['accepted'];orders=x['orders'];contacts=x['contacts']
 last=r['trace'][-1]
 for key in ('cash','receivables','accepted','orders','contacts'):
  assert abs(r[key]-last[key])<tol
 assert abs(r['obligations']-last['reserved']-last['tax_payable'])<tol
 for key in ('human_hours','founder_hours'):
  assert abs(r[key]-sum(x[key] for x in r['trace']))<tol
 assert abs(cum-r['settled_profit'])<tol
 assert abs(sum(x['profit'] for x in r['trace'][16:20])-r['trailing_year_profit'])<tol
 assert abs(r['obligations'])<tol and abs(r['receivables'])<tol
 return 26*9+4

def audit_file(path):
 rows=json.loads(Path(path).read_text());keys=set();checks=0
 for r in rows:
  key=tuple(r[k] for k in ('external_finance','inherited_assets','capital','mode','world','seed'))
  assert key not in keys;keys.add(key);checks+=audit_row(r)
 return {'rows':len(rows),'checks':checks}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('file');a=p.parse_args();print(audit_file(a.file))
