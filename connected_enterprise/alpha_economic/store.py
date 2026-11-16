"""Durable nonfinancial state machine and transactional outbox with one writer."""
from __future__ import annotations
from contextlib import contextmanager
import fcntl
import os
import sqlite3
from .core import canonical,digest,parse,read,safe,save

TERMINAL={'COMPLETE','DECLINED','FAILED','REFUNDED'}
TRANSITIONS={
 'DISCOVERED':{'QUALIFIED','DECLINED'},'QUALIFIED':{'CONSENTED','DECLINED'},
 'CONSENTED':{'FUNDED','DECLINED','REFUND_PENDING'},'FUNDED':{'BUILDING','REFUND_PENDING'},
 'BUILDING':{'VERIFIED','REFUND_PENDING'},'VERIFIED':{'DELIVERED','REFUND_PENDING'},
 'DELIVERED':{'ACCEPTED','REFUND_PENDING'},'ACCEPTED':{'SETTLED'},
 'SETTLED':{'ADVANCED'},'ADVANCED':{'COMPLETE'},'REFUND_PENDING':{'REFUNDED'},
}


class State:
    def __init__(self,root,policy):
        self.root=safe(root); self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.root.stat().st_mode&0o077: raise ValueError('PRIVATE_STATE_DIRECTORY_REQUIRED_0700')
        self.path=safe(self.root/'operations.sqlite')
        with self.db() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,body TEXT NOT NULL,state TEXT NOT NULL,
                data TEXT NOT NULL,priority INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,job TEXT,kind TEXT,body TEXT,prev TEXT,hash TEXT);
            CREATE TABLE IF NOT EXISTS effects(id TEXT PRIMARY KEY,request TEXT NOT NULL,day INTEGER NOT NULL,
                status TEXT NOT NULL,result TEXT);
            CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,job TEXT NOT NULL,status TEXT NOT NULL,result TEXT);
            CREATE TABLE IF NOT EXISTS capabilities(id TEXT PRIMARY KEY,scope TEXT NOT NULL,artifact TEXT NOT NULL,
                parent TEXT NOT NULL,funding TEXT NOT NULL,uses INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sources(url TEXT PRIMARY KEY,body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,body TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS hypotheses(id TEXT PRIMARY KEY,body TEXT NOT NULL);
            ''')
            existing=c.execute("SELECT v FROM meta WHERE k='policy'").fetchone()
            if existing and parse(existing[0])!=policy: raise ValueError('POLICY_CHANGED_EXPLICIT_MIGRATION_REQUIRED')
            c.execute("INSERT OR IGNORE INTO meta VALUES('policy',?)",(canonical(policy).decode(),))
            c.execute("INSERT OR IGNORE INTO meta VALUES('day','0')")
            c.execute("INSERT OR IGNORE INTO meta VALUES('paused','false')")

    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=15); c.row_factory=sqlite3.Row
        c.execute('PRAGMA synchronous=FULL');c.execute('PRAGMA foreign_keys=ON')
        try:
            with c: yield c
        finally: c.close()

    @contextmanager
    def lock(self):
        p=safe(self.root/'engine.lock')
        with open(p,'a+b') as f:
            try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise RuntimeError('ENGINE_ALREADY_RUNNING') from None
            try: yield
            finally: fcntl.flock(f,fcntl.LOCK_UN)

    @staticmethod
    def event(c,job,kind,body):
        prior=c.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        prev=prior[0] if prior else '0'*64
        h=digest({'job':job,'kind':kind,'body':body,'prev':prev})
        c.execute('INSERT INTO events(job,kind,body,prev,hash) VALUES(?,?,?,?,?)',(job,kind,canonical(body).decode(),prev,h))

    def log(self,job,kind,body):
        with self.db() as c:self.event(c,job,kind,body)

    def add(self,job,body,priority):
        with self.db() as c:
            old=c.execute('SELECT body FROM jobs WHERE id=?',(job,)).fetchone()
            if old:
                if old[0]!=canonical(body).decode():raise ValueError('JOB_CONTENT_CHANGED')
                return False
            c.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',(job,canonical(body).decode(),'DISCOVERED','{}',priority))
            self.event(c,job,'DISCOVERED',{'contract_sha256':digest(body)})
        return True

    def get(self,job):
        with self.db() as c:r=c.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone()
        if not r:raise KeyError(job)
        return {**dict(r),'body':parse(r['body']),'data':parse(r['data'])}

    def pending(self):
        with self.db() as c:
            rows=c.execute('SELECT id FROM jobs ORDER BY priority DESC,id').fetchall()
        return [self.get(r[0]) for r in rows if self.get(r[0])['state'] not in TERMINAL]

    def move(self,job,target,updates=None):
        with self.db() as c:
            row=c.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone()
            if target not in TRANSITIONS.get(row['state'],set()):raise ValueError('INVALID_STATE_TRANSITION')
            data=parse(row['data']);data.update(updates or {})
            c.execute('UPDATE jobs SET state=?,data=? WHERE id=?',(target,canonical(data).decode(),job))
            self.event(c,job,target,updates or {})

    def update(self,job,updates):
        with self.db() as c:
            row=c.execute('SELECT data FROM jobs WHERE id=?',(job,)).fetchone()
            data=parse(row[0]);data.update(updates)
            c.execute('UPDATE jobs SET data=? WHERE id=?',(canonical(data).decode(),job))

    def pause(self,value=True):
        if type(value) is not bool:raise ValueError('EXPLICIT_PAUSE_BOOLEAN_REQUIRED')
        with self.db() as c:
            c.execute("UPDATE meta SET v=? WHERE k='paused'",('true' if value else 'false',))
            self.event(c,'','PAUSED' if value else 'RESUMED',{})

    def paused(self):
        with self.db() as c:return c.execute("SELECT v FROM meta WHERE k='paused'").fetchone()[0]=='true'

    def day(self):
        with self.db() as c:return int(c.execute("SELECT v FROM meta WHERE k='day'").fetchone()[0])

    def tick(self):
        with self.db() as c:
            day=int(c.execute("SELECT v FROM meta WHERE k='day'").fetchone()[0])+1
            c.execute("UPDATE meta SET v=? WHERE k='day'",(str(day),))
        return day

    def effect(self,key,request,fn):
        """Intent durable before effect; retry uses the same key, body and financial time."""
        raw=canonical(request).decode()
        with self.db() as c:
            row=c.execute('SELECT * FROM effects WHERE id=?',(key,)).fetchone()
            if row:
                if row['request']!=raw:raise ValueError('IDEMPOTENCY_KEY_PAYLOAD_CHANGED')
                if row['status']=='DONE':return parse(row['result'])
                day=row['day']
            else:
                day=int(c.execute("SELECT v FROM meta WHERE k='day'").fetchone()[0])
                c.execute('INSERT INTO effects VALUES(?,?,?,?,?)',(key,raw,day,'PENDING',None))
        result=fn(day)
        with self.db() as c:
            c.execute("UPDATE effects SET status='DONE',result=? WHERE id=?",(canonical(result).decode(),key))
        return result

    def begin_attempt(self,job):
        with self.db() as c:
            n=c.execute('SELECT COUNT(*) FROM attempts WHERE job=?',(job,)).fetchone()[0]
            ident=job+'-attempt-'+str(n)
            c.execute('INSERT INTO attempts VALUES(?,?,?,?)',(ident,job,'STARTED',None))
            self.event(c,job,'CONSTRUCTION_STARTED',{'attempt':ident})
        return ident

    def finish_attempt(self,ident,result):
        with self.db() as c:
            c.execute("UPDATE attempts SET status='DONE',result=? WHERE id=?",(canonical(result).decode(),ident))

    def attempts(self,job):
        with self.db() as c:return [dict(r) for r in c.execute('SELECT * FROM attempts WHERE job=? ORDER BY id',(job,))]

    def recover(self):
        with self.db() as c:
            for r in c.execute("SELECT * FROM attempts WHERE status='STARTED'").fetchall():
                c.execute("UPDATE attempts SET status='INTERRUPTED' WHERE id=?",(r['id'],))
                self.event(c,r['job'],'INTERRUPTED_CONSTRUCTION',{'id':r['id'],'cost':'RETAIN_PREPAID_SIMULATED_ATTEMPT_NO_FREE_RETRY'})

    def retain(self,scope,artifact,parent,funding):
        if funding.get('funding')!='EARNED':raise ValueError('NATIVE_EARNED_FUNDING_REQUIRED')
        ident=digest(artifact)
        with self.db() as c:
            c.execute('INSERT OR IGNORE INTO capabilities(id,scope,artifact,parent,funding) VALUES(?,?,?,?,?)',
                (ident,scope,canonical(artifact).decode(),parent,canonical(funding).decode()))
        return ident

    def inherited(self,scope):
        with self.db() as c: rows=c.execute('SELECT * FROM capabilities WHERE scope=? ORDER BY id',(scope,)).fetchall()
        return [{**dict(r),'artifact':parse(r['artifact'])} for r in rows]

    def summary(self):
        with self.db() as c:
            jobs=[dict(r) for r in c.execute('SELECT id,state,priority FROM jobs ORDER BY id')]
            return {'jobs':jobs,'capabilities':c.execute('SELECT COUNT(*) FROM capabilities').fetchone()[0],
                    'events':c.execute('SELECT COUNT(*) FROM events').fetchone()[0],
                    'effects_pending':c.execute("SELECT COUNT(*) FROM effects WHERE status='PENDING'").fetchone()[0],
                    'hypotheses':c.execute('SELECT COUNT(*) FROM hypotheses').fetchone()[0],
                    'simulation_hour':self.day(),'paused':self.paused(),'real_customers_established':False}

    def audit(self):
        prev='0'*64
        with self.db() as c:events=c.execute('SELECT * FROM events ORDER BY seq').fetchall()
        for e in events:
            body={'job':e['job'],'kind':e['kind'],'body':parse(e['body']),'prev':prev}
            if e['prev']!=prev or e['hash']!=digest(body):raise ValueError('OPERATING_EVENT_CHAIN_CHANGED')
            prev=e['hash']
        return {'accepted':True,'events':len(events),'tip':prev,'scope':'LOCAL_INTEGRITY_NOT_EXTERNAL_ATTESTATION'}
