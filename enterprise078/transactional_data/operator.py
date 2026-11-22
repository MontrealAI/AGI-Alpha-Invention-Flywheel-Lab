import argparse,csv,json,os,sqlite3
from pathlib import Path

def validate(events):
 if not isinstance(events,list) or len(events)>1000000: raise ValueError('DECLARED_BATCH_REQUIRED')
 result={}
 for row in events:
  if not isinstance(row,dict) or set(row)!={'id','account','quantity'}: raise ValueError('EXACT_EVENT_REQUIRED')
  if any(not isinstance(row[k],str) or not row[k] or len(row[k])>80 for k in ('id','account')): raise ValueError('EVENT_IDENTITY_REQUIRED')
  if type(row['quantity']) is not int or abs(row['quantity'])>1000000000: raise ValueError('EXACT_BOUNDED_INTEGER_REQUIRED')
  item=(row['account'],row['quantity'])
  if row['id'] in result and result[row['id']]!=item: raise ValueError('CONFLICTING_EVENT')
  result[row['id']]=item
 return result

def connect(path):
 c=sqlite3.connect(str(path),isolation_level=None)
 c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA synchronous=FULL')
 c.execute('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,account TEXT NOT NULL,quantity INTEGER NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS totals(account TEXT PRIMARY KEY,units INTEGER NOT NULL,event_count INTEGER NOT NULL)')
 return c

def ingest(path,events,*,crash=None):
 rows=validate(events);c=connect(path);c.execute('BEGIN IMMEDIATE')
 try:
  for i,(identity,(account,quantity)) in enumerate(rows.items()):
   prior=c.execute('SELECT account,quantity FROM events WHERE id=?',(identity,)).fetchone()
   if prior is not None and prior!=(account,quantity): raise ValueError('CONFLICTING_PERSISTED_EVENT')
   if prior is None: c.execute('INSERT INTO events VALUES(?,?,?)',(identity,account,quantity))
   if crash=='before_commit' and i==len(rows)//2: os._exit(71)
  c.execute('COMMIT')
  if crash=='after_commit': os._exit(72)
  c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
 finally:
  if c.in_transaction: c.execute('ROLLBACK')
  c.close()

def project(path,*,crash=False):
 c=connect(path);c.execute('BEGIN IMMEDIATE')
 try:
  c.execute('DELETE FROM totals')
  c.execute('INSERT INTO totals SELECT account,SUM(quantity),COUNT(*) FROM events GROUP BY account')
  if crash: os._exit(73)
  c.execute('COMMIT');c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
 finally:
  if c.in_transaction: c.execute('ROLLBACK')
  c.close()

def export_csv(path,destination):
 c=sqlite3.connect(str(path))
 try:
  rows=c.execute('SELECT account,units,event_count FROM totals ORDER BY account').fetchall()
  with open(destination,'w',newline='') as f:
   w=csv.writer(f);w.writerow(('account','units','event_count'));w.writerows(rows)
 finally:c.close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['ingest','project']);p.add_argument('--database',type=Path,required=True);p.add_argument('--input',type=Path);p.add_argument('--crash',choices=['before_commit','after_commit','projection']);a=p.parse_args()
 if a.action=='ingest': ingest(a.database,json.loads(a.input.read_text()),crash=a.crash)
 else: project(a.database,crash=a.crash=='projection')
