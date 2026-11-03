import argparse,hashlib,json,re,subprocess
from pathlib import Path
from companion import evaluate

ROOT=Path(__file__).resolve().parent
PUBLIC=ROOT.parent/'research/super-alpha.pdf'
if not PUBLIC.is_file():PUBLIC=ROOT/'SUPER_ALPHA.pdf'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def check(build_only=False):
    expected=json.loads((ROOT/'results.json').read_text())
    if evaluate()!=expected:raise ValueError('Analytical results differ from the published snapshot')
    built=ROOT/'build/paper.pdf'
    if not built.is_file():raise ValueError('Compile paper.tex first')
    content=subprocess.check_output(['pdftotext',str(built),'-'],text=True)
    for word in ['SUPER','ALPHA','Inventing Economic Possibility','commercial window','13,566','48,141','123 profiles','960,000','References']:
        if word not in content:raise ValueError('Missing paper content: '+word)
    if '[?]' in content or '(??)' in content:raise ValueError('Unresolved paper reference')
    log=(ROOT/'build/paper.log').read_text()
    for token in ['Overfull','undefined','Missing character','multiply defined','destination with the same identifier']:
        if token in log:raise ValueError('LaTeX issue: '+token)
    pages=int(re.search(r'Pages:\s+(\d+)',subprocess.check_output(['pdfinfo',str(built)],text=True))[1])
    if not 20<=pages<=36:raise ValueError('Unexpected page count')
    if not build_only:
        manifest=json.loads((ROOT/'PUBLICATION.json').read_text())
        for name,expected_sha in manifest['source_files'].items():
            p=ROOT/name
            if not p.is_file() or p.is_symlink() or sha(p)!=expected_sha:raise ValueError('Source identity mismatch: '+name)
        if sha(PUBLIC)!=manifest['pdf']['sha256'] or PUBLIC.stat().st_size!=manifest['pdf']['bytes']:raise ValueError('Public PDF identity mismatch')
        if pages!=manifest['pdf']['pages']:raise ValueError('Page count mismatch')
        public_text=subprocess.check_output(['pdftotext',str(PUBLIC),'-'],text=True)
        if re.sub(r'\s+',' ',content)!=re.sub(r'\s+',' ',public_text):raise ValueError('Rebuilt text differs from the inspected PDF')
        if manifest['private_source_documents_published'] is not False:raise ValueError('Unexpected private source declaration')
    return {'status':'PASS','pages':pages,'analytical_snapshot':'MATCH','build_only':build_only,'scope':'Analytical illustration and research manuscript; no operating enterprise qualification'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--build-only',action='store_true');a=p.parse_args()
    print(json.dumps(check(a.build_only),sort_keys=True))
if __name__=='__main__':main()
