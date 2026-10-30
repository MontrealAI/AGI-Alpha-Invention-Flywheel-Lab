from pathlib import Path
import collections,json,hashlib,re,shutil
base=Path('/workspace/scratch/92d546ab6009/massbank_probe');rows=json.loads((base/'metadata-private.json').read_text());g=collections.defaultdict(lambda:collections.defaultdict(lambda:collections.defaultdict(list)))
for r in rows:
 conf=next((s for s in r['comment'] if s.startswith('CONFIDENCE ')),None)
 if conf not in ['CONFIDENCE 1','CONFIDENCE standard compound']:continue
 if not(r['inchikey'] and r['formula'] and r['precursor'] and r['adduct'] and r['energy'] and r['ms_type']=='MS2'):continue
 if not re.fullmatch(r'\d+ % \(nominal\)',r['energy']):continue
 key=(r['formula'],r['mode'],r['adduct'],tuple(r['instrument']),r['fragmentation_mode'])
 g[key][r['inchikey']][r['energy']].append(r)
options=[]
for key,ids in g.items():
 ids={k:v for k,v in ids.items() if len(v)>=2}
 if len(ids)<2:continue
 common=set.intersection(*(set(v) for v in ids.values()))
 if len(common)<2:continue
 precursor=[float(r['precursor']) for e in ids.values() for ee,rs in e.items() if ee in common for r in rs];ppm=(max(precursor)-min(precursor))/min(precursor)*1e6
 if ppm>10:continue
 options.append((len(ids),len(common),repr(key),key,ids,common,ppm))
options.sort(key=lambda x:(-x[0],-x[1],x[2]));n,ne,_,key,ids,energies,ppm=options[0];selected_ids=sorted(ids)[:8];energies=sorted(energies,key=lambda x:int(x.split()[0]));selected=[r for i in selected_ids for e in energies for r in ids[i][e]]
out=base/'development-dataset';out.mkdir(exist_ok=False);(out/'records').mkdir();observations=[]
for r in selected:
 p=Path(r['path']);shutil.copy2(p,out/'records'/p.name);lines=p.read_text().splitlines();start=next(i for i,s in enumerate(lines) if s.startswith('PK$PEAK:'));peaks=[]
 for line in lines[start+1:]:
  if line.startswith('//'):break
  s=line.strip().split()
  if len(s)>=2:
   try:peaks.append([float(s[0]),float(s[1])])
   except ValueError:pass
 obs={k:r[k] for k in ['sha256','peak_sha256','accession','license','date','formula','inchikey','energy','precursor','adduct','mode','instrument','fragmentation_mode','authors','comment','processing']};obs['record_file']='records/'+p.name;obs['source_url']='https://github.com/MassBank/MassBank-data/blob/d4cccb5b6756bb14d52568c82720dde1dd3d42e1/'+str(p).split('massbank-probe-data/',1)[1];obs['peaks']=peaks;observations.append(obs)
admission={'type':'RETROSPECTIVE_DEVELOPMENT_ONLY','source_repository':'https://github.com/MassBank/MassBank-data','source_commit':'d4cccb5b6756bb14d52568c82720dde1dd3d42e1','rule':'Before intensity outcomes: from Eawag/Eawag_Additional_Specs/Agilent records with MS2, full InChIKey, numeric precursor, exact single numeric percent nominal CE and confidence1/standardcompound, form exact formula/mode/adduct/instrument-string/fragmentation-field groups. Retain identities with >=2energies; require >=2common energies and precursor range<=10ppm. Choose largest identitycount, then largestcommonenergycount, then lexicalgroup; take first8fullInChIKeys lexically. Keep ALL records at ALL common energies for those identities. No spectrum similarity inspected for selection.','selected_formula':key[0],'mode':key[1],'adduct':key[2],'exact_instrument':key[3],'fragmentation_mode_field':key[4],'precursor_range_ppm':ppm,'identities':selected_ids,'energies':energies,'record_count':len(observations),'independent_replicates':'UNESTABLISHED: all records development; differinghash/date/accession do not certify separate acquisition. No protected confirmation or claimed authenticunknownidentification.','unknowns':['Exact acquisitionrun/injection provenance','Actual cost per independent CE scan vs steppedCE','Completeness of candidate library','Out-of-library structural identity','Fresh biological/environmental matrix generalization']}
(out/'ADMISSION.json').write_text(json.dumps(admission,indent=2)+'\n');(out/'observations.json').write_text(json.dumps(observations,indent=2)+'\n');print(json.dumps(admission,indent=2));print('Allmetadataoptions',[(x[0],x[1],x[3]) for x in options[:5]])
