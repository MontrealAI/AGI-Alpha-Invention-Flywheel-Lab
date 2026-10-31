"""Reproduce explicit engineering scenarios; none are customer/economic observations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from portfolio_scale.staged_coupling import choose


def scenarios():
    original=json.loads(Path(__file__).with_name('EXAMPLE.json').read_text())
    cases={'responsive_rival':copy.deepcopy(original)}
    passive=copy.deepcopy(original)
    for action in passive['portfolios']:del action['responses']['imitate']
    cases['passive_rival_control']=passive
    pricey=copy.deepcopy(original);pricey['probes'][0]['cost']=30_000_000
    cases['expensive_probe']=pricey
    delayed=copy.deepcopy(original);delayed['probes'][0]['discount_bps']=5000
    cases['delayed_probe']=delayed
    imitation=copy.deepcopy(original)
    imitation['portfolios'][2]['responses']['imitate']['useful'].update(net_receipts=90_000_000,rival_value=30_000_000)
    imitation['portfolios'][2]['responses']['imitate']['not_useful']['rival_value']=30_000_000
    cases['easy_imitation']=imitation
    zero=copy.deepcopy(original);zero['funding']['unrestrictedEarned']=0
    cases['no_earned_funding']=zero
    liability=copy.deepcopy(original)
    for response in liability['portfolios'][2]['responses'].values():
        for o in response.values():o['future_cash_required']=50_000_000
    cases['unaffordable_later_requirement']=liability
    return cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    results={name:choose(request) for name,request in scenarios().items()}
    paths=['portfolio_scale/staged_coupling.py','portfolio_scale/transformational.py',
           'tests/test_staged_coupling.py','campaign/staged-coupling-017/EXAMPLE.json',
           'campaign/staged-coupling-017/reproduce.py']
    report={'scope':'AUTHORED_FINITE_ENGINEERING_MODELS_NOT_BUSINESS_RESULTS',
            'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths},
            'results':results,'actual_spending':0,'actual_revenue':0,
            'native_account_execution':False,'market_calibration':False}
    with args.output.open('x',encoding='utf-8') as f:
        json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({name:dict(decision=r['decision'],expected_net=r['selected']['expected_net']) for name,r in results.items()},indent=2))


if __name__=='__main__':main()
