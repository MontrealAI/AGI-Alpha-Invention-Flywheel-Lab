"""Explicit recovery plumbing around the prospectively frozen economic policy.

The copied function below is checked against a mechanical AST transformation of
the original source. Only its output handling, account adapter, operation-state
markers and recovery resource annotation differ. No offer, cost, timing, tax,
refusal, funding or settlement branch may change under this guard.
"""
from __future__ import annotations

import ast
import copy
import hashlib

from portfolio071 import economics as original
from portfolio071.economics import (
    COSTS_USD, HORIZON_DAYS, MICRO, Path, World, _calendar, _pending_tax,
    _spend, aggregate_native, asdict, commercial_choice, digest, population,
    prospective_terms, strict_json, time, trailing_profit,
)
from portfolio071.recovery import write_same as _write_new

ORIGINAL_POLICY_SHA256 = "7fe3d1a874567f8732db6ddf1b4e521885fcdf74c396f8bea10afa908cb9e4bd"
ORIGINAL_BINDINGS = (
    "COSTS_USD", "HORIZON_DAYS", "MICRO", "Path", "World", "_calendar",
    "_pending_tax", "_spend", "aggregate_native", "asdict", "commercial_choice",
    "digest", "population", "prospective_terms", "strict_json", "time", "trailing_profit",
)


def _is_operation(node):
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        target = call.func
        if isinstance(target, ast.Name) and target.id == "_spend":
            return True
        if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                and target.value.id == "account"
                and target.attr in {"execute", "cost", "advance_financial"}):
            return True
    return False


class _RecoveryPlumbing(ast.NodeTransformer):
    """The complete, finite whitelist of permitted changes to the old policy."""

    def visit_FunctionDef(self, node):
        if node.name != "execute_trajectory":
            raise ValueError("EXACT_ORIGINAL_CONTROLLER_REQUIRED")
        node.name = "execute_recovered"
        node.args.kwonlyargs.append(ast.arg(arg="session"))
        node.args.kw_defaults.append(None)
        self.generic_visit(node)
        node.body.insert(0, ast.Expr(value=ast.Call(func=ast.Name(id="validate_controller", ctx=ast.Load()),
                                                   args=[], keywords=[])))
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == "JournalAccount":
            if len(node.args) != 3 or ast.unparse(node.args[2]) != "output / 'account.sqlite'":
                raise ValueError("EXACT_ORIGINAL_ACCOUNT_OPEN_REQUIRED")
            node.func = ast.Attribute(value=ast.Name(id="session", ctx=ast.Load()), attr="account", ctx=ast.Load())
            node.args = node.args[:2]
        if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "output" and node.func.attr == "mkdir"):
            matches = [item for item in node.keywords if item.arg == "exist_ok"]
            if len(matches) != 1 or not isinstance(matches[0].value, ast.Constant) or matches[0].value.value is not False:
                raise ValueError("EXACT_ORIGINAL_OUTPUT_CREATION_REQUIRED")
            matches[0].value = ast.Constant(value=True)
        return node

    @staticmethod
    def _marked(node):
        marker = ast.Expr(value=ast.Call(
            func=ast.Attribute(value=ast.Name(id="account", ctx=ast.Load()), attr="mark", ctx=ast.Load()),
            args=[ast.Constant(value=f"stable-original-line-{node.lineno}"),
                  ast.Call(func=ast.Name(id="locals", ctx=ast.Load()), args=[], keywords=[])], keywords=[]))
        return [marker, node]

    def visit_Expr(self, node):
        self.generic_visit(node)
        return self._marked(node) if _is_operation(node) else node

    def visit_Assign(self, node):
        self.generic_visit(node)
        result = self._marked(node) if _is_operation(node) else [node]
        if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Subscript)
                and isinstance(node.targets[0].value, ast.Name) and node.targets[0].value.id == "record"
                and isinstance(node.targets[0].slice, ast.Constant)
                and node.targets[0].slice.value == "resource_measurement"):
            result.append(ast.Expr(value=ast.Call(
                func=ast.Attribute(value=ast.Name(id="session", ctx=ast.Load()), attr="annotate_resources", ctx=ast.Load()),
                args=[ast.Name(id="record", ctx=ast.Load())], keywords=[])))
        return result


def expected_controller_ast():
    raw = Path(original.__file__).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_POLICY_SHA256:
        raise ValueError("ORIGINAL_ECONOMIC_POLICY_SOURCE_CHANGED")
    parsed = ast.parse(raw)
    candidates = [item for item in parsed.body if isinstance(item, ast.FunctionDef) and item.name == "execute_trajectory"]
    if len(candidates) != 1:
        raise ValueError("UNIQUE_ORIGINAL_CONTROLLER_REQUIRED")
    return ast.fix_missing_locations(_RecoveryPlumbing().visit(copy.deepcopy(candidates[0])))


def validate_controller():
    """Fail before output creation or account reopen if any policy branch changes."""
    expected = expected_controller_ast()
    raw = Path(__file__).read_bytes()
    parsed = ast.parse(raw)
    candidates = [item for item in parsed.body if isinstance(item, ast.FunctionDef) and item.name == "execute_recovered"]
    if len(candidates) != 1:
        raise ValueError("UNIQUE_RECOVERY_CONTROLLER_REQUIRED")
    normalized = ast.dump(candidates[0], include_attributes=False)
    if normalized != ast.dump(expected, include_attributes=False):
        raise ValueError("RECOVERY_ECONOMIC_POLICY_AST_DIFFERS")
    if any(globals()[name] is not getattr(original, name) for name in ORIGINAL_BINDINGS):
        raise ValueError("ORIGINAL_ECONOMIC_HELPER_BINDING_CHANGED")
    from portfolio071.recovery import write_same
    if _write_new is not write_same:
        raise ValueError("RECOVERY_OUTPUT_WRITER_BINDING_CHANGED")
    return {"accepted": True, "original_policy_sha256": ORIGINAL_POLICY_SHA256,
            "recovery_controller_sha256": hashlib.sha256(raw).hexdigest(),
            "expected_function_ast_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
            "operation_markers": sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                     and isinstance(n.func.value, ast.Name) and n.func.value.id == "account"
                                     and n.func.attr == "mark" for n in ast.walk(expected)),
            "scope": "Exact economic-policy AST under the declared recovery-only plumbing; adapter semantics require independent tests."}


def execute_recovered(root, manifest, output, *, capital_usd, world=World(), policy='working_capital_aware', earned_only_k2=False, horizon_days=HORIZON_DAYS, infer_idle_days=True, session):
    validate_controller()
    if policy not in {'working_capital_aware', 'stylized_prepaid_reach_capacity'}:
        raise ValueError('REGISTERED_POLICY_REQUIRED')
    if type(capital_usd) is not int or capital_usd < 0 or type(horizon_days) is not int or (horizon_days < 1):
        raise ValueError('REGISTERED_CAPITAL_AND_HORIZON_REQUIRED')
    if type(infer_idle_days) is not bool:
        raise ValueError('EXPLICIT_IDLE_DAY_OBSERVATION_POLICY_REQUIRED')
    from portfolio071.service import load_contracts
    root, output = (Path(root).absolute(), Path(output).absolute())
    jobs = load_contracts(root, manifest)
    by_purpose = {}
    for row in manifest['jobs']:
        request = strict_json((root / row['input']).read_bytes())
        by_purpose[request['task']] = row['id']
    if set(by_purpose) != {'heat_delivery', 'thermal_continuity'}:
        raise ValueError('TWO_DISTINCT_ACCEPTED_SCIENTIFIC_FUNCTIONS_REQUIRED')
    output.mkdir(parents=True, exist_ok=True)
    manifest_sha = _write_new(output / 'manifest.json', manifest)
    started_wall, started_cpu = (time.monotonic(), time.process_time())
    identity = f'{world.name}-{capital_usd}-{policy}-{int(earned_only_k2)}'
    record = {'schema': 'portfolio071/native-economic-trajectory/v1', 'id': identity, 'scope': 'CONDITIONAL_NATIVE_DESIGN_LICENSE_SIMULATION_NOT_PHYSICAL_DEPLOYMENT', 'world': asdict(world), 'capital_usd': capital_usd, 'policy': policy, 'infer_idle_days': infer_idle_days, 'earned_only_k2': earned_only_k2, 'manifest_sha256': manifest_sha, 'initial_finance': 'ASSUMED_RECEIVED_OPENING_EQUITY_FRESH_COUNTERFACTUAL_NOT_SECURED_FUNDS', 'decisions': [], 'daily': [], 'cost_receipts': [], 'tax_settlements': [], 'financing': [], 'K2_funding': None, 'population': population(world), 'stop_reason': None, 'actual_scientific_artifacts': len(jobs), 'modeled_licenses': 0, 'external_revenue_usd': 0, 'installed_physical_sites': 0, 'post_horizon_collected_licenses': 0, 'actual_model_billing': None, 'modeled_human_internal_hours': 18, 'actual_human_runtime_intervention_minutes_observed': 0, 'unmeasured_human_minutes': 'User mandate creation/oversight and historical engineering time are not instrumented; zero total-human-time claim is unsupported.'}
    pending = []
    collected_years = set()
    prepaid = {}
    prepayment_done = False
    tax_paid = 0
    operating_stop_day = None
    k1_ready = True
    k2_ready = False
    horizon_hour = horizon_days * 24
    with session.account(root, manifest, opening=capital_usd * MICRO, working=0, contract='portfolio071-' + digest(identity)[:24]) as account:
        for cost_name in ('research_and_failed_attempts', 'K1_construction', 'independent_validation', 'data_rights_and_legal_review', 'retirement_archive_and_support'):
            amount_usd = COSTS_USD[cost_name] * (world.research_cost_multiplier if cost_name == 'research_and_failed_attempts' else 1)
            account.mark('stable-original-line-259', locals())
            receipt = _spend(account, cost_name, amount_usd, 0)
            if receipt is None:
                record['decisions'].append({'day': 0, 'decision': 'REFUSE_UNFUNDED_RESEARCH', 'cost': cost_name})
                k1_ready = False
                operating_stop_day = 0
                record['stop_reason'] = 'INITIAL_RESEARCH_PREFUNDING_UNAVAILABLE'
                break
            record['cost_receipts'].append(receipt)
        if world.external_financing_requested:
            before = account.snapshot()
            try:
                account.mark('stable-original-line-270', locals())
                account.execute('finance', {'id': 'uncommitted-draw', 'amount': 1000000 * MICRO}, 0)
            except ValueError as error:
                record['financing'].append({'decision': 'REFUSED', 'reason': str(error), 'requested_usd': 1000000, 'cash_received_usd': 0, 'cash_unchanged': account.snapshot() == before})
            else:
                raise AssertionError('UNSUPPORTED_FINANCING_WAS_ACCEPTED')
        event_days = {0, 180}
        event_days.update(range(0, horizon_days, 365))
        for index in range(len(record['population'])):
            event_days.update(range(15 + index * 28, horizon_days, 365))
        for day in range(horizon_days):
            if infer_idle_days and day not in event_days:
                unchanged = {**record['daily'][-1], 'day': day, 'observation': 'INFERRED_UNCHANGED_NO_NATIVE_EVENT'}
                record['daily'].append(unchanged)
                continue
            hour = day * 24
            account.mark('stable-original-line-291', locals())
            account.advance_financial(hour)
            due, pending = ([p for p in pending if p['due_day'] <= day], [p for p in pending if p['due_day'] > day])
            for obligation in sorted(due, key=lambda p: (p['due_day'], p['id'])):
                action = 'refund' if obligation['default'] else 'release'
                account.mark('stable-original-line-295', locals())
                account.execute('event', {'id': obligation['id'], 'action': action, 'event_id': obligation['id'] + '-' + action}, hour)
                if not obligation['default']:
                    record['modeled_licenses'] += 1
                    collected_years.add((obligation['coalition'], obligation['year']))
                    state = account.snapshot()['summary']
                    pretax = state['profit'] + tax_paid
                    due_tax = max(0, pretax * world.tax_bps // 10000 - tax_paid)
                    if due_tax > obligation['price_usd'] * MICRO or due_tax > state['available']:
                        raise AssertionError('PRERELEASE_TAX_COMMITMENT_INSUFFICIENT')
                    if due_tax:
                        account.mark('stable-original-line-306', locals())
                        account.cost('tax-' + obligation['id'], due_tax, hour)
                        tax_paid += due_tax
                    record['tax_settlements'].append({'order_id': obligation['id'], 'hour': hour, 'post_horizon': False, 'gross_collection_microUSD': obligation['price_usd'] * MICRO, 'available_before_tax_microUSD': state['available'], 'tax_paid_microUSD': due_tax, 'payables_after_tax_microUSD': account.snapshot()['summary']['payables']})
                record['decisions'].append({'day': day, 'decision': 'ESCROW_CANCELLATION_REFUND' if obligation['default'] else 'COLLECTED_MODELED_LICENSE', 'order_id': obligation['id'], 'price_usd': obligation['price_usd']})
            if operating_stop_day is None and day % 365 == 0:
                overhead = COSTS_USD['annual_inference_compute_storage_maintenance'] + COSTS_USD['annual_administration_insurance_security']
                account.mark('stable-original-line-316', locals())
                receipt = _spend(account, f'overhead-year-{day // 365}', overhead, hour, tax_commitment=_pending_tax(pending, world))
                if receipt is None:
                    operating_stop_day = day
                    record['stop_reason'] = 'OVERHEAD_UNFUNDED'
                else:
                    record['cost_receipts'].append(receipt)
            if operating_stop_day is None and day == 180 and k1_ready and world.qualification_passes:
                account.mark('stable-original-line-324', locals())
                receipt = _spend(account, 'K2-development', COSTS_USD['K2_construction_and_requalification'], hour, expected=10000, earned_only=earned_only_k2, tax_commitment=_pending_tax(pending, world), work={'accepted_scientific_job': by_purpose['thermal_continuity'], 'purpose': 'Distinct thermal continuity design; accepted arithmetic, no physical qualification'})
                record['K2_funding'] = receipt
                k2_ready = receipt is not None
                if receipt is not None:
                    record['cost_receipts'].append(receipt)
                record['decisions'].append({'day': day, 'decision': 'K2_FUNDED' if k2_ready else 'K2_FUNDING_REFUSED', 'funding': receipt['funding'] if receipt else None})
            if operating_stop_day is None and k1_ready:
                for index, group in enumerate(record['population']):
                    first = 15 + index * 28
                    if day < first or (day - first) % 365 != 0:
                        continue
                    year = (day - first) // 365
                    renewal = (group['id'], year - 1) in collected_years
                    ident = f'license-{index:02d}-{year}'
                    choice = commercial_choice(group, world, day, renewal)
                    selected = choice['selected']
                    if selected is None:
                        contact = COSTS_USD['renewal_review'] if renewal else COSTS_USD['coalition_contact']
                        prepaid_contact = bool(year == 0 and group['id'] in prepaid)
                        if prepaid_contact:
                            contact = 0
                        account.mark('stable-original-line-350', locals())
                        receipt = _spend(account, 'unsuccessful-contact-' + ident, contact, hour, tax_commitment=_pending_tax(pending, world))
                        if receipt is not None:
                            record['cost_receipts'].append(receipt)
                        record['decisions'].append({'day': day, 'coalition': group['id'], 'decision': 'BUYER_OR_SUPPLIER_REFUSAL', 'contact_paid': receipt is not None, 'prepaid_contact_applied': prepaid_contact, 'renewal_after_collected_prior_year': renewal, 'choice': choice})
                        continue
                    state = account.snapshot()['summary']
                    if policy == 'stylized_prepaid_reach_capacity' and (not prepayment_done):
                        prepayment_done = True
                        for forecast_group in record['population']:
                            forecast = commercial_choice(forecast_group, world, day, False)['selected']
                            if forecast is None:
                                continue
                            prepay_cost = forecast['cost_usd']
                            account.mark('stable-original-line-366', locals())
                            receipt = _spend(account, 'prepaid-first-year-' + forecast_group['id'], prepay_cost, hour, tax_commitment=_pending_tax(pending, world), work={'coalition': forecast_group['id'], 'forecast_at_day': day, 'cost_breakdown': 'Same contact, integration, review, prepaid support and payment-fee quote as per-job control; unused capacity nonrefundable.'})
                            if receipt is not None:
                                prepaid[forecast_group['id']] = prepay_cost
                                record['cost_receipts'].append(receipt)
                        state = account.snapshot()['summary']
                    prepayment = prepaid.get(group['id'], 0) if year == 0 else 0
                    existing_tax = _pending_tax(pending, world)
                    feasible_cash = [c for c in choice['evaluated'] if c['decision'] == 'LICENSE' and (max(0, c['cost_usd'] - prepayment) + c['price_usd'] + 1) * MICRO + (c['price_usd'] * MICRO * world.tax_bps + 9999) // 10000 + existing_tax <= state['available']]
                    choice['unconstrained_selected'] = selected
                    if feasible_cash:
                        selected = max(feasible_cash, key=lambda c: (c['contribution_before_tax_usd'], -c['price_usd']))
                        choice['selected'] = selected
                    choice['cash_feasible_candidate_count'] = len(feasible_cash)
                    choice['cash_constrained_choice_regret_usd'] = max([c['contribution_before_tax_usd'] for c in feasible_cash] + [0]) - (selected['contribution_before_tax_usd'] if feasible_cash else 0)
                    new_tax = (selected['price_usd'] * MICRO * world.tax_bps + 9999) // 10000
                    needed = (max(0, selected['cost_usd'] - prepayment) + selected['price_usd'] + 1) * MICRO + new_tax + existing_tax
                    if state['available'] < needed or state['investmentStopped']:
                        record['decisions'].append({'day': day, 'coalition': group['id'], 'decision': 'PROFITABLE_BUT_UNFUNDED', 'available_microUSD': state['available'], 'required_microUSD': needed, 'renewal_after_collected_prior_year': renewal, 'contribution_before_tax_usd': selected['contribution_before_tax_usd'], 'choice': choice})
                        continue
                    unpaid_cost = max(0, selected['cost_usd'] - prepayment)
                    account.mark('stable-original-line-396', locals())
                    receipt = _spend(account, 'delivery-and-prepaid-support-' + ident, unpaid_cost, hour, expected=selected['contribution_before_tax_usd'], tax_commitment=existing_tax + new_tax, work={'coalition': group['id'], 'selected_members': selected['members'], 'scope': 'Complete modeled design license integration and prepaid support'})
                    if receipt is None and unpaid_cost:
                        raise AssertionError('AFFORDABLE_PRECOMMITTED_COST_REFUSED')
                    if receipt is not None:
                        record['cost_receipts'].append(receipt)
                    record['modeled_human_internal_hours'] += 12
                    buyer_id = group['id'] + '-year-' + str((day - first) // 365)
                    price = selected['price_usd'] * MICRO
                    due_day = day + world.collection_delay_days
                    terms = prospective_terms(ident, price, (due_day + 90) * 24, due_day * 24, residual=1000 * MICRO, counterparty_obligations='Synthetic consortium members voluntarily choose a shared already-verified computational design license. No physical performance or external agreement is claimed.')
                    account.mark('stable-original-line-411', locals())
                    account.execute('wallet', {'buyer': buyer_id, 'amount': price}, hour)
                    account.mark('stable-original-line-412', locals())
                    account.execute('register_terms', {'id': ident + '-terms', 'terms': terms}, hour)
                    account.mark('stable-original-line-413', locals())
                    account.execute('offer', {'id': ident, 'buyer': buyer_id, 'price': price, 'job_id': by_purpose['thermal_continuity'] if k2_ready else by_purpose['heat_delivery'], 'deadline': (due_day + 10) * 24, 'terms_id': ident + '-terms'}, hour)
                    for action in ('consent', 'fund', 'prepare'):
                        account.mark('stable-original-line-417', locals())
                        account.execute('event', {'id': ident, 'action': action, 'event_id': ident + '-' + action}, hour)
                    pending.append({'id': ident, 'due_day': due_day, 'price_usd': selected['price_usd'], 'coalition': group['id'], 'year': year, 'default': bool(world.default_every and (index + day // 365 + 1) % world.default_every == 0)})
                    event_days.update((due_day, due_day + 91))
                    record['decisions'].append({'day': day, 'coalition': group['id'], 'decision': 'ACCEPTED_CONDITIONAL_LICENSE', 'order_id': ident, 'choice': choice, 'payment_due_day': due_day, 'renewal_after_collected_prior_year': renewal, 'prepaid_capacity_applied_usd': min(prepayment, selected['cost_usd']), 'new_delivery_cost_usd': unpaid_cost})
            state = account.snapshot()['summary']
            if state['payables'] > 0 or state['investmentStopped']:
                if operating_stop_day is None:
                    operating_stop_day = day
                    record['stop_reason'] = 'NATIVE_OBLIGATIONS_OR_STOP_PRECLUDE_EXPANSION'
            record['daily'].append({'day': day, 'observation': 'AUTHORITATIVE_NATIVE_EVENT_SNAPSHOT', 'cash_microUSD': state['cash'], 'profit_microUSD': state['profit'], 'collections_microUSD': state['collections'], 'restricted_microUSD': state['tailReserve'] + state['custodyReserve'] + state['workingCapital'], 'payables_microUSD': state['payables'], 'available_microUSD': state['available'], 'pending_tax_commitment_microUSD': _pending_tax(pending, world), 'tax_commitments_covered': state['available'] >= _pending_tax(pending, world)})
        close_hour = horizon_hour - 1
        account.mark('stable-original-line-439', locals())
        account.cost('operating-clock-close-prepaid-retirement', 0, close_hour)
        record['operating_endpoint'] = account.snapshot()['summary']
        native_at_horizon = account.export()
        native_audit_at_horizon = account.audit()
        aggregation = aggregate_native(native_at_horizon['ledger'])
        rolling = trailing_profit(native_at_horizon['ledger'], operating_end_hour=horizon_hour, operating_complete=True, aggregation=aggregation)
        record['rolling_profit'] = {**rolling, 'start_date_inclusive': _calendar(max(0, horizon_hour - 365 * 24)), 'end_date_exclusive': _calendar(horizon_hour)}
        record['operating_complete'] = True
        record['observation_counts'] = {'authoritative_native_event_snapshots': sum((r['observation'] == 'AUTHORITATIVE_NATIVE_EVENT_SNAPSHOT' for r in record['daily'])), 'inferred_unchanged_daily_states': sum((r['observation'] == 'INFERRED_UNCHANGED_NO_NATIVE_EVENT' for r in record['daily']))}
        record['operating_stop_day'] = operating_stop_day
        record['stop_reason'] = record['stop_reason'] or 'REGISTERED_HORIZON_COMPLETE'
        record['native_account_audit'] = native_audit_at_horizon
        record['tax_paid_microUSD'] = tax_paid
        record['opening_plus_flows_reconciles'] = capital_usd * MICRO + record['operating_endpoint']['collections'] + record['operating_endpoint']['recoveryIncome'] - record['operating_endpoint']['expensePaid'] == record['operating_endpoint']['cash']
        record['milestone_1b'] = bool(rolling['trailing_365_day_profit_microUSD'] is not None and rolling['trailing_365_day_profit_microUSD'] >= 1000000000 * MICRO)
        record['milestone_3b'] = bool(rolling['trailing_365_day_profit_microUSD'] is not None and rolling['trailing_365_day_profit_microUSD'] >= 3000000000 * MICRO)
        record['external_financing_received_usd'] = 0
        record['native_export_sha256'] = _write_new(output / 'native-at-horizon.json', native_at_horizon)
        drain_days = sorted({p['due_day'] for p in pending} | {p['due_day'] + 91 for p in pending})
        for row in native_at_horizon['ledger'].get('prospective_terms', []):
            terms = strict_json(row['terms'])
            if terms['maturity_day'] >= horizon_hour:
                drain_days.append(terms['maturity_day'] // 24 + 1)
        for day in sorted(set(drain_days)):
            hour = day * 24
            if hour < horizon_hour:
                continue
            due = [p for p in pending if p['due_day'] == day]
            for obligation in due:
                action = 'refund' if obligation['default'] else 'release'
                account.mark('stable-original-line-476', locals())
                account.execute('event', {'id': obligation['id'], 'action': action, 'event_id': obligation['id'] + '-' + action}, hour)
                if not obligation['default']:
                    record['post_horizon_collected_licenses'] += 1
                    state = account.snapshot()['summary']
                    pretax = state['profit'] + tax_paid
                    due_tax = max(0, pretax * world.tax_bps // 10000 - tax_paid)
                    if due_tax > obligation['price_usd'] * MICRO or due_tax > state['available']:
                        raise AssertionError('PRERELEASE_TAX_COMMITMENT_INSUFFICIENT')
                    if due_tax:
                        account.mark('stable-original-line-486', locals())
                        account.cost('tax-' + obligation['id'], due_tax, hour)
                        tax_paid += due_tax
                    record['tax_settlements'].append({'order_id': obligation['id'], 'hour': hour, 'post_horizon': True, 'gross_collection_microUSD': obligation['price_usd'] * MICRO, 'available_before_tax_microUSD': state['available'], 'tax_paid_microUSD': due_tax, 'payables_after_tax_microUSD': account.snapshot()['summary']['payables']})
            account.mark('stable-original-line-492', locals())
            account.advance_financial(hour)
        record['post_horizon_drain_endpoint'] = account.snapshot()['summary']
        record['total_tax_after_drain_microUSD'] = tax_paid
        record['post_horizon_native_audit'] = account.audit()
        record['drain_export_sha256'] = _write_new(output / 'native-after-drain.json', account.export())
    record['resource_measurement'] = {'process_cpu_seconds': time.process_time() - started_cpu, 'wall_seconds': time.monotonic() - started_wall, 'model_api_calls': 0, 'incremental_spending_authorized_usd': 0}
    session.annotate_resources(record)
    profit = record['operating_endpoint']['profit']
    record['investor_test'] = {'required_simple_annual_return_bps': 1000, 'cumulative_company_profit_microUSD': profit, 'horizon_days': horizon_days, 'meets_hypothetical_equity_return_hurdle': profit * 365 * 10000 >= capital_usd * MICRO * horizon_days * 1000, 'financing_secured': False, 'founder_dilution': 'UNSPECIFIED_NO_EQUITY_TRANSACTION_MODELED', 'note': 'Investor hurdle is a separate feasibility diagnostic, not a fictitious wage or company expense.'}
    _write_new(output / 'trajectory.json', record)
    return record
