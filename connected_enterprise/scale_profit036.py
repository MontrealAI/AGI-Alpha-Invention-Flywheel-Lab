"""Source-bound native anchor + existing conditional 60-month aggregate.

This NEVER promotes a hypothetical customer or bundle into a native/real sale,
financial asset or qualified billion-dollar enterprise. No separate ledger.
"""
from __future__ import annotations
import argparse
import calendar
from collections import deque
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from enterprise.scale import default_config, simulate_scale, validate_config
from commercial.ledger import canonical, digest, strict_json

SCHEMA = 'agi-alpha/scale-profit036-protocol/v1'
RESULT = 'agi-alpha/scale-profit036-result/v1'
TARGET_CENTS = 100_000_000_000
OPENING_CENTS = 10_000_000
START = date(2026, 11, 1)
SCOPE = 'NATIVE_ANCHORED_UNCALIBRATED_CONDITIONAL_PROJECTION_NOT_EXECUTED_SCALE'
MAX_STDOUT = 2_000_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_bytes(value):
    return canonical(value)


def identity(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def strict_read(path, limit=1_000_000):
    p = Path(path)
    require(not p.is_symlink() and p.is_file() and p.stat().st_size <= limit, 'REGULAR_BOUNDED_INPUT_REQUIRED')
    return strict_json(p.read_bytes())


def validate_protocol(value):
    require(type(value) is dict and set(value) == {'schema','scope','evidence_role','opening_cents','target_profit_cents','months','seeds','cases','sources','stopping_rule'}, 'EXACT_PROFIT_PROTOCOL_REQUIRED')
    require(value['schema'] == SCHEMA and value['scope'] == 'CONDITIONAL_PROJECTION', 'PROJECTION_NOT_NATIVE_AUTHORITY')
    require(value['evidence_role'] == 'EXPOSED_DEVELOPMENT_WITH_FIXED_NEW_SEEDS', 'DISCLOSE_EXPOSED_SELECTION')
    require(type(value['opening_cents']) is int and value['opening_cents'] == OPENING_CENTS, 'EXACT_USD100000_CAPITAL_REQUIRED')
    require(type(value['target_profit_cents']) is int and value['target_profit_cents'] == TARGET_CENTS, 'ONE_BILLION_PROFIT_NOT_REVENUE')
    require(type(value['months']) is int and value['months'] == 60, 'FROZEN_SIXTY_MONTH_HORIZON')
    seeds = value['seeds']
    require(type(seeds) is list and seeds == [2610313701,2610313702,2610313703,2610313704], 'EXACT_FIXED_NEW_SEED_COHORT_REQUIRED')
    cases = value['cases']
    require(type(cases) is dict and set(cases) == {'low_ticket_incumbent','direct_enterprise','partner_distribution','partner_disrupted','partner_no_referrals'}, 'FIVE_FIXED_COMPARISON_CASES_REQUIRED')
    require(type(value['sources']) is list and 1 <= len(value['sources']) <= 8 and all(type(x) is str and x.startswith('https://') and len(x) <= 512 for x in value['sources']), 'SOURCE_URLS_REQUIRED')
    require(value['stopping_rule'] == 'EXACT_60_MONTHS_ALL_SEEDS_NO_REPLACEMENT_CASH_FAILURE_RETAINED', 'STOPPING_RULE_REQUIRED')
    baseline = default_config()
    for name, changes in cases.items():
        require(type(changes) is dict and set(changes) <= set(baseline) | {'net_settlement_fees','cash_receipt_tax_proxy_bps'}, 'KNOWN_EXISTING_AGGREGATE_PARAMETERS_ONLY')
        cfg = baseline | changes
        require(cfg['months'] == 60 and cfg['opening_cash_cents'] == OPENING_CENTS and cfg['initial_customers'] == 0 and cfg['scope'] == baseline['scope'], 'NO_HIDDEN_CAPITAL_OR_INITIAL_CUSTOMERS')
        require(cfg.get('cash_receipt_tax_proxy_bps') == 2500 and cfg.get('net_settlement_fees') is True, 'COMPLETE_DISCLOSED_SETTLEMENT_COST_SCOPE')
        require(cfg['payment_fee_bps'] > 0 and cfg['refund_probability'] > 0 and cfg['attempt_cost_cents'] > 0 and cfg['acquisition_budget_fraction'] > 0 and cfg['support_per_customer_cents'] > 0 and cfg['fixed_monthly_cost_cents'] > 0, 'NONZERO_COMPLETE_COST_PROXIES_REQUIRED')
        validate_config(cfg)
    return value


def daily_spread(value, days):
    """Conserve exact signed integer cents under a uniform within-month hypothesis."""
    require(type(value) is int and type(days) is int and days >= 28, 'INTEGER_MONTHLY_FLOW_REQUIRED')
    amount = abs(value)
    each, extra = divmod(amount, days)
    sign = -1 if value < 0 else 1
    parts = [sign * (each + (i < extra)) for i in range(days)]
    require(sum(parts) == value, 'FLOW_SPREAD_NOT_CONSERVED')
    return parts


def summarize_existing_projection(config, seed):
    """Exact-day report of the EXISTING aggregate's authored monthly cash model.

    Daily spreading only defines the 365-day observer and creates no sales/events.
    """
    validate_config(config)
    run = simulate_scale(config, seed)
    require(run['scope'] == 'CONDITIONAL_SCALE_PROJECTION' and run['config_sha256'] == identity(config), 'EXISTING_SCALE_SOURCE_REQUIRED')
    profit_window, cash_window = deque(maxlen=365), deque(maxlen=365)
    monthly = []
    prior_profit = prior_cost = prior_collected = 0
    day_offset = 0
    first = None
    peak = None
    for index, row in enumerate(run['monthly']):
        require(row['month'] == index + 1, 'CONTIGUOUS_MONTHLY_LEDGER_REQUIRED')
        cumulative_profit = row['cumulative_profit_cents']
        cumulative_cost = row['cumulative_cost_cents']
        cumulative_collected = row['cumulative_collected_revenue_cents']
        for field in (cumulative_profit, cumulative_cost, cumulative_collected, row['cash_cents'],row['restricted_cash_cents'],row['available_cash_cents']):
            require(type(field) is int, 'INTEGER_CENT_STATE_REQUIRED')
        revenue = cumulative_collected - prior_collected
        cost = cumulative_cost - prior_cost
        increment = cumulative_profit - prior_profit
        require(revenue == row['collected_revenue_cents'] and revenue >= 0 and cost >= 0, 'FLOW_INCREMENT_RECONCILIATION')
        require(row['cash_cents'] == OPENING_CENTS + cumulative_collected - cumulative_cost, 'ACTUAL_FINANCE_IN_AGGREGATE_MISMATCH')
        require(row['available_cash_cents'] == row['cash_cents'] - row['restricted_cash_cents'] and row['available_cash_cents'] >= 0, 'UNRESTRICTED_CASH_RECONCILIATION')
        m_start = date(START.year + (START.month - 1 + index)//12, (START.month - 1 + index)%12+1, 1)
        days = calendar.monthrange(m_start.year,m_start.month)[1]
        cost_parts = daily_spread(cost, days)
        for profit_day, collected_day, cost_day in zip(daily_spread(increment,days),daily_spread(revenue,days),cost_parts):
            profit_window.append(profit_day)
            cash_window.append(collected_day-cost_day)
        day_offset += days
        ttm_profit = sum(profit_window) if day_offset >= 365 else None
        ttm_cash = sum(cash_window) if day_offset >= 365 else None
        achieved = bool(ttm_profit is not None and ttm_profit >= TARGET_CENTS and ttm_cash >= TARGET_CENTS and row['available_cash_cents'] > 0)
        if first is None and achieved:
            first = index + 1
        if ttm_profit is not None:
            peak = ttm_profit if peak is None else max(peak,ttm_profit)
        monthly.append({'month':index+1,'end_date_utc':(m_start+timedelta(days=days-1)).isoformat(),
            'days_covered':day_offset,'active_customers':row['active_customers'],
            'new_activated':row['new_activated'],'collected_work_products':row['collected_projection_jobs'],
            'contacts':row['contacts'],'collected_cents':revenue,'cost_incurred_cents':cost,
            'net_profit_accrued_cents':increment,'ttm_365day_profit_cents':ttm_profit,
            'ttm_365day_cash_contribution_cents':ttm_cash,'available_cash_cents':row['available_cash_cents'],
            'restricted_cash_cents':row['restricted_cash_cents'],'cash_cents':row['cash_cents'],
            'profit_target_attained_under_hypotheses':achieved})
        prior_profit, prior_cost, prior_collected = cumulative_profit,cumulative_cost,cumulative_collected
    require((not monthly or (sum(x['net_profit_accrued_cents'] for x in monthly) == run['cumulative_profit_cents']
              and sum(x['cost_incurred_cents'] for x in monthly) == run['cumulative_cost_cents']
              and sum(x['collected_cents'] for x in monthly) == run['cumulative_collected_revenue_cents'])), 'REPLAY_TOTALS_NOT_CONSERVED')
    return {'seed':seed,'scope':'CONDITIONAL_60_MONTH_AGGREGATE_NOT_NATIVE_EXECUTION',
       'source_model':'enterprise.scale.simulate_scale','source_config_sha256':run['config_sha256'],
       'months_completed':run['months_completed'],'cash_survival':run['cash_survival'],
       'terminal_reason':run['terminal_reason'],'first_attainment_month_under_hypotheses':first,
       'peak_365day_profit_cents':peak,'ending_profit_cents':run['cumulative_profit_cents'],
       'ending_collections_cents':run['cumulative_collected_revenue_cents'],
       'ending_cash_cents':run['ending_cash_cents'],
       'ending_unrestricted_cash_cents':run['ending_unrestricted_cash_cents'],
       'binding_constraints':run['binding_constraints'],'monthly':monthly,
       'source_pricing_and_demands_are_unvalidated':True}


def native_anchor(output, timeout=180):
    """Explicitly trust and RE-EXECUTE the frozen native auditor. No private export."""
    root = Path(output).expanduser().absolute()
    require(root.is_dir() and not any(x.is_symlink() for x in (root,*root.parents)), 'TRUSTED_NORMAL_NATIVE_OUTPUT_REQUIRED')
    for name in ('FROZEN.json','COMPLETE.json','REPORT.json','SERVICES.json'):
        require((root/name).is_file() and not (root/name).is_symlink(), 'COMPLETE_FROZEN_NATIVE_SOURCE_REQUIRED')
    source = root/'source'
    require(source.is_dir() and not source.is_symlink() and 1 <= timeout <= 600, 'BOUNDED_SOURCE_AND_AUDIT_TIMEOUT')
    def run(subcommand):
        proc = subprocess.run([sys.executable,'-m','connected_enterprise',subcommand,'--output',str(root)],cwd=source,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
        require(proc.returncode == 0 and len(proc.stdout) <= MAX_STDOUT, 'CANONICAL_'+subcommand.upper()+'_FAILED')
        return strict_json(proc.stdout)
    audited = run('audit')
    scoreboard = run('scoreboard')
    freeze = strict_read(root/'FROZEN.json')
    report = strict_read(root/'REPORT.json')
    require(audited['accepted'] is True and audited['scope'] == 'NATIVE_FINANCE_AND_OPERATING_SEMANTICS_WITH_ARTIFACT_REEXECUTION_AND_REPORT_REDERIVATION', 'NATIVE_INDEPENDENT_AUDIT_REQUIRED')
    require(audited['source_sha256'] == scoreboard['source_sha256'] == freeze['source']['sha256'] == report['source_sha256'], 'SOURCE_SHA_MISMATCH')
    require(scoreboard['frozen_sha256'] == freeze['sha256'] and scoreboard['report_sha256'] == digest(report), 'FREEZE_OR_REPORT_MISMATCH')
    require(scoreboard['world_count'] == len(scoreboard['businesses']) == audited['worlds'] >= 2, 'MULTIPLE_INDEPENDENT_NATIVE_WORLDS_REQUIRED')
    require(len({b['business_reference'] for b in scoreboard['businesses']}) == len(scoreboard['businesses']), 'DUPLICATE_NATIVE_WORLD')
    worlds=[]
    for b in scoreboard['businesses']:
        state=b['financial_state_microUSD']
        configured_opening = freeze['configs'][b['case']]['opening']
        require(b['complete'] is True and type(configured_opening) is int and configured_opening == OPENING_CENTS*10000 and b['scope'] == 'CONDITIONAL_SIMULATION', 'NO_NATIVE_CAPITAL_TOPUP_OR_INCOMPLETE_WORLD')
        require(state['cash'] == configured_opening + state['collections'] + state['recoveryIncome'] - state['expensePaid'], 'NATIVE_CASH_CONSERVATION')
        require(b['actual_external_commerce']['customers'] == 0 and b['actual_external_commerce']['collections_microUSD'] == 0 and b['trailing_twelve_month_profit_microUSD'] is None, 'NO_ACTUAL_OR_ANNUAL_SHORTCUT')
        worlds.append({'id':b['business_reference'],'arm':b['arm'],'collections_microUSD':state['collections'],
          'profit_microUSD':state['profit'],'available_microUSD':state['available'],
          'settled_orders':b['recorded_counts']['settled_orders'],'verified_deliveries':b['recorded_counts']['completed_work'],
          'native_actions_sha256':b['native_actions_sha256'],'scope':'EXECUTED_14_DAY_NATIVE_SIMULATION'})
    return {'schema':'agi-alpha/scale-profit036-native-anchor/v1','source_sha256':audited['source_sha256'],
      'freeze_sha256':freeze['sha256'],'report_sha256':digest(report),
      'audit_sha256':digest(audited),'scoreboard_sha256':digest(scoreboard),
      'worlds':worlds,'native_profit_target_attained':False,'actual_customers':0,'actual_collections_cents':0,
      'validates_scale_demand_or_enterprise_contract_pricing':False,'funding_authority':False}


def execute(value, anchor):
    validate_protocol(value)
    require(anchor['schema'] == 'agi-alpha/scale-profit036-native-anchor/v1' and anchor['native_profit_target_attained'] is False, 'REDERIVED_NATIVE_ANCHOR_REQUIRED')
    runs={}
    for name,updates in value['cases'].items():
        cfg=default_config()|updates
        runs[name]=[summarize_existing_projection(cfg,s) for s in value['seeds']]
    summary={}
    for name,rows in runs.items():
        completed=[x['months_completed'] == 60 and x['cash_survival'] for x in rows]
        reached=[x['first_attainment_month_under_hypotheses'] for x in rows]
        summary[name]={'worlds':len(rows),'horizon_completed':sum(completed),
          'conditional_profit_target_crossings':sum(x is not None for x in reached),
          'first_attainment_months':reached,'terminal_reasons':[x['terminal_reason'] for x in rows],
          'ending_available_cash_cents':[x['ending_unrestricted_cash_cents'] for x in rows],
          'peak_ttm_profit_cents':[x['peak_365day_profit_cents'] for x in rows],
          'binding_constraints':sorted(set().union(*(set(x['binding_constraints']) for x in rows)))}
    return {'schema':RESULT,'scope':SCOPE,'source_anchored_native':anchor,'protocol_sha256':identity(value),
      'opening_cash_cents':OPENING_CENTS,'additional_capital_injected_cents':0,
      'target_profit_cents':TARGET_CENTS,'horizon_months':60,
      'summary':summary,'runs':runs,
      'economic_success':'NOT_ESTABLISHED_CONDITIONAL_PROJECTIONS_ONLY',
      'native_annual_profit':'NOT_ESTABLISHED',
      'real_customer_and_collection_result':'ZERO_EXTERNAL_CUSTOMERS_AND_COLLECTIONS',
      'cost_scope':'Modeled exact cash charges in existing conditional aggregator; 25% GROSS-RECEIPTS levy is a conservative nonstatutory tax proxy. Provider/model/engineering bills and partner rights remain unmeasured.',
      'limits':['No large-scale buyer contracts, channel supply, partner incentives, enterprise-grade delivery or willingness to pay are observed or established by the 14-day native anchor.',
                'Original native executive has a 200-buyer finite edition limit; this code DOES NOT remove it. Future aggregate cohorts are hypothetical, not executed native customer artifacts.',
                'Existing aggregate includes approximate large binomial draws and assumes independently purchasable completed-work units; offer bundles are not native qualified enterprise contracts.',
                '365-day projected profit uses uniform within-month allocation of exact monthly cents; it is not a daily native record. The 60-month horizon is calendar-based from 2026-11-01.',
                'Gross-receipt tax/levy proxy is conservative but not actual income-tax or jurisdiction compliance. No actual frontier AI/host/engineering metering or partner cost quote.',
                'No selection based on lucky seeds; all registered cases including failure and no-attainment are retained.']}


def output_once(path, result):
    output = Path(path).expanduser().absolute()
    require(not output.exists() and not output.is_symlink() and output.parent.is_dir() and not any(p.is_symlink() for p in output.parents), 'FRESH_OUTPUT_DIRECTORY_REQUIRED')
    output.mkdir(mode=0o700)
    for name,value in [('RESULT.json',result),('SUMMARY.json',result['summary']),('ANCHOR.json',result['source_anchored_native'])]:
        with (output/name).open('xb') as f:
            f.write(canonical_bytes(value)+b'\n');f.flush();os.fsync(f.fileno())
    return output


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-output',required=True)
    parser.add_argument('--protocol',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--trust-frozen-source',action='store_true')
    args=parser.parse_args(argv)
    try:
        require(args.trust_frozen_source, 'EXPLICIT_FROZEN_EXECUTABLE_SOURCE_TRUST_REQUIRED')
        target=Path(args.output).absolute();native=Path(args.native_output).absolute()
        require(target != native and target not in native.parents and native not in target.parents, 'OUTPUT_OUTSIDE_NATIVE_ACCOUNT')
        require(not target.exists(), 'FRESH_OUTPUT_REQUIRED_BEFORE_EXECUTION')
        registration=validate_protocol(strict_read(args.protocol))
        anchored=native_anchor(native)
        result=execute(registration,anchored)
        path=output_once(target,result)
        print(json.dumps({'output':str(path),'scope':result['scope'],'source_sha256':anchored['source_sha256'],
              'scenarios':result['summary'],'economic_success':result['economic_success']},sort_keys=True))
        return 0
    except (ValueError,OSError,subprocess.TimeoutExpired,TypeError,KeyError,OverflowError) as err:
        parser.exit(2,'REFUSED: '+str(err)+'\n')

if __name__ == '__main__':
    raise SystemExit(main())
