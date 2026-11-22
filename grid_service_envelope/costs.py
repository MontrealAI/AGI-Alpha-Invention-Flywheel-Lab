"""Conditional cost/financing requirements; no ledger, money or financing authority."""
from .inputs import registration


def annuity(rate, years):
    return rate/(1-(1+rate)**-years)


def cost_requirements(witness):
    r=registration(); c=r['modeled_usd']; f=r['finance']; k=witness['capacities'];scale=witness['it_capacity_mw']
    items={'compute_hardware':scale*c['it_capex_per_mw'],'site_electrical_cooling':scale*c['site_capex_per_mw'],'battery_energy':k['battery_mwh']*c['battery_capex_per_mwh'],'battery_power':k['battery_mw']*c['battery_power_capex_per_mw'],'backup':k['backup_mw']*c['backup_capex_per_mw'],'connection_setup':c['connection_setup'],'construction_verification':c['construction_verification']}
    direct=sum(items.values());contingency=direct*c['construction_contingency_fraction'];funded_assets=direct+contingency
    reserve=direct*c['performance_reserve_fraction_of_capex'];daily=witness['worst_daily_opex_usd'];annual_opex=365*daily+scale*c['fixed_opex_per_it_mw_year'];working=daily*c['working_capital_days']+scale*c['fixed_opex_per_it_mw_year']*c['working_capital_days']/365
    annual_assets=funded_assets*annuity(c['capital_opportunity_rate'],c['capital_life_years']);reserve_opportunity=reserve*c['capital_opportunity_rate'];subtotal=annual_assets+reserve_opportunity+annual_opex;work_per_year=12*scale*365
    debt=funded_assets*f['hypothetical_debt_fraction'];fee=debt*f['hypothetical_fee_fraction'];equity=funded_assets-debt+fee+reserve+working;debt_service=debt*annuity(f['hypothetical_debt_rate'],f['hypothetical_debt_term_years'])
    return {'basis':'USD illustrative coefficients, not quotes; annual repetition is conditional accounting, not365day execution','asset_line_items_usd':items,'direct_assets_usd':direct,'construction_contingency_usd':contingency,'asset_funding_usd':funded_assets,'restricted_performance_reserve_usd':reserve,'working_capital_usd':working,'all_cash_initial_requirement_usd':funded_assets+reserve+working,'annualized_asset_recovery_and_opportunity_usd':annual_assets,'annual_reserve_opportunity_usd':reserve_opportunity,'annual_operating_subtotal_usd':annual_opex,'annual_economic_subtotal_usd':subtotal,'annual_work_units_if_daily_repeat':work_per_year,'break_even_usd_per_modeled_work_unit_excluding_unknowns':subtotal/work_per_year,'unknown_additive_cost_U':'Utility incremental dispatch/startup/no-load, tax, permitting, real interconnection/reinforcement, emissions permissions, rights, outage liabilities and other local complete-delivery costs uncalibrated. True price=(subtotal+U)/work; U need not be small.','conditional_debt':{'available':None,'amount_usd':debt,'fee_usd':fee,'initial_equity_and_reserves_usd':equity,'annual_debt_service_usd':debt_service,'cash_receipts_required_before_equity_return_usd':annual_opex+debt_service,'note':'Debt principal is financing, not revenue. Debt service is cash-flow obligation, not added to economic annuity subtotal. No loan or account created.'},'reference_funding_coverage':{str(v):v>=funded_assets+reserve+working for v in f['reference_funding_usd']},'real_profit':None,'willingness_to_pay':None,'funding_secured':False}
