"""One fully source-bound *simulated* native-account turn, plus a different successor.

First: deliver and check an invoice-payment reconciliation for a synthetic buyer.
Second: fund and independently check a synthetic multi-building storage plan.
This executes no real sale, controls no electrical equipment, and proves no new
market, superior inventor, or real safety qualification.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil

from adaptive_enterprise import instruments as substrate
from adaptive_enterprise.checkers import audit_delivery
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal
from commercial.ledger import canonical
from . import power, independent

ROOT=Path(__file__).resolve().parents[2]
CENT=10_000  # cents -> microUSD
OPENING=500 * 1_000_000
CONTRACT='genesis-turn001-synthetic-native-v1'
PRICE=6500
PRE_COSTS={'setup':1200,'production':900,'payment_fee':200,'verification':500,'maintenance':400}
TAX_BPS=2000
SUCCESSOR=1800


def _save(path,obj):
    Path(path).write_bytes(canonical(obj)+b'\n')


def run(out,stress='central'):
    if stress not in ('central','no_demand','failed_acceptance'):
        raise ValueError('REGISTERED_STRESS_ONLY')
    out=Path(out).absolute()
    if out.exists() or any(p.is_symlink() for p in out.parents):
        raise ValueError('NEW_REGULAR_ACCOUNT_PATH_REQUIRED')
    out.mkdir(parents=True)
    runtime=out/'runtime'
    for name in sorted(set(SOURCE_PATHS)|set(substrate.SOURCE_PATHS)):
        dst=runtime/name;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,dst)
    manifest=substrate.prepare_services(runtime,'services',cohort_seed=392900,jobs_per_service=32)
    _save(out/'MANIFEST.json',manifest)
    jobs=[j for j in manifest['jobs'] if j['service_id']=='reconciliation']
    if not jobs:raise ValueError('NO_QUALIFIED_SOURCE_JOB')
    job=jobs[0]
    raw=json.loads((runtime/job['input']).read_text())
    source_sha=power.digest(raw)
    accepted=False
    native_summary=None;funding=None;successor_plan=None
    checks=[]; first_artifact=None
    with JournalAccount(runtime,manifest,out/'account.sqlite',opening=OPENING,working=0,contract=CONTRACT) as account:
        spend=account.spend('turn001-setup','setup',PRE_COSTS['setup']*CENT,0,
                 {'scope':'SYNTHETIC','source':source_sha},1,allow_seed=True)
        if spend is None:raise ValueError('UNFUNDED_INITIAL_WORK')
        before_offer=account.snapshot()['summary']
        # Buyer choices are an *authored simulation*: no invented human consent.
        buyer_value=9000 if stress!='no_demand' else 5000
        buyer_budget=10000
        outside_utility=1800
        buyer_would_accept=(buyer_value-PRICE)>outside_utility and PRICE<=buyer_budget
        if buyer_would_accept:
            account.execute('wallet',{'buyer':'SIM-TURN001-BUYER','amount':buyer_budget*CENT},1)
            account.execute('offer',{'id':'turn001-order','buyer':'SIM-TURN001-BUYER',
                'price':PRICE*CENT,'job_id':job['id'],'deadline':6},1)
            for action in ('consent','fund'):
                account.execute('event',{'id':'turn001-order','action':action,'event_id':'turn001-'+action},1)
            if account.spend('turn001-production','production_contract',PRE_COSTS['production']*CENT,1,
                   {'scope':'SYNTHETIC','job_id':job['id'],'source':source_sha},1,allow_seed=True) is None:
                raise ValueError('UNFUNDED_FIRST_DELIVERY')
            first_artifact=substrate.produce(raw,'generated_schema',mode='conventional')
            if stress=='failed_acceptance':first_artifact['outcome_scope']='intake_readiness'
            account.cost('turn001-verification',PRE_COSTS['verification']*CENT,2)
            checks.append(audit_delivery('reconciliation',raw,first_artifact))
            reference=json.loads((runtime/job['artifact']).read_text())
            equivalent=substrate._semantics(first_artifact)==substrate._semantics(reference)
            accepted=checks[-1]['accepted'] and first_artifact['outcome_scope']=='complete_outcome' and equivalent
            if accepted:
                account.cost('turn001-payment-fee',PRE_COSTS['payment_fee']*CENT,2)
                for action in ('prepare','release'):
                    account.execute('event',{'id':'turn001-order','action':action,'event_id':'turn001-'+action},2)
            else:
                account.execute('event',{'id':'turn001-order','action':'refund','event_id':'turn001-refund'},2)
        account.cost('turn001-maintenance',PRE_COSTS['maintenance']*CENT,3)
        tax=0;earned=0
        if accepted:
            pretax=PRICE-sum(PRE_COSTS.values())
            tax=pretax*TAX_BPS//10000
            account.cost('turn001-model-tax',tax*CENT,3)
            earned=pretax-tax
        before_successor=account.snapshot()['summary']
        if accepted:
            funding=account.spend('turn001-successor','instrument',SUCCESSOR*CENT,4,
                 {'scope':'SYNTHETIC_RESEARCH','from_first_delivery_sha256':power.digest(first_artifact),
                  'destination':'distinct shared-storage feasibility','not_field_certified':True},
                 1,allow_seed=False)
            if funding is None or funding['funding']!='EARNED':
                raise ValueError('EARNED_FUNDED_SUCCESSOR_REQUIRED')
            # A retained source-integrity/independent-checker *method* is adapted
            # to energy units and allocation. This is authored transfer, NOT
            # measured superiority of a self-improving discovery policy.
            energy_data=power.scenario()
            successor_plan=power.solve(energy_data)
            if not independent.accept_power(energy_data,successor_plan):
                raise ValueError('SUCCESSOR_NOT_INDEPENDENTLY_ACCEPTED')
        native_summary=account.snapshot()['summary']
        audited=account.audit()
        exported=account.export()
        _save(out/'NATIVE_EXPORT.json',exported)  # keep local; do not upload private authority
        money=None
        if accepted:
            money={'price_cents':PRICE,'pre_successor_costs_cents':list(PRE_COSTS.values()),
                   'tax_rate_basis_points':TAX_BPS,'tax_cents':tax,
                   'earned_before_successor_cents':earned,'successor_cost_cents':SUCCESSOR,
                   'net_after_successor_cents':earned-SUCCESSOR,'actual_customer_receipts_cents':0}
            independent.accept_cents(money)
        report={'schema':'genesis-turn001/native/v1', 'scenario':stress,
              'source_sha256':source_sha,'model_buyer_value_cents':buyer_value,
              'model_buyer_budget_cents':buyer_budget,'model_buyer_outside_utility_cents':outside_utility,
              'model_buyer_would_accept':buyer_would_accept,
              'first_accepted':accepted,'first_artifact_sha256':power.digest(first_artifact) if first_artifact else None,
              'checker_acceptances':[c['accepted'] for c in checks],
              'first_reference_equivalent':equivalent if buyer_would_accept else None,
              'pre_offer_unrestricted_earned_microUSD':before_offer['unrestrictedEarned'],
              'pre_successor_unrestricted_earned_microUSD':before_successor['unrestrictedEarned'],
              'successor_funded_from':funding['funding'] if funding else None,
              'successor_plan':successor_plan,'successor_source':power.scenario() if successor_plan else None,
              'simulated_profit_after_r_and_d_cents':money['net_after_successor_cents'] if money else None,
              'modeled_cash':money,'native_summary':native_summary,
              'native_audit_passed':True,
              'actual_customer_receipts_cents':0,'real_buyer_acceptance':False,
              'physical_safety_qualified':False,'real_cross_domain_discovery_advantage':False,
              'scope':'Native SIMULATED sale, real executed software and independent artifact checks; second opportunity is research-only energy allocation, not a real microgrid or field battery certification.'}
        if not audited:raise ValueError('NATIVE_AUDIT_FAILED')
        _save(out/'REPORT.json',report)
    return report


def audit(out):
    out=Path(out).absolute()
    report=json.loads((out/'REPORT.json').read_text())
    manifest=json.loads((out/'MANIFEST.json').read_text())
    exported=json.loads((out/'NATIVE_EXPORT.json').read_text())
    checked=audit_journal(exported,root=out/'runtime',manifest=manifest)
    if not checked:raise ValueError('NATIVE_JOURNAL_REJECTED')
    if report['successor_plan']:
        assert independent.accept_power(report['successor_source'],report['successor_plan'])
        assert independent.accept_cents(report['modeled_cash'])
        assert report['successor_funded_from']=='EARNED' and report['first_accepted']
        assert report['pre_offer_unrestricted_earned_microUSD'] < SUCCESSOR*CENT
        assert report['pre_successor_unrestricted_earned_microUSD'] >= SUCCESSOR*CENT
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('run','audit'))
    parser.add_argument('--output',required=True)
    parser.add_argument('--stress',default='central',choices=('central','no_demand','failed_acceptance'))
    args=parser.parse_args()
    if args.action=='run':
        result=run(args.output,args.stress)
        print(json.dumps({k:result[k] for k in ('scenario','first_accepted','successor_funded_from','simulated_profit_after_r_and_d_cents','actual_customer_receipts_cents')},sort_keys=True))
    else:
        print(json.dumps({'audit_passed':audit(args.output)}))

if __name__=='__main__':main()
