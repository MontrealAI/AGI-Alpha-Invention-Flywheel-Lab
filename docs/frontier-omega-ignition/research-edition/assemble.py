#!/usr/bin/env python3
"""Build the reviewed research/IGNITION preview from the existing World Lab.
No network, new model calls or publication authority. Refuses ambiguous anchors.
"""
from pathlib import Path
import argparse, hashlib, json, re, shutil
ROOT=Path(__file__).resolve().parent

def replace_one(s, old, new):
    if s.count(old)!=1: raise ValueError('Source anchor changed; reconcile before assembly: '+old[:80])
    return s.replace(old,new,1)

def assemble(base, output, fragments=ROOT):
    base, output, fragments=Path(base),Path(output),Path(fragments)
    if output.exists(): raise ValueError('Choose a new output directory; existing work is preserved.')
    if base.is_symlink() or not base.is_file(): raise ValueError('Base must be a regular file.')
    s=base.read_text(encoding='utf-8')
    if 'id="ignition"' in s or 'window.FRONTIER_STUDIO=' in s: raise ValueError('Base is already assembled.')
    for anchor in ('window.FRONTIER_WORLD_LAB=', 'id="mission"', 'id="source-grid"'):
        if s.count(anchor)!=1: raise ValueError('Unrecognized World Lab source: '+anchor)
    s,n=re.subn(r'<title>[^<]*</title>','<title>FRONTIER Ω — Capturing the Exponential | IGNITION</title>',s,count=1)
    if n!=1: raise ValueError('Missing title')
    s,n=re.subn(r'<div class="heritage">.*?</div>','<div class="heritage"><b>BUILT IN MONTRÉAL</b><span></span><b>OPEN TO THE WORLD</b></div>',s,count=1)
    if n!=1: raise ValueError('Missing heritage block')
    story='<section class="story"><div class="story-track"><div><div class="era">The ambition</div><div class="year" style="font-size:32px">See what becomes possible.</div><p>Connect advancing intelligence to a company, an idea, or an outcome worth making real.</p></div><div class="divider">→</div><div><div class="era">The standard</div><div class="year" style="font-size:32px">Build what changes the answer.</div><p>Construct the missing means. Test the result. Keep what makes the next worthwhile possibility attainable.</p></div></div></section>'
    s,n=re.subn(r'<section class="story">.*?</section>',lambda _:story,s,count=1,flags=re.S)
    if n!=1: raise ValueError('Missing story block')
    s,n=re.subn(r'<br>2019:.*?<br>','<br>Construct the means. Expand what becomes possible. Preserve what helps the next construction.<br>',s,count=1)
    if n!=1: raise ValueError('Footer structure changed')
    s,n=re.subn(r"^\s*\['Institutional history[^\n]*\n",'',s,count=1,flags=re.M)
    if n!=1: raise ValueError('Source-list structure changed')
    s=replace_one(s,'FIRST PUBLIC EDITION','IGNITION CONSTRUCTION EDITION')
    s=replace_one(s,'Enter the Frontier Lab','Bring your ambition')
    s=replace_one(s,'href="#experiments">Witness the live experiments','href="#construction">Explore the construction studio')
    s=replace_one(s,'Three demonstrations.<br><span class="text-gold">Three different frontiers.</span>','Continue the investigation.<br><span class="text-gold">Three foundational experiments.</span>')
    css=(fragments/'studio.css').read_text()+(fragments/'ignition.css').read_text()
    header,separator,body=s.partition('</head>')
    if not separator: raise ValueError('Missing document head')
    s=replace_one(header,'</style>',css+'</style>')+separator+body
    anchor='<section class="science anchor" id="experiments">'
    s=replace_one(s,anchor,(fragments/'ignition.html').read_text()+(fragments/'studio.html').read_text()+anchor)
    head,tail=s.rsplit('</body>',1)
    s=head+''.join('<script>\n'+(fragments/name).read_text()+'\n</script>\n' for name in ('construction-core.js','studio-ui.js','ignition-ui.js'))+'</body>'+tail
    if s.count('id="ignition"')!=1 or 'Institutional history' in s: raise ValueError('Editorial check failed')
    s=s.replace("↗", "→")  # Preserve the existing publication typography rule.
    # No unrelated repository data, manuscripts, account files or credentials are copied.
    output.mkdir(parents=True)
    (output/'index.html').write_text(s,encoding='utf-8')
    allow=('construction-core.js','studio-ui.js','ignition-ui.js','studio.html','studio.css','ignition.html','ignition.css','independent_check.py','README.md','DEMO_SCRIPT.md','tests/test_construction.cjs','tests/test_browser.py','tests/test_ignition.py')
    for name in allow:
        p=fragments/name
        if p.is_symlink() or not p.is_file(): raise ValueError('Missing regular source fragment: '+name)
        dest=output/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    (output/'evidence').mkdir(exist_ok=True)
    manifest={'schema':'frontier/assembled-preview-v1','base_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'files':{str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()},'authority':[],'model_calls':0,'status':'assembled-not-yet-qualified'}
    (output/'ASSEMBLY.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();print(assemble(a.base,a.output))
