"""Independent read-only reconciliation of the exposed commercial worlds."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sqlite3
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(directory, policy_path, expected_result, expected_policy, output):
    wall, cpu = time.monotonic(), time.process_time()
    report_path = directory / 'RESULT.json'
    if sha(report_path) != expected_result or sha(policy_path) != expected_policy:
        raise ValueError('SOURCE_FROZEN_AUTHORITY_MISMATCH')
    report, policy = json.loads(report_path.read_text()), json.loads(policy_path.read_text())
    checks, summaries, database_hashes = [], {}, {}
    def check(condition, description):
        checks.append({'check': description, 'passed': bool(condition)})
    for world in report['worlds']:
        identity = world['id']
        database = directory / identity / 'exchange.sqlite'
        database_hashes[identity] = sha(database)
        connection = sqlite3.connect('file:' + str(database.resolve()) + '?mode=ro&immutable=1', uri=True)
        connection.row_factory = sqlite3.Row
        try:
            journal = [dict(row) for row in connection.execute('SELECT seq,order_id,kind,amount FROM journal ORDER BY seq')]
            sums = {}
            for row in journal:
                sums[row['kind']] = sums.get(row['kind'], 0) + int(row['amount'])
            orders = [dict(row) for row in connection.execute('SELECT id,buyer,price,state,custody,refund_due,compensation_due FROM trades ORDER BY id')]
            reserved = sum(int(row[0]) for row in connection.execute("SELECT cap FROM investments WHERE state='reserved'"))
        finally:
            connection.close()
        revenue = sums.get('revenue', 0) - sums.get('contra_revenue', 0)
        collections = sums.get('collections', 0) - sums.get('reversal_paid', 0)
        expenses, paid = sums.get('expense', 0), sums.get('expense_paid', 0)
        recovery = sums.get('recovery_income', 0)
        profit = revenue + recovery - expenses
        cash = policy['opening_microUSD'] + collections + recovery - paid - sums.get('investment_paid', 0)
        terminal = world['snapshots']['terminal_180day_with_unresolved_exposure_retained']
        after = world['snapshots']['after_prespecified_conditional_reservation']
        check(journal == world['journal'] and orders == world['orders'], identity + ': original read-only SQL equals report')
        check(terminal['profit'] == profit and after['profit'] == profit, identity + ': accrual profit reconciles including reversals')
        check(terminal['cash'] == cash and after['cash'] == cash, identity + ': cash excludes opening equity from revenue')
        check(terminal['collections'] == collections == world['net_collections_microUSD'], identity + ': net collection reconciles')
        check(after['reservedInvestment'] == reserved and after['available'] == max(0, terminal['available'] - reserved), identity + ': investment reservation is not construction spend')
        check(world['construction_spend'] == 0 and sums.get('investment_paid', 0) == 0, identity + ': no successor expenditure invented')
        check(after['unrestrictedEarned'] <= max(0, profit - reserved), identity + ': conditional earned funds do not include opening equity')
        check(expenses >= sum(policy['modeled_costs_microUSD'].values()), identity + ': all admitted costs including unsold')
        if any(order['state'] == 'released' for order in orders):
            check(terminal['tailReserve'] >= policy['price_microUSD'] + 200000 and terminal['workingCapital'] >= policy['route']['additional_dispute_reserve_microUSD'], identity + ': principal and tariff fee exposure retained')
        if world['buyer_inputs']['reversal']:
            check(collections == 0 and revenue == 0 and after['investmentStopped'] and after['unrestrictedEarned'] == 0, identity + ': late reversal removes earnings and stops investment')
        summaries[identity] = {'participates': world['participates_under_assumptions'], 'profit_microUSD': profit, 'cash_microUSD': cash,
                               'conditional_reserved_investment_microUSD': reserved, 'construction_paid_microUSD': sums.get('investment_paid', 0)}
        check(database_hashes[identity] == sha(database), identity + ': read-only database bytes unchanged')
    competitive = summaries['equal_ai_native_outside_option']
    check(competitive['participates'] is False and competitive['profit_microUSD'] == -sum(policy['modeled_costs_microUSD'].values()), 'equal-tool AI alternative retains the no-demand loss')
    decision = report['evidence_grounded_decision']
    check(decision['qualified_unrestricted_simulated_earned_funds_microUSD'] == 0 and decision['real_orders'] == 0, 'modeled positive balances not promoted to demand-grounded qualified funds')
    result = {'schema': 'agi-alpha/consequential009-independent-commerce-review/v1', 'passed': all(x['passed'] for x in checks),
              'result_sha256': expected_result, 'policy_sha256': expected_policy, 'verifier_sha256': sha(__file__),
              'checks': checks, 'worlds': summaries, 'database_hashes': database_hashes,
              'strongest_supported_consequential_limit': 'Under the admitted equal-AI-native outside option the buyer refuses and the complete authored36USD cost is lost. The positive12.25USD world therefore cannot establish competitive viability. Exact human job time, actual inference/enterprise costs and AGI ALPHA participation remain unmeasured; no measured human loss or AI advantage is established.',
              'defect_adjudication': 'No additional accounting defect was established in these eight fixed modeled histories. This is read-only arithmetic reconciliation, not empirical calibration of tariffs, demand, costs, settlement guarantees or buyer value.',
              'scope': 'Procedural separate reviewer on shared host/model; counterfactual worlds are not additive sales. Earlier r2 artifact/receipt source identities remain historical after later source revisions.',
              'resources': {'cpu_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - wall, 'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'complete_monetary_cost': None}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--expected-result', required=True)
    parser.add_argument('--expected-policy', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.directory, args.policy, args.expected_result, args.expected_policy, args.output)
    print(json.dumps({'passed': result['passed'], 'checks': len(result['checks']), 'failed': [c['check'] for c in result['checks'] if not c['passed']]}))
    raise SystemExit(0 if result['passed'] else 1)
