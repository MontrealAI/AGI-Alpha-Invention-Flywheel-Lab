from pathlib import Path
import collections,hashlib,json,re
root=Path('/workspace/scratch/92d546ab6009/massbank-probe-data');rows=[]
for folder in ['Eawag','Eawag_Additional_Specs','Agilent']:
 for p in sorted((root/folder).glob('*.txt')):
  text=p.read_text(errors='replace');d=collections.defaultdict(list)
  for line in text.splitlines():
   if ': ' in line:
    k,v=line.split(': ',1);d[k].append(v)
  def sub(k,s): return next((v[len(s)+1:] for v in d[k] if v.startswith(s+' ')),None)
  peaks=text.split('PK$PEAK:')[-1].strip();row={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'peak_sha256':hashlib.sha256(peaks.encode()).hexdigest(),'license':d['LICENSE'],'accession':d['ACCESSION'],'date':d['DATE'],'formula':d['CH$FORMULA'][0] if d['CH$FORMULA'] else None,'inchikey':sub('CH$LINK','INCHIKEY'),'energy':sub('AC$MASS_SPECTROMETRY','COLLISION_ENERGY'),'ms_type':sub('AC$MASS_SPECTROMETRY','MS_TYPE'),'mode':sub('AC$MASS_SPECTROMETRY','ION_MODE'),'adduct':sub('MS$FOCUSED_ION','PRECURSOR_TYPE'),'instrument':d['AC$INSTRUMENT'],'instrument_type':d['AC$INSTRUMENT_TYPE'],'authors':d['AUTHORS'],'comment':d['COMMENT'],'processing':d['MS$DATA_PROCESSING'],'peak_count':d['PK$NUM_PEAK'],'precursor':sub('MS$FOCUSED_ION','PRECURSOR_M/Z')};rows.append(row)
Path('/workspace/scratch/92d546ab6009/massbank_probe/metadata-private.json').write_text(json.dumps(rows,indent=2)+'\n')
groups=collections.defaultdict(list)
for r in rows:
 if r['inchikey'] and r['ms_type']=='MS2' and r['adduct'] and r['energy']:
  key=(r['inchikey'][:14],r['energy'],r['mode'],r['adduct'],str(r['instrument']));groups[key].append(r)
rep=[v for v in groups.values() if len({r['peak_sha256'] for r in v})>=2]
chemical=collections.defaultdict(set)
for k,v in groups.items(): chemical[(k[0],k[2],k[3],k[4])].add(k[1])
repchem=collections.defaultdict(set)
for v in rep:
 r=v[0];repchem[(r['inchikey'][:14],r['mode'],r['adduct'],str(r['instrument']))].add(r['energy'])
summary={'records':len(rows),'licensed':dict(collections.Counter(str(r['license']) for r in rows)),'instrument_strings':dict(collections.Counter(str(r['instrument']) for r in rows)),'energy_counts':dict(collections.Counter(str(r['energy']) for r in rows)),'eligible_metadata_groups':len(groups),'groups_with_2_distinct_peak_records':len(rep),'compound_mode_adduct_instrument_with_2_energies':sum(len(v)>=2 for v in chemical.values()),'compound_mode_adduct_instrument_with_2_energies_and_distinct_peak_record_repetition_each':sum(len(v)>=2 for v in repchem.values()),'replicate_caution':'Distinct peak hashes at same energy are not proof of independently measured replicates. Review acquisition metadata before admission.'}
Path('/workspace/scratch/92d546ab6009/massbank_probe/ACCESS_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
