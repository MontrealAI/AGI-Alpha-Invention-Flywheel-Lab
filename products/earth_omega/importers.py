"""Normalize reviewed public sources without turning collection time into observation time."""
import calendar, csv, hashlib, io, json
from pathlib import Path
from .earth import Invalid, MAX_BYTES, SOURCES, point, stamp, num

def normalize(folder, kind, observed_at=None):
    p=Path(folder); raw=(p/'source.raw').read_bytes(); receipt=json.loads((p/'receipt.json').read_text())
    if len(raw)>MAX_BYTES or hashlib.sha256(raw).hexdigest()!=receipt['sha256']: raise Invalid('snapshot hash mismatch')
    if receipt['source']!=SOURCES[kind]: raise Invalid('unexpected source URL')
    retrieved=stamp(receipt['retrieved_at']); rows=[]
    def make(ident,coordinates,when,**extra):
        if stamp(when)>retrieved: raise Invalid('observation postdates retrieval')
        return {'id':str(ident),'coordinates':point(coordinates),'observed_at':when,'source':receipt['source'],
                'snapshot_sha256':receipt['sha256'],**extra}
    if kind=='paris':
        data=json.loads(raw)
        for x in data['results']:
            if x.get('statut_pdc')!='En service': continue
            c=x['coordonneesxy']; date=x.get('date_maj')
            if not date: raise Invalid('Paris row missing producer date')
            rows.append(make(x['id_pdc_local'],[c['lon'],c['lat']],date+'T00:00:00Z'))
    elif kind=='chargers':
        if observed_at is None: raise Invalid('Montreal observed_at from official metadata required, not retrieval date')
        for f in json.loads(raw)['features']:
            x=f['properties']; rows.append(make(x['NOM_BORNE_RECHARGE'],f['geometry']['coordinates'],observed_at))
    else:
        text=raw.decode('utf-8-sig'); dialect=csv.Sniffer().sniff(text[:8192],delimiters=',;')
        for x in csv.DictReader(io.StringIO(text),dialect=dialect):
            y=int(x['Annee']); month=int(x['Mois']); days=calendar.monthrange(y,month)[1]
            when=f'{y:04}-{month:02}-{days:02}T23:59:59Z'
            energy=num(float(x['Nombre_kwh_total'].replace(',','.')),'kwh')
            rows.append(make(f"{x['Numero_borne']}:{y}-{month}",[float(x['Longitude']),float(x['Latitude'])],when,daily_kwh=energy/days))
    ids=[r['id'] for r in rows]
    if len(ids)!=len(set(ids)): raise Invalid('duplicate source observations')
    return {'observations':rows,'provenance':receipt,'limitations':'Source coverage incomplete. Utilization is historical, not transferable demand.'}
