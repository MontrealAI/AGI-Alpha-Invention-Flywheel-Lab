"""Read-only reviewer of the registered matrix. Reads designated public exports, never opens an account."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

WORLDS = ('central', 'weak', 'copycat', 'no_demand', 'failed_activation')
OPENING = 100_000_000_000
CENT = 10_000
INVOICE = 6_250_000
DAYS = (90, 118)
PUBLIC = ('SOURCE','CONTRACT','MANIFEST','STUDY','PLAN','ORDERS','CHANNEL','NATIVE_EXPORT','REPORT')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def digest(value):
    return sha(json.dumps(value, separators=(',', ':'), sort_keys=True, allow_nan=False).encode())

def read(path):
    def pairs(items):
        obj = dict(items)
        require(len(items) == len(obj), 'duplicate JSON key')
        return obj
    return json.loads(path.read_bytes(), object_pairs_hook=pairs)

def source_files(src, identities):
    for name, expected in identities.items():
        path = src / name
        require(path.is_file() and path.resolve().is_relative_to(src) and sha(path.read_bytes()) == expected,
                'source differs ' + name)

def fee_cents(price, bps):
    q, rem = divmod(price * bps, 10000)
    return q + bool(rem)

def choose(market, menu, private):
    # Normalize semantically redundant offers, enumerate each purchase mask, choose
    # the worst seller contribution among buyer-optimal carts with the public tie convention.
    outcomes = market['outcomes']
    index = {o['id']: i for i, o in enumerate(outcomes)}
    by_set = {frozenset(o['services']): i for i, o in enumerate(outcomes)}
    min_price = {}
    for offer in menu.get('menu', menu['rules']):
        i = index[offer['outcome_id']]
        if i:
            min_price[i] = min(min_price.get(i, offer['price_cents']), offer['price_cents'])
    entries = sorted(min_price.items())
    choices = []
    for mask in range(1 << len(entries)):
        purchased = [entry for k, entry in enumerate(entries) if mask >> k & 1]
        price = sum(p for _, p in purchased)
        if price > private['budget_cents']:
            continue
        services = frozenset(s for i, _ in purchased for s in outcomes[i]['services'])
        index_ = by_set[services]
        utility = private['values'][index_] - price - private['outside_utility'] if purchased else 0
        proceeds = price - fee_cents(price, market['payment_bps']) - outcomes[index_]['cost_cents']
        name = outcomes[index_]['id']
        basket = [outcomes[i]['id'] for i, _ in purchased]
        key = -utility, bool(purchased), proceeds, price, name, len(basket), basket
        choices.append((key, dict(outcome_id=name, price_cents=price, utility_cents=utility,
                                  seller_contribution_cents=proceeds, declined=not purchased,
                                  basket=basket, services=sorted(services))))
    return min(choices, key=lambda element: element[0])[1]

def private_draw(purpose, buyer, day):
    return int(digest([2026110401, purpose, buyer, day])[:16], 16)

class CashReplay:
    """Interpret the allowed low-level events with explicit customer balances and escrow."""
    def __init__(self):
        self.wallets = {}
        self.credits = {}
        self.trades = {}
        self.reservations = {}
        self.expense = self.paid = self.revenue = 0
        self.settled_ids = []
        self.debits = {}
        self.sequence = []

    def balances(self):
        funded = sum(o['price'] for o in self.trades.values() if o['state'] in ('fund','prepare'))
        tail = sum(self.trades[i]['price'] + 200_000 for i in self.settled_ids)
        cash = OPENING + self.revenue - self.paid
        payable = self.expense - self.paid
        reserved = sum(self.reservations.values())
        net = self.revenue - self.expense
        protection = funded + tail
        from_seed = min(protection, max(0, OPENING + min(net, 0)))
        free = max(0, cash - payable - protection)
        earned = max(0, min(free, max(0, net) - (protection - from_seed)) - reserved)
        return dict(cash=cash, expenses=self.expense, expensePaid=self.paid, revenue=self.revenue,
                    collections=self.revenue, profit=net, custodyRestricted=funded, custodyReserve=funded,
                    tailReserve=tail, available=max(0, free-reserved), unrestrictedEarned=earned,
                    workingCapital=0, recoveryIncome=0, payables=payable, reservedInvestment=reserved)

    def check_balance(self, stated, label):
        for key, value in self.balances().items():
            require(type(stated[key]) is int and stated[key] == value, label + ': ' + key)

    def step(self, event):
        day, seq, op, a = (event[k] for k in ('day','seq','op','args'))
        require(seq == len(self.sequence) and 0 <= day < 365 and
                (not self.sequence or day >= self.sequence[-1]['day']), 'event sequencing')
        self.check_balance(event['before'], f'before {seq} {op}')
        ident = a.get('id')
        if op == 'cost':
            require(ident not in self.debits and a['amount'] >= 0, 'duplicate or negative expense')
            self.paid += min(a['amount'], self.balances()['available'])
            self.expense += a['amount']
            self.debits[ident] = a['amount']
        elif op == 'reserve':
            require(a['expected_net_value'] > 0 and ident not in self.reservations and
                    0 < a['amount'] <= self.balances()['unrestrictedEarned'], 'unfunded reserve')
            self.reservations[ident] = a['amount']
        elif op == 'finish':
            reserved = self.reservations.pop(ident)
            require(ident not in self.debits and 0 <= a['amount'] <= reserved, 'unfunded finish')
            self.paid += min(a['amount'], self.balances()['available'])
            self.expense += a['amount']
            self.debits[ident] = a['amount']
        elif op == 'wallet':
            buyer = a['buyer']
            require(buyer not in self.wallets, 'wallet top-up')
            self.wallets[buyer] = self.credits[buyer] = a['amount']
        elif op == 'offer':
            require(ident not in self.trades and a['buyer'] in self.wallets and a['price'] > 0, 'unfunded offer')
            self.trades[ident] = dict(a, state='offer', day=day)
        elif op == 'event':
            order = self.trades[ident]
            buyer = order['buyer']
            state, new = order['state'], a['action']
            require((state,new) in (('offer','consent'),('consent','fund'),('fund','prepare'),
                                    ('prepare','release'),('fund','refund')), 'invalid order transition')
            if new == 'fund':
                self.wallets[buyer] -= order['price']
                require(self.wallets[buyer] >= 0, 'buyer negative cash')
            elif new == 'release':
                self.revenue += order['price']
                self.settled_ids.append(ident)
            elif new == 'refund':
                self.wallets[buyer] += order['price']
            order['state'] = new
            order['last_day'] = day
        else:
            raise ValueError('unregistered operation ' + op)
        self.check_balance(event['after'], f'after {seq} {op}')
        self.sequence.append(event)

def validate_contacts(root, info, books, cash):
    from adaptive_enterprise.checkers import audit_delivery
    records = info['ORDERS']; market_study = info['STUDY']
    cases = market_study['study']['cases']; choices = market_study['selection']['decisions']
    inventory = {j['id']:j for j in info['MANIFEST']['jobs']}
    spends = {r['request']['id']: r['receipt'] for r in info['NATIVE_EXPORT']['connected_journal']['entries'] if r['request']['operation']=='spend'}
    runtime = root/'runtime'
    available = defaultdict(int); wins = Counter()
    daily = Counter(); by_service = Counter(); used_jobs=set(); seen_orders=set()
    loose=Counter(); expect_spends={'reach-setup':20_000_000,'reach-discovery':15_000_000}
    collected=0; prefix_rows=[]; fresh_paid=Counter(); count_qualified=0
    for j,row in enumerate(records,1):
        buyer,day,status=row['buyer'],row['day'],row['status']
        require(row['ordinal']==j and books[j-1]==(buyer,day,row['source'],row['source_plan_id'],row['exposure_id']), 'exposure outside registered contacts')
        warm=row['source']=='warm'
        case_i=(int(buyer[-3:])-1)//9 if warm else 0
        model=cases[case_i]['market']
        selection=choices[case_i]
        menu=cases[case_i]['runs'][selection['selected_arm']]['program']
        require(digest(model)==row['market_sha256'] and digest(menu)==row['program_sha256'], 'menu/market identity')
        if warm: prefix_rows.append(row)
        if row['source']=='paid': fresh_paid[buyer]+=1
        expected_money=dict(quote_microUSD=0,production_microUSD=0,fee_microUSD=0,collections_microUSD=0)
        if selection['action']=='NONENTRY':
            require(status=='NONENTRY' and row['private'] is None and row['choice'] is None, 'private info on null game')
        else:
            expected_money['quote_microUSD']=100_000
            require(row['quote_id']==f'reach-quote-{j}', 'missing quote identity')
            expect_spends[row['quote_id']]=100_000
            if warm:
                typ=model['types'][(int(buyer[-3:])-1)%9]
                eligible=True
            else:
                p=private_draw('type',buyer,0)%sum(t['weight'] for t in model['types'])
                for typ in model['types']:
                    p-=typ['weight']
                    if p<0: break
                eligible=private_draw('qualify',buyer,day)%10_000 < (5000 if wins[buyer] else 7500)
            if not eligible:
                require(status=='UNQUALIFIED' and row['private'] is None and row['choice'] is None, 'unqualified buyer sold')
            else:
                count_qualified+=1
                initial=typ['budget_cents']*(1 if warm else 2)
                cap=min(typ['budget_cents'], initial-available[buyer])
                private=dict(values=typ['values'][:],outside_utility=typ['outside_utility'],budget_cents=cap)
                scenario=info['CONTRACT']['scenario']
                if not warm and scenario=='weak': private['values']=[x//2 for x in private['values']]
                if not warm and scenario=='no_demand': private['values']=[0]*len(private['values'])
                if not warm and scenario=='copycat': private['outside_utility']+=choose(model,menu,private)['utility_cents']
                choice=choose(model,menu,private)
                require(row['private']==private and row['choice']==choice and row['remaining_before_cents']==initial-available[buyer], 'deviation or lifetime wallet violation')
                if choice['declined']:
                    require(status=='DECLINED' and not row['components'], 'involuntary order')
                else:
                    require(choice['utility_cents']>0 and choice['price_cents']<=cap, 'voluntary strict gain')
                    target=next(o for o in model['outcomes'] if o['id']==choice['outcome_id'])
                    parts=row['components']
                    require([c['service'] for c in parts]==choice['services'] and sum(c['price_cents'] for c in parts)==choice['price_cents'], 'cart composition')
                    if daily[day]+len(parts)>2 or any(by_service[c['service']]>=48 for c in parts):
                        require(status=='CAPACITY', 'capacity refusal')
                    else:
                        srcs=[]
                        for c in parts:
                            job=inventory[c['job_id']]
                            require(c['service']==job['service_id'],'job service')
                            slot=7+int(buyer[-3:]) if warm else 36+4*int(buyer[-3:])+(fresh_paid[buyer] if row['source']=='paid' else 0)
                            require(c['job_id']==[q['id'] for q in inventory.values() if q['service_id']==c['service']][slot], 'job alignment')
                            for field in ('input','artifact'):
                                path=runtime/job[field]
                                require(path.resolve().is_relative_to(runtime.resolve()) and sha(path.read_bytes())==job[field+'_sha256'], 'job source')
                            srcs.append((job,read(runtime/job['input']),read(runtime/job['artifact'])))
                        if any(c['service']=='reconciliation' and any(not raw['units'].get(k) for k in ('invoices','payments')) for c,(_,raw,_) in zip(parts,srcs)):
                            require(status=='UNSUPPORTED','unsupported sale')
                        elif (choice['price_cents']+target['cost_cents']+fee_cents(choice['price_cents'],model['payment_bps']))*CENT > cash.sequence[spends[row['quote_id']]['native_event_sequence']]['after']['available']:
                            require(status=='ILLIQUID','unavailable working cash committed')
                        else:
                            require(status in ('SETTLED','REFUNDED'), 'eligible funded order absent')
                            expected_money['production_microUSD']=target['cost_cents']*CENT
                            expect_spends[f'reach-production-{j}']=expected_money['production_microUSD']
                            daily[day]+=len(parts)
                            checks=[]
                            for c,(job,raw,reference) in zip(parts,srcs):
                                require(c['job_id'] not in used_jobs and c['order_id'] not in seen_orders,'duplicate work')
                                used_jobs.add(c['job_id']); seen_orders.add(c['order_id']); by_service[c['service']]+=1
                                artifact=c['artifact']; checked=audit_delivery(c['service'],raw,artifact)
                                equivalent=all(artifact[k]==reference[k] for k in ('normalized_input','useful_outcome'))
                                require(checked==c['verification'] and bool(c['admitted_outcome_equal'])==equivalent,'unverified output')
                                checks.append(checked['accepted'] and equivalent and artifact['outcome_scope']=='complete_outcome')
                                trade=cash.trades[c['order_id']]
                                require(trade['buyer']==buyer and trade['price']==c['price_cents']*CENT and trade['job_id']==c['job_id'] and trade['day']==day and trade['last_day']==day+int(warm), 'unbound native job')
                                require(trade['state']==('release' if status=='SETTLED' else 'refund'), 'partial union')
                            require(all(checks)==(status=='SETTLED'), 'failed evidence nevertheless collected or valid order damaged')
                    if status=='SETTLED':
                        require(cash.credits[buyer]==initial*CENT, 'wallet initial balance')
                        expected_money['fee_microUSD']=fee_cents(choice['price_cents'],model['payment_bps'])*CENT
                        expected_money['collections_microUSD']=choice['price_cents']*CENT
                        expect_spends[f'reach-fee-{j}']=expected_money['fee_microUSD']
                        collected+=expected_money['collections_microUSD']; wins[buyer]+=1; available[buyer]+=choice['price_cents']
                require(row['remaining_after_cents']==initial-available[buyer], 'unexpected wallet remainder')
        require(all(row[k]==v for k,v in expected_money.items()), 'order financial claim')
        loose[status]+=1
    require(len(records)==len(books) and seen_orders==set(cash.trades) and collected==cash.revenue,'completeness')
    require(set(cash.wallets)=={cash.trades[i]['buyer'] for i in cash.trades} and all(cash.wallets[b]==cash.credits[b]-available[b]*CENT for b in cash.wallets), 'terminal buyer wallets')
    return expect_spends,dict(status=dict(loose),qualified=count_qualified,unique_settled_buyers=len(wins),repeat_settled_buyers=sum(n>=2 for n in wins.values()),service_units=dict(by_service),maximum_daily_units=max(daily.values(),default=0),warm_digest=digest(prefix_rows))

def financial_evidence(info,cash,expected):
    entries=info['NATIVE_EXPORT']['connected_journal']['entries']; due={}
    operating={}
    for row in entries:
        q=row['request']; require(row['status']=='COMPLETE','unresolved native obligation')
        if q['operation']=='spend':
            ident=q['id']; receipt=row['receipt']; action=cash.sequence[receipt['native_event_sequence']]
            require(ident not in due and q['amount']==action['args']['amount'] and q['day']==action['day'], 'debit or receipt mismatch')
            earned=q['expected_net']>0 and (action['op']=='finish')
            require(row['funding']==('EARNED' if earned else 'SEED') and (earned or q['allow_seed']), 'seed used for earned invoice')
            native_id=action['args']['id']; require(native_id in cash.debits,'missing recorded debit')
            if earned:
                require(receipt['plan_id']==native_id and native_id=='connected014-resource-'+digest(ident)[:32], 'unbound earned invoice')
            else:
                require(action['op']=='cost' and native_id=='connected014-seed-'+digest({'request':q,'source_sha256':receipt['source_sha256']})[:32], 'unbound seed debit')
            due[ident]=q['amount']; operating[native_id]=ident
        elif q['op']=='cost':
            ident=q['args']['id']
            require(ident in cash.debits and ident not in due and q['args']['amount']==cash.debits[ident],'unbound expense')
            due[ident]=q['args']['amount']; operating[ident]=ident
    require(set(operating)==set(cash.debits),'unexplained ledger cost')
    freeze=[k for k in due if k.startswith('reach-freeze-')]
    require(len(freeze)==1 and due[freeze[0]]==0,'study freeze')
    expected[freeze[0]]=0; expected['reach-maintenance']=12_000_000
    expected['reach-modeled-tax']=max(0,cash.revenue-sum(expected.values()))//5
    require(due==expected and sum(due.values())==cash.expense,'reconciled categories or tax discrepancy')
    return {'setup':20_000_000,'discovery':15_000_000,'maintenance':12_000_000,
            'quotes':sum(v for k,v in due.items() if k.startswith('reach-quote-')),
            'productive_work':sum(v for k,v in due.items() if k.startswith('reach-production-')),
            'collection_fees':sum(v for k,v in due.items() if k.startswith('reach-fee-')),
            'channel_invoices':sum(v for k,v in due.items() if k.startswith('reach-pilot-')),
            'modeled_tax':expected['reach-modeled-tax']}

def exposure_routes(info):
    channel=info['CHANNEL']; contacts=[]; last={}; appearances=Counter(); duplicate=0
    seen_exposures=set()
    for day in range(365):
        if 5<=day<=83 and (day-2)%3==0:
            warm=f'warm-{(day-2)//3:03d}'
            contacts.append((warm,day,'warm',None,warm))
        owned=None
        if 92<=day<=169 and (day-92)%7==0:
            owned=f'reach-{(day-92)//7:03d}'
            contacts.append((owned,day,'organic',None,f'organic-{day}-{owned}'))
        daily=channel['exposures_by_day'][str(day)]
        require(daily['attempted_slots']==daily['realized_exposures']+daily['unused_slots'] and
                daily['realized_exposures']==len(daily['exposures']), 'supplier slot economics')
        todays=set()
        for row in daily['exposures']:
            buyer=row['customer_id']; tranche=row['source_plan_id']; ident=row['exposure_id']
            purchased=channel['purchase_receipts'][tranche]
            require(buyer not in todays and buyer.startswith('reach-') and 4<=int(buyer[-3:])<24 and
                    purchased['activation_day']<=day<purchased['expiry_day'] and day-last.get(buyer,-100)>=7 and
                    appearances[buyer]<3 and ident not in seen_exposures, 'invalid, expired, or duplicate reach')
            seen_exposures.add(ident); last[buyer]=day; appearances[buyer]+=1; todays.add(buyer)
            if buyer!=owned: contacts.append((buyer,day,'paid',tranche,ident))
            else: duplicate+=1
        require(len(todays)<=2,'supplier capacity')
    return contacts,dict(raw_paid_exposures=len(seen_exposures),distinct_exposed_buyers=len(appearances),same_day_deduplications=duplicate)

def check_purchases(info,cash,expected):
    rows=info['ORDERS']; channel=info['CHANNEL']; paid_plan=None; accepted=[]
    for index,(day,d) in enumerate(zip(DAYS,info['PLAN']['decisions']),1):
        pre=[a for a in cash.sequence if a['day']<day]
        state=pre[-1]['after']; prefix=d['prefix']; require(prefix==dict(sequence=len(pre),actions_sha256=digest(pre),
            available_microUSD=state['available'],earned_microUSD=state['unrestrictedEarned']),'future or stale liquidity')
        warm=[r for r in rows if r['source']=='warm' and r['day']<day]
        paid=[r for r in rows if r['source']=='paid' and r['source_plan_id']==paid_plan and r['day']<day]
        exclusive=[r for r in paid if int(r['buyer'][-3:])>=12 and r['status']=='SETTLED']
        for r in paid: require(r['paid_exclusive']==(int(r['buyer'][-3:])>=12),'misattributed overlapping lead')
        gross=sum(r['collections_microUSD']-r['fee_microUSD']-r['production_microUSD'] for r in warm)
        settled=sum(r['status']=='SETTLED' for r in warm)
        attributable=sum(r['collections_microUSD'] for r in exclusive)-sum(r[k] for r in paid for k in ('production_microUSD','quote_microUSD','fee_microUSD'))-(INVOICE if paid_plan else 0)
        estimate=(2*gross//settled if settled else 0)-INVOICE-4_200_000 if index==1 else attributable
        should=bool(info['CONTRACT']['arm']=='pilot' and settled and estimate>0 and state['unrestrictedEarned']>=INVOICE and
                    state['available']>=INVOICE+12_000_000 and (index==1 or paid_plan and exclusive))
        require(d['day']==day and d['policy']['action']==('BUY' if should else 'SKIP') and d['policy']['expected_net_microUSD']==estimate and bool(d['funding'])==should and bool(d['purchase'])==should,'tranche rule mismatch')
        if should:
            f=d['funding']; plan=f['plan_id']; p=d['purchase']; terminal=cash.sequence[f['native_event_sequence']]
            require(f['funding']=='EARNED' and f['amount']==INVOICE and terminal['day']==day and terminal['op']=='finish' and terminal['args']['id']==plan and
                    plan==p['source_plan_id'] and p==channel['purchase_receipts'][plan] and p['invoice_microUSD']==INVOICE and
                    p['purchased_day']==day and p['activation_day']==day+2 and p['expiry_day']==day+23, 'paid rights without prior earned expense')
            if index==1:paid_plan=plan
            expected[f'reach-pilot-{index}']=INVOICE
        accepted.append({'day':day,'decision':'BUY' if should else 'SKIP','earned_microUSD':state['unrestrictedEarned'],
                         'expected_net_microUSD':estimate,'first_plan_exclusive_orders':len(exclusive),'first_plan_attribution_microUSD':attributable})
    require(len(accepted)==2==len(info['PLAN']['decisions']) and sum(d['decision']=='BUY' for d in accepted)==len(channel['instances']), 'undisclosed tranche')
    return accepted

def case(root,src,arm,world):
    start={name:sha((root/(name+'.json')).read_bytes()) for name in PUBLIC}; info={name:read(root/(name+'.json')) for name in PUBLIC}
    require(info['CONTRACT']['arm']==arm and info['CONTRACT']['scenario']==world and info['CONTRACT']['clock']=={'start_day':0,'end_day_exclusive':365},'wrong account or year')
    source_files(src,info['SOURCE'])
    require(info['SOURCE']['campaign/omega-paid-reach-20261104/PROTOCOL.md']=='2b6eef4a9535f6f626e2ca88fcc432c672f1b9cc45ec5bef868e3378d38f5277', 'preregistration changed')
    source_digest=digest(info['SOURCE']); report=info['REPORT']
    require(info['CONTRACT']['source_sha256']==source_digest==report['source_sha256'] and report['actual_revenue_usd']==0,'incorrect version or real-revenue claim')
    ledger=info['NATIVE_EXPORT']['ledger']; require(ledger['config']['opening']==OPENING and ledger['config']['working']==0,'opening principal')
    cash=CashReplay()
    for a in ledger['actions']:cash.step(a)
    cash.check_balance(ledger['summary'],'closing')
    require(report['native_summary']==ledger['summary'] and report['native_export_sha256']==digest(info['NATIVE_EXPORT']), 'stale report')
    contacts,reach=exposure_routes(info)
    expected,production=validate_contacts(root,info,contacts,cash)
    decisions=check_purchases(info,cash,expected)
    expenses=financial_evidence(info,cash,expected)
    require(start=={name:sha((root/(name+'.json')).read_bytes()) for name in PUBLIC}, 'artifact changed during inspection')
    return {'opening_microUSD':OPENING,'source_sha256':source_digest,'public_file_sha256':start,
            'native_events':len(cash.sequence),'complete_native_financial_microUSD':cash.balances(),
            'expenses_by_type_microUSD':expenses,'buyer_and_work_checks':production,'paid_reach':reach,'tranches':decisions}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',required=True,type=Path)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--commit',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(); src=args.source.resolve()
    require(subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()==args.commit,'source commit')
    sys.path.insert(0,str(src)); data={}; warm=set(); source_hashes=set()
    for world in WORLDS:
        arms={arm:case(args.results/world/arm,src,arm,world) for arm in ('organic','pilot')}
        left,right=arms['organic'],arms['pilot']
        for r in arms.values():warm.add(r['buyer_and_work_checks']['warm_digest']); source_hashes.add(r['source_sha256'])
        delta=right['complete_native_financial_microUSD']['profit']-left['complete_native_financial_microUSD']['profit']
        volume=right['buyer_and_work_checks']['status'].get('SETTLED',0)-left['buyer_and_work_checks']['status'].get('SETTLED',0)
        data[world]={'accounts':arms,'pilot_minus_organic_after_tax_microUSD':delta,'pilot_minus_organic_settled_baskets':volume}
    require(len(warm)==len(source_hashes)==1,'unmatched exposed warm-up or source')
    receipt={'scope':'Public exports only, no native signer access or new trades. Independent action-by-action accounting and buyer choice. Authoritative low-level artifact checker reused.',
             'source_commit':args.commit,'source_sha256':next(iter(source_hashes)),'reviewer_script_sha256':sha(Path(__file__).read_bytes()),
             'period':'simulated day [0,365)','accepted':True,'accounts':10,'paired_results':data}
    with args.output.open('x') as file: json.dump(receipt,file,sort_keys=True,indent=2);file.write('\n')
    print({world:(data[world]['pilot_minus_organic_after_tax_microUSD'],data[world]['pilot_minus_organic_settled_baskets']) for world in WORLDS})

if __name__=='__main__': main()
