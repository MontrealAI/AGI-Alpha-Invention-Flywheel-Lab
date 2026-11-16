"""Bounded, auditable EV charging site screening. Python 3.11+, stdlib only."""
from __future__ import annotations
import argparse, csv, hashlib, html, io, itertools, json, math, pathlib, sys
from datetime import datetime, timezone
from urllib.request import build_opener, HTTPRedirectHandler, Request

SOURCES = {
    'paris': 'https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/belib-points-de-recharge-pour-vehicules-electriques-donnees-statiques/records?limit=100',
    'chargers': 'https://donnees.montreal.ca/dataset/c999d1a9-8333-4871-9226-7d3a53f490a6/resource/b502cee9-ff87-44fa-9a8e-722285202b0d/download/bornes-recharge-publiques.geojson',
    'utilization': 'https://donnees.montreal.ca/fr/dataset/4b2f9b4c-abac-4c36-997a-85c22e22bf0b/resource/a9050c7b-2337-4cc2-ae07-6a53c99e01f6/download/chargeurs_statistiques.csv',
}
MAX_BYTES = 32 * 1024 * 1024
COST_CATEGORIES = ('installation','grid','land','energy','maintenance','network','insurance','tax','financing','decommissioning','acquisition')
REQUIRED = ('site_control', 'permitted_use', 'grid_connection', 'accessibility')
DISCLAIMER = ('Pre-feasibility scenarios, not proven commercially viable places. Municipal charger coverage is incomplete. '
              'Nearby historical use is not forecast demand. No site acquisition, grid reservation, zoning approval, '
              'field validation, customer demand or autonomous commercial success is established.')

class Invalid(ValueError): pass

def canonical(x): return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
def digest(x): return hashlib.sha256(canonical(x)).hexdigest()
def stamp(s):
    try:
        d = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if d.tzinfo is None: raise ValueError()
        return d.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError): raise Invalid('timestamp must be ISO8601 with timezone')
def num(v, name, lo=0, hi=1e12):
    if isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise Invalid(f'{name}: finite numeric value in [{lo},{hi}] required')
    return float(v)
def point(v):
    if not isinstance(v,list) or len(v)!=2: raise Invalid('coordinates must be [longitude,latitude]')
    return [num(v[0], 'longitude', -180,180), num(v[1], 'latitude', -90,90)]
def distance(a,b):
    x,y=map(math.radians,a); u,v=map(math.radians,b)
    h=math.sin((v-y)/2)**2+math.cos(y)*math.cos(v)*math.sin((u-x)/2)**2
    return 6371.0088 * 2 * math.asin(min(1,math.sqrt(h)))
def load(path):
    raw=pathlib.Path(path).read_bytes()
    if len(raw)>MAX_BYTES: raise Invalid('input exceeds 32MiB safety bound')
    return json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(Invalid('nonfinite JSON')))

def evidence(e, asof, max_age):
    if not isinstance(e,dict) or not isinstance(e.get('source'),str) or not e['source'].strip(): raise Invalid('evidence requires source')
    age=(asof-stamp(e.get('observed_at'))).total_seconds()/86400
    if age<0: raise Invalid('future evidence timestamp')
    return age<=max_age

def validate(m):
    if m.get('schema')!='earth-omega/1': raise Invalid('unsupported mission schema')
    asof=stamp(m.get('as_of'))
    max_age=num(m.get('max_age_days',90),'max_age_days',1,3660)
    num(m.get('budget_money'),'budget_money')
    if m.get('currency') not in ('CAD','EUR'): raise Invalid('CAD or EUR required; no implicit FX')
    if m.get('evidence_mode') not in ('fixture','operator-supplied','public-snapshot'): raise Invalid('evidence_mode required')
    sites=m.get('sites')
    if not isinstance(sites,list) or not 1<=len(sites)<=20: raise Invalid('1..20 sites supported by exact portfolio solver')
    ids=set(); coordinates=set()
    for s in sites:
        sid=s.get('id')
        if not isinstance(sid,str) or not sid or len(sid)>120 or sid in ids: raise Invalid('unique nonempty site id required')
        ids.add(sid); coords=tuple(point(s.get('coordinates')))
        if coords in coordinates: raise Invalid('duplicate candidate coordinates: merge the same physical site')
        coordinates.add(coords)
        if not evidence(s.get('location_evidence'),asof,max_age): pass
        for k in REQUIRED:
            e=s.get('constraints',{}).get(k)
            if e:
                if e.get('status') not in ('yes','no','unknown'): raise Invalid('constraint status invalid')
                evidence(e,asof,max_age)
        econ=s.get('economics')
        if not isinstance(econ,dict): raise Invalid('economics required')
        evidence(econ,asof,max_age)
        for k in ('capex_money','annual_fixed_cost_money','price_money_per_kwh','variable_cost_money_per_kwh','residual_money'):
            num(econ.get(k),k)
        num(econ.get('discount_rate'),'discount_rate',0,1)
        years=num(econ.get('years'),'years',1,40)
        if not years.is_integer(): raise Invalid('years integer required')
        r=econ.get('daily_kwh_range')
        if not isinstance(r,list) or len(r)!=2: raise Invalid('daily_kwh_range [low,high] required')
        low,high=[num(v,'daily_kwh',0,1e7) for v in r]
        if low>high: raise Invalid('inverted daily_kwh_range')
        if not isinstance(econ.get('cost_scope'),list) or not econ['cost_scope']: raise Invalid('explicit cost_scope required')
        if not isinstance(s.get('demand_group'),str) or not s['demand_group']: raise Invalid('demand_group required; overlapping catchments must share a group')
        if not isinstance(econ.get('unpriced_costs'),list): raise Invalid('unpriced_costs required, never assume zero')
    observations=m.get('observations',[])
    if not isinstance(observations,list) or len(observations)>100000: raise Invalid('invalid observation collection')
    obsids=set()
    for o in observations:
        oid=o.get('id')
        if not isinstance(oid,str) or oid in obsids: raise Invalid('unique observation ids required')
        obsids.add(oid); point(o.get('coordinates')); evidence(o,asof,max_age)
        if 'daily_kwh' in o: num(o['daily_kwh'],'observed daily_kwh',0,1e7)
    return asof,max_age

def economics(e):
    rate=e['discount_rate']; years=int(e['years'])
    annuity=sum(1/(1+rate)**t for t in range(1,years+1))
    margin=e['price_money_per_kwh']-e['variable_cost_money_per_kwh']
    terminal=e['residual_money']/(1+rate)**years
    npvs=[365*d*margin*annuity-e['annual_fixed_cost_money']*annuity-e['capex_money']+terminal for d in e['daily_kwh_range']]
    break_even=(e['capex_money']-terminal+e['annual_fixed_cost_money']*annuity)/(365*margin*annuity) if margin>0 else None
    return {'npv_money_range':[round(min(npvs),2),round(max(npvs),2)],
            'break_even_daily_kwh':round(break_even,3) if break_even is not None else None,
            'accounting':'discounted modeled project cash flows; not realized profit',
            'cost_scope':e['cost_scope'],'unpriced_costs':e['unpriced_costs']}

def screen(m):
    asof,max_age=validate(m); rows=[]; actions=[]
    for s in m['sites']:
        missing=[]; rejected=[]
        if not evidence(s['location_evidence'],asof,max_age): missing.append('fresh_location')
        for k in REQUIRED:
            e=s.get('constraints',{}).get(k)
            if e and e['status']=='no': rejected.append(k)
            elif not e or e['status']!='yes' or not evidence(e,asof,max_age): missing.append(k)
        if not evidence(s['economics'],asof,max_age): missing.append('fresh_economics')
        if s['economics']['unpriced_costs']: missing.append('unpriced_costs')
        coverage=s['economics'].get('cost_coverage',{})
        for category in COST_CATEGORIES:
            item=coverage.get(category,{}) if isinstance(coverage,dict) else {}
            if not isinstance(item,dict) or item.get('status') not in ('included','not_applicable') or not isinstance(item.get('basis'),str) or not item['basis'].strip():
                missing.append('cost_'+category)
        nearby=[]; stale=0
        for o in m.get('observations',[]):
            d=distance(s['coordinates'],o['coordinates'])
            if d<=2:
                fresh=evidence(o,asof,max_age)
                stale+=not fresh
                nearby.append({'id':o['id'],'distance_km':round(d,3),'fresh':fresh,'source':o['source'],
                               'observed_at':o['observed_at'],'daily_kwh':o.get('daily_kwh')})
        econ=economics(s['economics'])
        status='REJECT_CONSTRAINT' if rejected else 'NEEDS_EVIDENCE' if missing else 'SCENARIO_POSITIVE' if econ['npv_money_range'][0]>0 else 'SCENARIO_UNCERTAIN' if econ['npv_money_range'][1]>0 else 'NO_BUILD_IN_SCENARIO'
        row={'id':s['id'],'coordinates':s['coordinates'],'status':status,'missing':missing,'rejected':rejected,
             'economics':econ,'nearby_observations':sorted(nearby,key=lambda x:(x['distance_km'],x['id'])),
             'stale_nearby_count':stale,'coverage':'municipal/public evidence only; absence is not absence of competition'}
        rows.append(row)
        for k in missing: actions.append({'site_id':s['id'],'action':'obtain_evidence','field':k,'reason':'required before eligible portfolio selection'})
    # Robust portfolio on supplied downside scenarios, not expected sales. Non-entry is always feasible.
    eligible=[(s,r) for s,r in zip(m['sites'],rows) if r['status']=='SCENARIO_POSITIVE']
    best=(0.0,0.0,())
    for mask in range(1<<len(eligible)):
        selected=[eligible[i] for i in range(len(eligible)) if mask>>i&1]
        if len({s['demand_group'] for s,r in selected}) != len(selected): continue
        cost=sum(s['economics']['capex_money'] for s,r in selected)
        ids=tuple(sorted(s['id'] for s,r in selected)); value=sum(r['economics']['npv_money_range'][0] for s,r in selected)
        if cost<=m['budget_money'] and (value>best[0] or (value==best[0] and (cost,ids)<(best[1],best[2]))): best=(value,cost,ids)
    rows.sort(key=lambda r:(-r['economics']['npv_money_range'][0],r['id']))
    return {'schema':'earth-report/1','input_sha256':digest(m),'currency':m['currency'],'as_of':m['as_of'],'evidence_mode':m['evidence_mode'],
            'disclaimer':DISCLAIMER,'sites':rows,'next_actions':actions,
            'portfolio':{'selected_site_ids':list(best[2]),'capex_money':round(best[1],2),'downside_npv_money':round(best[0],2),
                         'scope':'exact enumeration of <=20 supplied sites, one site per declared demand group; costs additive; unmodeled cross-group cannibalization remains a risk',
                         'not_authorization_to_invest':True}}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise Invalid('redirect refused: source must be reviewed explicitly')

def collect(kind,out):
    url=SOURCES[kind]; req=Request(url,headers={'User-Agent':'EARTH-Omega/1 (+https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab)'})
    with build_opener(NoRedirect()).open(req,timeout=60) as response:
        raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise Invalid('source exceeds32MiB bound; use documented bounded extract')
    dest=pathlib.Path(out); dest.mkdir(parents=True,exist_ok=False)
    (dest/'source.raw').write_bytes(raw)
    receipt={'source':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
             'license':'verify source metadata' if kind=='paris' else 'CC BY 4.0','attribution':'Ville de Paris / Belib' if kind=='paris' else 'Ville de Montréal','coverage':'first100 records only; NOT complete inventory' if kind=='paris' else 'public municipal chargers only',
             'observed_at':None,'freshness':'retrieval date does not establish observation date'}
    (dest/'receipt.json').write_bytes(canonical(receipt))
    return receipt

def render(report):
    esc=lambda x:html.escape(str(x),quote=True)
    cards=''.join('<section><h2>'+esc(r['id'])+'</h2><b>'+esc(r['status'])+'</b><p>Scenario NPV '+esc(r['economics']['npv_money_range'])+'</p><p>Break-even daily kWh: '+esc(r['economics']['break_even_daily_kwh'])+'</p><p>Missing: '+esc(', '.join(r['missing']) or 'none in declared scope')+'</p><p>Public observations within2km: '+str(len(r['nearby_observations']))+'</p></section>' for r in report['sites'])
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>EARTH Ω | Decision dossier</title><style>body{background:#09141e;color:#edf6f2;font:18px system-ui;max-width:1050px;margin:50px auto;padding:24px}h1{font-size:3rem}section{background:#142735;border:1px solid #345349;border-radius:12px;padding:20px;margin:20px 0}b{color:#bbdba0}p{line-height:1.6}code{overflow-wrap:anywhere}</style><h1>EARTH Ω</h1><p>Commercial charging site pre-feasibility</p><p>'+esc(report['disclaimer'])+'</p><p>Evidence mode: <b>'+esc(report['evidence_mode'])+'</b></p><p>Scenario portfolio: '+esc(report['portfolio']['selected_site_ids'])+'</p>'+cards+'<p>Input SHA256 <code>'+esc(report['input_sha256'])+'</code></p></html>'

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('screen'); a.add_argument('mission'); a.add_argument('--out',required=True)
    a=sub.add_parser('verify'); a.add_argument('mission'); a.add_argument('report')
    a=sub.add_parser('normalize'); a.add_argument('kind',choices=SOURCES); a.add_argument('snapshot'); a.add_argument('--observed-at'); a.add_argument('--out',required=True)
    a=sub.add_parser('investigate'); a.add_argument('mission'); a.add_argument('--out',required=True)
    a=sub.add_parser('collect'); a.add_argument('kind',choices=SOURCES); a.add_argument('--out',required=True)
    args=p.parse_args()
    try:
        if args.cmd=='collect': print(json.dumps(collect(args.kind,args.out))); return
        if args.cmd=='normalize':
            from .importers import normalize
            normalized=normalize(args.snapshot,args.kind,args.observed_at)
            with pathlib.Path(args.out).open('xb') as f: f.write(canonical(normalized))
            print(json.dumps({'observations':len(normalized['observations']),'output':args.out})); return
        if args.cmd=='investigate':
            from .agent import run, deterministic_policy
            result=run(load(args.mission),deterministic_policy); result['execution']='DETERMINISTIC_TOOL_LOOP_NOT_MODEL_BACKED'
            with pathlib.Path(args.out).open('xb') as f: f.write(canonical(result))
            print(json.dumps({'steps':len(result['trace']),'execution':result['execution']})); return
        m=load(args.mission); r=screen(m)
        if args.cmd=='verify':
            if canonical(load(args.report))!=canonical(r): raise Invalid('report differs from deterministic recomputation')
            print('VERIFIED: exact recomputation; input truth/authenticity NOT established'); return
        out=pathlib.Path(args.out); out.mkdir(parents=True,exist_ok=False)
        (out/'report.json').write_bytes(canonical(r)); (out/'index.html').write_text(render(r),encoding='utf-8')
        print(json.dumps({'output':str(out),'portfolio':r['portfolio'],'mode':r['evidence_mode']}))
    except (Invalid,ValueError,OSError,KeyError,TypeError,AttributeError) as e:
        print(f'EARTH rejected: {e}',file=sys.stderr); sys.exit(2)
if __name__=='__main__': main()
