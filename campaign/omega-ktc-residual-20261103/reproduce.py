"""Replay all registered cases and exploratory control, then independently score.

Uses installed NumPy/SciPy/matplotlib, no installations or paid API calls.
Downloads public pinned artifacts only through fetch_sources.py. Reproduction
writes scratch outputs here; public RESULT.json is not overwritten until all
six reconstruction cases and independent scorer equivalence complete.
"""
from pathlib import Path
import os,sys,subprocess
ROOT=Path(__file__).resolve().parent
ENV=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
def run(*args):subprocess.run([sys.executable,*args],cwd=ROOT,env=ENV,check=True)
if __name__=='__main__':
 run('fetch_sources.py')
 for level in [1,4,7]:
  for kind in ['limited','full']:run('run_baseline.py',str(level),kind)
 for level in [1,4,7]:run('run_cuqi.py',str(level))
 for level in [1,4,7]:
  for kind in ['limited','full','cuqi3']:run('score_fast.py',str(level),kind)
 # Retain the unchanged original scorer as the independent implementation check.
 for level in [1,4]:run('score.py',str(level),'limited')
 run('review_score_equivalence.py')
 run('summarize.py')
