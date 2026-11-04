"""Render the public five-pair aggregate; never open an account or run a world."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT_URL = 'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
PROTOCOL_COMMIT = '786d1d085f83c70ab8b7b9a3ee0c79530af7c79b'
RUNTIME_COMMIT = '9187e8f0b57d4b11124a14ed89582914f33b30b6'
PROTOCOL_SHA = '2b6eef4a9535f6f626e2ca88fcc432c672f1b9cc45ec5bef868e3378d38f5277'
COMPARISON_SHA = '3daf2c05535c9bee7e857dbe40a3ade9be3deed17c27b0532df3e68c21a52c00'
WORLDS = {'central': 'Central', 'weak': 'Weak demand', 'copycat': 'Copycat',
          'no_demand': 'No demand', 'failed_activation': 'Failed activation'}
REASONS = {'FUNDED_TRIAL': 'Funded trial', 'FUNDED_RENEWAL': 'Funded renewal',
           'ORGANIC_CONTROL': 'Organic control', 'NO_WARM_COLLECTION': 'No opening collection',
           'FIRST_INVOICE_ABSENT': 'First invoice absent',
           'NO_EXCLUSIVE_COLLECTION': 'No exclusive collection',
           'NONPOSITIVE_EXPECTED_NET': 'Nonpositive estimated net',
           'INSUFFICIENT_UNRESTRICTED_EARNINGS': 'Insufficient earned cash',
           'INSUFFICIENT_AVAILABLE_AFTER_MAINTENANCE': 'Insufficient cash after maintenance'}
SHAS = ('source_sha256', 'protocol_sha256', 'matched_job_manifest_sha256_excluding_cpu_seconds',
        'matched_menu_study_sha256')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(type(value) is int, 'Expected integer native amount or count')
    return value


def usd(value, signed=False):
    whole, fraction = divmod(abs(integer(value)), 1_000_000)
    frac = f'{fraction:06d}'.rstrip('0').ljust(2, '0')
    sign = '−' if value < 0 else ('+' if signed and value > 0 else '')
    return f'{sign}${whole:,}.{frac}'


def table(headers, rows):
    return '\n'.join('| ' + ' | '.join(str(x) for x in row) + ' |'
                     for row in [headers, ['---'] * len(headers), *rows])


def validate(data):
    require(data['schema'] == 'omega/earned-paid-reach-paired-evidence/v1' and
            data['window_days'] == [0, 365] and data['end_day_exclusive'] is True and
            data['opening_microUSD_each'] == 100_000_000_000 and data['actual_revenue_usd'] == 0 and
            data['actual_complete_lifecycle_cost_usd'] is None, 'Unexpected study or accounting boundary')
    require(set(data['pairs']) == set(WORLDS), 'All five registered pairs required')
    design = data['shared_design_and_prefix']
    require(all(re.fullmatch(r'[0-9a-f]{64}', design[k]) for k in SHAS), 'Invalid design fingerprints')
    require(design['protocol_sha256'] == PROTOCOL_SHA and data['comparison_program_sha256'] == COMPARISON_SHA,
            'Expected the registered protocol and corrected-source summarizer')
    warm = design['warm_prefix']
    require(warm['before_day'] == 90 and warm['contacts'] == 27, 'Unexpected warm prefix')
    for pair in data['pairs'].values():
        require(set(pair) == {'organic', 'pilot', 'comparison'}, 'Unexpected arms')
        for arm in ('organic', 'pilot'):
            case = pair[arm]
            require(case['native_audit_accepted'] is True and
                    re.fullmatch(r'[0-9a-f]{64}', case['audit_receipt_sha256']), 'Missing accepted native audit')
            money, costs, work = (case[k] for k in ('financial_microUSD', 'incurred_expense_breakdown_microUSD', 'reach_and_work'))
            require(all(type(v) is int for v in (*money.values(), *costs.values())), 'Fractional ledger units')
            require(sum(costs.values()) == money['incurred_expenses_including_tax'] and
                    money['profit_after_modeled_tax'] == money['recognized_revenue'] + money['recovery_income'] - sum(costs.values()) and
                    money['cash'] == data['opening_microUSD_each'] + money['collections'] + money['recovery_income'] - money['cash_expenses_paid'],
                    'Ledger identity failed')
            require(money['collections'] == warm['collections_microUSD'] + work['post_warm_collections_microUSD']
                    and work['settled_baskets'] == warm['settled_baskets'] + work['post_warm_settled_baskets'],
                    'Warm and fresh results do not reconcile')
            require([t['day'] for t in case['tranches']] == [90, 118], 'Wrong review days')
            for t in case['tranches']:
                require(t['reason'] in REASONS and t['action'] in ('BUY', 'SKIP'), 'Unknown decision receipt')
                require((t['reason'] == 'ORGANIC_CONTROL') == (arm == 'organic') and
                        (t['reason'] in ('FUNDED_TRIAL', 'FUNDED_RENEWAL')) == (t['action'] == 'BUY'),
                        'Contradictory arm or decision reason')
                if t['action'] == 'BUY':
                    require(arm == 'pilot' and t['funding'] == 'EARNED' and t['invoice_microUSD'] == 6_250_000,
                            'Purchase without earned native funding')
                    require(t['supplier_final_state'] in ('FAILED', 'EXPIRED'), 'Unfinished supplier contract')
                else:
                    require(t['invoice_microUSD'] == 0, 'Declined invoice was charged')
            require(sum(t['invoice_microUSD'] for t in case['tranches']) == costs.get('paid_reach', 0), 'Invoice mismatch')
        for key, actual in pair['comparison']['pilot_minus_organic_financial_microUSD'].items():
            require(actual == pair['pilot']['financial_microUSD'][key] - pair['organic']['financial_microUSD'][key],
                    'Incorrect reported financial difference')
        diff = pair['pilot']['reach_and_work']['settled_baskets'] - pair['organic']['reach_and_work']['settled_baskets']
        require(pair['comparison']['pilot_minus_organic_counts']['settled_baskets'] == diff, 'Incorrect volume difference')
        profits = {a: pair[a]['financial_microUSD']['profit_after_modeled_tax'] for a in ('organic', 'pilot')}
        profits['arithmetic_nonentry'] = 0
        winners = [a for a, value in profits.items() if value == max(profits.values())]
        require(pair['comparison']['highest_annual_modeled_profit_including_nonentry'] == winners,
                'Incorrect highest profit or missing tie')


def report(data, evidence_sha, evidence_link):
    validate(data)
    warm = data['shared_design_and_prefix']['warm_prefix']
    comparison, funding, financial, reserves, behavior = [], [], [], [], []
    gains = renewals = both = 0
    losses, ties, unprofitable_renewals = [], [], []
    best = None
    for slug, world in WORLDS.items():
        pair = data['pairs'][slug]
        c, pilot = pair['comparison'], pair['pilot']
        closing = [pair[a]['financial_microUSD']['profit_after_modeled_tax'] for a in ('organic', 'pilot')]
        delta = c['pilot_minus_organic_financial_microUSD']['profit_after_modeled_tax']
        volume = c['pilot_minus_organic_counts']['settled_baskets']
        gains += delta > 0
        if delta < 0:
            losses.append(world)
        elif delta == 0:
            ties.append(world)
        both += delta > 0 and volume > 0
        first, renewal = pilot['tranches']
        renewals += renewal['action'] == 'BUY'
        if renewal['action'] == 'BUY' and delta <= 0:
            unprofitable_renewals.append(world)
        comparison.append([world, usd(closing[0]), usd(closing[1]), usd(delta, True), f'{volume:+d}',
                           ', '.join('Nonentry' if a == 'arithmetic_nonentry' else a.title()
                                     for a in c['highest_annual_modeled_profit_including_nonentry'])])
        observed = renewal['decision_observations']
        funding.append([world, REASONS[first['reason']], usd(first['earned_before_microUSD']),
                        first.get('supplier_final_state', '—').title(), observed['first_exclusive_settled'],
                        usd(renewal['attributed_pretax_microUSD']), REASONS[renewal['reason']],
                        usd(first['invoice_microUSD'] + renewal['invoice_microUSD'])])
        for arm in ('organic', 'pilot'):
            row = pair[arm]
            m, expenses, w = row['financial_microUSD'], row['incurred_expense_breakdown_microUSD'], row['reach_and_work']
            result = (m['profit_after_modeled_tax'], world, arm)
            if best is None or result[0] > best[0]:
                best = result
            label = [world, arm.title()]
            financial.append(label + [usd(m[k]) for k in ('collections', 'recognized_revenue',
                             'incurred_expenses_including_tax', 'cash_expenses_paid')] +
                             [usd(expenses.get('modeled_tax', 0)), usd(w['refunded_buyer_principal_microUSD']),
                              usd(m['profit_after_modeled_tax'])])
            reserves.append(label + [usd(m[k]) for k in ('cash', 'available_cash', 'available_earned_cash',
                           'tail_reserve', 'payables', 'custody_restricted', 'custody_reserve',
                           'reserved_investment', 'working_capital')])
            behavior.append(label + [w['post_warm_contacts'], w['post_warm_settled_baskets'],
                            usd(w['post_warm_collections_microUSD']), w['paid_exposures'],
                            w['same_day_organic_paid_overlaps'], w['paid_routed_contacts_to_organic_roster'],
                            w['repeat_settled_buyers'], w['refunded_baskets']])
    design = data['shared_design_and_prefix']
    return '\n\n'.join([
        '# Can collected earnings finance profitable paid reach?',
        f'Paid reach raised after-tax simulated profit in **{gains} of five** registered environments. '
        f'Both profit and settled order volume increased in **{both}**. The seller bought a second tranche in **{renewals}**. '
        'Each comparison covers the complete simulated year from day 0 through day 364. Each account started with $100,000.',
        table(['Environment', 'Organic profit', 'Pilot profit', 'Pilot − organic', 'Additional settled orders', 'Highest modeled profit'], comparison),
        (f'Paid reach reduced annual profit in {", ".join(losses)}. ' if losses else '') +
        (f'The two arms tied in {", ".join(ties)}. ' if ties else '') +
        (f'The renewal hurdle was met without a positive matched annual benefit in {", ".join(unprofitable_renewals)}. ' if unprofitable_renewals else '') +
        'The nonentry comparator has zero revenue and zero costs. Each pair uses separate accounts and the same buyers, jobs, menu and organic contact schedule. '
        'The five environments have no empirical probability weights.',
        '## What the seller knew before spending',
        f'All ten accounts reproduced the same 27 previously exposed opportunities before day 90. They each collected '
        f'{usd(warm["collections_microUSD"])} on {warm["settled_baskets"]} accepted orders. The fresh cohort began afterward. '
        'The first purchase required liquid earned funds and a positive estimate under the preregistered assumption of two incremental orders. '
        'At renewal the seller credited only collections from buyers outside the complete organic roster, then deducted the entire first invoice and all first-plan variable costs.',
        table(['Environment', 'Day 90', 'Earned cash before trial', 'First supplier state', 'Exclusive orders', 'Attributable pretax', 'Day 118', 'Total invoices'], funding),
        'The renewal rule used its own prior receipts. Capacity displaced by paid work can affect enterprise profit. The matched annual difference above measures that effect along with all other modeled changes. In the failed-activation environment the supplier shock was hidden at purchase.',
        '<details>\n<summary>Fresh contact, settlement and overlap counts</summary>',
        table(['Environment', 'Arm', 'Fresh contacts', 'Fresh orders', 'Fresh collections', 'Paid exposures', 'Same-day overlaps', 'Paid contacts to organic roster', 'Repeat buyers', 'Refunded orders'], behavior),
        '</details>\n\n<details>\n<summary>Annual income, costs and buyer refunds in US dollars</summary>',
        table(['Environment', 'Arm', 'Collected', 'Recognized revenue', 'Incurred expenses incl. tax', 'Expenses paid', 'Modeled tax', 'Buyer principal refunded', 'Profit'], financial),
        'Study and setup were expensed under the original $35 envelope. Annual maintenance was $12. Each purchased supplier tranche cost $6.25 including support. The 20% provision applies to positive modeled pretax income. Opening capital is financing. Refunded custody principal is reported separately from revenue and expenses.',
        '</details>\n\n<details>\n<summary>Closing cash and obligations in US dollars</summary>',
        table(['Environment', 'Arm', 'Cash', 'Available', 'Unrestricted earned', 'Tail reserve', 'Payables', 'Restricted custody', 'Custody reserve', 'Reserved investment', 'Working capital'], reserves),
        '</details>',
        '## Scale and evidence boundary',
        f'The most profitable registered account earned **{usd(best[0])}** ({best[1]}, {best[2]}). Its gap to $3 billion was '
        f'**{usd(3_000_000_000_000_000 - best[0])}**. The published budgets, voluntary choices and contact rights of the 27 warm buyers and 24 fresh prospects cap possible collections in this experiment at $2,054.21 even before costs. '
        'Demand, supplier reliability, retention, fees and unit costs are hypotheses. Actual commercial revenue was $0. The complete real costs of development, compute, support and acquisition remain unknown.',
        'These are ten new independent simulation accounts. The earlier primary account, later engineering replays and any public-release operation have separate identities. The aggregate records independent audits for these ten accounts. A release or a run from downloaded bytes requires its own dated receipt.',
        f'Protocol commit `{PROTOCOL_COMMIT}` · execution source `{RUNTIME_COMMIT}` · runtime source-map SHA-256 `{design["source_sha256"]}`. '
        f'[Preregistration]({ROOT_URL}/blob/{PROTOCOL_COMMIT}/campaign/omega-paid-reach-20261104/PROTOCOL.md) · '
        f'[Execution source]({ROOT_URL}/tree/{RUNTIME_COMMIT})',
        f'Aggregate SHA-256 `{evidence_sha}` · comparison program SHA-256 `{COMPARISON_SHA}`. '
        f'[Ten audited accounts and machine-readable comparison]({evidence_link})',
    ]) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('aggregate', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--evidence-link', default='./EVIDENCE.json', help='Relative artifact or GitHub HTTPS URL')
    args = p.parse_args()
    require(re.fullmatch(r'(?:https://github\.com/|\./)[a-zA-Z0-9_./-]+', args.evidence_link),
            'Safe GitHub or relative evidence link required')
    raw = args.aggregate.read_bytes()
    content = report(json.loads(raw), sha256(raw).hexdigest(), args.evidence_link)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(content)


if __name__ == '__main__':
    main()
