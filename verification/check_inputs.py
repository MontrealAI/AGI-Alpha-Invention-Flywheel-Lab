import argparse, hashlib, json, pathlib

EXPECTED={
'pglib_opf_case14_ieee.m':'bd5c568621de65e4b0922317010868bc7fa94173807faa10ea8fdbbe77c28106',
'pglib_opf_case30_ieee.m':'cae3290639d989731d32428aacf30c0b918bc91db73bc54791f3aa62d3f76c70'}

def check_inputs(directory, manifest=None):
    directory=pathlib.Path(directory)
    if manifest is not None:
        declared=json.loads(pathlib.Path(manifest).read_text())
        if declared.get('files')!=EXPECTED:
            raise ValueError('Input manifest does not match frozen expected identities')
    verified={}
    for filename,expected in EXPECTED.items():
        path=directory/filename
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=expected:
            raise ValueError('Input identity mismatch: '+filename)
        verified[filename]=actual
    return verified

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--manifest');a=p.parse_args()
    print(json.dumps({'verified':check_inputs(a.directory,a.manifest)},sort_keys=True))

if __name__=='__main__':main()
