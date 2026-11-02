"""Prospective full-workflow cost assumptions; no measured human/model billing."""
def comparison():
    # Hours are bottom-up authored sensitivity, NOT measurements or CPU ratios.
    stages={
      'acquisition_qualification':(.10,.25,.50),
      'onboarding_intake':(.15,.35,.75),
      'reconciliation_and_open_items':(.50,1.00,2.00),
      'draft_postings_and_handoff':(.25,.50,1.00),
      'independent_verification_correction':(.25,.60,1.20),
      'delivery_support':(.15,.30,.60),
      'shared_development_per_job':(.10,.20,.60),
    }
    wage=24.36
    return {'scope':'FULL_RECEIVABLES_CLOSE_PREPARATION_WITH_CONVENTIONAL_AUTOMATION',
      'human_hours_by_stage_low_central_high':stages,
      'human_hours_total':[sum(v[i] for v in stages.values()) for i in range(3)],
      'base_hourly_wage_usd':wage,'loaded_multiplier_cases':[1.25,1.43,1.75],
      'central_human_labor_cost_usd':sum(v[1] for v in stages.values())*wage*1.43,
      'human_software_per_job_usd_cases':[0,5,15],
      'benchmark_boundary':'H number is labor component plus separately shown software, NOT all-in cost; do not compare111.47 directly with AI core10 as lifecycle advantage. Add matched channel spend, failed work, capacity/capital, fees, taxes and obligations; avoid adding onboard/acquisition labor twice.',
      'human_development_amortization':{'authored_total_hours':20,'authored_jobs':100,'per_job_hours':.2,'alternative':'charge full20h to first job; denominator is not observed demand'},
      'duration_evidence':'AUTHORED_BOTTOM_UP_NOT_TIMED_HUMAN_TRIAL; reusable producer/classic automation available to H',
      'wage_source':'https://www.bls.gov/ooh/office-and-administrative-support/bookkeeping-accounting-and-auditing-clerks.htm',
      'loaded_multiplier_evidence':'AUTHORED_NOT_OCCUPATION_SPECIFIC_MEASURE',
      'frontier_price_proxy_usd_per_million':{'input':10,'output':50,'cached_input':1},
      'price_source':'https://developers.openai.com/api/docs/pricing','price_proxy_name':'Astra public standard input/output proxy','price_checked_date':'2026-11-02','cached_rate_used':False,
      'attempted_unit_core_cases':{
         '5':{'input_tokens':100000,'output_tokens':20000,'model_proxy_usd':2,'compute_usd':.25,'verification_retry_usd':.75,'support_usd':1,'variable_maintenance_usd':1},
         '10':{'input_tokens':200000,'output_tokens':40000,'model_proxy_usd':4,'compute_usd':.50,'verification_retry_usd':1.50,'support_usd':2,'variable_maintenance_usd':2},
         '15':{'input_tokens':300000,'output_tokens':60000,'model_proxy_usd':6,'compute_usd':.75,'verification_retry_usd':2.25,'support_usd':3,'variable_maintenance_usd':3}},
      'token_rationale':'Authored primary-production token envelope only. Verification/retry, support and variable-maintenance budgets are ADDITIONAL frontier-agent resources, not duplicated primary tokens. At same10/50 proxy, each extra1USD can represent50k input plus10k output; this is illustrative allocation, not measured necessity. Base5 totalmodel4.75 pluscompute.25. No paid calls; no permanent callcounts or minimum; cache savings not additionally applied.',
      'maintenance_boundary':'Variable maintenance covers incremental per-client mapping/update work. Fixed500/month covers service monitoring/incident standby. Setup10k covers initial shared engineering. These are disjoint authored scopes, not measured bills.',
      'additional_costs':'Native accounting separately charges shared setup, fixed maintenance, paid acquisition, capacity, onboarding, payment fees, failures and taxes; accepted-unit total is not core5/10/15.',
      'actual_model_billing':None,'human_intervention':'Observed engineering/prompt/review by user and included agents; no observed autonomous market operation. Any deployment requiring human intervention must add its cost, not erase otherwise positive hybrid profit.'}
