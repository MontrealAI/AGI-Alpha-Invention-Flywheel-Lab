"""Public paired contract scenarios using the actual ChannelBook transition rules.

Forecast seeds are declared hypotheses, never the environment seed or future
buyer draws. Observed contract states and contacts are copied, not mutated.
"""
import copy
from commercial.ledger import digest
from .channels import ChannelBook,validate_contracts

PUBLIC_SEEDS=(290031,290032,290033,290034)

def forecast_contract(contracts,state,buyers,now_day,future_day,contract_id,owned_contact_count=0,target_customer_ids=None):
    contracts=validate_contracts(contracts)
    if contract_id not in contracts or type(now_day) is not int or not now_day<future_day<=now_day+30:
        raise ValueError('BOUNDED_REAL_CONTRACT_WINDOW_REQUIRED')
    if state.get('last_day')!=now_day or any(e['day']>now_day for e in state['events']):
        raise ValueError('CURRENT_OBSERVED_CHANNEL_STATE_REQUIRED')
    for instance in state['instances'].values():
        if instance.get('terms')!=contracts.get(instance.get('contract_id')) or instance['purchased_day']>now_day:
            raise ValueError('OBSERVED_CONTRACT_TERMS_CHANGED')
    terms=contracts[contract_id]
    live=[x for x in state['instances'].values() if x['contract_id']==contract_id and x['state'] not in ('FAILED','EXPIRED') and x['expiry_day']>now_day]
    admitted=len(live)<terms['max_active_tranches'] and now_day+terms['lead_days']<=future_day<now_day+terms['lead_days']+terms['duration_days']
    if type(owned_contact_count) is not int or not 0<=owned_contact_count<=8:raise ValueError('BOUNDED_OWNED_CONTACT_POPULATION_REQUIRED')
    # Canonical engine owns only its initial four audience identities; the
    # hypothesis may use fewer, never create unpaid additional owned reach.
    owned_base=set(sorted(buyers)[:min(4,owned_contact_count)])
    if target_customer_ids is not None:owned_base|={ident for ident,b in buyers.items() if b['onboarded'] and b['active']}
    targets=set(buyers) if target_customer_ids is None else set(target_customer_ids)
    if not targets<=set(buyers) or target_customer_ids is not None and (not isinstance(target_customer_ids,list) or len(targets)!=len(target_customer_ids)):raise ValueError('PUBLIC_TARGET_SUBSET_REQUIRED')
    owned_ids=owned_base&targets
    eligible={i for i,b in buyers.items() if i not in owned_base and i in targets and (not b['onboarded'] or not b['active'])}
    prospects=[{'id':i} for i in sorted(buyers)]
    rows=[]
    for seed in PUBLIC_SEEDS:
        pair={}
        for purchase in (False,True):
            if purchase and not admitted:continue
            book=ChannelBook(seed,contracts);observed=copy.deepcopy(state);observed['binding_sha256']=book.state['binding_sha256']
            book=ChannelBook(seed,contracts,observed)
            if purchase:book.purchase(contract_id,now_day,'PUBLIC-HYPOTHETICAL-'+contract_id+'-'+str(now_day))
            attempts=0;contacts=0;window=[]
            for day in range(now_day+1,future_day+1):
                exposed=book.expose(day,prospects)
                attempts+=book.state['exposures_by_day'][str(day)]['attempted_slots']
                contacts+=len(exposed)
                if day==future_day:window=sorted({r['customer_id'] for r in exposed if r['customer_id'] in eligible})
            pair['candidate' if purchase else 'baseline']={'window_contacts':len(window),'window_customer_ids':window,'attempted_slots_to_window':attempts,'realized_contacts_to_window':contacts}
        rows.append({'public_seed':seed,**pair})
    return {'schema':'sequence-real-channel-scenarios/v1','contract_id':contract_id,'terms':terms,'invoice_microUSD':terms['price_microUSD']+terms['support_microUSD'],
            'new_tranche_admissible':admitted,'observed_state_sha256':digest(state),'public_buyer_status_sha256':digest({i:{k:b[k] for k in ('onboarded','active')} for i,b in buyers.items()}),
            'now_day':now_day,'future_day':future_day,'owned_customer_ids':sorted(owned_ids),'rows':rows,**({'target_customer_ids':sorted(targets),'total_owned_contact_count':len(owned_base)} if target_customer_ids is not None else {}),
            'scope':'DECLARED_PAIRED_PUBLIC_SEED_HYPOTHESES_NOT_PRIVATE_FUTURE_REPLAY',
            'limits':'Actual ChannelBook transition algorithm: observed live tranches, per-contract lead/expiry/retries, shared contacts/cooldown/fatigue and overlap. Four deterministic hypothetical seeds are not calibrated expectations. Only final-window delivery value is credited; all intervening outreach/qualification is charged. No later collections or reserve releases fund present action.'}
