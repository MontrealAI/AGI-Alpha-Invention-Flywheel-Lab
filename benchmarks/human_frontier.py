"""Illustrative full-autonomy frontier AI versus human-delivered service costing.

This calculator does not execute agents, validate output quality, or observe sales.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

MONEY = Decimal('0.01')
PHASES = ('production', 'research_and_source_check', 'adversarial_qa', 'correction_and_testing',
          'customer_acquisition', 'customer_support_and_delivery', 'development_and_maintenance')
NON_MODEL_COSTS = ('external_tools_and_data_usd', 'compute_and_storage_usd',
                   'failed_attempts_and_retries_usd', 'paid_distribution_usd',
                   'payment_and_delivery_fees_usd', 'warranty_and_liability_reserve_usd',
                   'non_model_development_amortization_usd')
CASE_FIELDS = {'id','outcome','role','human_hours','ai_operation','autonomous_phases',
               'ai_non_model_costs', 'assumed_price_usd', 'agent_human_hours'}
PHASE_FIELDS = {'name','model','input_tokens','output_tokens'}


def decimal(value):
    if type(value) not in (str, int, float):
        raise ValueError('Expected finite numeric amount')
    try:
        x = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError('Invalid decimal') from error
    if not x.is_finite() or x < 0:
        raise ValueError('Negative or nonfinite amount')
    return x


def usd(value):
    return str(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def analyze(data):
    if not isinstance(data, dict) or set(data) != {'metadata','wage_burden','roles','models','cases'}:
        raise ValueError('Unknown top-level schema')
    meta = data['metadata']
    if (meta.get('evidence_status') != 'ILLUSTRATIVE_UNVALIDATED'
            or meta.get('same_outcome_independently_verified') is not False
            or type(meta.get('actual_sales')) is not int or meta['actual_sales'] != 0
            or meta.get('execution_type') != 'HYPOTHETICAL_FULLY_AUTONOMOUS'):
        raise ValueError('Cannot claim observed autonomous performance, quality or sales')
    burden = data['wage_burden']
    loading = decimal(burden['employer_cost_per_hour']) / decimal(burden['wage_salary_per_hour'])
    if not Decimal(1) <= loading <= Decimal(3):
        raise ValueError('Invalid human wage loading')
    if not isinstance(data['cases'], list) or len(data['cases']) == 0:
        raise ValueError('No cases')
    seen = set()
    output = []
    for case in data['cases']:
        if not isinstance(case, dict) or set(case) != CASE_FIELDS:
            raise ValueError('Case schema mismatch; old human-review benchmark is invalid here')
        name = case['id']
        if type(name) is not str or not name or name in seen:
            raise ValueError('Duplicate or empty case ID')
        seen.add(name)
        if type(case['outcome']) is not str or not case['outcome']:
            raise ValueError('Required outcome absent')
        if case['ai_operation'] != 'FULLY_AUTONOMOUS_END_TO_END':
            raise ValueError('This experiment concerns a fully autonomous enterprise')
        if decimal(case['agent_human_hours']) != 0:
            raise ValueError('Human-in-the-loop effort requires a separate hybrid comparison')
        role = case['role']
        if role not in data['roles']:
            raise ValueError('Unknown human occupation')
        wage = decimal(data['roles'][role]['wage_usd_per_hour'])
        H = decimal(case['human_hours']) * wage * loading
        if H <= 0:
            raise ValueError('Positive human duration required')
        phases = case['autonomous_phases']
        if not isinstance(phases, list) or len(phases) != len(PHASES):
            raise ValueError('Every autonomous business phase must be represented')
        if set(case['ai_non_model_costs']) != set(NON_MODEL_COSTS):
            raise ValueError('Incomplete non-model cost categories')
        per_phase = []
        total_tokens = Decimal(0)
        found = set()
        for phase in phases:
            if not isinstance(phase, dict) or set(phase) != PHASE_FIELDS:
                raise ValueError('Unknown or missing agent-phase fields')
            phase_name = phase['name']
            if phase_name not in PHASES or phase_name in found:
                raise ValueError('Duplicate or missing workflow phase')
            found.add(phase_name)
            model = phase['model']
            if model not in data['models']:
                raise ValueError('Unpriced model')
            for label in ('input_tokens', 'output_tokens'):
                if type(phase[label]) is not int or phase[label] < 0 or phase[label] > 20_000_000:
                    raise ValueError('Invalid token usage')
            rate = data['models'][model]
            cost = (Decimal(phase['input_tokens']) * decimal(rate['input_usd_per_million'])
                    + Decimal(phase['output_tokens']) * decimal(rate['output_usd_per_million'])) / Decimal(1_000_000)
            total_tokens += cost
            per_phase.append({'phase':phase_name,'model':model,'model_cost_usd':usd(cost),
                              'input_tokens':phase['input_tokens'],'output_tokens':phase['output_tokens']})
        if found != set(PHASES):
            raise ValueError('Incomplete autonomous operation')
        extras = sum((decimal(case['ai_non_model_costs'][k]) for k in NON_MODEL_COSTS), Decimal(0))
        ai_total = total_tokens + extras
        price = decimal(case['assumed_price_usd'])
        output.append({'id':name,'outcome':case['outcome'],'human_role':role,
            'human_hours_assumed':str(decimal(case['human_hours'])),
            'human_loaded_labor_usd':usd(H),
            'agent_human_hours':'0',
            'autonomous_operation_human_labor_usd':'0.00',
            'ai_workflow_model_cost_usd':usd(total_tokens),
            'autonomous_phase_costs':per_phase,
            'ai_non_model_assumption_costs_usd':usd(extras),
            'ai_total_scenario_cost_usd':usd(ai_total),
            'assumed_sale_price_usd':usd(price),
            'conditional_ai_contribution_usd':usd(price - ai_total),
            'human_loaded_labor_minus_ai_scenario_usd':usd(H - ai_total),
            'quality_and_same_outcome_verified':False,
            'real_customer_demand_verified':False,
            'commercial_conclusion':'ILLUSTRATIVE_ONLY'})
    return {'schema':'alpha-human-frontier-autonomous-benchmark/v2',
            'inputs_sha256':sha(data),'human_wage_loading_factor':str(loading),
            'comparison_priority':'PRIMARY_HUMAN_FULLY_LOADED_SERVICE_VS_FULLY_AUTONOMOUS_FRONTIER_AI',
            'autonomous_operation_includes':list(PHASES),
            'mandatory_human_verification':'NONE',
            'secondary_comparators':['human_delivered_ai_assisted_service',
                                     'competent_alternative_autonomous_ai','free_self_service','no_launch'],
            'caveat':'All job hours, model tokens, acceptance, recurring tools, customer demand, acquisition, development amortization, risk and sale prices are assumptions; only model tariffs and wage schedules are sourced. A model output is not buyer-accepted work.',
            'cost_status':'SCENARIO_ONLY_NOT_METERED','actual_customer_receipts_usd':'0',
            'all_outcomes_confirmed':False,'commercial_success':'UNESTABLISHED',
            'full_invention_flywheel':'UNESTABLISHED','cases':output}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default=str(Path(__file__).with_name('illustrative_cases.json')))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output_path = Path(args.output)
    try:
        if output_path.exists():
            raise FileExistsError('Preserve prior output; target exists')
        input_path = Path(args.input)
        if input_path.stat().st_size > 1_000_000:
            raise ValueError('Input exceeds 1MB')
        result = analyze(json.loads(input_path.read_text(encoding='utf-8')))
        with output_path.open('x',encoding='utf-8') as stream:
            json.dump(result,stream,indent=2,ensure_ascii=False,allow_nan=False)
            stream.write('\n')
    except (ValueError, TypeError, OSError, InvalidOperation, ZeroDivisionError) as error:
        parser.exit(2,f'REFUSED: {error}\n')
    print('Scenario only:',output_path,'; no humans charged to autonomous operation, no validated sale')


if __name__ == '__main__':
    main()
