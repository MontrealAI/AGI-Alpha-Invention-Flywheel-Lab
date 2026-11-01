"""Reconstruct voluntary complete-scope decisions from native offers and public inputs."""
from .complete_offer_market import request_profile,private_atom,market_context,actual_choice


def audit_market(result,tape):
    from .verify import _private_draw
    cfg=result['config'];policy=cfg['complete_offer_policy'];seed=result['seed']
    buyers={b['id']:b for b in result['buyers']}
    choices=[d for d in result['decisions'] if d.get('kind') in {'offer','outside_choice'}]
    orders={(o['customer_id'],o['qualified_time']):o for o in result['orders']}
    if len(orders)!=len(result['orders']):raise ValueError('ONE_COMPLETE_ORDER_PER_REQUEST')
    refunds={a['args']['id']:a['day'] for a in tape['actions'] if a['op']=='event' and a['args']['action']=='refund'}
    outside={};seen=set();offered=0
    for d in choices:
        ident=d['customer_id'];t=d['time'];key=(ident,t)
        if ident not in buyers or key in seen or _private_draw(seed,[t//24,ident],'need')>=cfg['arrival_bps']/10000:raise ValueError('UNIQUE_OBSERVED_COMPLETE_REQUEST_REQUIRED')
        seen.add(key)
        committed=sum(o['price'] for o in result['orders'] if o['customer_id']==ident and o['qualified_time']<t and (o['id'] not in refunds or refunds[o['id']]>t))
        observed=outside.get(ident,0)+committed
        context=market_context(policy,ident,observed)
        if d.get('market_context')!=context or d.get('human_price') is not None or d.get('public_rival_price') is not None:raise ValueError('COMPLETE_MARKET_CONTEXT_NOT_REDERIVED')
        price=d['price'];service=d['service_id']
        if d['kind']=='offer':
            offered+=1
            from .strategic_commerce import selected_delivery
            wrapper=result.get('joint_actions',{}).get(d.get('joint_allocation_sha256'))
            if wrapper is None:raise ValueError('COMPLETE_OFFER_SELECTION_RECEIPT_REQUIRED')
            pick=selected_delivery(wrapper['allocation'],d['joint_option_id'])
            if pick['job_id'] not in policy['requested_jobs'][ident]:raise ValueError('UNREQUESTED_CUSTOMER_JOB')
            if pick['price']!=price or pick['service_id']!=service:raise ValueError('COMPLETE_SCOPE_OR_QUOTE_CHANGED')
        elif price is not None:raise ValueError('NO_BID_CANNOT_HAVE_PRICE')
        index=private_atom(policy,ident,seed)
        budget=request_profile(policy,ident)['atoms'][index]['budget_microUSD']
        chosen=actual_choice(context,index,budget-observed,service if price is not None else None,price,_private_draw(seed,[t//24,ident],'complete-offer-tie'))
        if d['buyer_choice']!=chosen['provider'] or d['chosen'] is not (chosen['provider']=='us') or d.get('outside_option_name')!=chosen['name'] or d.get('outside_service_id')!=chosen['service_id']:raise ValueError('VOLUNTARY_COMPLETE_SCOPE_CHOICE_CHANGED')
        if chosen['provider']=='us':
            order=orders.get(key)
            if order is None or order['price']!=price or order['offer']['service_id']!=service:raise ValueError('COMPLETE_CHOICE_NOT_NATIVE_ORDER')
        else:
            if key in orders:raise ValueError('DECLINED_COMPLETE_SCOPE_BECAME_ORDER')
            spend=chosen['spend']
            if d.get('outside_spend',0)!=spend:raise ValueError('COMPLETE_OUTSIDE_SPEND_CHANGED')
            outside[ident]=outside.get(ident,0)+spend
    if set(orders)-seen or any(b['outside_spend']!=outside.get(ident,0) for ident,b in buyers.items()):raise ValueError('COMPLETE_BUYER_BUDGET_NOT_RECONCILED')
    return {'voluntary_buyer_decisions_recomputed':len(choices),'enterprise_offers_recomputed':offered,'unavailable_offer_outside_choices_recomputed':len(choices)-offered}
