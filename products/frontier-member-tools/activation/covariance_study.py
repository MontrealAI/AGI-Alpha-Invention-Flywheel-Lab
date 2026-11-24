"""Run a release-vintaged ExoClock forecast comparison on original timing files."""

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
from hashlib import sha256
from math import ceil, isclose, sqrt
from pathlib import Path
from statistics import fmean, median
from zipfile import ZipFile

from science_substrate import canonical, read_json


FENCE = Decimal('2460035.5')
EXCLUDE = frozenset(('GJ357b','HD108236e','HD260655c','TOI-444b','TOI-942c'))
METHODS = ('released_marginals','weighted','huber','adaptive_horizon')
FILE_LIMIT = 3_500_000
OBS_HEADER = ('Tmid (BJD_TDB)','Tmid unc.','source','ID')


def source(path, role, binding):
    with path.open('rb') as stream:
        raw=stream.read(FILE_LIMIT+1)
    if len(raw)>FILE_LIMIT or sha256(raw).hexdigest()!=binding[role]['sha256']:
        raise ValueError('SOURCE_BYTE_IDENTITY:'+role)
    return raw


def decimals(values):
    numbers=tuple(map(Decimal,values))
    if not all(value.is_finite() for value in numbers):
        raise ValueError('NONFINITE_MEASUREMENT')
    return numbers


def elements(raw):
    header,*rows=raw.decode().splitlines()
    if header.split()[0]!='Planet' or 'BJD_TDB' not in header:
        raise ValueError('EPOCH_SOURCE_UNITS')
    catalog={}
    for line in rows:
        name,*values=(value.strip() for value in line.split('\t'))
        if len(values)!=4 or name in catalog:
            raise ValueError('SOURCE_EPHEMERIS_SHAPE')
        t,u,p,v=decimals(values)
        if not (t>0 and u>=0 and p>0 and v>=0):
            raise ValueError('SOURCE_EPHEMERIS_RANGE')
        catalog[name]=(t,u,p,v)
    return catalog


def observations(raw, early):
    header,*rows=raw.decode().splitlines()
    if tuple(x.strip() for x in header.split('\t'))!=OBS_HEADER:
        raise ValueError('TIMING_TABLE_UNITS')
    groups=defaultdict(list)
    for number,line in enumerate(rows,2):
        columns=line.split('\t')
        name=''
        if early:
            # The early release prepends a fixed-width planet name to the time.
            name,columns[0]=columns[0][:15].strip(),columns[0][15:]
        time,sigma,kind,key=(value.strip() for value in columns)
        y,s=decimals((time,sigma))
        if not (y>0 and s>0 and kind and key and (not early or name)):
            raise ValueError('INVALID_TIMING_ROW')
        groups[name].append((y,s,kind,key,number))
    return groups


def group_epochs(rows, t, p):
    result={}
    for y,s,kind,key,line in rows:
        with localcontext() as context:
            context.prec=45
            n=round((y-t)/p)
        if n not in result or (s,key,line)<result[n][:3]:
            result[n]=(s,key,line,y,kind)
    return [(n,point[3]-t-n*p,point[0]) for n,point in sorted(result.items())]


def weighted(fit, weights):
    total=sum(weights)
    x=sum(w*n for (n,_,_),w in zip(fit,weights))/total
    y=sum(w*d for (_,d,_),w in zip(fit,weights))/total
    xx=sum(w*(n-x)**2 for (n,_,_),w in zip(fit,weights))
    slope=sum(w*(n-x)*(d-y) for (n,d,_),w in zip(fit,weights))/xx
    return x,y,xx,total,slope


def normal_equations(fit,target):
    with localcontext() as context:
        context.prec=50
        points=[(n,d,1/s**2) for n,d,s in fit]
        sw=sum(w for _,_,w in points)
        sx=sum(w*n for n,_,w in points)
        sy=sum(w*d for _,d,w in points)
        sxx=sum(w*n*n for n,_,w in points)
        sxy=sum(w*n*d for n,d,w in points)
        determinant=sw*sxx-sx*sx
        forecast=((sxx*sy-sx*sxy)+target*(sw*sxy-sx*sy))/determinant
        variance=(sxx-2*target*sx+target**2*sw)/determinant
        return float(forecast),float(variance)


def methods(rows, ephemeris, observed):
    t,u,p,v=ephemeris
    y,s,_,_,_=observed
    n=round((y-t)/p)
    if abs((y-t)-n*p)==p/2:
        return None
    error=float(y-t-n*p)*86400
    fit=[(epoch,float(deviation),float(sigma)) for epoch,deviation,sigma in rows]
    weights=[1/sigma**2 for _,_,sigma in fit]
    initial=weighted(fit,weights)
    robust=initial
    for _ in range(8):
        x,center,_,_,slope=robust
        adjusted=[w*min(1,1.345/max(1e-12,abs(d-center-(epoch-x)*slope)/sd))
                  for (epoch,d,sd),w in zip(fit,weights)]
        robust=weighted(fit,adjusted)
    noise=median(float(sigma) for _,_,sigma in rows)
    result={'released_marginals':(error,86400*sqrt(float(u*u+(n*v)**2)+noise**2))}
    for name,(x,center,xx,total,slope) in (('weighted',initial),('huber',robust)):
        mean=center+(n-x)*slope
        variance=1/total+(n-x)**2/xx
        if name=='weighted':
            d,pv=normal_equations(rows,n)
            if not (isclose(d,mean,rel_tol=1e-8,abs_tol=1e-11)
                    and isclose(pv,variance,rel_tol=1e-9,abs_tol=1e-14)):
                raise ValueError('INDEPENDENT_NORMAL_EQUATIONS')
        result[name]=(error-mean*86400,86400*sqrt(variance+noise**2))
    marks=[item[0] for item in rows]
    band='long' if abs(n-median(marks))>max(1,max(marks)-min(marks)) else 'short'
    return n,band,result


def cohort(ephemerides, older, filename):
    dropped=Counter()
    admitted=[]
    with ZipFile(filename) as zipfile:
        members={info.filename:info for info in zipfile.infolist()
                 if info.filename.startswith('by_planet/') and info.filename.endswith('.txt')}
        if len(members)>1000 or any(row.file_size>500_000 for row in members.values()):
            raise ValueError('TIMING_ARCHIVE_BOUNDS')
        for name,ephem in sorted(ephemerides.items()):
            if name in EXCLUDE:
                dropped['previous_pilot']+=1
                continue
            entry=members.get('by_planet/'+name+'.txt')
            if entry is None:
                dropped['no_later_file']+=1
                continue
            early=group_epochs(older.get(name,[]),ephem[0],ephem[2])
            if len(early)<4:
                dropped['few_older_epochs']+=1
                continue
            later=observations(zipfile.read(entry),False)['']
            space=[x for x in later if x[0]>FENCE+1 and x[2]=='space']
            if not space:
                dropped['no_later_space_timing']+=1
                continue
            first=min(space)
            estimate=methods(early,ephem,first)
            if estimate is None:
                dropped['ambiguous_epoch']+=1
                continue
            n,band,result=estimate
            bucket=int(sha256(('liberation-covariance-v1:'+name).encode()).hexdigest(),16)%100
            admitted.append({'target':name,'epoch':n,'band':band,'used_for':'calibration' if bucket<35 else 'confirmation',
                'older_epochs':len(early),'observed_bjd_tdb':str(first[0]),'observed_sigma_s':float(first[1])*86400,
                'witness':f'{entry.filename}:L{first[4]}','timing_id':first[3],'forecasts':result})
    return admitted,dict(dropped)


def conformal(points, name):
    scores=sorted(abs(row['forecasts'][name][0])/row['forecasts'][name][1] for row in points)
    rank=ceil(.90*(len(scores)+1))
    return scores[rank-1] if 1<=rank<=len(scores) else None


def wilson_lower(hits,count):
    hit=hits/count
    z=1.959963984540054
    return (hit+z*z/(2*count)-z*sqrt(hit*(1-hit)/count+z*z/(4*count*count)))/(1+z*z/count)


def assess(cases):
    train=[row for row in cases if row['used_for']=='calibration']
    held=[row for row in cases if row['used_for']=='confirmation']
    pooled={name:conformal(train,name) for name in METHODS[:-1]}
    bands={kind:[row for row in train if row['band']==kind] for kind in ('long','short')}
    distinguish=all(len(group)>=12 for group in bands.values())
    by_band={kind:conformal(group,'weighted') if distinguish else pooled['weighted'] for kind,group in bands.items()}
    report={'calibration_count':len(train),'confirmation_count':len(held),'calibration_bands':{k:len(v) for k,v in bands.items()},
            'distinct_intervention':distinguish,'pooled_multipliers':pooled,'horizon_multipliers':by_band,
            'observing_authority':'ABSTAIN'}
    if not held or None in pooled.values() or None in by_band.values():
        return {**report,'verdict':'ABSTAIN_INSUFFICIENT_SUPPORT','methods':{}}
    results={}
    for name in METHODS:
        predictions=[row['forecasts']['weighted' if name=='adaptive_horizon' else name] for row in held]
        scales=[by_band[row['band']] if name=='adaptive_horizon' else pooled[name] for row in held]
        intervals=[sd*q for (_,sd),q in zip(predictions,scales)]
        errors=[abs(error) for error,_ in predictions]
        covered=sum(err<=half for err,half in zip(errors,intervals))
        lower=wilson_lower(covered,len(held))
        results[name]={'hits':covered,'targets':len(held),'fraction':covered/len(held),'wilson_lower_95':lower,
            'mae_seconds':fmean(errors),'median_full_width_s':2*median(intervals),'total_margin_minutes':sum(intervals)/30,
            'reservation_minutes':{str(base):sum(intervals)/30 + base*len(held) for base in (90,150,240)},
            'eligible':len(held)>=30 and covered/len(held)>=.90 and lower>=.8}
    conventional=[name for name in ('weighted','huber') if results[name]['eligible']]
    winner=min(conventional,key=lambda name:results[name]['median_full_width_s']) if conventional else None
    selected=results['adaptive_horizon']
    qualifies=(winner is not None and selected['eligible'] and distinguish and
               selected['median_full_width_s']<=.9*results[winner]['median_full_width_s'])
    return {**report,'verdict':'QUALIFIED_HISTORICAL_WINDOW_GAIN' if qualifies else 'NO_QUALIFYING_WINDOW_GAIN',
            'methods':results,'strongest_eligible_fit':winner}


def run(args):
    binding=read_json(args.sources)
    for name in ('early_elements','early_observations'):
        if not binding[name]['version_created']<'2023-04-01' or binding[name]['version']!=1:
            raise ValueError('EARLIER_VERSION_AVAILABILITY')
    ephemerides=elements(source(args.elements,'early_elements',binding))
    older=observations(source(args.older,'early_observations',binding),True)
    if any(row[0]>=FENCE for values in older.values() for row in values):
        raise ValueError('FUTURE_TRAINING_TIMING')
    raw=source(args.later,'later_observations',binding)
    # Use the verified bytes, not a second open of the pathname.
    from io import BytesIO
    cases,dropped=cohort(ephemerides,older,BytesIO(raw))
    result=assess(cases)
    return {'scope':'Historical release-vintaged comparison. Later measurements are public; no live future observations or bookings.',
            'earlier_planets':len(ephemerides),'earlier_rows':sum(map(len,older.values())),
            'excluded':dropped,'independent_exact_weighted_checks':len(cases),'study':result,'cases':cases}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for path in ('sources','elements','older','later'):
        parser.add_argument('--'+path,type=Path,required=True)
    print(canonical(run(parser.parse_args())).decode())
