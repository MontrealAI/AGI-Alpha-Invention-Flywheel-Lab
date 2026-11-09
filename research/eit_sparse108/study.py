"""Source-bound archive-only shape classification; NOT physical/commercial qualification.
Preregistration: 8d973616313547cf716a3a02d700537f968b6601.
"""
from collections import Counter
import csv
from hashlib import md5,sha256
import io,json,math,time
from urllib.request import Request,urlopen

FREEZE_SHA="8d973616313547cf716a3a02d700537f968b6601"
URL="https://zenodo.org/records/7192883/files/"
SOURCES={"circle":("circle_petg.csv","262a968766cd034914155ac2bfcd121e"),
         "square":("square_petg.csv","bbdccac3f0ffb63cb0c1cd8b045fba9c"),
         "triangle":("triangle_petg.csv","6d22c805a62e1017b841ab311a775156")}
CIRCLE_SHA256="2e6b357e41b8b69bca8e23ce7a8b924677bae80ecab34da8830a4edada4ab62f"
CHANNELS=tuple(f"E_{i:02d}" for i in range(1,17))
PAIR_ORDER=tuple((a,(a+8)%16) for a in range(16))
PAIRS={4:(0,2,4,6),8:tuple(range(8)),16:tuple(range(16))}
REQUIRED=frozenset(("value_desc","object","material","r","phi","meas_num","ex_mat_0","ex_mat_1")+CHANNELS)
CLASSES=tuple(sorted(SOURCES))
MAX_BYTES=20_000_000

def verify_source(blob,label):
    if label not in SOURCES: raise ValueError("UNREGISTERED_SOURCE_LABEL")
    if not isinstance(blob,bytes) or not blob or len(blob)>MAX_BYTES: raise ValueError("SOURCE_SIZE_INVALID")
    m,s=md5(blob).hexdigest(),sha256(blob).hexdigest()
    if m!=SOURCES[label][1]: raise ValueError("SOURCE_MD5_CHANGED")
    if label=="circle" and s!=CIRCLE_SHA256: raise ValueError("CIRCLE_SHA256_CHANGED")
    return {"file":SOURCES[label][0],"bytes":len(blob),"official_md5":m,"observed_sha256":s}

def fetch_source(label):
    url=f"{URL}{SOURCES[label][0]}?download=1"
    with urlopen(Request(url,headers={"User-Agent":"AGI-ALPHA-EIT108-Research/1"}),timeout=90) as response:
        blob=response.read(MAX_BYTES+1)
    identity=verify_source(blob,label)
    identity["url"]=url
    return blob,identity

def group_position_key(r,phi):
    if not isinstance(r,str) or not r or not isinstance(phi,str) or not phi:
        raise ValueError("MISSING_PHYSICAL_POSITION")
    return r,phi

def is_held_out(r,phi):
    r,phi=group_position_key(r,phi)
    return int.from_bytes(sha256(f"eit108|{r}|{phi}".encode()).digest()[:8],"big")%5==0

def parse_16_channel_row(row):
    if not isinstance(row,dict) or None in row or any(v is None for v in row.values()):
        raise ValueError("RAGGED_ROW")
    try: a,b=int(row["ex_mat_0"]),int(row["ex_mat_1"])
    except (TypeError,ValueError,KeyError) as exc: raise ValueError("INVALID_INJECTION_PAIR") from exc
    if (a,b) not in PAIR_ORDER: raise ValueError("NONREGISTERED_INJECTION_PAIR")
    absent={a,(a+1)%16,b,(b+1)%16}
    vals=[]
    for i,k in enumerate(CHANNELS):
        raw=row[k]
        if i in absent:
            if raw not in ("NA",""): raise ValueError("INJECTION_NEIGHBOR_HAS_NUMERIC_VOLTAGE")
        else:
            if not isinstance(raw,str) or raw!=raw.strip() or raw in ("NA",""):
                raise ValueError("MISSING_REQUIRED_MEASURED_CHANNEL")
            try: v=float(raw)
            except ValueError as exc: raise ValueError("INVALID_MEASURED_VOLTAGE") from exc
            if not math.isfinite(v): raise ValueError("NONFINITE_MEASURED_VOLTAGE")
            vals.append(v)
    if len(vals)!=12: raise ValueError("UNEXPECTED_VOLTAGE_COUNT")
    return a,tuple(vals)

def parse_csv(blob,label):
    if label not in SOURCES: raise ValueError("UNREGISTERED_SOURCE_LABEL")
    try: body=blob.decode("utf-8-sig")
    except UnicodeError as exc: raise ValueError("SOURCE_NOT_UTF8") from exc
    first=body.split("\n",1)[0]
    delimiter=";" if first.count(";")>first.count(",") else ","
    reader=csv.DictReader(io.StringIO(body),delimiter=delimiter)
    names=reader.fieldnames or []
    if len(names)!=len(set(names)) or not REQUIRED.issubset(names):
        raise ValueError("MISSING_OR_DUPLICATE_FIELDS")
    groups={}
    nrows=nmeasure=0
    locations=set()
    for row in reader:
        nrows+=1
        if nrows>250000: raise ValueError("EXCESSIVE_SOURCE_ROWS")
        if None in row or any(v is None for v in row.values()): raise ValueError("RAGGED_ROW")
        if row["value_desc"]!="measurement": continue
        nmeasure+=1
        if row["object"]!=label: raise ValueError("SOURCE_LABEL_DISAGREEMENT")
        mat,r,phi,num=(row[k] for k in ("material","r","phi","meas_num"))
        locations.add(group_position_key(r,phi))
        a,vals=parse_16_channel_row(row)
        d=groups.setdefault((mat,r,phi,num),{})
        if a in d: raise ValueError("DUPLICATE_ACQUISITION_PAIR_IN_GROUP")
        d[a]=vals
    if not groups: raise ValueError("NO_MEASUREMENTS")
    missing=sum(set(d)!=set(range(16)) for d in groups.values())
    if missing: raise ValueError(f"INCOMPLETE_16_PAIR_GROUP:{missing}")
    if nmeasure!=16*len(groups): raise ValueError("GROUP_COUNT_RECONCILIATION_FAILED")
    return groups,{"csv_rows":nrows,"measurement_rows":nmeasure,"archive_measurement_groups":len(groups),
                   "exact_stored_position_strings":len(locations),"source_shape":label,"independent_new_specimens":0}

def vector(group,indices):
    if set(group)!=set(range(16)): raise ValueError("INCOMPLETE_GROUP")
    feat=[]
    for i in indices:
        vals=group[i]
        if len(vals)!=12 or not all(math.isfinite(x) for x in vals):
            raise ValueError("INVALID_GROUP_MEASURED_CHANNELS")
        feat.extend(vals)
    return feat

def prepare(groups_by_label):
    out={}
    for n,selected in PAIRS.items():
        xt,xv,yt,yv=[],[],[],[]
        trainpos,testpos=set(),set()
        counts={}
        for label in CLASSES:
            groups=groups_by_label[label]
            ct=cv=0
            tr,tv=set(),set()
            for (mat,r,phi,num),measured in groups.items():
                feat=vector(measured,selected)
                if is_held_out(r,phi):
                    xv.append(feat);yv.append(label);testpos.add((r,phi));tv.add((r,phi));cv+=1
                else:
                    xt.append(feat);yt.append(label);trainpos.add((r,phi));tr.add((r,phi));ct+=1
            counts[label]={"train_groups":ct,"heldout_groups":cv,
                           "distinct_train_positions":len(tr),"distinct_heldout_positions":len(tv)}
            if min(ct,cv,len(tr),len(tv))<20: raise ValueError("INSUFFICIENT_REGISTERED_SPLIT")
        if trainpos & testpos: raise ValueError("POSITION_SPLIT_LEAKAGE")
        out[n]=(xt,xv,yt,yv,counts,len(trainpos),len(testpos))
    return out

def metrics(actual,predicted):
    if not actual or len(actual)!=len(predicted): raise ValueError("INVALID_PREDICTION_LENGTH")
    matrix={t:{p:0 for p in CLASSES} for t in CLASSES}
    for truth,guess in zip(actual,predicted):
        if truth not in CLASSES or guess not in CLASSES: raise ValueError("UNKNOWN_PREDICTION_LABEL")
        matrix[truth][guess]+=1
    recalls={s:matrix[s][s]/max(1,sum(matrix[s].values())) for s in CLASSES}
    correct=sum(matrix[s][s] for s in CLASSES)
    return {"accuracy":correct/len(actual),"correct_groups":correct,"heldout_groups":len(actual),
            "macro_recall":sum(recalls.values())/3,"per_class_recall":recalls,"confusion_truth_rows":matrix}

def evaluate(groups):
    from sklearn.ensemble import RandomForestClassifier,ExtraTreesClassifier
    inputs=prepare(groups)
    results={}
    for n in (4,8,16):
        xt,xv,yt,yv,counts,nt,nv=inputs[n]
        t0=time.process_time()
        m=RandomForestClassifier(n_estimators=200,random_state=108,min_samples_leaf=2,
                                 class_weight="balanced_subsample",n_jobs=1)
        m.fit(xt,yt)
        z=metrics(yv,m.predict(xv))
        z["fit_predict_cpu_seconds"]=round(time.process_time()-t0,6)
        z["finite_measured_features_per_group"]=12*n
        z["group_splits"]={"train":len(yt),"heldout":len(yv),"train_positions":nt,
                           "heldout_positions":nv,"per_class":counts}
        results[f"rf{n}"]=z
        if n==16:
            t0=time.process_time()
            m=ExtraTreesClassifier(n_estimators=400,random_state=108,min_samples_leaf=2,
                                   class_weight="balanced_subsample",n_jobs=1)
            m.fit(xt,yt)
            z=metrics(yv,m.predict(xv))
            z["fit_predict_cpu_seconds"]=round(time.process_time()-t0,6)
            z["finite_measured_features_per_group"]=192
            results["extra_trees16"]=z
    full=max(results["rf16"]["accuracy"],results["extra_trees16"]["accuracy"])
    for n in (4,8):
        z=results[f"rf{n}"]
        z["absolute_accuracy_gap_vs_strong_full"]=full-z["accuracy"]
        passed=z["accuracy"]>=0.95 and z["accuracy"]>=full-0.02 and min(z["per_class_recall"].values())>=0.90
        z["technical_screen"]="PASS_PROXY_ONLY" if passed else "FAIL_RETAINED"
    return results

def run():
    t0,c0=time.perf_counter(),time.process_time()
    identities,groups,counts={},{},{}
    for label in CLASSES:
        blob,identity=fetch_source(label)
        groups[label],counts[label]=parse_csv(blob,label)
        identities[label]=identity
    results=evaluate(groups)
    return {"schema":"eit108/preregistered-heldout-shape-sparse/v1","protocol_freeze_sha":FREEZE_SHA,
            "sources":identities,"source_stats":counts,"registered_comparison":results,
            "source_observations_already_public":True,"fresh_physical_specimens":0,
            "physical_acquisition_time_savings_established":False,
            "strong_human_and_specialist_comparison_executed":False,
            "historic_published_direct_shape_rf_competitor":"SBrT2026 DOI:10.14209/sbrt.2026.1571299951",
            "native_accounts_operated":0,"actual_collections_usd":0,
            "native_trailing365_complete_cost_profit_usd":None,"whole_engineering_billing_usd":None,
            "commercial_benefit":"UNQUALIFIED","physical_end_use":"UNQUALIFIED",
            "decision":"HOLD_NO_BID_NO_DEPLOY",
            "cpu_seconds":round(time.process_time()-c0,6),"wall_seconds":round(time.perf_counter()-t0,6)}

if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True,indent=2))
