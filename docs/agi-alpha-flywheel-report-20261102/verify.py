import argparse,hashlib,json,re,subprocess,sys,zipfile
from pathlib import Path
from audit import audit,witness

ROOT=Path(__file__).resolve().parent
PUBLIC=ROOT.parent/'research/agi-alpha-flywheel-20261102-report.pdf'
if not PUBLIC.is_file():PUBLIC=ROOT/'AGI_ALPHA_FLYWHEEL_2026_11_02_REPORT.pdf'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--build-only',action='store_true');a=p.parse_args()
    result=audit(json.loads((ROOT/'evidence/observations.json').read_text()));witness()
    built=ROOT/'build/paper.pdf'
    assert built.is_file() and built.read_bytes().startswith(b'%PDF-')
    text=subprocess.check_output(['pdftotext',str(built),'-'],text=True)
    for phrase in ['AGI ALPHA','FLYWHEEL','2026 11 02 Report','110','13,566','48,141','23','1,079.68','References']:assert phrase in text,phrase
    assert '[?]' not in text and '(??)' not in text
    log=(ROOT/'build/paper.log').read_text()
    assert 'Overfull' not in log and 'undefined' not in log
    pages=int(re.search(r'Pages:\s+(\d+)',subprocess.check_output(['pdfinfo',str(built)],text=True))[1])
    assert 15<=pages<=40
    if not a.build_only:
        manifest=json.loads((ROOT/'PUBLICATION.json').read_text())
        for name,expected in manifest['source_files'].items():
            path=ROOT/name
            assert path.is_file() and not path.is_symlink() and sha(path)==expected,name
        assert PUBLIC.is_file() and sha(PUBLIC)==manifest['pdf']['sha256']
        assert PUBLIC.stat().st_size==manifest['pdf']['bytes']
        assert manifest['pdf']['pages']==pages
        public_text=subprocess.check_output(['pdftotext',str(PUBLIC),'-'],text=True)
        assert re.sub(r'\s+',' ',text)==re.sub(r'\s+',' ',public_text),'compiled and inspected paper text differ'
        assert manifest['private_source_documents_published'] is False
    print(json.dumps({'status':'PASS','pages':pages,'compact_audit':result,'pdf_scope':'Research report, no new native runtime qualification','build_only':a.build_only},sort_keys=True))
if __name__=='__main__':main()
