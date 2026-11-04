"""Independent finite rival actions and end-to-end checks. Read-only, synthetic examples."""
import argparse
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import sys
from unittest.mock import patch

def allocations(spec, scene, seller, price):
    recipients={'seller':[], 'rival':[], 'outside':[]}
    gains=0
    for b in spec['buyer_profiles']:
        if b['id'] not in scene['active_buyers']:
            continue
        offers=[(b['outside_utility'],2,'outside')]
        for tag, priority, offer in [('rival',1,price), ('seller',0,seller)]:
            if offer is not None and b['budget'] >= offer:
                offers.append((b['value']-offer,priority,tag))
        utility,_,winner=max(offers)
        recipients[winner].append(b['id'])
        if winner=='seller':
            gains+=utility-b['outside_utility']
    return recipients,gains

def independent_responses(spec, selected, scene, seller):
    base=spec['rival']
    chosen=[o for o in spec['operators'] if o['id'] in selected]
    methods={'native':(base['fixed'],base['unit'],0,0)}
    if scene['rival_can_copy'] and chosen:
        methods['copy']=(base['fixed']+sum(o['fixed_delta'] for o in chosen),
                         base['unit']+sum(o['unit_delta'] for o in chosen),
                         sum(o['build'] for o in chosen),sum(o['partner_payment'] for o in chosen))
    agents,gain=allocations(spec,scene,seller,None)
    actions=[(0,-len(agents['seller']),0,0,0,'none',None,agents,gain)]
    for price in base['price_grid']:
        agents,gain=allocations(spec,scene,seller,price)
        n=len(agents['rival'])
        for method,(fixed,unit,build,partner) in methods.items():
            if fixed<0 or unit<0:
                continue
            profit=n*price-base['quote']-build-(fixed+unit*n+partner if n else 0)
            actions.append((profit,-len(agents['seller']),1,price,int(method=='native'),method,price,agents,gain))
    return max(actions,key=lambda a:a[:5])

def all_seller_strategies(spec):
    # These fixtures have no prerequisites or exclusions. The rival has no separate cash balance in this grammar.
    for op in spec['operators']:
        assert not op['requires'] and not op['exclusive'] and op['partner_payment']>=op['partner_outside']
    best=(Fraction(0),Fraction(0),0,0)
    winning=([],None,Fraction(0))
    ops=spec['operators']
    count=0
    for n in range(min(spec['limits']['max_operators'],len(ops))+1):
        for chosen in combinations(ops,n):
            selected=[o['id'] for o in chosen]
            for quote in spec['price_grid']:
                count+=1
                profits=[]
                for scene in spec['scenarios']:
                    agent=independent_responses(spec,selected,scene,quote)
                    if not any(op['partner_payment']<op['partner_outside'] for op in chosen):
                        fixed=spec['production']['fixed']+scene['fixed_extra']+sum(o['fixed_delta'] for o in chosen)
                        unit=spec['production']['unit']+scene['unit_extra']+sum(o['unit_delta'] for o in chosen)
                        qty=len(agent[7]['seller'])
                        cost=spec['production']['quote']+sum(o['build'] for o in chosen)
                        if qty:
                            cost+=fixed+qty*unit+sum(o['partner_payment'] for o in chosen)
                        if min(fixed,unit)<0 or cost>spec['opening_cash']-spec['protected_cash']:
                            break
                        profits.append((scene['weight_bps'],(qty*quote if scene['accepted'] else 0)-cost))
                if len(profits)!=len(spec['scenarios']):
                    continue
                worst=max([0]+[-x for _,x in profits]); lim=spec['limits']
                if worst>lim['max_loss']:
                    continue
                expected=sum(Fraction(w*x,10000) for w,x in profits)
                score=(expected-Fraction(worst*lim['downside_penalty_bps'],10000),expected,-n,-quote)
                if score>best:
                    best,winning=score,(selected,quote,expected)
    return winning,count

def micro(copy_enabled=True):
    return {
        'schema':'agi-alpha/economic-game-maker/v1','basis':'DECLARED_COMPLETE_INFORMATION_SYNTHETIC','outcome':'one unit',
        'opening_cash':200,'protected_cash':0,'buyer_profiles':[{'id':'u','value':100,'budget':100,'outside_utility':0}],
        'production':{'fixed':0,'unit':0,'quote':0},'operators':[{'id':'o','requires':[],'exclusive':'',
        'fixed_delta':0,'unit_delta':0,'build':20,'partner_payment':0,'partner_outside':0}],
        'rival':{'fixed':0,'unit':0,'quote':0,'price_grid':[10]},'scenarios':[{'id':'x','weight_bps':10000,
        'active_buyers':['u'],'rival_can_copy':copy_enabled,'accepted':True,'collected':True,'fixed_extra':0,'unit_extra':0}],
        'price_grid':[50],'limits':{'max_operators':1,'max_states':20,'max_loss':40,'downside_penalty_bps':0}}

def run(path):
    sys.path.insert(0,str(path.resolve()))
    from mechanism_harness import game_maker as impl
    kernel=impl.kernel
    samples=0; discrepancies=Counter(); mode=Counter(); examples=[]; budget_excess=0
    bill=0
    original=kernel.choices
    def counted(*args,**kwargs):
        nonlocal bill
        bill+=1
        return original(*args,**kwargs)
    op=tuple(['o'])
    with patch.object(kernel,'choices',side_effect=counted):
        for copy_enabled,fixed,unit,delta_f,delta_u,build,partner,n,quote,quote_cost in product(
                (False,True),(0,5),(0,4),(-5,0,4),(-4,0,3),(0,7),(0,6),(0,1,2),(4,8,11),(0,2)):
            s=micro(copy_enabled);s['price_grid']=[4,8,11];o=s['operators'][0]
            o.update(fixed_delta=delta_f,unit_delta=delta_u,build=build,partner_payment=partner,partner_outside=partner)
            s['production'].update(fixed=9,unit=9)
            s['rival'].update(fixed=fixed,unit=unit,quote=quote_cost,price_grid=[4,8,11])
            s['buyer_profiles']=[dict(id='a',value=13,budget=11,outside_utility=3),dict(id='b',value=16,budget=8,outside_utility=5)]
            scene=s['scenarios'][0];scene['active_buyers']=['a','b'][:n]
            ref=independent_responses(s,op,scene,quote)
            q0=bill;real=impl.follower(s,op,scene,quote)
            budget_excess+=bill-q0>len(s['rival']['price_grid'])+1
            expected=(ref[6],ref[0],ref[7]['seller'],ref[7]['rival'],ref[8])
            seen=tuple(real[k] for k in ['quote','rival_profit','seller_buyers','rival_buyers','buyer_gain_over_outside'])
            samples+=1;mode[ref[5]]+=1
            method_matches = 'tactic' not in real or real['tactic'] == {'native':'unchanged','copy':'copy','none':'nonentry'}[ref[5]]
            if seen!=expected or not method_matches:
                discrepancies[ref[5]]+=1
                if len(examples)<3:examples.append({'parameters':[copy_enabled,fixed,unit,delta_f,delta_u,build,partner,n,quote,quote_cost],'expected':expected,'actual':seen})
    package=path/'mechanism_harness/game_maker_fixture.json'
    fixture=json.loads(package.read_bytes())
    games={}
    for name,s in [('public_fixture',fixture),('wasteful_operator',micro()),('copy_disabled',micro(False))]:
        expected,count=all_seller_strategies(s); real=impl.invent(s); w=real['winner']
        actual=(w['operators'],w['quote'],Fraction(w['expected_profit']))
        assert count==real['states_evaluated']
        bound=deepcopy(s);bound['limits']['max_states']=count-1
        bounded=impl.invent(bound);assert bounded['status']=='SEARCH_BOUND_EXHAUSTED' and bounded['winner'] is None
        games[name]={'expected':[expected[0],expected[1],str(expected[2])],'actual':[actual[0],actual[1],str(actual[2])],'states':count,'bounded_stop':True,'matched':expected==actual}
    return {'source_file_sha256':{p:sha256((path/'mechanism_harness'/p).read_bytes()).hexdigest() for p in ('game_maker.py','_game_maker_v1.py','game_input.py')},'oracle_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'Declared perfect-information microgames; operating and financial accounts untouched. Buyer ties outside then rival; rival maximizing profit then fewest seller buyers, then entry and greatest price. Native-first for equally profitable technology at same price. Copied build paid at offer; partner/fixed/per-unit only on sale.','microcases':samples,'optimal_methods':dict(mode),'response_disagreements':dict(discrepancies),'mismatch_examples':examples,'buyer_allocation_calls':bill,'budget_excess_cases':budget_excess,'end_to_end':games,'accepted':not discrepancies and not budget_excess and all(g['matched'] for g in games.values())}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();x=run(a.source)
    with a.output.open('x') as f:json.dump(x,f,sort_keys=True,indent=2);f.write('\n')
    print(x['accepted'],x['microcases'],x['response_disagreements'],x['budget_excess_cases'],x['end_to_end'])
