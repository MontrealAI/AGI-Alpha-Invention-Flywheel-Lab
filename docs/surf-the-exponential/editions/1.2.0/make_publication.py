#!/usr/bin/env python3
"""Initialize a NEW 1.2.0 source/PDF binding after build and review.

Never repairs a mismatch or overwrites an existing manifest. Released users should
run package.py --verify, not this initializer. Prior editions are not touched.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import package

ROOT=Path(__file__).resolve().parent

def main():
    path=ROOT/'PUBLICATION.json'
    if path.exists():
        raise SystemExit('A manifest already exists. Refusing to rebind a published edition.')
    pdf=ROOT/'canonical/SURF_THE_EXPONENTIAL.pdf'
    if not pdf.is_file():raise SystemExit('Build canonical/SURF_THE_EXPONENTIAL.pdf first.')
    data=pdf.read_bytes()
    info=subprocess.check_output(['pdfinfo',str(pdf)],text=True)
    pages=int(next(line.split(':',1)[1].strip() for line in info.splitlines() if line.startswith('Pages:')))
    names=package.source_inventory(ROOT)
    files=[{'path':name,'bytes':len((ROOT/name).read_bytes()),'sha256':package.digest((ROOT/name).read_bytes())} for name in names]
    compiled_names=package.compiled_inventory(ROOT)
    compiled=[row for row in files if row['path'] in compiled_names]
    bib=shutil.which('bibtex') or shutil.which('bibtex.original')
    manifest={
        'schema':'surf-publication/v1','title':'SURF THE EXPONENTIAL: The Missing Move',
        'subtitle':'From Verified Criticism to New Capabilities, Viable Markets, and Better Inventors',
        'author':'Vincent Boucher','affiliations':['MONTREAL.AI','QUEBEC.AI'],
        'edition':'1.2.0','publication_date':'2026-11-05','release_tag':'surf-the-exponential-v1.2.0',
        'reader_url':'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/surf-the-exponential-v1.2.0',
        'parent_edition':{'edition':'1.1.0','canonical_pdf_sha256':'45b063750a325a4e94be45e7dd3ea1595cdf74c1e446496f50504e44028349a1','source_archive_sha256':'708952677e5be4ecfabb66530a0b759c9828ec4a1552e7736fe49132524f734a','preserved':True},
        'canonical_pdf':{'repository_path':'docs/surf-the-exponential/editions/1.2.0/canonical/SURF_THE_EXPONENTIAL.pdf',
          'repository_relative_to_source':'canonical/SURF_THE_EXPONENTIAL.pdf','bundle_path':'canonical/SURF_THE_EXPONENTIAL.pdf',
          'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'pages':pages},
        'build':{'entrypoint':'python3 build.py --output canonical/SURF_THE_EXPONENTIAL.pdf','source_date_epoch':1793836800,
          'reference_pdflatex':subprocess.check_output(['pdflatex','--version'],text=True).splitlines()[0],
          'reference_bibtex':subprocess.check_output([bib,'--version'],text=True).splitlines()[0],
          'shell_escape':False,'reproducibility':'Two clean builds on one toolchain; cross-toolchain bytes may differ. Canonical bytes are retained.'},
        'binding_scope':'File identities, not semantic truth or evidence of actual trade. Run all three checkers and tests.',
        'source_files':files,'source_tree_sha256':package.digest(package.canonical_json(files)),
        'compiled_inputs':compiled,'compiled_input_tree_sha256':package.digest(package.canonical_json(compiled)),
        'release_assets':{'pdf':'SURF_THE_EXPONENTIAL.pdf','source_archive':'SURF_THE_EXPONENTIAL_SOURCE.zip','manifest':'PUBLICATION.json','checksums':'SHA256SUMS'},
        'evidence':{'retained_tests':29,'new_decision_tests':29,'total_tests':58,'review_grid':2304,
                    'representation_partition_count':21147,'decision_relation_partition_checks':2560,'decision_economic_cases':840,
                    'actual_revenue':0,'frontier_model_experiments':0}}
    path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    package.validated_content(ROOT)
    print(json.dumps({'edition':'1.2.0','pdf_sha256':manifest['canonical_pdf']['sha256'],'pages':pages,'source_files':len(files)}))

if __name__=='__main__':main()
