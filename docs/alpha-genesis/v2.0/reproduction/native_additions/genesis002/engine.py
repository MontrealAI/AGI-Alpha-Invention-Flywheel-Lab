"""Resume-safe frontier portfolio to actual artifacts and native simulated receipts.

Prices, buyers, budgets and resource tariffs are authored scenarios. Actual code
executes on synthetic source records. No paid provider or real transaction exists.
"""
from __future__ import annotations
import copy
import os
from pathlib import Path
import time
from .backend import Backend
from .common import canonical, digest, package_identity, read, write, integer
from .decision import validate, select, startup_screen
from .routing import qualify, learn_and_test

CENT = 10_000
STRESSES = ('central', 'no_demand', 'failed_acceptance', 'payment_failure')
AUTHORITY_SUFFIXES = ('.actions.jsonl', '.adaptive-simulation-key', '.connected-journal.json')


def checked_directory(path):
    out = Path(os.path.abspath(path))
    if any(p.is_symlink() for p in (out, *out.parents)):
        raise ValueError('SYMLINK_OUTPUT_REFUSED')
    if out.exists() and not out.is_dir():
        raise ValueError('OUTPUT_DIRECTORY_REQUIRED')
    return out


def effective_config(original, stress):
    c = copy.deepcopy(original)
    if stress == 'no_demand':
        for offer in c['offers']:
            offer['buyer_value_cents'] = 0
    return c


def require_authority(out):
    if any(p.name != 'account.sqlite.writer.lock' for p in out.glob('account.sqlite*')) or (out/'REPORT.json').exists():
        for suffix in AUTHORITY_SUFFIXES:
            path = out / ('account.sqlite' + suffix)
            if not path.is_file() or path.is_symlink():
                raise ValueError('EXISTING_ACCOUNT_AUTHORITY_MISSING_NO_RESEED')


def _spend(account, ident, kind, cents, day, work, expected_net, allow_seed):
    if cents == 0:
        account.cost(ident + '-zero', 0, day)
        return {'funding': 'NO_RESOURCE_SPEND', 'amount_microUSD': 0}
    receipt = account.spend(ident, kind, cents * CENT, day, work, expected_net * CENT, allow_seed=allow_seed)
    if receipt is None:
        raise ValueError('UNFUNDED_ACTION:' + ident)
    return receipt


def _job(manifest, sid, ordinal):
    # Fixed distinct inputs, not cherry-picking acceptance after producing an answer.
    index = 8 + ordinal + ordinal // 7
    jobs = [j for j in manifest['jobs'] if j['service_id'] == sid]
    return jobs[index]


def run(repo, output, config=None, *, stress='central', resume=False, max_cycles=None):
    if stress not in STRESSES:
        raise ValueError('UNKNOWN_STRESS')
    if max_cycles is not None:
        integer(max_cycles, 'max_cycles', 1)
    out = checked_directory(output)
    backend = Backend(Path(repo))
    source = {'native': backend.identity(), 'genesis': package_identity()}
    if not resume:
        validate(config)
        if startup_screen(config)['action']!='QUALIFY_CANDIDATE':
            raise ValueError('NO_JUSTIFIED_STARTUP_IN_DECLARED_FINITE_MODEL')
        out.mkdir(parents=True, exist_ok=False)
        contract = {'schema': 'genesis002/contract/v1', 'configuration': config,
                    'stress': stress, 'source': source,
                    'evidence_role': 'FINITE_AUTHORED_INTEGRATION',
                    'source_cost_basis': 'AUTHORED_PREPAID_RESOURCE_ENVELOPES; actual host/model bills unknown',
                    'external_authority': 'NONE'}
        write(out/'CONTRACT.json', contract, immutable=True)
    else:
        contract = read(out/'CONTRACT.json')
        if contract['source'] != source:
            raise ValueError('EXECUTING_SOURCE_CHANGED')
        if config is not None and config != contract['configuration']:
            raise ValueError('REGISTERED_CONFIGURATION_CHANGED')
        if stress != contract['stress']:
            raise ValueError('REGISTERED_STRESS_CHANGED')
        config = contract['configuration']
        validate(config)
        require_authority(out)
    c = effective_config(config, stress)
    runtime = out/'runtime'
    if not (out/'MANIFEST.json').exists():
        if runtime.exists() or (out/'bootstrap').exists():
            raise ValueError('INCOMPLETE_PREACCOUNT_BOOTSTRAP_REQUIRES_INSPECTION')
        stage = out/'bootstrap'
        stage.mkdir()
        manifest = backend.prepare(stage, config['cohort_seed'], config['cycles'])
        os.rename(stage, runtime)
        write(out/'MANIFEST.json', manifest, immutable=True)
    manifest = read(out/'MANIFEST.json')
    started_cpu, started_wall = time.process_time(), time.monotonic()
    account = backend.account(runtime, manifest, out, config)
    try:
        if (out/'REPORT.json').exists():
            prior = read(out/'NATIVE_EXPORT.json')
            if account.export() != prior:
                raise ValueError('COMPLETED_ACCOUNT_CHANGED_NO_SILENT_CONTINUATION')
            from .audit import audit
            audit(repo, out)
            return read(out/'REPORT.json')
        base_work = {'contract_sha256': digest(contract), 'source_sha256': digest(source)}
        _spend(account,'g2-setup','setup',config['setup_cents'],0,base_work,1,True)
        _spend(account,'g2-discovery','discovery',config['discovery_cents'],0,base_work,1,True)
        if (out/'QUALIFICATION.json').exists():
            qualification = read(out/'QUALIFICATION.json')
        else:
            qualification = qualify(backend.substrate,backend.checker,c['methods'],c['cohort_seed'])
            write(out/'QUALIFICATION.json',qualification,immutable=True)
        account.cost('g2-freeze-'+digest({'contract':contract,'qualification':qualification})[:32],0,0)
        completed_now = 0
        for ordinal in range(c['cycles']):
            record_path = out/'episodes'/f'{ordinal:06d}.json'
            if record_path.exists():
                continue
            intent_path = out/'intents'/f'{ordinal:06d}.json'
            day = 2 + ordinal * 3
            if intent_path.exists():
                intent = read(intent_path)
            else:
                snapshot = account.snapshot()
                summary = snapshot['summary']
                decision = select(c,available_cents=summary['available']//CENT,
                    earned_cents=summary['unrestrictedEarned']//CENT,earned_only=ordinal>0 and c['continuation_funding_policy']=='EARNED_ONLY',
                    qualification=qualification)
                chosen = decision['selected']
                job = _job(manifest,chosen['service_id'],ordinal) if chosen else None
                intent = {'ordinal':ordinal,'day':day,'before_sequence':snapshot['sequence'],
                          'before':summary,'decision':decision,'job':job}
                write(intent_path,intent,immutable=True)
            chosen = intent['decision']['selected']
            record = {'intent_sha256':digest(intent),'ordinal':ordinal,'day':day,
                      'status':'NONENTRY','artifact':None,'funding':None}
            if chosen is not None:
                work = {**base_work,'intent_sha256':digest(intent)}
                acq = _spend(account,f'g2-acquire-{ordinal}','acquisition',c['acquisition_cents'],day,
                             work,chosen['contribution_cents'],ordinal==0 or c['continuation_funding_policy']=='AVAILABLE_NATIVE_CASH')
                record['acquisition_funding'] = acq
                if stress == 'payment_failure':
                    record['status']='NO_PAYMENT'
                else:
                    offer = next(o for o in c['offers'] if o['id']==chosen['offer_id'])
                    job = intent['job']; raw = read(runtime/job['input'])
                    buyer, ident = f'SIM-g2-buyer-{ordinal}', f'g2-order-{ordinal}'
                    account.execute('wallet',{'buyer':buyer,'amount':offer['buyer_budget_cents']*CENT},day)
                    account.execute('offer',{'id':ident,'buyer':buyer,'price':chosen['price_cents']*CENT,
                        'job_id':job['id'],'deadline':day+5},day)
                    for action in ('consent','fund'):
                        account.execute('event',{'id':ident,'action':action,'event_id':ident+'-'+action},day)
                    production = chosen['complete_cost_cents']-chosen['fee_cents']-c['acquisition_cents']
                    paid = _spend(account,f'g2-produce-{ordinal}','production',production,day,
                                  work,chosen['contribution_cents'],ordinal==0 or c['continuation_funding_policy']=='AVAILABLE_NATIVE_CASH')
                    artifact_path = out/'deliveries'/f'{ordinal:06d}.json'
                    if artifact_path.exists():
                        delivery = read(artifact_path)
                    else:
                        artifact = backend.substrate.produce(raw,'generated_schema',mode=chosen['adapter'])
                        if stress=='failed_acceptance':
                            artifact['outcome_scope']='intake_readiness'
                        check = backend.checker(job['service_id'],raw,artifact)
                        reference = read(runtime/job['artifact'])
                        equivalent = backend.substrate._semantics(reference)==backend.substrate._semantics(artifact)
                        delivery = {'artifact':artifact,'check':check,'admitted_outcome_equal':equivalent,
                                    'input_sha256':digest(raw)}
                        write(artifact_path,delivery,immutable=True)
                    # An actual-production anchor supplements, not replaces, the legacy native contract.
                    account.cost(f'g2-output-{ordinal}-'+digest(delivery)[:32],0,day)
                    accepted = delivery['check']['accepted'] is True and delivery['admitted_outcome_equal'] and delivery['artifact']['outcome_scope']=='complete_outcome'
                    if accepted:
                        account.cost(f'g2-fee-{ordinal}',chosen['fee_cents']*CENT,day)
                        actions = ('prepare','release')
                        record['status']='SETTLED'
                    else:
                        actions = ('refund',)
                        record['status']='REFUNDED'
                    for action in actions:
                        account.execute('event',{'id':ident,'action':action,'event_id':ident+'-'+action},day+1)
                    record.update(artifact=digest(delivery),funding=paid,native_order_id=ident)
            record['after'] = account.snapshot()
            write(record_path,record,immutable=True)
            completed_now += 1
            if max_cycles is not None and completed_now>=max_cycles and ordinal+1<c['cycles']:
                write(out/'PROGRESS.json',{'complete':False,'completed_cycles':ordinal+1,
                    'configuration_sha256':digest(config),'native_sequence':account.snapshot()['sequence']})
                return {'complete':False,'completed_cycles':ordinal+1,'scope':'SIMULATED'}
        final_day = 3*c['cycles']+3
        episodes = [read(out/'episodes'/f'{i:06d}.json') for i in range(c['cycles'])]
        revenue = sum(read(out/'intents'/f'{r["ordinal"]:06d}.json')['decision']['selected']['price_cents']
                      for r in episodes if r['status']=='SETTLED')
        pretax_cost = config['setup_cents']+config['discovery_cents']
        for r in episodes:
            chosen = read(out/'intents'/f'{r["ordinal"]:06d}.json')['decision']['selected']
            if chosen is None: continue
            pretax_cost += c['acquisition_cents']
            if r['status'] in ('SETTLED','REFUNDED'):
                pretax_cost += chosen['complete_cost_cents']-chosen['fee_cents']-c['acquisition_cents']
            if r['status']=='SETTLED': pretax_cost += chosen['fee_cents']
        modeled_tax = max(0,revenue-pretax_cost)*c['tax_bps']//10_000
        account.cost('g2-modeled-tax',modeled_tax*CENT,final_day)
        research_path = out/'RESEARCH_DECISION.json'
        if research_path.exists():
            research_decision = read(research_path)
        else:
            snapshot = account.snapshot()
            amount = c['successor_research_cents']
            eligible = (amount>0 and c['successor_expected_benefit_cents']>amount and
                        min(snapshot['summary']['available'],snapshot['summary']['unrestrictedEarned'])>=amount*CENT)
            research_decision = {'conduct':eligible,'before':snapshot,
                'cost_cents':amount,'expected_benefit_cents':c['successor_expected_benefit_cents'],
                'valuation_basis':'AUTHORED_EXPERIMENT_OPTION_VALUE_NOT_REVENUE',
                'scope':'Research funding only, no guaranteed gain or deployment authority.'}
            write(research_path,research_decision,immutable=True)
        research = None
        if research_decision['conduct']:
            amount = c['successor_research_cents']
            funding = _spend(account,'g2-successor','research',amount,final_day,
                {**base_work,'decision_sha256':digest(research_decision)},
                c['successor_expected_benefit_cents']-amount,False)
            if (out/'ROUTING_STUDY.json').exists():
                study = read(out/'ROUTING_STUDY.json')
            else:
                study = learn_and_test(backend.substrate,backend.checker,c['cohort_seed']+100)
                write(out/'ROUTING_STUDY.json',study,immutable=True)
            research = {'funding':funding,'study_sha256':digest(study),'decision':study['decision']}
            account.cost('g2-study-'+digest(study)[:32],0,final_day)
        exported = account.export()
        write(out/'NATIVE_EXPORT.json',exported,immutable=True)
        result = {'schema':'genesis002/result/v1','complete':True,'scope':'SIMULATED_NATIVE_ACCOUNT',
            'contract_sha256':digest(contract),'source':source,'stress':stress,'cycles':c['cycles'],
            'settled':sum(r['status']=='SETTLED' for r in episodes),
            'refunded':sum(r['status']=='REFUNDED' for r in episodes),
            'nonentry':sum(r['status']=='NONENTRY' for r in episodes),
            'no_payment':sum(r['status']=='NO_PAYMENT' for r in episodes),
            'modeled_revenue_cents':revenue,'modeled_operating_cost_cents':pretax_cost,
            'modeled_tax_cents':modeled_tax,'modeled_research_cost_cents':c['successor_research_cents'] if research else 0,
            'modeled_profit_cents':revenue-pretax_cost-modeled_tax-(c['successor_research_cents'] if research else 0),
            'native_summary':account.snapshot()['summary'],'native_export_sha256':digest(exported),
            'native_audit':account.audit(),'research':research,'actual_revenue_usd':0,
            'complete_actual_lifecycle_cost':'UNMEASURED','blue_sky_breakthrough':'NOT_ESTABLISHED',
            'autonomous_frontier_model_campaign':'NOT_EXECUTED',
            'external_model_calls':0,'meta_discovery_superiority':'NOT_ESTABLISHED'}
        if source != {'native':backend.identity(),'genesis':package_identity()}:
            raise ValueError('SOURCE_CHANGED_DURING_OPERATION')
        write(out/'REPORT.json',result,immutable=True)
        write(out/'RESOURCE_RECEIPT.json',{'invocation_process_cpu_seconds':time.process_time()-started_cpu,
            'invocation_wall_seconds':time.monotonic()-started_wall,
            'scope':'This invocation only; not entire development cost or actual billing.'})
    finally:
        account.close()
    from .audit import audit
    audit(repo,out)
    from .report import render
    (out/'OPEN_ME.html').write_text(render(out),encoding='utf-8')
    return result
