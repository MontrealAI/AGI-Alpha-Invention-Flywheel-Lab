"""Synthetic controls live in temporary databases; no human responses are recorded."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from trial import ARMS, REG, COSTS, adjudicate, allocation, blind, enroll, initialize, receive, summarize


class ReaderControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.auth={'study':REG['id'],'human_collection_authorized':True,'authority_reference':'synthetic-unit-control',
                   'accounting':{'currency':'CAD','measurement_window':'synthetic test only','allocation_rule':'synthetic apportioned shares'}}
        self.write('authorization',self.auth)
        initialize(self.dir/'private',self.dir/'authorization')
        self.db=sqlite3.connect(self.dir/'private/roster.sqlite');self.db.row_factory=sqlite3.Row
        self.addCleanup(self.db.close)

    def write(self,name,x):
        p=self.dir/name;p.write_text(json.dumps(x));return p

    def consent(self,subject='synthetic-reader'):
        return {'study':'RR-H1','subject':subject,'lang':'en','stratum':'screen_reader','consented':True,
               'fluent':True,'reads_research':True,'paper_and_key_unseen':True,'unique_person':True,
               'retention_terms_explained':True,'consent_reference':'synthetic-control'}

    def enroll(self):
        enroll(self.db,self.write('consent',self.consent()))
        return self.db.execute('SELECT * FROM enrollment').fetchone()

    def test_allocation_and_orders(self):
        for lang in ('en','fr'):
            for stratum in ('screen_reader','ordinary'):
                samples=[allocation('51'*32,lang,stratum,i) for i in range(16)]
                for i in range(0,16,4):self.assertEqual(set(a for a,_ in samples[i:i+4]),set(ARMS))
                for arm in ARMS:
                    orders=[o for a,o in samples if a==arm]
                    self.assertEqual(len({o[0] for o in orders}),4)
                    self.assertEqual(len({tuple(o) for o in orders}),4)
                    self.assertEqual(len({(s,t) for o in orders for s,t in zip(o,o[1:])}),12)

    def test_authority_and_duplicate(self):
        self.auth['human_collection_authorized']=False
        with self.assertRaises(ValueError):initialize(self.dir/'denied',self.write('denied-auth',self.auth))
        invalid=self.consent();invalid['paper_and_key_unseen']=False
        with self.assertRaises(ValueError):enroll(self.db,self.write('known',invalid))
        self.enroll()
        with self.assertRaises(sqlite3.IntegrityError):enroll(self.db,self.dir/'consent')

    def test_missing_wrong_units_disagreement_abstention_and_withdrawal(self):
        record=self.enroll();order=json.loads(record['order_json'])
        rows=[{'task':t,'status':'answered','answer':a,'quote':'source snippet',
               'page':9,'elapsed_ms':800,'interruption':''} for t,a in zip(order,('89 model units','89 dollars','unsupported'))]
        rows.append({'task':order[-1],'status':'unresolved','answer':'','quote':'','page':None,'elapsed_ms':1200,'interruption':''})
        submit={'session':record['session'],'rows':rows,'barrier':'','technology':'synthetic only'}
        bad={**submit,'rows':list(reversed(rows))}
        with self.assertRaises(ValueError):receive(self.db,self.write('bad',bad))
        self.db.rollback()
        receive(self.db,self.write('partial',{**submit,'rows':rows[:1]}))
        receive(self.db,self.write('response',submit))
        amended=[dict(r) for r in rows];amended[0]['answer']='changed answer'
        with self.assertRaises(ValueError):receive(self.db,self.write('edited',{**submit,'rows':amended}))
        self.db.rollback()
        blind(self.db,self.dir/'blind'); hidden=json.loads((self.dir/'blind').read_text())
        self.assertEqual(len(hidden),3)
        self.assertFalse(any(set(row)&{'elapsed_ms','subject','arm','stratum'} for row in hidden))
        verdict={order[0]:'accepted',order[1]:'consequential_error',order[2]:'accepted'}
        first=[{'id':r['id'],'grade':verdict[r['task']],'basis':'synthetic blinded source check'} for r in hidden]
        def decisions(name,rs):return self.write(name,{'reviewer':name,'decisions':rs})
        a=decisions('reviewer-1',first)
        b=decisions('reviewer-2',[{**r,'grade':'ordinary_error'} if r['grade']=='consequential_error' else r for r in first])
        with self.assertRaises(ValueError):adjudicate(self.db,a,b,None)
        with self.assertRaises(ValueError):adjudicate(self.db,a,a,None)
        third=decisions('reviewer-3',[r for r in first if r['grade']=='consequential_error'])
        grades=adjudicate(self.db,a,b,third)
        summary=summarize(self.db,grades,None);group='en.screen_reader.'+record['arm']
        v=summary['strata'][group]
        self.assertEqual((v['assigned'],v['accepted'],v['consequential_errors'],v['unresolved']),(4,2,1,1))
        self.assertIsNone(v['cost_micros_per_accepted'])
        costfile=self.write('cost',{'currency':'CAD','groups':{group:{k:10 for k in COSTS}}})
        self.assertEqual(summarize(self.db,grades,costfile)['strata'][group]['cost_micros_per_accepted'],40)
        self.db.execute('UPDATE enrollment SET withdrawn=1,response=NULL')
        self.db.commit()
        self.assertEqual(summarize(self.db,{},None)['withdrawn'],1)
        with self.assertRaises(ValueError):receive(self.db,self.dir/'response')


if __name__=='__main__':unittest.main()
