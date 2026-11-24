"""Restore exact public evidence packets using an independently checked plan."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
import json
from itertools import combinations
from pathlib import Path
import re
from time import perf_counter_ns
from urllib.parse import urlsplit
from zipfile import ZipFile

from pages import PAGES, REPO, digest, get

PACKS = ('frontier-foundry-1.0.0.zip','frontier-foundry-1.1.0.zip',
         'frontier-inventor-1.0.0.zip','frontier-learning-1.0.0.zip')
HEX = re.compile(r'[0-9a-f]{64}\Z')
RAW = re.compile(rf'/{re.escape(REPO)}/[0-9a-f]{{40}}/(?:products/frontier-member-tools|products/alpha-genesis-harness|publication)/[a-zA-Z0-9_./-]+\Z')


def project(case,catalog):
    required=case['required']
    if not 1<=len(required)<=16 or len(set(required))!=len(required) or any(not HEX.fullmatch(x) for x in required):
        raise ValueError('PACKET_TARGET')
    if type(case['cap']) is not int or not 1<=case['cap']<=12:
        raise ValueError('PACKET_BUDGET')
    masks={key:sum(1<<i for i,content in enumerate(required) if content in obj['supplies'])
           for key,obj in catalog.items()}
    rows=[(key,mask,catalog[key]['bytes'],catalog[key]['kind']=='archive') for key,mask in sorted(masks.items()) if mask]
    return (1<<len(required))-1,rows


def optimal(case,catalog):
    goal,rows=project(case,catalog)
    if len(rows)>48:
        raise ValueError('SOURCE_TABLE_SIZE')
    states={0:(0,())}
    candidates=[]
    for _ in range(case['cap']):
        after={}
        for mask,(cost,path) in states.items():
            for key,available,size,_ in rows:
                updated=mask|available
                if updated==mask:
                    continue
                choice=cost+size,(*path,key)
                if updated not in after or choice<after[updated]:
                    after[updated]=choice
        if goal in after:
            value,path=after.pop(goal)
            candidates.append((value,len(path),path))
        states=after
    return list(min(candidates)[2]) if candidates else None


def bounded_exact(case,catalog):
    # Comparison harness uses independently enumerated subsets for small held tables.
    goal,rows=project(case,catalog)
    if len(rows)>22 or case['cap']>8:
        raise ValueError('INDEPENDENT_ENUMERATION_BOUND')
    best=None
    for count in range(1,min(case['cap'],len(rows))+1):
        for selected in combinations(rows,count):
            mask=0
            for _,covered,_,_ in selected:
                mask|=covered
            if mask==goal:
                choice=(sum(r[2] for r in selected),count,tuple(r[0] for r in selected))
                if best is None or choice<best:
                    best=choice
    return list(best[2]) if best else None


def construct_plan(case,catalog,policy):
    pending,rows=project(case,catalog)
    path=[]
    for r in range(case['cap'],0,-1):
        active=[(key,coverage&pending,byte_count,bit) for key,coverage,byte_count,bit in rows if coverage&pending]
        table=[(gain.bit_count(),size,gain,pending.bit_count(),int(archive),pending)
               for _,gain,size,archive in active]
        if not table:
            return None
        choice=policy(table,r)
        if type(choice) is not int or not 0<=choice<len(active):
            return None
        name,gain,_,_=active[choice]
        path.append(name)
        pending&=~gain
        if not pending:
            return path
    return None


def result(case,catalog,path):
    if not path or len(path)>case['cap'] or len(set(path))!=len(path) or any(x not in catalog for x in path):
        return {'state':'REJECTED','reason':'NO_VALID_PLAN'}
    observed={digest for key in path for digest in catalog[key]['supplies']}
    if not set(case['required'])<=observed:
        return {'state':'REJECTED','reason':'INCOMPLETE_COVERAGE'}
    return {'state':'MATCHED','reads':len(path),'bytes':sum(catalog[x]['bytes'] for x in path),'plan':path}


def compare(case,catalog,program=None,independent=False):
    start=perf_counter_ns()
    chosen=optimal(case,catalog)
    reference=result(case,catalog,chosen)
    duration=perf_counter_ns()-start
    if independent:
        enumerated=result(case,catalog,bounded_exact(case,catalog))
        fields=('state','reads','bytes')
        if [reference.get(k) for k in fields]!=[enumerated.get(k) for k in fields]:
            raise ValueError('CONVENTIONAL_DIVERGENCE')
    full=result(case,catalog,[case['archive']])
    output={'case':case['id'],'exact':reference,'full':full,'exact_ns':duration}
    if program is not None:
        from table_program import Refused
        start=perf_counter_ns()
        try:
            candidate=result(case,catalog,construct_plan(case,catalog,program))
        except Refused as error:
            candidate={'state':'REJECTED','reason':str(error)}
        output['candidate']=candidate
        output['candidate_ns']=perf_counter_ns()-start
    return output


def allowed(source):
    url=source['url']
    if source['kind']=='archive':
        return url in {PAGES+name for name in PACKS}
    bits=urlsplit(url)
    return (source['kind']=='direct' and bits.scheme=='https' and bits.netloc=='raw.githubusercontent.com'
            and not bits.query and not bits.fragment and '..' not in bits.path.split('/') and RAW.fullmatch(bits.path))


def collect(case,catalog,path,destination,parallel=1):
    expected=result(case,catalog,path)
    if expected['state']!='MATCHED' or type(parallel) is not int or not 1<=parallel<=8:
        raise ValueError('UNQUALIFIED_PLAN')
    required=set(case['required'])
    objects={}
    receipts=[]
    start=perf_counter_ns()
    sources=[catalog[key] for key in path]
    for source in sources:
        length=source['bytes']
        if not allowed(source) or not 1<=length<=600000 or not HEX.fullmatch(source['sha256']):
            raise ValueError('SOURCE_AUTHORITY')

    def receive(source):
        length=source['bytes']
        data=get(source['url'],length)
        if len(data)!=length or sha256(data).hexdigest()!=source['sha256']:
            raise ValueError('SOURCE_DRIFT')
        return data

    with ThreadPoolExecutor(max_workers=min(parallel,len(sources))) as pool:
        bodies=list(pool.map(receive,sources))
    for source,data in zip(sources,bodies):
        receipts.append({'source':source['url'],'bytes':len(data),'sha256':source['sha256']})
        if source['kind']=='direct':
            objects[source['sha256']]=data
        else:
            with ZipFile(BytesIO(data)) as z:
                manifest=json.loads(z.read('manifest.json'))['file_sha256']
                for name,digest_ in manifest.items():
                    if digest_ in required-objects.keys():
                        if z.getinfo(name).file_size>600000:
                            raise ValueError('ARCHIVE_MEMBER_SIZE')
                        body=z.read(name)
                        if sha256(body).hexdigest()!=digest_:
                            raise ValueError('ARCHIVE_MEMBER_DRIFT')
                        objects[digest_]=body
    if not required<=objects.keys():
        raise ValueError('INCOMPLETE_PACKET')
    destination.mkdir(mode=0o700,parents=True,exist_ok=True)
    for ident in sorted(required):
        target=destination/ident
        if target.is_symlink():
            raise ValueError('OUTPUT_TARGET')
        try:
            with target.open('xb') as file:
                file.write(objects[ident])
        except FileExistsError:
            if target.is_symlink() or not target.is_file() or target.stat().st_size!=len(objects[ident]) or target.read_bytes()!=objects[ident]:
                raise ValueError('OUTPUT_CONFLICT') from None
    receipt={'schema':'frontier/public-packet-v1','case':case['id'],**expected,'objects':sorted(required),
             'sources':receipts,'parallel':parallel,'wall_ns':perf_counter_ns()-start,'case_sha256':digest(case)}
    from study import atomic
    atomic(destination/'receipt.json',receipt)
    return receipt
