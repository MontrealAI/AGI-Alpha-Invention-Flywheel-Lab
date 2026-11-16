"""Streaming complementary national IRVE evidence; never infer absence or demand."""
import csv, hashlib, json, math, pathlib, tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.request import Request, build_opener
from .earth import Invalid, NoRedirect, canonical, distance, load, num, point, stamp

URL='https://proxy.transport.data.gouv.fr/resource/consolidation-transport-irve-statique'
METADATA='https://transport.data.gouv.fr/datasets/base-nationale-des-points-de-recharge-pour-vehicules-electriques-en-france-irve'
LICENSE='https://www.etalab.gouv.fr/licence-ouverte-open-licence/'
MAX_NATIONAL_BYTES=256*1024*1024  # separate streamed source, observed ~129MB; no RAM-sized load
MAX_ROWS=500000
FIELDS={'id_pdc_itinerance','id_station_itinerance','consolidated_longitude','consolidated_latitude',
        'consolidated_is_lon_lat_correct','date_maj','date_mise_en_service','condition_acces','horaires','datagouv_dataset_id','datagouv_resource_id','datagouv_last_modified'}

def hash_file(path):
    h=hashlib.sha256(); size=0
    with open(path,'rb') as f:
        while b:=f.read(1024*1024):
            size+=len(b)
            if size>MAX_NATIONAL_BYTES: raise Invalid('national CSV exceeds256MiB streaming bound')
            h.update(b)
    return h.hexdigest(),size

def fetch(path):
    h=hashlib.sha256(); size=0
    request=Request(URL,headers={'User-Agent':'EARTH-Omega/1','Accept-Encoding':'identity'})
    with build_opener(NoRedirect()).open(request,timeout=60) as response, open(path,'xb') as f:
        if response.status!=200 or response.headers.get('Content-Encoding','identity')!='identity': raise Invalid('complete uncompressed200response required')
        length=response.headers.get('Content-Length')
        if length and int(length)>MAX_NATIONAL_BYTES: raise Invalid('national source larger than supported streaming bound')
        while b:=response.read(1024*1024):
            size+=len(b)
            if size>MAX_NATIONAL_BYTES: raise Invalid('national source exceeds256MiB streaming bound')
            h.update(b); f.write(b)
        if length and size!=int(length): raise Invalid('incomplete national source')
    return h.hexdigest(),size

def inspect_csv(path,leads,asof,max_age_days=90):
    num(max_age_days,'max_age_days',1,3660)
    if not isinstance(leads,list) or not 1<=len(leads)<=1000: raise Invalid('1..1000discovered leads required')
    positions=[point(l['coordinates']) for l in leads]
    # Conservative bounding rectangle around all leads; selected records still checked by haversine.
    minx=min(x for x,y in positions)-.02; maxx=max(x for x,y in positions)+.02
    miny=min(y for x,y in positions)-.01; maxy=max(y for x,y in positions)+.01
    if not all(40<=y<=52 and -6<=x<=11 for x,y in positions): raise Invalid('this national spatial adapter supports mainland France bounds only')
    counts=Counter(); selected=[]; invalid=Counter(); total=0
    oldlimit=csv.field_size_limit(); csv.field_size_limit(1024*1024)
    try:
        with open(path,encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if not FIELDS<=set(reader.fieldnames or ()): raise Invalid('national CSV schema mismatch')
            for index,row in enumerate(reader,2):
                total+=1
                if total>MAX_ROWS: raise Invalid('national row bound exceeded')
                pid=row.get('id_pdc_itinerance','').strip()
                if not pid: invalid['missing_point_id']+=1; continue
                counts[pid]+=1
                try:
                    sid=row['id_station_itinerance'].strip()
                    if not sid: raise Invalid('station_id')
                    if row['consolidated_is_lon_lat_correct'].lower()!='true': raise Invalid('unconfirmed_coordinates')
                    coords=point([float(row['consolidated_longitude']),float(row['consolidated_latitude'])])
                    if not(minx<=coords[0]<=maxx and miny<=coords[1]<=maxy): continue
                    observed=row['date_maj']; date=stamp(observed+'T00:00:00Z')
                    if date>asof: raise Invalid('future_observation')
                    commissioned=row.get('date_mise_en_service','').strip()
                    commissioning_date=None
                    if commissioned:
                        try: commissioning_date=stamp(commissioned+'T00:00:00Z')
                        except Invalid: pass
                    selected.append({'commissioning_date':commissioned or None,'commissioning_status':'unknown' if commissioning_date is None else 'future_declared' if commissioning_date>asof else 'declared_started_not_operationally_verified',
                                     'condition_acces':row.get('condition_acces') or None,'horaires':row.get('horaires') or None,'point_id':pid,'station_id':sid,'coordinates':coords,'observed_at':date.isoformat(),
                                     'fresh':(asof-date).total_seconds()/86400<=max_age_days,'operator':row.get('nom_operateur'),
                                     'producer_dataset_id':row['datagouv_dataset_id'],'producer_resource_id':row['datagouv_resource_id'],
                                     'producer_last_modified':row['datagouv_last_modified'],'csv_row':index})
                except (ValueError,TypeError,KeyError,AttributeError) as e: invalid[str(e)]+=1
    finally: csv.field_size_limit(oldlimit)
    duplicate_ids={pid for pid,n in counts.items() if n>1}
    selected=[x for x in selected if x['point_id'] not in duplicate_ids]
    if len(selected)>100000: raise Invalid('spatial extract exceeds100000record bound; narrow the geography')
    grid=defaultdict(list)
    for obs in selected: grid[(math.floor(obs['coordinates'][0]*100),math.floor(obs['coordinates'][1]*100))].append(obs)
    comparisons=[]; match_count=0; used=set()
    for lead,coords in zip(leads,positions):
        nearby=[]; future=[]
        gx,gy=math.floor(coords[0]*100),math.floor(coords[1]*100)
        candidates=(o for dx in (-1,0,1) for dy in (-1,0,1) for o in grid[(gx+dx,gy+dy)])
        for obs in candidates:
            d=distance(coords,obs['coordinates'])
            if d<=.5:
                match_count+=1
                if match_count>100000: raise Invalid('comparison expansion exceeds100000matches; narrow the lead cohort')
                used.add(obs['point_id'])
                if obs['commissioning_status']=='future_declared':
                    future.append(obs['point_id']); continue
                nearby.append({'point_id':obs['point_id'],'station_id':obs['station_id'],'fresh':obs['fresh'],'distance_km':round(d,3)})
        comparisons.append({'site_id':lead['id'],'national_point_count':len(nearby),
                            'national_station_count':len({o['station_id'] for o in nearby}),
                            'fresh_national_point_count':sum(o['fresh'] for o in nearby),
                            'belib_station_count_from_prior_snapshot':len(lead.get('nearby_public_stations',[])),
                            'future_commissioning_points_excluded':sorted(future),
                            'count_scope':'Static declared inventory, not confirmed operating or public-access competitors. Restricted/unknown access remains in the inventory count.',
                            'national_observations':sorted(nearby,key=lambda x:(x['distance_km'],x['point_id'])),
                            'interpretation':'Separate overlapping evidence layers: do not sum counts. Zero matches means not observed in this snapshot, not no competition.'})
    return {'rows_scanned':total,'invalid_rows_by_reason':dict(invalid),'duplicate_point_ids_quarantined':len(duplicate_ids),
            'spatially_retained_unique_points':len(selected),'observation_table':{o['point_id']:o for o in selected if o['point_id'] in used},'comparisons':comparisons,'radius_km':.5,
            'maximum_age_days':max_age_days,'bounding_box':[minx,miny,maxx,maxy]}

def complement(discovery,out,snapshot=None,max_age_days=90):
    dossier=load(discovery)
    if dossier.get('schema')!='earth-discovery/1': raise Invalid('expected EARTH discovery dossier')
    root=pathlib.Path(out); root.mkdir(parents=True,exist_ok=False)
    now=datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix='earth-irve-') as tmp:
        path=pathlib.Path(snapshot) if snapshot else pathlib.Path(tmp)/'national.csv'
        sha,size=hash_file(path) if snapshot else fetch(path)
        retrieved=datetime.now(timezone.utc)
        result=inspect_csv(path,dossier['leads'],now,max_age_days)
    result.update(schema='earth-national-comparison/1',as_of=now.isoformat(),discovery_sha256=hashlib.sha256(canonical(dossier)).hexdigest(),
                  source={'url':URL,'metadata':METADATA,'sha256':sha,'bytes':size,'retrieval_started_at':None if snapshot else now.isoformat(),'retrieved_at':None if snapshot else retrieved.isoformat(),
                          'mode':'operator_supplied_snapshot_unverified_origin' if snapshot else 'actual_http_download',
                          'license':'Licence Ouverte2.0','license_url':LICENSE,'attribution':"Point d’Accès National transport.data.gouv.fr and original data producers"},
                  qualified_commercial_sites=0,
                  limitations=['Static inventory is not live availability, utilization, grid capacity or demand',
                               'Source is national consolidation but completeness is not guaranteed',
                               'Producer observation date controls freshness; consolidation or retrieval does not refresh old facts',
                               'Belib and national layers overlap; no additive combined count or exclusive additional-site claim',
                               'No economics, ranking promotion, outreach or commercial qualification derives from these counts'])
    (root/'national-comparison.json').write_bytes(canonical(result))
    (root/'ATTRIBUTION.txt').write_text('National evidence: Point d’Accès National transport.data.gouv.fr and original producers. Licence Ouverte2.0.\n'+LICENSE+'\nOriginal parking-derived database remains under ODbL1.0; this comparison does not remove its attribution/share-alike obligations.\n')
    return {'output':str(root/'national-comparison.json'),'rows_scanned':result['rows_scanned'],
            'compared_leads':len(result['comparisons']),'qualified_commercial_sites':0,'source_sha256':sha}
