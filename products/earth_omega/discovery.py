"""Autonomous public-inventory discovery. Rule-based evidence agent, not an LLM."""
from datetime import datetime, timezone
from collections import Counter
import hashlib, html, json, pathlib
from .earth import collect, load, canonical, Invalid, distance, point, stamp, num

LICENSE_URL='https://opendatacommons.org/licenses/odbl/1-0/'

def discover_records(parking,chargers,asof,min_spaces=100,max_age_days=90):
    num(min_spaces,'min_spaces',1,100000); num(max_age_days,'max_age_days',1,3660)
    if not isinstance(parking,list) or not isinstance(chargers,list): raise Invalid('expected full export JSON lists')
    if len(parking)>10000 or len(chargers)>100000: raise Invalid('inventory exceeds bounded implementation')
    stations={}; invalid_chargers=0
    id_counts=Counter(c.get('id_pdc_local') for c in chargers if isinstance(c,dict) and isinstance(c.get('id_pdc_local'),str))
    for c in chargers:
        try:
            if c.get('statut_pdc')!='En service': continue
            point_id=c['id_pdc_local']
            if not isinstance(point_id,str) or not point_id or id_counts[point_id]!=1: raise Invalid('duplicate/missing charging point ID')
            ident=c['id_station_local']
            if not isinstance(ident,str) or not ident: raise Invalid('missing station ID')
            xy=point([c['coordonneesxy']['lon'],c['coordonneesxy']['lat']])
            date=stamp(c['date_maj']+'T00:00:00Z')
            if date>asof: raise Invalid('future charger date')
            stations.setdefault(ident,{'coordinates':[],'latest':date,'points':0})['points']+=1
            stations[ident]['coordinates'].append(xy)
            stations[ident]['latest']=min(stations[ident]['latest'],date) # conservative group freshness
        except (KeyError,TypeError,ValueError,AttributeError): invalid_chargers+=1
    leads=[]; rejected=[]; seen=set()
    for p in parking:
        ident=p.get('id') if isinstance(p,dict) else None
        try:
            if not isinstance(ident,str) or ident in seen: raise Invalid('missing or duplicate facility ID')
            seen.add(ident); coords=point([p['xlong'],p['ylat']]); capacity=num(p['nb_places'],'parking capacity',0,100000)
            if capacity<min_spaces: rejected.append({'id':ident,'reason':'below minimum declared spaces'}); continue
            observed=p.get('mis_a_jour'); age=None
            if observed:
                age=(asof-stamp(observed)).total_seconds()/86400
                if age<0: raise Invalid('future parking observation')
            ev=p.get('nb_voitures_electriques')
            if ev is not None: ev=num(ev,'existing electric spaces',0,capacity)
            nearby=[]
            for sid,s in stations.items():
                km=min(distance(coords,xy) for xy in s['coordinates'])
                if km<=.5: nearby.append({'station_id':sid,'distance_km':round(km,3),'points':s['points'],'fresh':(asof-s['latest']).total_seconds()/86400<=max_age_days})
            gaps=['operator_participation','site_control','permitted_use','grid_capacity_and_quote','demand_measurement','all_project_costs']
            if age is None or age>max_age_days: gaps.append('fresh_parking_inventory')
            if ev is None: gaps.append('existing_on_site_charging_count')
            leads.append({'id':ident,'name':p.get('nom'),'coordinates':coords,'declared_spaces':capacity,
                          'declared_electric_spaces':ev,'spaces_not_in_reported_non_pmr_ev_category':capacity-ev if ev is not None else None,
                          'observed_at':observed,'inventory_fresh':age is not None and age<=max_age_days,
                          'public_operator_name':p.get('deleg'),'public_access_category':p.get('type_usagers'),
                          'nearby_public_stations':sorted(nearby,key=lambda x:(x['distance_km'],x['station_id'])),
                          'status':'UNVALIDATED_RETROFIT_LEAD','evidence_needed':gaps,
                          'why_discovered':'Public inventory reports a parking facility meeting the requested capacity threshold; this is not availability or demand evidence.'})
        except (KeyError,ValueError,TypeError,AttributeError) as e: rejected.append({'id':ident,'reason':str(e)})
    # Prioritize evidence-gathering on fresh known low-charging facilities, not profitability.
    leads.sort(key=lambda x:(not x['inventory_fresh'],x['declared_electric_spaces'] is None,
                             (x['declared_electric_spaces']/x['declared_spaces']) if x['declared_electric_spaces'] is not None else 1,
                             -x['declared_spaces'],x['id']))
    return {'schema':'earth-discovery/1','method':'AUTOMATED_RULE_BASED_PUBLIC_INVENTORY_DISCOVERY_NOT_LLM',
            'as_of':asof.isoformat(),'input_counts':{'parking':len(parking),'charging_points':len(chargers),'invalid_charging_records':invalid_chargers},
            'policy':{'minimum_spaces':min_spaces,'maximum_age_days':max_age_days,'nearby_radius_km':.5},
            'leads':leads,'excluded':rejected,'qualified_commercial_sites':0,
            'ranking_basis':'Evidence-gathering priority: fresh inventory, known lower reported non-PMR EV-space fraction (excludes accessible EV spaces), larger capacity. Not a demand or profitability score.',
            'limitations':['Only municipal concession parking and Belib stations; not all properties or competitors',
                           'No outreach, investment, lease or grid reservation', 'Public operator names do not imply willingness to partner',
                           'Missing charging count is unknown, never zero','Reported EV spaces exclude accessible EV spaces; complement is not proven uncharged capacity','No commercial opportunity is qualified by this run']}

def discover(out,min_spaces=100,max_age_days=90):
    root=pathlib.Path(out); root.mkdir(parents=True,exist_ok=False)
    receipts={}; data={}; trace=[]
    for kind in ('parking_metadata','paris_metadata','parking','paris_all'):
        receipt=collect(kind,root/kind); receipts[kind]=receipt; data[kind]=load(root/kind/'source.raw')
        trace.append({'tool':'collect_reviewed_source','source_key':kind,'sha256':receipt['sha256'],'bytes':receipt['bytes']})
    for kind in ('parking_metadata','paris_metadata'):
        meta=data[kind]['metas']['default']
        if 'odbl' not in (str(meta.get('license',''))+' '+str(meta.get('license_url',''))).lower(): raise Invalid('source license changed; explicit review needed')
    for kind,meta in (('parking','parking_metadata'),('paris_all','paris_metadata')):
        count=data[meta]['metas']['default']['records_count']
        if count!=len(data[kind]): raise Invalid('export count differs from metadata; repeat only after inspecting source change')
    result=discover_records(data['parking'],data['paris_all'],datetime.now(timezone.utc),min_spaces,max_age_days)
    result['sources']=receipts; result['database_license']={'name':'ODbL1.0','url':LICENSE_URL,'attribution':'Ville de Paris, Direction de la Voirie et des Déplacements; Belib static-data publisher. Contains information from Paris Data under ODbL.'}
    trace.append({'tool':'discover_and_cross_reference','leads':len(result['leads']),'qualified':0})
    result['trace']=trace
    (root/'discovery.json').write_bytes(canonical(result))
    export={'type':'FeatureCollection','license':result['database_license'],'features':[{'type':'Feature','geometry':{'type':'Point','coordinates':lead['coordinates']},'properties':lead} for lead in result['leads']]}
    (root/'leads.geojson').write_bytes(canonical(export))
    (root/'index.html').write_text(render_discovery(result),encoding='utf-8')
    (root/'ATTRIBUTION.txt').write_text('Contains information from Ville de Paris / Paris Data, available under ODbL 1.0.\n'+LICENSE_URL+'\nDerived database distributed under ODbL. Code retains repository license.\n')
    return {'output':str(root/'discovery.json'),'leads':len(result['leads']),'qualified_commercial_sites':0,'execution':result['method']}


def render_discovery(r):
    e=lambda x:html.escape(str(x),quote=True)
    cards=''.join('<article><h2>'+e(x['name'])+'</h2><p>'+e(x['id'])+' · '+e(x['declared_spaces'])+' declared parking spaces</p><p>Inventory fresh: '+e(x['inventory_fresh'])+' · Reported non-PMR EV spaces (accessible EV spaces excluded): '+e(x['declared_electric_spaces'])+'</p><p>Evidence needed: '+e(', '.join(x['evidence_needed']))+'</p></article>' for x in r['leads'])
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>EARTH Ω · Discovered leads</title><style>body{background:#0a1720;color:#ecf4ef;font:17px system-ui;max-width:1000px;margin:auto;padding:35px}h1{font-size:3rem}article{background:#152c37;padding:20px;margin:14px 0;border-radius:12px}a{color:#c4e2b0}p{line-height:1.5}</style><h1>EARTH Ω</h1><p>'+str(len(r['leads']))+' automatically discovered retrofit leads. <b>0 commercially qualified sites.</b></p><p>'+e(r['ranking_basis'])+'</p><p>Rule-based discovery, not a model-backed result. No outreach or investment performed.</p><p><a href="discovery.json">Evidence dossier</a> · <a href="leads.geojson">GIS-ready leads</a> · <a href="ATTRIBUTION.txt">ODbL attribution</a></p>'+cards+'<p>'+e(r['database_license']['attribution'])+'</p></html>'
