from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from . import source

_ORIGINAL_CLIENT = '''
import importlib,json,pathlib,sys,tempfile
kind,root,input_path,artifact_path=sys.argv[1:]
root=pathlib.Path(root)
program=root/('tasks/19_wave/problem/input/program' if kind=='wave' else 'tasks/23_dynamic_grocery/problem/input/program')
sys.path.insert(0,str(program))
verifier=importlib.import_module('verifier');evaluator=importlib.import_module('evaluator')
with tempfile.TemporaryDirectory(prefix='operational075-original-client-') as folder:
 if kind=='grocery_locked':
  rolling=importlib.import_module('_grocery_rolling');paths=json.loads(pathlib.Path(input_path).read_text());payloads=[pathlib.Path(p).read_bytes() for p in paths]
  if len(payloads)!=18:raise ValueError('All eighteen original submissions required before final client')
  transcript=rolling.RollingEpisode(program).finalize_locked_submissions([json.loads(p.decode('utf-8')) for p in payloads],payloads)
  pathlib.Path(artifact_path).write_text(json.dumps(transcript,sort_keys=True,separators=(',',':'),allow_nan=False))
 if kind in ('grocery','grocery_locked'):
  context=pathlib.Path(folder)/'context.json';context.write_text(json.dumps({'information_mode':'rolling_batch_v1','phase':'completed','epoch':18,'committed_periods':18,'total_periods':18}));input_path=str(context)
 accepted,reason=verifier.verify(input_path,artifact_path)
 result={'accepted':bool(accepted),'reason':str(reason),'original_verifier':'verifier.verify','original_evaluator':'evaluator.evaluate','scope':'UPSTREAM_COMPUTATIONAL_CLIENT_ONLY'}
 if accepted:result['objective']=evaluator.evaluate(input_path,artifact_path)
 print(json.dumps(result,sort_keys=True,allow_nan=False))
'''


def _run(kind, source_root, input_path, artifact_path):
    receipt = source.verify_source(source_root)
    artifact_path = Path(artifact_path).absolute()
    if artifact_path.is_symlink() or kind != 'grocery_locked' and not artifact_path.is_file():
        raise ValueError('OPERATIONAL075_REGULAR_SUBMISSION_REQUIRED')
    completed = subprocess.run([sys.executable, '-I', '-c', _ORIGINAL_CLIENT, kind, str(Path(source_root).absolute()), str(input_path), str(artifact_path)], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if completed.returncode != 0:
        result = {'accepted': False, 'reason': 'Original client process failed', 'returncode': completed.returncode, 'diagnostic': completed.stderr[-1500:]}
    else:
        result = json.loads(completed.stdout)
    return dict(result, upstream_commit=receipt['upstream_commit'], source_manifest_sha256=receipt['source_manifest_sha256'], submission_sha256=hashlib.sha256(artifact_path.read_bytes()).hexdigest() if artifact_path.exists() else None, original_client_process_returncode=completed.returncode)


def verify_wave(source_root, input_path, artifact_path):
    if Path(input_path).absolute() != source.source_path(source_root, source.WAVE_INPUT):
        raise ValueError('OPERATIONAL075_PINNED_WAVE_INPUT_REQUIRED')
    return _run('wave', source_root, input_path, artifact_path)


def verify_grocery(source_root, artifact_path):
    return _run('grocery', source_root, '', artifact_path)


def finalize_grocery(source_root, locked_paths, artifact_path):
    import tempfile
    paths = [str(Path(p).absolute()) for p in locked_paths]
    if len(paths) != 18 or len(set(paths)) != 18:
        raise ValueError('OPERATIONAL075_EIGHTEEN_DISTINCT_LOCKED_SUBMISSIONS_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='operational075-locked-list-') as folder:
        path = Path(folder) / 'paths.json'; path.write_text(json.dumps(paths))
        return _run('grocery_locked', source_root, path, artifact_path)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('kind', choices=('wave', 'grocery')); parser.add_argument('--source', type=Path, required=True); parser.add_argument('--input', type=Path); parser.add_argument('--artifact', type=Path, required=True); args = parser.parse_args()
    result = verify_wave(args.source, args.input, args.artifact) if args.kind == 'wave' else verify_grocery(args.source, args.artifact)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
