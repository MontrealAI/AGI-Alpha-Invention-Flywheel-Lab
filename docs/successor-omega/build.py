#!/usr/bin/env python3
"""Build, validate and package only the SUCCESSOR OMEGA publication."""
from __future__ import annotations
import argparse, csv, hashlib, json, os, platform, re, shutil, subprocess, sys, zipfile
from pathlib import Path

SOURCE_FILES = ['paper.tex','references.bib','companion.py','test_companion.py',
                'PROTOCOL.md','README.md','CITATION.cff','reader.html','share.svg','build.py',
                'sections/institution.tex','sections/evidence.tex','sections/study.tex',
                'sections/frontier.tex','sections/appendix.tex','sections/review.tex',
                'sections/thesis.tex','qualification.py','uncertainty.py','test_review.py',
                'test_uncertainty.py','REVIEW_PROTOCOL.md','REVIEW.md']
EPOCH='1793747522'
REPO='https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
TAG='successor-omega-v1.1.0'

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path,value): Path(path).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def run(cmd,cwd,log,env=None):
    with Path(log).open('w') as out:
        p=subprocess.run(cmd,cwd=cwd,stdout=out,stderr=subprocess.STDOUT,env=env)
    if p.returncode:
        print(Path(log).read_text()[-14000:])
        raise RuntimeError('Command failed: '+str(cmd))

def physical():
    L=3.828e26; irradiance=1361.; f=1e-12; eta=.3; sigma=5.670374419e-8
    area=f*L/irradiance; heat=(1-eta)*f*L; emit=.9*sigma*300**4
    result={'scope':'Illustrative dimensional calculation, not a physical design',
            'nominal_solar_luminosity_W':L,'nominal_irradiance_W_m2':irradiance,
            'intercepted_fraction':f,'assumed_efficiency':eta,'intercepted_W':f*L,
            'useful_W':eta*f*L,'effective_collector_m2':area,
            'assumed_areal_mass_kg_m2':1,'collector_mass_kg':area,
            'assumed_emissivity':.9,'assumed_temperature_K':300,
            'conversion_waste_W':heat,'radiating_flux_W_m2':emit,
            'radiating_area_m2':heat/emit}
    assert 281000 < area/1e6 < 282000
    assert 6.47e11 < heat/emit < 6.49e11
    return result

def source_zip(work,output,extra):
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in sorted(SOURCE_FILES+extra):
            info=zipfile.ZipInfo(name,(2026,11,3,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,(work/name).read_bytes())

def integrate_site(here,output,record,reader):
    root=here.parents[1]; site=root/'docs/research'
    manifest_path=site/'publication-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    old={p['file']:digest(site/p['file']) for p in manifest['papers'] if p['file']!='successor-omega-v1.1.0.pdf'}
    shutil.copyfile(output/'SUCCESSOR_OMEGA.pdf',site/'successor-omega-v1.1.0.pdf')
    shutil.copyfile(output/'successor-omega-social.png',site/'successor-omega-v1.1.0-social.png')
    shutil.copyfile(here/'share.svg',site/'successor-omega-v1.1.0-card.svg')
    (site/'successor-omega.html').write_text(reader)
    item={'file':'successor-omega-v1.1.0.pdf','bytes':record['pdf_bytes'],'sha256':record['pdf_sha256']}
    manifest['papers']=[p for p in manifest['papers'] if p['file']!=item['file']]+[item]
    write_json(manifest_path,manifest)
    script=root/'scripts/build_research_site.py'; text=script.read_text()
    if "'successor-omega-v1.1.0.pdf'" not in text:
        text=text.replace('PAPERS = (',"PAPERS = (\n    'successor-omega-v1.1.0.pdf',",1)
        if "'successor-omega.html'" not in text:
            text=text.replace('PAGES = (',"PAGES = ('successor-omega.html', ",1)
        text=text.replace('ASSETS = (',"ASSETS = ('successor-omega-v1.1.0-card.svg', 'successor-omega-v1.1.0-social.png', ",1)
        script.write_text(text)
    tests=root/'tests/test_research_site.py'; text=tests.read_text()
    text=text.replace('self.assertEqual(len(site.PAPERS), 22)','self.assertEqual(len(site.PAPERS), 23)')
    # The stable reader URL remains a single page.
    tests.write_text(text)
    index=site/'index.html'; text=index.read_text()
    card=re.search(r'<article[^>]*id="successor-omega".*?</article>',text,re.S)
    if not card: raise ValueError('Existing SUCCESSOR reader card not found')
    revised=card.group().replace('1.0.0','1.1.0').replace('successor-omega.pdf','successor-omega-v1.1.0.pdf')
    text=text[:card.start()]+revised+text[card.end():];index.write_text(text)
    readme=site/'README.md'; text=readme.read_text()
    start=text.index('## SUCCESSOR Ω — The Institution That Compounds')
    end=text.find('\n## ',start+3)
    if end<0:end=len(text)
    part=text[start:end].replace('1.0.0','1.1.0').replace('successor-omega.pdf','successor-omega-v1.1.0.pdf')
    part+='\nReviewed edition 1.1.0 corrects a temporal authority defect and adds 96 exact unknown-schedule environments. Only one new case favors portability, with greater downside. The original [edition 1.0.0 PDF](successor-omega.pdf) and release are preserved.\n'
    readme.write_text(text[:start]+part+text[end:])
    for name,sha in old.items():
        if digest(site/name)!=sha:raise AssertionError('Earlier PDF changed: '+name)
    evidence=here/'evidence'; evidence.mkdir(exist_ok=True)
    for name in ['results.json','uncertainty.json','uncertainty16.json','physical.json','SOURCE_PDF_BINDING.json']:
        shutil.copyfile(output/'source'/name,evidence/name)

def build(args):
    here=Path(__file__).resolve().parent; output=args.output.resolve()
    if output.exists():raise ValueError('Output must be a new directory')
    output.mkdir(parents=True); work=output/'source'; work.mkdir()
    for name in SOURCE_FILES:
        target=work/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(here/name,target)
    env=os.environ.copy();env.update(SOURCE_DATE_EPOCH=EPOCH,FORCE_SOURCE_DATE='1',TZ='UTC')
    run([sys.executable,'-m','unittest','-v','test_companion','test_review','test_uncertainty'],work,output/'tests.log',env)
    if not re.search(r'Ran 62 tests in', (output/'tests.log').read_text()):
        raise AssertionError('Unexpected regression test count')
    run([sys.executable,'companion.py','--output','results.json'],work,output/'study.log',env)
    result=json.loads((work/'results.json').read_text()); main=result['main']; grid=result['grid_summary']
    assert [main[k]['terminal_cash'] for k in ('portable','no_portable','legacy','ordinary_equal_content')]==[330,300,292,330]
    assert grid=={'cases':162,'positive':19,'ties':143,'negative':0,'max_gain':61,'fixed_infeasible':108,'fixed_loses':43,'fixed_wins':11,'fixed_ties':0}
    for k,r in main.items():
        assert 100+r['collections']-r['outflows']==r['terminal_cash']
        assert all(x['pre_collection']>=20 for x in r['trace'])
    for horizon,name in [(8,'uncertainty.json'),(16,'uncertainty16.json')]:
        run([sys.executable,'uncertainty.py','--horizon',str(horizon),'--output',name],work,output/f'uncertainty-{horizon}.log',env)
    u8=json.loads((work/'uncertainty.json').read_text())
    u16=json.loads((work/'uncertainty16.json').read_text())
    assert u8['summary']=={'cases':48,'oracle_comparisons':96,'positive':0,'ties':48,'max_gain':'0'}
    assert u16['summary']=={'cases':48,'oracle_comparisons':96,'positive':1,'ties':47,'max_gain':'7468537859/536870912'}
    from fractions import Fraction
    riskrows=[]
    for x in u16['rows']:
        if x['opening_cash']==100 and x['failure']=='0':
            full=x['full'];control=x['without_portable']
            riskrows.append(f"{x['q']} & {float(Fraction(full['expected'])):.3f} & {float(Fraction(control['expected'])):.3f} & {float(Fraction(x['gain'])):.3f} & {full['min_terminal']} / {control['min_terminal']} "+r'\\')
    (work/'uncertainty_rows.tex').write_text('\n'.join(riskrows)+'\n')
    write_json(work/'physical.json',physical())
    (work/'generated.tex').write_text('% Generated by build.py from the exact companion.\n')
    with (work/'cash.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['t','portable','no_portable','legacy']);w.writerow([0,100,100,100])
        for i in range(16):w.writerow([i+1]+[main[k]['trace'][i]['closing'] for k in ('portable','no_portable','legacy')])
    names={'build_p':'Build P','run_p':'Deliver P','renew_p':'Renew P'}
    rows=[]
    for x in main['portable']['trace']:
        rows.append(f"{x['t']} & {names[x['action']]} & {x['opening']} & {x['paid']} & {x['collected']} & {x['closing']} "+r'\\')
    (work/'trace_rows.tex').write_text('\n'.join(rows)+'\n')
    tex=r'\pdfinfoomitdate=1\pdftrailerid{}\pdfsuppressptexinfo=15\input{paper.tex}'
    command=['pdflatex','-interaction=nonstopmode','-halt-on-error','-no-shell-escape','-jobname=paper',tex]
    run(command,work,output/'latex-1.log',env)
    bibtex=shutil.which('bibtex') or shutil.which('bibtex.original')
    if not bibtex:raise RuntimeError('BibTeX is required')
    run([bibtex,'paper'],work,output/'bibtex.log',env)
    run(command,work,output/'latex-2.log',env);run(command,work,output/'latex-3.log',env)
    log=(work/'paper.log').read_text(errors='replace')
    bad=[line for line in log.splitlines() if any(x in line for x in ['Overfull \\hbox','Overfull \\vbox','undefined references','undefined citations','Missing character:'])]
    write_json(output/'typesetting-warnings.json',bad)
    if bad:raise AssertionError('Typesetting qualification failed: '+str(bad))
    pdf=output/'SUCCESSOR_OMEGA.pdf';shutil.copyfile(work/'paper.pdf',pdf)
    info=subprocess.check_output(['pdfinfo',str(pdf)],text=True)
    pages=int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1))
    record={'schema':1,'edition':'1.1.0','title':'SUCCESSOR Omega: The Institution That Compounds',
            'pdf_sha256':digest(pdf),'pdf_bytes':pdf.stat().st_size,'pages':pages,
            'source_files':{n:digest(work/n) for n in sorted(SOURCE_FILES)},
            'generated_files':{n:digest(work/n) for n in ['results.json','physical.json','cash.csv','trace_rows.tex','generated.tex','uncertainty.json','uncertainty16.json','uncertainty_rows.tex']},
            'tests':62,'grid_cases':162,'grid_oracle_comparisons':324,
            'uncertainty_cases':96,'uncertainty_oracle_comparisons':192,'interval_assertions':671,
            'history_tree_comparisons':24,
            'scope':'Authored finite study and local logic witness; not market, ASI or physical evidence'}
    write_json(work/'SOURCE_PDF_BINDING.json',record);write_json(output/'SOURCE_PDF_BINDING.json',record)
    reader=(work/'reader.html').read_text().replace('@@PAGES@@',str(pages)).replace('@@SHA@@',record['pdf_sha256']).replace('@@BYTES@@',str(record['pdf_bytes']))
    assert '@@' not in reader
    (output/'successor-omega.html').write_text(reader)
    import cairosvg
    cairosvg.svg2png(url=str(work/'share.svg'),write_to=str(output/'successor-omega-social.png'))
    extra=['results.json','physical.json','cash.csv','trace_rows.tex','generated.tex','SOURCE_PDF_BINDING.json','uncertainty.json','uncertainty16.json','uncertainty_rows.tex']
    source_zip(work,output/'SUCCESSOR_OMEGA_SOURCE.zip',extra)
    write_json(output/'BUILD_ENVIRONMENT.json',{'python':platform.python_version(),'pdflatex':subprocess.check_output(['pdflatex','--version'],text=True).splitlines()[0],'bibtex':subprocess.check_output([bibtex,'--version'],text=True).splitlines()[0],'source_date_epoch':EPOCH})
    assets=['SUCCESSOR_OMEGA.pdf','SUCCESSOR_OMEGA_SOURCE.zip','SOURCE_PDF_BINDING.json']
    (output/'SHA256SUMS').write_text(''.join(digest(output/n)+'  '+n+'\n' for n in assets))
    if args.publish_site:integrate_site(here,output,record,reader)
    print(json.dumps(record,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--publish-site',action='store_true')
    build(p.parse_args())
