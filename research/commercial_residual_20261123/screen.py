import json
from fractions import Fraction
from time import perf_counter, process_time

# Frozen inputs: public PROTOCOL.md at 6f7bb6e2bbed0216d875fe0b3bbf385f512a79e4.
start_wall, start_cpu = perf_counter(), process_time()
target = 3_000_000_000
submitted, passed = 321_021, 226_899
accepted, certified = 138_300_000_000, 128_400_000_000
ach = 737_000_000
stock = accepted - certified
fees = {str(rate): stock * rate // 100 for rate in (10, 20, 25, 100)}
required_fraction = Fraction(target, stock)
ach_fraction = Fraction(target, ach)
grid_requirement = Fraction(target, 8200)
checks = {
    'declaration_count_reconciles': submitted - passed + passed == submitted,
    'stock_reconciles': stock + certified == accepted,
    'fee_identity': all(100 * value == stock * int(rate) for rate, value in fees.items()),
    'stock_required_identity': required_fraction * stock == target,
    'ach_cannot_reach_target_even_at_100_percent': ach < target and ach_fraction > 1,
    'cms_average_identity': 1_500_000_000 * 10 == 15_000_000_000,
    'grid_required_identity': grid_requirement * 8200 == target,
}
result = {
    'not_recorded_passed_declarations': submitted - passed,
    'approx_accepted_minus_certified_usd': stock,
    'hypothetical_gross_fees_usd_by_percent': fees,
    'required_gross_fraction_exact': str(required_fraction),
    'required_gross_percent': float(100 * required_fraction),
    'ach_missing_subset_max_theoretical_gross_usd': ach,
    'ach_required_gross_fraction_exact': str(ach_fraction),
    'ach_required_gross_percent': float(100 * ach_fraction),
    'cms_simple_annual_mean_usd': 15_000_000_000 // 10,
    'grid_required_net_usd_per_stock_project_exact': str(grid_requirement),
    'grid_required_net_usd_per_stock_project': float(grid_requirement),
    'checks': checks,
    'commercial_admission': False,
    'native_account_operation': False,
    'actual_billing': None,
    'calculation_cpu_seconds': process_time() - start_cpu,
    'calculation_wall_seconds': perf_counter() - start_wall,
}
print(json.dumps(result, indent=2, sort_keys=True))
if not all(checks.values()):
    raise SystemExit(1)
