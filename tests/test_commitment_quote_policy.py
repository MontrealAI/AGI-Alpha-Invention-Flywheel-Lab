"""Frozen public information and native execution checks; no real commerce."""
import copy
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from research.commitment_quote_policy import decide, SCHEMA
from campaign.genesis_commitment001 import service
from campaign.genesis_commitment001.delivery import default_requests, produce
from campaign.genesis_commitment001.native import BusinessAccount
from connected_enterprise.finance import SOURCE_PATHS, audit_journal

USD = 1_000_000
ROOT = Path(__file__).resolve().parents[1]


def public_observation():
    return {'schema': SCHEMA, 'now_hour': 1, 'acceptance_id': 'restore-17-v1',
            'friction_microUSD': 100*USD, 'non_tax_cost_microUSD': 1950*USD,
            'tax_numerator':1,'tax_denominator':5,'tax_deduction_before_closing_microUSD':1850*USD,
            'minimum_contribution_microUSD': 1, 'tick_microUSD': 10_000,
            'alternatives': [
                {'source_id': 'AUTHORED-'+name, 'acceptance_id': 'restore-17-v1',
                 'price_microUSD': price*USD, 'observed_hour': 0,
                 'valid_until_hour': 2, 'complete': True}
                for name, price in [('human',4000),('human-ai',3300),
                                    ('autonomous',3200),('self-service',3100)]]}


class QuotePolicyTests(unittest.TestCase):
    def test_central_public_quote_and_strong_direct_tie(self):
        obs = public_observation(); before = copy.deepcopy(obs)
        result = decide(obs)
        direct = min(q['price_microUSD'] for q in obs['alternatives']) - 100*USD - 10_000
        self.assertEqual(result['price_microUSD'], direct)
        self.assertEqual(direct, 2_999_990_000)
        self.assertEqual(result['planned_contribution_microUSD'], 819_992_000)
        self.assertFalse(result['spend_authorized'])
        self.assertEqual(obs, before)

    def test_exhaustive_independent_integer_oracle(self):
        for outside, friction, cost, tick in itertools.product(range(1,41),range(6),range(36),(1,2,3,5)):
            obs = public_observation()
            obs.update(friction_microUSD=friction, non_tax_cost_microUSD=cost, tick_microUSD=tick,
                       tax_numerator=0,tax_deduction_before_closing_microUSD=0)
            obs['alternatives'] = [obs['alternatives'][0]]
            obs['alternatives'][0]['price_microUSD'] = outside
            feasible = [p for p in range(tick,outside+1,tick) if p+friction<outside and p-cost>=1]
            result = decide(obs)
            self.assertEqual(result['price_microUSD'], max(feasible) if feasible else None,
                             (outside,friction,cost,tick))

    def test_no_economic_universal_integer_ceiling(self):
        obs=public_observation(); obs['alternatives']=[obs['alternatives'][0]]
        obs['alternatives'][0]['price_microUSD']=10**60+3
        obs.update(friction_microUSD=0,tick_microUSD=7,non_tax_cost_microUSD=10**40)
        result=decide(obs); price=result['price_microUSD']
        self.assertEqual(price % 7,0)
        self.assertLess(price,10**60+3)
        self.assertGreaterEqual(price+7,10**60+3)

    def test_missing_stale_incomplete_or_incomparable_abstains(self):
        variants=[]
        for key,value in [('complete',False),('valid_until_hour',0),
                          ('observed_hour',2),('acceptance_id','different-outcome')]:
            obs=public_observation();obs['alternatives'][0][key]=value;variants.append(obs)
        obs=public_observation();obs['alternatives']=[];variants.append(obs)
        for obs in variants:
            self.assertEqual(decide(obs)['action'],'ABSTAIN')

    def test_unprofitable_quote_abstains(self):
        obs=public_observation();obs['non_tax_cost_microUSD']=3000*USD
        self.assertEqual(decide(obs)['action'],'ABSTAIN')

    def test_hidden_fields_and_invalid_exact_inputs_refused(self):
        for key in ('scenario','buyer_value','buyer_budget','future_shock','future_collections'):
            obs=public_observation();obs[key]='PRIVATE'
            with self.assertRaisesRegex(ValueError,'PUBLIC_OBSERVATION_FIELDS'):decide(obs)
        for value in (True,-1,1.5,'1'):
            obs=public_observation();obs['non_tax_cost_microUSD']=value
            with self.assertRaises(ValueError):decide(obs)
        for field in ('tick_microUSD','minimum_contribution_microUSD'):
            obs=public_observation();obs[field]=0
            with self.assertRaises(ValueError):decide(obs)
        obs=public_observation();obs['alternatives'].append(copy.deepcopy(obs['alternatives'][0]))
        with self.assertRaisesRegex(ValueError,'UNIQUE_QUOTE'):decide(obs)

    def test_provisional_tax_prevents_false_break_even_admission(self):
        obs=public_observation();obs['alternatives'][-1]['price_microUSD']=2050_020000
        self.assertEqual(decide(obs)['action'],'ABSTAIN')

    def test_fresh_tax_confirmation_matches_exhaustive_ordinary_pricing(self):
        # Prospectively fixed in F02_ADDENDUM.md, not selected by outcome.
        for outside,numerator,denominator in [(205543,1,4),(270717,2,5),(361286,1,3)]:
            obs=public_observation();obs['alternatives']=[obs['alternatives'][0]]
            obs['alternatives'][0]['price_microUSD']=outside
            obs.update(friction_microUSD=10000,non_tax_cost_microUSD=195000,
                       tax_deduction_before_closing_microUSD=185000,
                       tax_numerator=numerator,tax_denominator=denominator,tick_microUSD=1)
            feasible=[p for p in range(1,outside) if p+10000<outside and
                      p-195000-max(0,p-185000)*numerator//denominator>=1]
            self.assertEqual(decide(obs)['price_microUSD'],max(feasible) if feasible else None)


def execute_native_arm(arm, evidence_dir=None):
    """Disposable engineering fixture; never an existing enterprise account."""
    obs=public_observation()
    prices={'fixed':3000*USD,
            'ordinary':min(q['price_microUSD'] for q in obs['alternatives'])-obs['friction_microUSD']-obs['tick_microUSD'],
            'constructor':decide(obs)['price_microUSD']}
    price=prices[arm]
    # Only the environment sees valuation and budget; these never enter decide().
    value,budget,outside_utility=4300*USD,3500*USD,900*USD
    outside=max(outside_utility,max(value-q['price_microUSD'] for q in obs['alternatives']),0)
    buys=budget>=price and value-price-obs['friction_microUSD']>outside
    with tempfile.TemporaryDirectory(prefix='quote-native-fixture-') as temp:
        home=Path(temp);source=home/'source'
        for name in sorted(set(SOURCE_PATHS)|set(service.source_paths(ROOT))):
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
        requests=default_requests()
        requests[0]['records']=[{'account_id':'fresh-'+str(i),'name':'Synthetic '+str(i),
                                'balance_cents':1700+i*137} for i in range(17)]
        manifest=service.prepare_manifest(source,[{'id':r['id'],'request':r,
            'delivery_path':service.DELIVERIES+r['id']+'.json'} for r in requests])
        suppliers={'shared-worker':{'units':1,'consent':'AUTHORED_SIMULATED_ACCEPTANCE',
                                   'common_dependency':'fixture-host'}}
        with BusinessAccount(source,manifest,home/'account.sqlite',
                             contract='public-quote-fixture-'+arm,suppliers=suppliers) as business:
            account=business.account
            for ident,cost in [('setup',880),('acquisition',100)]:
                account.cost('quote-'+ident,cost*USD,0 if ident=='setup' else 1)
            before_successor=None;accepted=False;tamper_rejected=None;prepaid=None
            if buys:
                work={'capacity':{'supplier':'shared-worker','start':4,'end':8,'units':1},
                      'costs':{'complete-first-production':840*USD},'expected_net':1,
                      'job':'restore-first','order':'first','buyer':'buyer-first'}
                prepaid=business.reserve_delivery('capacity-first',840*USD,3,work,allow_seed=True)
                if prepaid is None:raise AssertionError('native reservation refused')
                business.begin('restore-first','first','buyer-first',price,budget,3,10,18)
                artifact=produce(requests[0],method='direct' if arm=='ordinary' else 'retained')
                receipt=business.deliver('restore-first','first',artifact,7);accepted=receipt['accepted']
                if not accepted:raise AssertionError('independent acceptance failed')
                broken=copy.deepcopy(artifact);broken['request_id']='wrong'
                tamper_rejected=not service.verify_delivery(source,manifest,'restore-first',broken)['accepted']
                business.event('first','release',10);account.cost('payment',30*USD,10)
                tax=max(0,account.snapshot()['summary']['profit'])//5
                account.cost('tax-first',tax,10);account.advance_financial(19)
                before_successor=copy.deepcopy(account.snapshot()['summary'])
                original=account.export()
                # This is a decision, never an attempted partial commission.
                if min(before_successor['available'],before_successor['unrestrictedEarned'])>=990*USD:
                    raise AssertionError('registered expected deferral contradicted')
                if account.export()!=original:raise AssertionError('decision wrote financial state')
            account.cost('closing',100*USD,120)
            record=account.export();audit=audit_journal(record,root=source,manifest=manifest)
            result={'arm':arm,'price_microUSD':price,'buyer_buys':buys,'accepted':accepted,
                    'tamper_rejected':tamper_rejected,'prepaid':prepaid is not None,
                    'summary':record['ledger']['summary'],'before_successor':before_successor,
                    'successor_budget_microUSD':990*USD,'successor_funded':False,
                    'seed_can_fund_successor':bool(before_successor and before_successor['available']>=990*USD),
                    'audit_accepted':audit['accepted'],'scope':'DISPOSABLE_AUTHORED_ENGINEERING_FIXTURE',
                    'actual_revenue_microUSD':0,'trailing_365_profit':None,
                    'tax_basis':'20 percent provision at first collection; no subsequent negative-tax credit assumed'}
            if evidence_dir is not None:
                dest=Path(evidence_dir);dest.mkdir(parents=True,exist_ok=False)
                paths=sorted(set(SOURCE_PATHS)|set(service.source_paths(ROOT)))
                sources={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}
                packet={'result':result,'public_observation':obs,'manifest':manifest,
                        'native_export':record,'source_hashes':sources,
                        'delivered':{str(path.relative_to(source)):json.loads(path.read_bytes())
                                     for path in (source/service.DELIVERIES).glob('*.json')}}
                raw=json.dumps(packet,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
                (dest/'PUBLIC.json.gz').write_bytes(gzip.compress(raw,mtime=0))
            return result


class NativeQuoteTests(unittest.TestCase):
    def test_all_frozen_arms_and_complete_successor_deferral(self):
        results=[execute_native_arm(arm) for arm in ('fixed','ordinary','constructor')]
        fixed,ordinary,constructed=results
        self.assertFalse(fixed['buyer_buys'])
        self.assertEqual(fixed['summary']['profit'],-1080*USD)
        for result in results:self.assertTrue(result['audit_accepted'])
        for result in (ordinary,constructed):
            self.assertTrue(result['prepaid'] and result['accepted'] and result['tamper_rejected'])
            self.assertEqual(result['before_successor']['profit'],919_992_000)
            self.assertEqual(result['before_successor']['unrestrictedEarned'],919_992_000)
            self.assertEqual(result['summary']['profit'],819_992_000)
            self.assertFalse(result['successor_funded'])
            self.assertTrue(result['seed_can_fund_successor'])
        self.assertEqual(ordinary['summary'],constructed['summary'])

    def test_public_replay_rejects_native_and_presentation_mutations(self):
        from scripts.qualify_commitment_quote import audit_packet
        with tempfile.TemporaryDirectory(prefix='quote-evidence-mutations-') as temp:
            dest=Path(temp)/'honest';execute_native_arm('constructor',dest)
            file=dest/'PUBLIC.json.gz'
            self.assertTrue(audit_packet(file)['accepted'])
            original=json.loads(gzip.decompress(file.read_bytes()))
            mutations=[('result','price_microUSD',1),('result','arm','ordinary'),
                       ('result','successor_budget_microUSD',1),('result','seed_can_fund_successor',False),
                       ('result','actual_revenue_microUSD',1),('result','trailing_365_profit',1),
                       ('result','before_successor',None),('result','successor_funded',True),
                       ('public_observation','friction_microUSD',1)]
            for section,key,value in mutations:
                bad=copy.deepcopy(original);bad[section][key]=value
                mutant=Path(temp)/'mutant.json.gz'
                mutant.write_bytes(gzip.compress(json.dumps(bad).encode(),mtime=0))
                with self.assertRaises(ValueError,msg=(section,key)):audit_packet(mutant)
            bad=copy.deepcopy(original)
            bad['native_export']['ledger']['summary']['profit']+=1
            mutant.write_bytes(gzip.compress(json.dumps(bad).encode(),mtime=0))
            with self.assertRaises(ValueError):audit_packet(mutant)


if __name__=='__main__':unittest.main()
