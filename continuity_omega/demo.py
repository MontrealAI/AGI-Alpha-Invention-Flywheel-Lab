"""Synthetic fixture data only; names, orders and amounts are not real commerce."""
from copy import deepcopy
from .engine import digest

SPEC='d9'*32

def case_for(name='nominal'):
    events=[
        {'sequence':1,'type':'ACCEPT','order_id':'LBL-100','quantity':1000,'product':'LABEL-A','spec_sha256':SPEC,'deadline_hours':48},
        {'sequence':2,'type':'ACCEPT','order_id':'LBL-200','quantity':800,'product':'LABEL-A','spec_sha256':SPEC,'deadline_hours':48},
        {'sequence':3,'type':'ACCEPT','order_id':'LBL-300','quantity':600,'product':'LABEL-A','spec_sha256':SPEC,'deadline_hours':48},
        {'sequence':4,'type':'AMEND','order_id':'LBL-100','quantity':1100},
        {'sequence':5,'type':'CANCEL','order_id':'LBL-300'},
    ]
    case={'schema':'continuity-omega/synthetic-drill-v1','mode':'SYNTHETIC','real_authority':False,
        'exercise_id':'PRINT-SIM-001','source_events':events,'source_seal':digest(events),
        'objective':{'product':'LABEL-A','deadline_hours':48,'no_lost_orders':True,'no_duplicates':True},
        'restored_snapshot':[{'order_id':'LBL-100','quantity':1000}, {'order_id':'LBL-300','quantity':600}],
        'buyer':{'maximum_offer':5800,'simulated_eligibility':True},
        'scope_rights_declared':True,'blocked_failure_domains':[],
        'economics':{'offer':5700,'costs':{'assessment':450,'setup':650,'reservation':350,'supplier':2500,
            'transport':400,'verification':250,'support':200,'rights':100,'contingency':150}},
        'suppliers':[
            {'supplier_id':'PRINTER-P','product':'LABEL-A','capacity_units':3200,'lead_hours':22,
             'failure_domain':'POWER-NORTH','available':True,'simulated_qualification':True,'simulated_commitment':True,
             'quoted_cost':2500,'existing_reservations':[{'start_hour':0,'end_hour':48,'units':1100}]},
            {'supplier_id':'PRINTER-Q','product':'LABEL-A','capacity_units':1800,'lead_hours':20,
             'failure_domain':'POWER-SOUTH','available':True,'simulated_qualification':True,'simulated_commitment':True,
             'quoted_cost':2200,'existing_reservations':[]},
        ],
    }
    if name=='nominal':pass
    elif name=='tampered_source':case['source_events'][1]['quantity']=1000  # seal intentionally not updated
    elif name=='overbooked':case['suppliers'][0]['existing_reservations'][0]['units']=1400
    elif name=='correlated_outage':case['blocked_failure_domains']=['POWER-NORTH']
    elif name=='unqualified':case['suppliers'][0]['simulated_commitment']=False
    elif name=='late':case['suppliers'][0]['lead_hours']=55
    elif name=='buyer_declines':case['buyer']['maximum_offer']=5500
    elif name=='uneconomic':case['economics']['costs']['support']=1000
    elif name=='unapproved_sharing':case['scope_rights_declared']=False
    elif name=='no_order_source':case['source_events']=[]
    elif name=='missing_from_restored':case['restored_snapshot']=[{'order_id':'LBL-100','quantity':1000}]
    elif name=='extra_restored':case['restored_snapshot'].append({'order_id':'FAKE-001','quantity':1})
    else:raise ValueError('unknown fixture '+name)
    return case

CASES=('nominal','tampered_source','overbooked','correlated_outage','unqualified','late',
    'buyer_declines','uneconomic','unapproved_sharing','no_order_source','missing_from_restored','extra_restored')
