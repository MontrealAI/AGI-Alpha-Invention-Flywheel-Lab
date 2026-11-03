import csv,sqlite3
from pathlib import Path

def reference(events):
 unique={};totals={}
 for row in events:
  if set(row)!= {'id','account','quantity'} or type(row['quantity']) is not int: raise ValueError('INVALID_REFERENCE_EVENT')
  key=row['id'];value=(row['account'],row['quantity'])
  if key in unique and unique[key]!=value: raise ValueError('AMBIGUOUS_REFERENCE')
  unique[key]=value
 for account,q in unique.values():
  current=totals.setdefault(account,[0,0]);current[0]+=q;current[1]+=1
 return [(k,*v) for k,v in sorted(unique.items())],[(k,*v) for k,v in sorted(totals.items())]

def inspect(path):
 c=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
 try:
  return {'events':c.execute('SELECT id,account,quantity FROM events ORDER BY id').fetchall(),'totals':c.execute('SELECT account,units,event_count FROM totals ORDER BY account').fetchall(),'integrity':c.execute('PRAGMA integrity_check').fetchall()}
 finally:c.close()

def verify(path,events,*,projection=True,csv_path=None):
 expected,totals=reference(events);state=inspect(path);errors=[]
 if state['integrity']!=[('ok',)]: errors.append('SQLITE_INTEGRITY')
 if state['events']!=expected: errors.append('EXACT_DURABLE_EVENTS')
 if projection and state['totals']!=totals: errors.append('EXACT_DERIVED_STATE')
 if csv_path is not None:
  try:
   with open(csv_path,newline='') as f:
    reader=csv.reader(f);header=next(reader);actual=[(r[0],int(r[1]),int(r[2])) for r in reader]
   if header!=['account','units','event_count'] or actual!=totals: errors.append('EXACT_CSV_OUTPUT')
  except (ValueError,IndexError,StopIteration): errors.append('MALFORMED_CSV')
 return {'accepted':not errors,'errors':errors,'unique_events':len(expected),'groups':len(totals),'total_units':sum(r[1] for r in totals),'scope':'actual local SQLite and CSV; synthetic nonfinancial records'}
