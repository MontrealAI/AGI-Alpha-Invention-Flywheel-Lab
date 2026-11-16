"""One persistent controller connecting all stages to canonical native economics.

Default execution is an explicitly declared simulation of commerce around actual
instrument construction and delivery. External payment observations never enter
this simulator as real revenue. Runtime plug-ins cannot change this authority.
"""
from __future__ import annotations
from pathlib import Path
import time
from .core import canonical,contract,digest,identifier,immutable,parse,read,save,worst_cost
from .checker import check,verify
from .commerce import offer,consent,acceptance
from .delivery import package
from .discovery import Discovery
from .native import NativeTreasury
from .store import State

POLICY_FIELDS={'schema','scope','opening_microUSD','working_microUSD','startup_microUSD',
               'minimum_margin_microUSD','allow_seed_production','frontier_urls','source_hosts',
               'frontier_research_microUSD','frontier_research_expected_net_microUSD','sources_every_ticks'}


def policy(value):
    if not isinstance(value,dict) or set(value)!=POLICY_FIELDS or value['schema']!='alpha-economic/policy/v1' or value['scope']!='SIMULATED':
        raise ValueError('EXACT_SIMULATED_POLICY_REQUIRED_LIVE_AUTHORITY_IS_SEPARATE')
    for key in POLICY_FIELDS:
        if key.endswith('_microUSD') and (type(value[key]) is not int or value[key]<0):raise ValueError('EXACT_POLICY_MONEY_REQUIRED')
    if type(value['allow_seed_production']) is not bool:raise ValueError('EXPLICIT_SEED_AUTHORITY_REQUIRED')
    if type(value['sources_every_ticks']) is not int or value['sources_every_ticks']<1:raise ValueError('POSITIVE_POLL_INTERVAL_REQUIRED')
    if not isinstance(value['frontier_urls'],list) or not isinstance(value['source_hosts'],list):raise ValueError('EXPLICIT_SOURCE_ALLOWLIST_REQUIRED')
    return value


def default_policy():
    return {'schema':'alpha-economic/policy/v1','scope':'SIMULATED','opening_microUSD':20_000_000,
            'working_microUSD':1_000_000,'startup_microUSD':500_000,'minimum_margin_microUSD':200_000,
            'allow_seed_production':True,'frontier_urls':[],'source_hosts':[],
            'frontier_research_microUSD':0,'frontier_research_expected_net_microUSD':0,'sources_every_ticks':20}


class Engine:
    def __init__(self,root,policy_value,agent,buyer,buyer_keys,*,clock=time.time,retriever=None):
        self.policy=policy(policy_value);self.state=State(root,self.policy);self.root=self.state.root
        if getattr(buyer,'scope',None)!='SIMULATED_COUNTERPARTY':
            raise ValueError('REAL_BUYER_CANNOT_BE_SETTLED_ON_SIMULATED_NATIVE_RAIL')
        self.agent,self.buyer,self.keys,self.clock=agent,buyer,buyer_keys,clock
        self.treasury=None
        self.discovery=Discovery(self.state,self.policy,buyer_keys,agent,retriever)

    def _open(self):
        if self.treasury is None:
            self.treasury=NativeTreasury(self.root,opening=self.policy['opening_microUSD'],working=self.policy['working_microUSD'])
            self.state.effect('startup',{'operation':'cost','key':'alpha-startup','amount':self.policy['startup_microUSD']},lambda day:self.treasury.cost('alpha-startup',self.policy['startup_microUSD'],day))

    def close(self):
        if self.treasury:self.treasury.close();self.treasury=None

    def submit(self,envelope):return self.discovery.admit(envelope,int(self.clock()))

    def _spend(self,job,label,amount,work,expected_net,allow_seed=None):
        allow=self.policy['allow_seed_production'] if allow_seed is None else allow_seed
        req={'operation':'spend','key':job+'-'+label,'amount':amount,'work':work,'expected_net':expected_net,'allow_seed':allow}
        if amount==0:return {'funding':'DECLARED_ZERO_SIMULATED_COST','amount':0}
        return self.state.effect(job+'-'+label,req,lambda day:self.treasury.spend(job+'-'+label,amount,day,work,expected_net,allow))

    def _advance_one(self,row):
        job,c,data,stage=row['id'],row['body'],row['data'],row['state'];now=int(self.clock())
        if now>c['expires_at'] and stage in ('FUNDED','BUILDING','VERIFIED','DELIVERED'):
            self.state.move(job,'REFUND_PENDING',{'reason':'CUSTOMER_CONTRACT_EXPIRED'});return True
        if stage=='CONSENTED' and now>c['expires_at']:
            self.state.move(job,'DECLINED',{'reason':'UNFUNDED_CONSENT_EXPIRED'});return True
        if stage=='DISCOVERED':
            margin=c['price_microUSD']-worst_cost(c)
            reason=None
            if c['expires_at']<now:reason='REQUEST_EXPIRED'
            elif margin<self.policy['minimum_margin_microUSD']:reason='NONVIABLE_DECLARED_COMPLETE_COST_ENVELOPE'
            elif not check(c,c['ordinary'])['accepted']:reason='ORDINARY_CONTROL_FAILS_CONTRACT'
            self.state.move(job,'DECLINED' if reason else 'QUALIFIED',{'reason':reason,'worst_cost_microUSD':worst_cost(c),'expected_margin_microUSD':margin})
        elif stage=='QUALIFIED':
            quoted=offer(c,now)
            if c['expires_at']<now:
                self.state.move(job,'DECLINED',{'reason':'OFFER_EXPIRED'});return True
            pay=self._spend(job,'acquisition',c['costs_microUSD']['acquisition'],{'contract':digest(c)},data['expected_margin_microUSD'])
            if pay is None:
                self.state.move(job,'DECLINED',{'reason':'ACQUISITION_UNFUNDED'});return True
            response=self.buyer.quote(c,quoted,now)
            if response.get('pending'):return False
            accepted=consent(response,c,quoted,self.keys[c['buyer']],now)
            self.state.move(job,'CONSENTED' if accepted['accepted'] else 'DECLINED',{'quote':quoted,'consent':response,'reason':None if accepted['accepted'] else 'BUYER_CHOSE_OUTSIDE_OPTION_OR_NO_PURCHASE'})
        elif stage=='CONSENTED':
            bound=self.state.effect(job+'-fund',{'operation':'begin','job':job,'contract':digest(c),'consent':digest(data['consent'])},lambda day:self.treasury.begin(c,day))
            self.state.move(job,'FUNDED',bound)
        elif stage=='FUNDED':
            # Every declared support, tax and failure cost is incurred, not omitted from success metrics.
            fixed={k:v for k,v in c['costs_microUSD'].items() if k not in ('acquisition','construction_per_attempt')}
            paid=self._spend(job,'fixed-costs',sum(fixed.values()),{'cost_categories_microUSD':fixed},data['expected_margin_microUSD'])
            if paid is None:self.state.move(job,'REFUND_PENDING',{'reason':'PRODUCTION_UNFUNDED'});return True
            inherited=self.state.inherited(c['scope_key'])
            chosen=None
            for old in inherited:
                instrument=old['artifact']['instrument']
                if check(c,instrument)['accepted']:
                    chosen={'schema':'alpha-economic/artifact/v1','contract_sha256':digest(c),'instrument':instrument,
                            'provenance':{'kind':'REVALIDATED_REUSE','parent_artifact_sha256':old['id'],'parent_job':old['parent']}}
                    break
            self.state.move(job,'BUILDING',{'candidate':chosen,'construction_mode':'REUSE' if chosen else 'MODEL_OR_FIXTURE'})
        elif stage=='BUILDING':
            artifact=data.get('candidate')
            if artifact is None:
                attempts=self.state.attempts(job)
                if len(attempts)>=c['max_attempts']:
                    # A valid conventional alternative is not artificially disqualified.
                    artifact={'schema':'alpha-economic/artifact/v1','contract_sha256':digest(c),'instrument':c['ordinary'],
                              'provenance':{'kind':'CONVENTIONAL_FALLBACK','attempts':len(attempts)}}
                else:
                    ident=self.state.begin_attempt(job)
                    paid=self._spend(job,'construction-'+str(len(attempts)),c['costs_microUSD']['construction_per_attempt'],
                                     {'attempt':ident},data['expected_margin_microUSD'])
                    if paid is None:
                        self.state.finish_attempt(ident,{'accepted':False,'reason':'UNFUNDED'})
                        self.state.move(job,'REFUND_PENDING',{'reason':'CONSTRUCTION_UNFUNDED'});return True
                    feedback=data.get('feedback',[])
                    try:
                        with self.state.db() as db:sources=[parse(r[0]) for r in db.execute('SELECT body FROM sources ORDER BY url')]
                        candidate,provenance=self.agent.construct(c,feedback,ident,sources)
                        result=check(c,candidate,groups=('training',))
                        self.state.finish_attempt(ident,{'training':result,'provenance':provenance})
                        if not result['accepted']:
                            self.state.update(job,{'feedback':feedback+[{'attempt':ident,'training_acceptance':False}]});return True
                        artifact={'schema':'alpha-economic/artifact/v1','contract_sha256':digest(c),'instrument':candidate,'provenance':provenance}
                    except (ValueError,TypeError,KeyError,RuntimeError,OSError) as exc:
                        self.state.finish_attempt(ident,{'accepted':False,'error_type':type(exc).__name__})
                        self.state.update(job,{'feedback':feedback+[{'attempt':ident,'error_type':type(exc).__name__}]});return True
            checked=verify(c,artifact)
            if not checked['accepted']:
                # Do not leak confirmation cases/answers to a repair prompt.
                artifact={'schema':'alpha-economic/artifact/v1','contract_sha256':digest(c),'instrument':c['ordinary'],
                          'provenance':{'kind':'CONVENTIONAL_FALLBACK_AFTER_CONFIRMATION_FAILURE'}}
                checked=verify(c,artifact)
            self.state.move(job,'VERIFIED',{'artifact':artifact,'verification':checked})
        elif stage=='VERIFIED':
            # Verify immediately before handing bytes to any buyer transport.
            verify(c,data['artifact'])
            current=self.treasury.snapshot()
            if self.state.day()>=data['maturity']-1:
                self.state.move(job,'REFUND_PENDING',{'reason':'PRODUCTION_DEADLINE_MISSED'});return True
            checked=self.state.effect(job+'-prepare',{'operation':'prepare','job':job,'artifact':digest(data['artifact'])},lambda day:self.treasury.prepare(c,data['artifact'],day))
            pkg=package(c,data['artifact'],self.root/'outbox'/job)
            self.state.move(job,'DELIVERED',{'package':pkg,'native_prepare':checked})
        elif stage=='DELIVERED':
            response=self.buyer.deliver(c,data['artifact'],data['package'],self.root/'outbox'/job/'solution.zip',now)
            if response.get('pending'):return False
            accepted=acceptance(response,c,data['artifact'],data['package'],self.keys[c['buyer']],now)
            self.state.move(job,'ACCEPTED' if accepted['accepted'] else 'REFUND_PENDING',{'acceptance':response,'reason':None if accepted['accepted'] else 'BUYER_REJECTED_DELIVERY'})
        elif stage=='ACCEPTED':
            receipt=self.state.effect(job+'-release',{'operation':'release','job':job,'acceptance':digest(data['acceptance'])},lambda day:self.treasury.release(c,day))
            self.state.move(job,'SETTLED',{'collection':receipt})
        elif stage=='SETTLED':
            # Refund/dispute exposure is not made available by relabeling a payment.
            if self.state.day()<=data['maturity']:return False
            self.treasury.advance(self.state.day())
            duplicate=any(digest(a['artifact']['instrument'])==digest(data['artifact']['instrument']) for a in self.state.inherited(c['scope_key']))
            if duplicate:
                self.state.move(job,'ADVANCED',{'reinvestment':{'funding':'NONE','reason':'ALREADY_RETAINED_NO_INCREMENTAL_INSTRUMENT'},'retained_capability':None});return True
            plan=self.state.effect(job+'-reinvest',{'operation':'reinvest','job':job,'artifact':digest(data['artifact']),'amount':c['reinvestment_microUSD'],'benefit_hypothesis':c['reuse_benefit_microUSD']},lambda day:self.treasury.reinvest(c,data['artifact'],day))
            asset=None
            if plan.get('funding')=='EARNED':asset=self.state.retain(c['scope_key'],data['artifact'],job,plan)
            self.state.move(job,'ADVANCED',{'reinvestment':plan,'retained_capability':asset})
        elif stage=='ADVANCED':
            self.state.move(job,'COMPLETE',{'native_financial_audit':self.treasury.audit(),'real_commerce':False})
        elif stage=='REFUND_PENDING':
            self.state.effect(job+'-refund',{'operation':'refund','job':job,'contract':digest(c)},lambda day:self.treasury.refund(c,day))
            self.state.move(job,'REFUNDED',{'real_commerce':False})
        else:return False
        return True

    def _sources(self):
        changed=self.discovery.poll()
        if not changed:return
        generation=digest([s['sha256'] for s in changed])
        fee=self.policy['frontier_research_microUSD']
        if fee<=0:
            self.state.log('','FRONTIER_RESEARCH_NOT_FUNDED',{'sources':generation});return
        paid=self._spend('frontier-'+generation,'research',fee,{'sources':generation},
                         self.policy['frontier_research_expected_net_microUSD'],allow_seed=False)
        if paid is None:self.state.log('','FRONTIER_RESEARCH_NOT_FUNDED',{'sources':generation});return
        with self.state.db() as db:
            if db.execute('SELECT 1 FROM messages WHERE id=?',('research-'+generation,)).fetchone():return
            db.execute('INSERT INTO messages VALUES(?,?,0)',('research-'+generation,canonical({'status':'STARTED','recovery':'NO_AUTOMATIC_RETRY_WITHOUT_NEW_FUNDING'}).decode()))
        try:
            self.discovery.hypotheses(changed,'discover-'+generation)
            with self.state.db() as db:db.execute('UPDATE messages SET processed=1 WHERE id=?',('research-'+generation,))
        except (ValueError,RuntimeError,OSError) as exc:self.state.log('','RESEARCH_FAILED',{'error_type':type(exc).__name__,'cost_retained':True})

    def _recover_effects(self):
        # Finish old side-effect intents before any later native financial time.
        # This includes an interrupted prepaid construction attempt, even when
        # recovery already marked the computation itself as interrupted.
        with self.state.db() as db:
            rows=db.execute("SELECT * FROM effects WHERE status='PENDING' ORDER BY day,rowid").fetchall()
        for row in rows:
            req=parse(row['request']);op=req.get('operation')
            def finish(day):
                if op=='cost':return self.treasury.cost(req['key'],req['amount'],day)
                if op=='spend':return self.treasury.spend(req['key'],req['amount'],day,req['work'],req['expected_net'],req['allow_seed'])
                record=self.state.get(req['job']);c=record['body'];data=record['data']
                if op=='begin':return self.treasury.begin(c,day)
                if op=='prepare':return self.treasury.prepare(c,data['artifact'],day)
                if op=='release':return self.treasury.release(c,day)
                if op=='reinvest':return self.treasury.reinvest(c,data['artifact'],day)
                if op=='refund':return self.treasury.refund(c,day)
                raise ValueError('UNKNOWN_PENDING_EFFECT_REQUIRES_RECONCILIATION')
            self.state.effect(row['id'],req,finish)

    def step(self):
        self._open()
        self._recover_effects()
        if self.state.paused():return False
        # Never advance the financial clock past an unresolved effect.
        with self.state.db() as db:pending=db.execute("SELECT COUNT(*) FROM effects WHERE status='PENDING'").fetchone()[0]
        if not pending:self.state.tick()
        day=self.state.day()
        if not pending:self.treasury.advance(day)
        if day%self.policy['sources_every_ticks']==0 and not pending:self._sources()
        for row in self.state.pending():
            if self._advance_one(row):return True
        return False

    def run(self,*,watch=False,poll=1.0,max_ticks=None,stop=None):
        if type(poll) not in (int,float) or not __import__('math').isfinite(poll) or poll<0.001:raise ValueError('POSITIVE_FINITE_POLL_REQUIRED')
        ticks=0
        with self.state.lock():
            self._open();self._recover_effects();self.state.recover()
            try:
                while stop is None or not stop.is_set():
                    if max_ticks is not None and ticks>=max_ticks:break
                    self.step();ticks+=1
                    if not watch and (not self.state.pending() or self.state.paused()):break
                    if watch:time.sleep(poll)
                return self.report()
            finally:self.close()

    def report(self):
        self._open();record=self.treasury.export();save(self.root/'native-export.json',record)
        return {'implementation':'ALPHA Economic Engine 0.2.0','scope':'SIMULATED_COMMERCE_REAL_INSTRUMENT_EXECUTION',
                'state':self.state.summary(),'operating_audit':self.state.audit(),'native_audit':self.treasury.audit(),
                'native_summary':record['ledger']['summary'],'funding':[{'id':e['request']['id'],'funding':e['receipt']['funding'],'amount_microUSD':e['request']['amount']} for e in record['connected_journal']['entries'] if e['request']['operation']=='spend' and e['status']=='COMPLETE'],
                'agent_status':self.agent.status(),'actual_customers_observed':0,'actual_collections':0,
                'actual_complete_cost_profit':None,'actual_host_and_model_billing':'UNMEASURED',
                'autonomous_general_invention':'NOT_ESTABLISHED','live_financial_authority':'NOT_GRANTED'}
