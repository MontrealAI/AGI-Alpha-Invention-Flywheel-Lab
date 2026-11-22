import sqlite3,tempfile
from pathlib import Path

def check():
 rows=[]
 for dedup in (False,True):
  for fault in ('ack','drop_before','drop_after'):
   with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'instrument.sqlite'
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE effects (token TEXT, quantity INTEGER)')
    if dedup: db.execute('CREATE UNIQUE INDEX unique_token ON effects(token)')
    db.commit()
    if fault!='drop_before':
     db.execute('INSERT INTO effects VALUES (?,?)',('sample-A',7));db.commit()
    db.close()
    db=sqlite3.connect(path)
    if fault!='ack': db.execute('INSERT OR IGNORE INTO effects VALUES (?,?)',('sample-A',7));db.commit()
    actual=db.execute('SELECT COALESCE(SUM(quantity),0) FROM effects').fetchone()[0];db.close()
    rows.append({'persistent_unique_token':dedup,'fault':fault,'quantity_after_reopen_and_retry':actual,'exact_once':actual==7})
 return {'sqlite_version':sqlite3.sqlite_version,'rows':rows,'scope':'actual local transactional writes and process-level connection reopen; not power failure or physical lab equivalence','expected_match':all(r['exact_once']==(r['persistent_unique_token'] or r['fault']!='drop_after') for r in rows)}
