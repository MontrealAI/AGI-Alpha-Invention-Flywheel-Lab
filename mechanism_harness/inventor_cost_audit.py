"""Independent expense completeness for the declared Omega native contract.

The canonical financial auditor proves integrity of posted entries. This layer
also proves that every required expense exists exactly once, including a zero
modeled tax. It neither owns money nor changes tax policy or historical accounts.
"""
from __future__ import annotations


def audit_costs(exported, result, records, tariff, tax_record):
    journal=exported['connected_journal']['entries']
    actions=exported['ledger']['actions']
    settled=[r for r in records if r['complete']]
    expected_spends={'omega-setup','omega-discovery'}|{f"quote-{r['index']}" for r in records}|{f"produce-{r['index']}" for r in settled}
    if result['successor'] is not None:expected_spends.add('omega-successor')
    spends=[e for e in journal if e['request'].get('operation')=='spend']
    if (len(spends)!=len(expected_spends) or {e['request']['id'] for e in spends}!=expected_spends
            or any(e['status']!='COMPLETE' for e in spends)):
        raise ValueError('COST_CLOSURE_UNREPORTED_OR_MISSING_SPEND')
    expected={}
    for r in settled:
        price=r['price']
        if type(price) is not int or price<0:raise ValueError('COST_CLOSURE_EXACT_PRICE_REQUIRED')
        expected[f"fee-{r['index']}"]=((price*tariff['payment_bps']+9999)//10000,r['day'])
    expected['annual-maintenance']=(tariff['annual_maintenance'],364)
    pretax_cost=sum(e['request']['amount'] for e in spends)+sum(amount for amount,_ in expected.values())
    revenue=sum(r['price'] for r in settled)
    tax=max(0,revenue-pretax_cost)*tariff['tax_bps']//10000
    if type(tax_record) is not dict or set(tax_record)!={'amount'} or type(tax_record['amount']) is not int or tax_record['amount']!=tax:
        raise ValueError('COST_CLOSURE_TAX_DERIVATION_CHANGED')
    expected['modeled-tax']=(tax,364)
    direct=[e for e in journal if e['request'].get('operation')=='execute' and e['request'].get('op')=='cost']
    if len(direct)!=len(expected) or {e['request']['args']['id'] for e in direct}!=set(expected):
        raise ValueError('COST_CLOSURE_MISSING_DUPLICATED_OR_EXTRA_DEBIT')
    positions={}
    for entry in direct:
        req=entry['request'];ident=req['args']['id'];amount,day=expected[ident]
        if (entry['status']!='COMPLETE' or set(req['args'])!={'id','amount'}
                or type(req['args']['amount']) is not int or req['args']['amount']!=amount
                or type(req['day']) is not int or req['day']!=day):
            raise ValueError('COST_CLOSURE_AMOUNT_OR_DAY_CHANGED')
        native=[(j,a) for j,a in enumerate(actions) if a['op']=='cost' and a['args'].get('id')==ident]
        if len(native)!=1 or native[0][1]['args']!=req['args'] or native[0][1]['day']!=day:
            raise ValueError('COST_CLOSURE_NATIVE_DEBIT_NOT_EXACTLY_ONCE')
        positions[ident]=native[0][0]
    if positions['modeled-tax']<=positions['annual-maintenance']:
        raise ValueError('COST_CLOSURE_TAX_PRECEDES_MAINTENANCE')
    for r in settled:
        order=f"omega-trade-{r['index']}"
        releases=[j for j,a in enumerate(actions) if a['op']=='event' and a['args'].get('id')==order and a['args'].get('action')=='release']
        if len(releases)!=1 or positions[f"fee-{r['index']}"]>=releases[0]:
            raise ValueError('COST_CLOSURE_FEE_AFTER_RELEASE')
    total=pretax_cost+tax;summary=exported['ledger']['summary']
    if (summary['revenue']!=revenue or summary['collections']!=revenue
            or summary['expenses']!=total or summary['expensePaid']!=total
            or summary['profit']!=revenue-total):
        raise ValueError('COST_CLOSURE_RECONSTRUCTION_MISMATCH')
    return {'accepted':True,'expected_expenses':total,'expected_revenue':revenue,
            'modeled_tax':tax,'scope':'Exact registered expense completeness, not actual market or tax evidence.'}
