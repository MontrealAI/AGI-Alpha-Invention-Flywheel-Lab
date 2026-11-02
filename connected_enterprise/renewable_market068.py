"""Opt-in demand-stock and renewal sensitivity, NOT a native financial account.

The physical input is recurring employer-paid work, not a finite queue of named
customer orders. Buyer choice and all economic parameters are authored scenarios.
No authority, purchases, demand or revenue is created by running this module.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from json import dumps

MICRO = 1_000_000
SCHEMA = 'agi-alpha/renewable-paid-work-market068/v3'


def digest(value):
    return sha256(dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Scenario:
    bookkeeping_jobs: int = 1_532_400
    customer_support_jobs: int = 2_666_000
    paid_hours_per_job_year: int = 2080
    hours_per_packet: int = 4
    serviceable_bps: int = 2000
    eligible_organizations: int = 500_000
    new_eligible_organizations_per_month: int = 2_000
    opening_customers: int = 0
    customer_monthly_packets: int = 24
    customer_monthly_purchase_bps: int = 9500
    monthly_retention_bps: int = 9700
    cold_conversion_bps: int = 500
    followup_conversion_bps: int = 1000
    winback_conversion_bps: int = 2000
    winback_consent_bps: int = 4000
    followup_permission_bps: int = 10000
    acceptance_bps: int = 9500
    collection_bps: int = 9900
    quote_micro: int = 95 * MICRO
    full_human_office_cost_micro: int = 191 * MICRO
    avoidable_human_cost_bps: int = 6500
    buyer_value_ceiling_micro: int = 105 * MICRO
    employer_external_budget_per_customer_month_micro: int = 3_000 * MICRO
    first_attempt_micro: int = 10 * MICRO
    accepted_completion_micro: int = 14 * MICRO
    onboarding_micro: int = 6 * MICRO
    cold_contact_micro: int = 25 * MICRO
    followup_contact_micro: int = 10 * MICRO
    winback_contact_micro: int = 10 * MICRO
    payment_bps: int = 290
    tail_per_accepted_micro: int = 2 * MICRO
    monthly_capacity_packets: int = 10_000_000
    annual_fixed_micro: int = 50_000_000 * MICRO
    monthly_marketing_target_micro: int = 2_000_000 * MICRO
    prior_profit_reinvestment_bps: int = 3500
    opening_equity_micro: int = 20_000_000 * MICRO
    income_tax_bps: int = 2000
    months: int = 24

    def validate(self):
        fields=asdict(self)
        for k,v in fields.items():
            if type(v) is not int or v < 0:
                raise ValueError('NONNEGATIVE_INTEGER_REQUIRED:'+k)
        for k in ('serviceable_bps','customer_monthly_purchase_bps','monthly_retention_bps',
                  'cold_conversion_bps','followup_conversion_bps','winback_conversion_bps',
                  'winback_consent_bps','followup_permission_bps','acceptance_bps','collection_bps','avoidable_human_cost_bps',
                  'payment_bps','prior_profit_reinvestment_bps','income_tax_bps'):
            if fields[k]>10000:raise ValueError('BASIS_POINTS_REQUIRED:'+k)
        for k in ('paid_hours_per_job_year','hours_per_packet','customer_monthly_packets',
                  'monthly_capacity_packets','first_attempt_micro','cold_contact_micro',
                  'followup_contact_micro','winback_contact_micro','quote_micro','months'):
            if not fields[k]:raise ValueError('POSITIVE_REQUIRED:'+k)
        if self.months>120:raise ValueError('FINITE_TEST_HORIZON_MAX_120_MONTHS')
        if self.opening_customers>self.eligible_organizations:raise ValueError('INITIAL_MARKET_STOCK_INVALID')
        return self



def renewed_work_identity(customer_id, service_id, period_number, ordinal, source_sha256):
    """A new work *identity*, not a new job, purchase, offer or permission.

    Native adoption must independently check actual work, buyer authority and
    source bytes before making this an offered/accepted deliverable.
    """
    if any(not isinstance(x,str) or not x or len(x)>160 for x in (customer_id,service_id)):
        raise ValueError('NAMED_CUSTOMER_AND_SERVICE_REQUIRED')
    if any(type(x) is not int or x<0 for x in (period_number,ordinal)):
        raise ValueError('NONNEGATIVE_PERIOD_AND_REQUEST_ORDINAL_REQUIRED')
    if (not isinstance(source_sha256,str) or len(source_sha256)!=64 or
            any(c not in '0123456789abcdef' for c in source_sha256)):
        raise ValueError('SOURCE_SHA256_BINDING_REQUIRED')
    return 'renewal068-'+digest([source_sha256,customer_id,service_id,period_number,ordinal])[:40]


def _fixed_month(annual,month):
    base,rem=divmod(annual,12)
    return base + (1 if (month-1)%12<rem else 0)


def simulate(case:Scenario):
    """Deterministic aggregate projection; no synthetic output is counted as a delivered job.

    Charges recurring work before collecting it, and marketing before next-period
    acquisition. Never spends next-month revenue. Source/buyer identity is only
    aggregate in this sensitivity model; native per-buyer qualification is separate.
    """
    a=case.validate()
    total_packet_equivalents=(a.bookkeeping_jobs+a.customer_support_jobs)*a.paid_hours_per_job_year//a.hours_per_packet
    annual_serviceable=total_packet_equivalents*a.serviceable_bps//10000
    monthly_serviceable=annual_serviceable//12
    active=a.opening_customers
    uncontacted=a.eligible_organizations-active
    warm_ready=dormant_eligible=dormant_unavailable=exhausted=0
    cash=a.opening_equity_micro
    prior_profit=0
    outstanding_tail=0
    rows=[]; stopped=False
    choice_ceiling=min(a.buyer_value_ceiling_micro,
                       a.full_human_office_cost_micro*a.avoidable_human_cost_bps//10000)
    for month in range(1,a.months+1):
        if stopped:
            rows.append({'month':month,'status':'HALTED_PREPAYMENT_REQUIRED','closing_cash_micro':cash,
                        'protected_tail_micro':outstanding_tail,
                        'trailing_12_profit_micro':None,'new_customers':0,'accepted_deliveries':0})
            continue
        begin_cash=cash
        uncontacted+=a.new_eligible_organizations_per_month
        eligible_total=(a.eligible_organizations+month*a.new_eligible_organizations_per_month)
        retained=active*a.monthly_retention_bps//10000
        churned=active-retained
        dormant_eligible+=churned
        active=retained
        fixed=_fixed_month(a.annual_fixed_micro,month)
        can_sell=a.quote_micro<=choice_ceiling
        # Monthly purchasing authority is an explicit exogenous employer budget flow.
        # It is NOT company cash, and is NOT secretly replenished from company sales.
        affordable_packets_per_customer=min(a.customer_monthly_packets,
            a.employer_external_budget_per_customer_month_micro//a.quote_micro)
        requested=(active*affordable_packets_per_customer*a.customer_monthly_purchase_bps//10000 if can_sell else 0)
        admitted=min(requested,monthly_serviceable,a.monthly_capacity_packets)
        # Reserve enough to fund even 100% acceptance and all payment fees, before collection.
        worst_fees_per_attempt=(a.quote_micro*a.payment_bps+9999)//10000
        maximum_commit_cost=(a.first_attempt_micro+a.accepted_completion_micro+worst_fees_per_attempt+
                             a.tail_per_accepted_micro)
        existing_obligations=outstanding_tail
        available_before_collection=cash-existing_obligations
        if available_before_collection<fixed:
            # A halt cancels unaffordable new operations, not already due support.
            # The previous month's accrual is a real reserved payable and is
            # discharged exactly once without a second profit expense.
            cash-=existing_obligations
            outstanding_tail=0
            if cash!=a.opening_equity_micro+sum(r.get('profit_micro',0) for r in rows):
                raise AssertionError('HALT_MATURITY_AND_PROFIT_RECONCILIATION_FAILED')
            stopped=True
            rows.append({'month':month,'status':'STOP_NOT_ENOUGH_CASH_FOR_FIXED_COST',
                         'opening_cash_micro':begin_cash,'minimum_fixed_required_micro':fixed,
                         'support_cash_settled_micro':existing_obligations,
                         'closing_cash_micro':cash,'protected_tail_micro':outstanding_tail,
                         'cash_available_after_tail_micro':cash,
                         'trailing_12_profit_micro':None,
                         'new_customers':0,'accepted_deliveries':0})
            continue
        affordable=(available_before_collection-fixed)//maximum_commit_cost
        attempted=min(admitted,affordable)
        accepted=attempted*a.acceptance_bps//10000
        actually_paid=accepted*a.collection_bps//10000
        production=attempted*a.first_attempt_micro+accepted*a.accepted_completion_micro
        fees=accepted*a.quote_micro*a.payment_bps//10000
        # Monthly recurring work is from EXISTING customers; new ones start next month.
        # Outreach purchases may use only cash left after old tails and current production.
        tail_new=accepted*a.tail_per_accepted_micro
        marketing_budget=max(0,available_before_collection-fixed-production-fees-tail_new)
        proposed=a.monthly_marketing_target_micro+max(0,prior_profit)*a.prior_profit_reinvestment_bps//10000
        marketing_budget=min(marketing_budget,proposed) if can_sell else 0
        # Each contact reserves the worst-case onboarding fee; only conversions pay it.
        remaining=marketing_budget
        followups=min(warm_ready,remaining//(a.followup_contact_micro+a.onboarding_micro))
        remaining-=followups*(a.followup_contact_micro+a.onboarding_micro)
        followup_new=followups*a.followup_conversion_bps//10000
        warm_ready-=followups
        exhausted+=followups-followup_new
        consented=dormant_eligible*a.winback_consent_bps//10000
        winback_contacts=min(consented,remaining//(a.winback_contact_micro+a.onboarding_micro))
        remaining-=winback_contacts*(a.winback_contact_micro+a.onboarding_micro)
        winback_new=winback_contacts*a.winback_conversion_bps//10000
        dormant_eligible-=winback_contacts
        dormant_unavailable+=winback_contacts-winback_new
        cold_contacts=min(uncontacted,remaining//(a.cold_contact_micro+a.onboarding_micro))
        cold_new=cold_contacts*a.cold_conversion_bps//10000
        uncontacted-=cold_contacts
        # An unsuccessful cold contact does not automatically grant a second-contact right.
        # Eligibility is an explicit sensitivity assumption, NOT evidence of consent.
        cold_nonbuyers=cold_contacts-cold_new
        permitted_followup=cold_nonbuyers*a.followup_permission_bps//10000
        warm_ready+=permitted_followup
        disallowed_followup=cold_nonbuyers-permitted_followup
        exhausted+=disallowed_followup
        new_customers=followup_new+winback_new+cold_new
        active+=new_customers
        acquisition=(followups*a.followup_contact_micro+winback_contacts*a.winback_contact_micro+
                     cold_contacts*a.cold_contact_micro)
        onboarding=new_customers*a.onboarding_micro
        # A failed/declined collection is written off. It is not enterprise cash.
        revenue=accepted*a.quote_micro
        credit_losses=(accepted-actually_paid)*a.quote_micro
        collections=actually_paid*a.quote_micro
        expense_before_tax=fixed+production+fees+acquisition+onboarding+credit_losses+tail_new
        pretax=revenue-expense_before_tax
        tax=max(0,pretax)*a.income_tax_bps//10000
        expense=expense_before_tax+tax
        profit=revenue-expense
        cash+=collections-(existing_obligations+fixed+production+fees+acquisition+onboarding+tax)
        # Previous protected support is paid at maturity; new supported work is accrued now.
        outstanding_tail=tail_new
        if cash<outstanding_tail:
            # A realistic sponsor needs further cash to reserve its obligations.
            stopped=True
            status='STOP_UNDERFUNDED_TAIL';trailing=None
        else:
            status='SIMULATED_FUNDED' if attempted==requested else 'SIMULATED_FUNDED_PARTIAL_CAPACITY'
            trailing=(sum(row['profit_micro'] for row in rows[-11:] if 'profit_micro' in row)+profit if month>=12 and all('profit_micro' in r for r in rows[-11:]) else None)
        if cash-outstanding_tail!=a.opening_equity_micro+sum(r.get('profit_micro',0) for r in rows)+profit:
            raise AssertionError('CASH_AND_PROFIT_RECONCILIATION_FAILED')
        if active+uncontacted+warm_ready+dormant_eligible+dormant_unavailable+exhausted != eligible_total:
            raise AssertionError('CUSTOMER_STOCK_MUST_BE_CONSERVED')
        if accepted>attempted or attempted>monthly_serviceable or attempted>a.monthly_capacity_packets:
            raise AssertionError('ACCEPTED_WORK_EXCEEDS_REALIZED_ELIGIBILITY')
        if cash<0:
            raise AssertionError('NEGATIVE_CASH_INVALID')
        if revenue>retained*a.employer_external_budget_per_customer_month_micro:
            raise AssertionError('BUYER_BUDGET_EXCEEDED')
        row={'month':month,'status':status,'opening_cash_micro':begin_cash,'closing_cash_micro':cash,
             'protected_tail_micro':outstanding_tail,'cash_available_after_tail_micro':cash-outstanding_tail,
             'eligible_organizations':eligible_total,'active_customers':active,'retained':retained,'churned':churned,
             'new_customers':new_customers,'new_cold':cold_new,'new_followup':followup_new,'reactivated':winback_new,
             'cold_contacts':cold_contacts,'followup_contacts':followups,'winback_contacts':winback_contacts,
             'followup_permission_author_assumption_bps':a.followup_permission_bps,
             'followup_rights_assumed_new':permitted_followup,
             'followup_rights_denied_new':disallowed_followup,
             'never_contacted':uncontacted,'warm_followup_pending':warm_ready,'dormant_eligible':dormant_eligible,
             'dormant_unavailable':dormant_unavailable,'exhausted_contact_rights':exhausted,
             'underlying_serviceable_packets_month':monthly_serviceable,'customer_requested_packets':requested,
             'externally_assumed_buyer_budget_micro':retained*a.employer_external_budget_per_customer_month_micro,
             'buyer_budget_committed_micro':revenue,
             'buyer_budget_unused_micro':retained*a.employer_external_budget_per_customer_month_micro-revenue,
             'admitted_attempts':attempted,'unserved_requests':requested-attempted,
             'accepted_deliveries':accepted,'paid_deliveries':actually_paid,
             'revenue_micro':revenue,'collections_micro':collections,'credit_loss_micro':credit_losses,
             'production_micro':production,'processing_micro':fees,'outreach_micro':acquisition,
             'support_accrual_micro':tail_new,'support_cash_settled_micro':existing_obligations,
             'onboarding_micro':onboarding,'fixed_micro':fixed,'tax_micro':tax,'expense_micro':expense,
             'profit_micro':profit,'trailing_12_profit_micro':trailing,
             'human_office_comparable_cost_per_packet_micro':a.full_human_office_cost_micro,
             'customer_avoidable_cost_ceiling_micro':choice_ceiling,
             'buyer_choice':'ELIGIBLE_UNDER_ASSUMED_PRICE_AND_QUALITY' if can_sell else 'NO_BID_ABOVE_AVOIDABLE_COST_OR_VALUE'}
        rows.append(row)
        prior_profit=profit
    milestones={str(target):next((r['month'] for r in rows if r['trailing_12_profit_micro'] is not None and r['trailing_12_profit_micro']>=target*MICRO),None)
                for target in (1_000_000_000,3_000_000_000)}
    return {'schema':SCHEMA,'input_sha256':digest(asdict(a)),'input':asdict(a),
            'evidence':'CONDITIONAL_AGGREGATE_NOT_NATIVE_OR_ACTUAL_COMMERCE',
            'source_work_basis':'BLS PAID JOB COUNTS; WORK PACKETS AND ORGANIZATIONS ARE EXPLICIT AUTHOR ASSUMPTIONS',
            'market_unconstrained_by_initial_loaded_customer_list':True,
            'trailing_12_milestone_months':milestones,'rows':rows,
            'qualification_limitations':['Neither buyer choice nor customer consent has been observed',
                'Default 100% second-contact eligibility is an authored legacy assumption, not permission; the no_followup_rights stress sets it to zero and records rejected repeat contacts',
                'No individual orders, native JournalAccount receipts, real collections, or source-backed production at projected volume',
                'Source job counts do not imply identical tasks, demand or purchase rights',
                'Support tails are conservatively treated as fully payable after one month; earlier v1 reserve-release forecasts omitted this expense',
                'Collection loss, onboarding, support, tax, fixed costs and AI resources are scenario assumptions',
                'Initial capital is a declared simulated equity scenario, not an authorized investment',
                'Comparing human-office avoidable cost is not proof of service price or market capture',
                'Fresh enterprise work and customer acquisition are distinct: existing customer work recurs',
                'Employer spending budgets renew by explicit authored external appropriation; no company cash is created',
                'Cash collections are same-period after operating spend; no settlement-lag or realized claims are modeled',
                'No competitor response is imposed in the primary human-only comparison; price pressure needs separate stress']}


def cases():
    b=Scenario()
    params={
        'central_unvalidated':b,
        'small_100k_no_extra_finance':replace(b,opening_equity_micro=100_000*MICRO),
        'no_paid_acquisition':replace(b,monthly_marketing_target_micro=0,prior_profit_reinvestment_bps=0),
        'no_followup_rights':replace(b,followup_permission_bps=0),
        'weak_conversion':replace(b,cold_conversion_bps=100,followup_conversion_bps=200),
        'more_expensive_outreach':replace(b,cold_contact_micro=125*MICRO),
        'low_retention':replace(b,monthly_retention_bps=8500),
        'no_buyer_value':replace(b,buyer_value_ceiling_micro=80*MICRO),
        'higher_ai_cost':replace(b,first_attempt_micro=30*MICRO,accepted_completion_micro=30*MICRO),
        'low_serviceability':replace(b,serviceable_bps=250),
        'extended_reachable_pool_2m':replace(b,eligible_organizations=2_000_000),
        'low_external_employer_budget':replace(b,employer_external_budget_per_customer_month_micro=95*MICRO),
        'zero_new_employers':replace(b,new_eligible_organizations_per_month=0),
        'no_collection':replace(b,collection_bps=0),
    }
    results={}
    for name,settings in params.items():
        x=simulate(settings);last=x['rows'][-1]
        results[name]={'input_sha256':x['input_sha256'],'last_status':last['status'],
            'last_month_cash_usd':last['closing_cash_micro']/MICRO,
            'last_month_customer_count':last.get('active_customers'),
            'last_month_paid_deliveries':last.get('paid_deliveries'),
            'trailing_12_profit_usd':(last['trailing_12_profit_micro']/MICRO if last['trailing_12_profit_micro'] is not None else None),
            'first_3b_month':x['trailing_12_milestone_months']['3000000000']}
    return {'schema':SCHEMA,'cases':results,'claim':'SENSITIVITY_ONLY_NOT_NATIVE_BUSINESS_EXECUTION'}


if __name__=='__main__':
    print(dumps(cases(),indent=2,sort_keys=True))
