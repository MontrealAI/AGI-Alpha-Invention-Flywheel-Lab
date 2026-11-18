"""Exercise all public reader workflows and the page key with an independent PDF reader."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata

import pymupdf

from materials import ARMS, HERE, REG, pages, sha, sources
from trial import packet


def normal(text):
    text=re.sub(r'(?<=[^\W\d_])-\n[ \t]*(?=[^\W\d_])','',text)
    return ' '.join(unicodedata.normalize('NFKC',text).replace('’',"'").split())


def qualify(output):
    output.mkdir(parents=True,exist_ok=False)
    result={'study':REG['id'],'kind':'automated_pre_enrollment_qualification','actual_participants':0,
            'reader_accuracy':None,'reader_time':None,'assistive_technology_benefit':None,'complete_cost_per_accepted_reader_outcome':None,
            'source_pairs':{},'registrations_sha256':sha(HERE/'REGISTERED.json'),
            'code_sha256':{n:sha(HERE/n) for n in ('materials.py','trial.py','concordance.js','form.js','qualify.py')},
            'tools':{'pymupdf':pymupdf.VersionBind,'python':sys.version.split()[0],
                     'poppler':subprocess.run(['pdftotext','-v'],capture_output=True,text=True).stderr.splitlines()[0]}}
    for lang in ('en','fr'):
        files=sources(lang);raw=pages(files['pdf'])
        with pymupdf.open(files['pdf']) as doc:
            witnesses=[]
            for task in [t for t in REG['tasks'] if t['lang']==lang]:
                pg=doc[task['page']-1]
                text=normal(pg.get_text(sort=False))
                if normal(task['evidence']) not in text:
                    # Geometric reconstruction is an independent view of multi-column lines.
                    text=normal(pg.get_text(sort=True))
                assert normal(task['evidence']) in text,(task['id'],task['page'],task['evidence'])
                witnesses.append({'id':task['id'],'physical_page':task['page'],'reference_snippet_present':True})
            assert len(doc)==len(raw)==REG['languages'][lang]['pdf_pages']
        receipts={}
        for arm in ARMS:
            start=time.monotonic()
            ids=[t['id'] for t in REG['tasks'] if t['lang']==lang]
            row={'session':'technical-'+lang+'-'+arm,'lang':lang,'arm':arm,'withdrawn':False,'order_json':json.dumps(ids)}
            folder=output/(lang+'-'+arm)
            packet(row,folder)
            area=folder/'publication'
            assert all(sha(area/p.name)==sha(p) for p in files.values())
            form=(folder/'START.html').read_text()
            assert all(t['rubric'] not in form for t in REG['tasks'])
            assert 'role="status"' in form and 'type="number"' in form
            branch={}
            if arm=='C':
                rc=json.loads((area/'edition/receipt.json').read_text());branch={'locator':rc['summary']}
            elif arm=='B':
                s=(area/'index-pages.html').read_text()
                assert all(f'#page={n}"' in s for n in range(1,len(raw)+1))
                branch={'indexed_pages':len(raw)}
            elif arm=='D':
                s=(area/'index-pages.html').read_text()
                data=s.split('<script type="application/json" id="pages">',1)[1].split('</script>',1)[0]
                assert json.loads(data)==raw
                branch={'indexed_pages':len(raw)}
            receipts[arm]={'build_wall_s':round(time.monotonic()-start,6),'bytes':sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()),**branch}
        result['source_pairs'][lang]={'source_pdf_sha256':sha(files['pdf']),'source_html_sha256':sha(files['html']),
                                      'physical_pages':len(raw),'source_checks':witnesses,'packets':receipts}
    result['qualification']='passed'
    (output/'QUALIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(qualify(args.output),ensure_ascii=False,indent=2))
