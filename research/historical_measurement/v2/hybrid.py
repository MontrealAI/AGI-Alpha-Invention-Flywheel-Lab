"""Frozen v2 merger. Semantic readings come from the included assistant, not a paid API.
Run only after semantic predictions are saved; never use evaluator labels here.
"""
import csv,json,argparse,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parent

def route(row):
 return 'compiled' if row['state']=='no_water_contact' and float(row['separation_margin'])>=.30 and float(row['distance_dry'])<=1.0 else 'semantic'

def main():
 a=argparse.ArgumentParser();a.add_argument('--phase',choices=['repair','confirmation'],required=True);args=a.parse_args();phase=args.phase
 sem=json.loads((P/(phase+'_semantic_predictions.json')).read_text())
 compiled=list(csv.DictReader((P/(phase+'_compiled.csv')).open()));lookup={(x['filename'],x['query']):x for x in compiled}
 rows=[]
 for s in sem:
  c=lookup[(s['filename'],s['query'])];r=route(c)
  # Geometry mismatch, obscurity or semantics can invalidate an apparently confident compiled dry result.
  if s.get('geometry_valid') is False:r='semantic'
  state=c['state'] if r=='compiled' else s['state']
  rows.append({**s,'semantic_state':s['state'],'state':state,'route':r,'compiled_state':c['state'],'compiled_margin':c['separation_margin']})
 (P/(phase+'_hybrid_predictions.json')).write_text(json.dumps(rows,indent=2))
 print(json.dumps({'phase':phase,'rows':len(rows),'semantic_routed':sum(x['route']=='semantic' for x in rows),'compiled_routed':sum(x['route']=='compiled' for x in rows),'semantic_baseline_readings':len(rows),'billing':'unknown;no separately billed API called'},indent=2))
if __name__=='__main__':main()
