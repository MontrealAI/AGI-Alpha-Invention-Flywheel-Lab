"""Build the complete reading editions from executed, hash-bound evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/next009'
BASE='https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
EVIDENCE={
 'primary':'evidence/next009/verification/primary-confirmation/artifacts/ACCEPTANCE.json',
 'net3':'evidence/next009/numeric-edition/verification-v1/artifacts/NET3_NUMERIC_FEASIBILITY.json',
 'successor':'evidence/next009/verification/successor-primary-final-v2/artifacts/ACCEPTANCE.json',
 'commerce':'evidence/next009/commerce/net1-primary-final-v1/artifacts/COMMERCIAL.json',
 'audit':'evidence/next009/verification/commercial-audit/artifacts/AUDIT.json',
 'monitor_repair':'evidence/next009/verification/monitor-race-repair-v1/artifacts/REPORT.json',
 'failed_replay':'evidence/next009/reproduction/public-clean-r1/RECEIPT.json',
 'download_failure':'evidence/next009/reproduction/WHOLE_REPO_DOWNLOAD_FAILURE.json',
 'post_stop_inspection':'evidence/next009/reproduction/POST_FAILURE_PROCESS_INSPECTION.json',
}

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build(commit):
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('IMMUTABLE_EVIDENCE_COMMIT')
    read={k:json.loads((ROOT/v).read_bytes()) for k,v in EVIDENCE.items()}
    if not read['successor']['any_verified_model_successor_benefit'] or read['successor']['earned_funded_successor']:
        raise ValueError('PAPER_DECISION_INPUT_CHANGED')
    tracked=set(subprocess.check_output(['git','ls-tree','-r','--name-only',commit],cwd=ROOT,text=True).splitlines())
    archived={}
    for p in (ROOT/'evidence/next009/archives').glob('*.manifest.json'):
        for name in json.loads(p.read_bytes())['entries']:archived[name]=p.relative_to(ROOT).as_posix()
    def links(match):
        label,relative=match.group(1),match.group(2)
        path=(DOC/relative).resolve().relative_to(ROOT).as_posix()
        target=path if path in tracked else archived.get(path)
        if target is None:raise ValueError('UNPUBLISHED_READING_REFERENCE:'+path)
        return '['+label+']('+BASE+'/blob/'+commit+'/'+target+')'
    methods=(DOC/'methods.md').read_text().split('\n',1)[1]
    successor=(DOC/'successor.md').read_text()
    commerce=(DOC/'commerce-section.md').read_text()
    commerce=commerce.split('## Result and evidence scope',1)[1]
    commerce='## Commercial execution and evidence scope'+commerce
    commerce=commerce.split('| Claim | Defensible statement at this section',1)[0]
    commerce=commerce.replace('Joint demand/defect/warranty stress','Joint demand, defect and warranty stress')
    table=re.search(r'(?m)^\| Scenario \| Opening equity \|[^\n]+\n(?:\|[^\n]+\n)+',commerce)
    if table:
        rows=[[v.strip() for v in line.split('|')[1:-1]] for line in table.group(0).strip().splitlines()]
        halves=[]
        for columns in ([0,1,2,3],[0,4,5,6]):
            halves.append('\n'.join('| '+' | '.join(row[i] for i in columns)+' |' for row in rows)+'\n')
        commerce=commerce[:table.start()]+'\n'.join(halves)+commerce[table.end():]
    commerce=commerce.replace('## Reinvestment decision and integrated claim review','## Reinvestment policy and executed decision')
    discussion=(DOC/'discussion.md').read_text()
    abstract='''## Abstract

We construct and execute an observation-plan compiler that converts a reproduced information obstruction into a calibrated measurement program, then extends its retained rule to fresh work with bounded time-varying drift. On a source-pinned nine-source EPA model, a same-sensor reference removes an all-sensor uncalibrated ambiguity; a four-sensor plan survives every permitted erasure and passes 72 of 72 protected independent and actual-runtime cases. A separately declared 92-source numerical edition satisfies 108,836 pair/outage obligations while preserving its original raw range failure. On a prospectively frozen, previously uninspected 35-source model, drift-aware plans remove old-plan failures at all four nonzero declared drift bounds; 700 distinct latent worlds yield 2,100 successful matched-arm runtime evaluations. Retention, equal-content ordinary reuse, reset and conventional controls tie, so discovery superiority is not established. An artifact-bound simulated exchange and six frozen cashflow scenarios are executed. The base scenario yields CAD2,057.81 modeled profit and CAD1,557.81 conditional earned cash, but offer-specific demand, actual inference usage and complete costs remain unqualified. Qualified unrestricted earnings are zero, and the useful successor is research-funded. The result is verified finite-model technical enablement and reproducible conditional economics; the connected earned-funded commercial mission is incomplete.

**Evidence categories:** executed construction; procedurally independent verification; modeled economics; no actual commerce. **Scientific evidence source:** `COMMIT_TOKEN`. **Date:** 30 October 2026.
'''.replace('COMMIT_TOKEN',commit)
    body='\n\n'.join([abstract,methods,successor,commerce,discussion])
    body=re.sub(r'\[([^\]]+)\]\((\.\./\.\./[^)]+)\)',links,body)
    # Use Markdown dollar math consistently in both GitHub and Pandoc editions.
    body=body.replace('\\[','$$').replace('\\]','$$').replace('\\(','$').replace('\\)','$')
    title='AGI ALPHA: Verified Measurement Construction and Conditional Commercial Execution'
    header=f'''---
title: "{title}"
subtitle: "Finite-model enablement, a fresh drift-aware successor, and an uncompleted earned-funded flywheel"
author: "AGI ALPHA development team; prepared for Vincent Boucher"
date: "30 October 2026"
lang: en
---

'''
    figure_dir=DOC/'figures';figure_dir.mkdir(exist_ok=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    rows=read['successor']['all_drift_levels'];labels=[r['drift_bound_pp'] for r in rows]
    fig,axes=plt.subplots(1,2,figsize=(10,3.4),layout='constrained')
    axes[0].plot(range(5),[len(r['arms'][0]['selected_sensors']) for r in rows],marker='o',color='#155e75',linewidth=2,label='All revised arms and conventional control')
    axes[0].axhline(12,color='#64748b',linestyle='--',label='Old plan: 12 sensors')
    axes[0].set(xticks=range(5),xticklabels=labels,xlabel='Tested drift scenario\n(percentage points)',ylabel='Selected sensors',title='More capable information model; tied controls')
    axes[0].legend(fontsize=7,loc='upper left')
    failed=[r['old_plan']['failed_pair_count'] for r in rows]
    axes[1].bar(range(5),failed,color='#b45309',width=.65)
    for i,v in enumerate(failed):axes[1].text(i,v+.35,str(v),ha='center')
    axes[1].set(xticks=range(5),xticklabels=labels,xlabel='Tested drift scenario\n(percentage points)',ylabel='Old-plan failed pair obligations',title='Fresh unmet constraints are removed',ylim=(0,23))
    fig.savefig(figure_dir/'successor.png',dpi=220);fig.savefig(figure_dir/'successor.pdf');plt.close(fig)
    body=body.replace('Every revised plan passes the exact all-pair condition',
        '![All five frozen drift levels are retained. New plans pass every pair/outage check; all construction arms tie the conventional control. Source: successor acceptance receipt.](figures/successor.png)\n\nEvery revised plan passes the exact all-pair condition',1)
    markdown=header+body
    (DOC/'paper.md').write_text(markdown)
    # HTML is self-contained: data-embedded figure, inline CSS, MathML, no external JavaScript.
    css='''body{font:18px/1.65 system-ui,-apple-system,sans-serif;color:#172b3a;background:#fbfcfe;max-width:880px;margin:42px auto;padding:0 24px}h1,h2,h3{line-height:1.2;color:#123b50}h1{font-size:2.25rem}h2{margin-top:2.5rem;border-top:1px solid #dce5ec;padding-top:1.2rem}a{color:#126782}p{margin:1em 0}table{font-size:.82rem;line-height:1.45;border-collapse:collapse;width:100%;display:block;overflow-x:auto}th,td{padding:.55rem .65rem;border:1px solid #d4dfe7;vertical-align:top}th{background:#e8f0f6}code{font-size:.82em;overflow-wrap:anywhere}pre{padding:16px;background:#e8eff5;overflow:auto}img{max-width:100%;height:auto}figcaption{font-size:.85em;color:#475569}#TOC{font-size:.85em;padding:18px;background:#eef4f8}math{overflow-x:auto;max-width:100%}@media print{body{max-width:none;font-size:11pt}#TOC{break-after:page}h2{break-after:avoid}table{display:table;font-size:8pt}a{color:inherit}}'''
    (DOC/'reading.css').write_text(css)
    (DOC/'latex-header.tex').write_text('\\DeclareUnicodeCharacter{2212}{\\ensuremath{-}}\n\\usepackage{microtype}\n\\usepackage{longtable,booktabs,array}\n\\usepackage{xurl}\n\\AtBeginDocument{\\hypersetup{colorlinks=true,urlcolor=blue,linkcolor=black}}\n\\setlength{\\emergencystretch}{3em}\n\\setlength{\\LTpre}{0.5em}\n\\setlength{\\LTpost}{0.8em}\n')
    common=['pandoc','paper.md','--from','markdown+tex_math_dollars','--standalone','--toc','--toc-depth=2','--resource-path','.']
    subprocess.run(common+['--to','html5','--mathml','--self-contained','--css','reading.css','--metadata','title='+title,'--output','paper.html'],cwd=DOC,check=True)
    subprocess.run(common+['--to','latex','--variable','documentclass=article','--variable','fontsize=11pt','--variable','geometry=margin=0.85in','--variable','colorlinks=true','--include-in-header','latex-header.tex','--output','paper.tex'],cwd=DOC,check=True)
    tex=(DOC/'paper.tex').read_text()
    tex=re.sub(r'\\texttt\{([^{}]+)\}',lambda m: r'\nolinkurl{'+m.group(1).replace(r'\_', '_')+'}' if len(m.group(1))>35 else m.group(0),tex)
    (DOC/'paper.tex').write_text(tex)
    for _ in range(2):
        result=subprocess.run(['pdflatex','-no-shell-escape','-interaction=nonstopmode','-halt-on-error','paper.tex'],cwd=DOC,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (DOC/'latex-build.log').write_text(result.stdout)
        if result.returncode:raise RuntimeError('LATEX_FAILED; inspect docs/next009/latex-build.log')
    inputs=[*EVIDENCE.values(),'verification/next009/CONFIRMATION_FREEZE.json','verification/next009/SUCCESSOR_FREEZE.json',
            'campaign/next-009/ALLOCATION.json','campaign/next-009/OPPORTUNITIES.md','campaign/next-009/MODEL_EXECUTION.json',
            'research/next009/commerce/policy.json','research/next009/commerce/source_docket.json','research/next009/REPLAY_INPUTS.json',
            'docs/next009/methods.md','docs/next009/successor.md','docs/next009/commerce-section.md','docs/next009/discussion.md',
            'research/next009/build_paper.py','research/next009/resource_monitor009.py']
    evidence_inputs={p:digest(ROOT/p) for p in inputs}
    (DOC/'paper.inputs.json').write_text(json.dumps({'evidence_commit':commit,'files':evidence_inputs,'scope':'Executed evidence and authoring inputs; public link targets may be lossless archive indices for restored members.'},indent=2)+'\n')
    outputs=['paper.md','paper.tex','paper.pdf','paper.html','reading.css','latex-header.tex','figures/successor.png','figures/successor.pdf']
    build={'generated_utc':datetime.now(timezone.utc).isoformat(),'evidence_commit':commit,'inputs_sha256':digest(DOC/'paper.inputs.json'),
        'outputs':{p:digest(DOC/p) for p in outputs},'python':platform.python_version(),'matplotlib':matplotlib.__version__,
        'pandoc':subprocess.check_output(['pandoc','--version'],text=True).splitlines()[0],
        'pdf_engine':'pdflatex -no-shell-escape; two passes','visual_inspection':'PENDING_SEPARATE_QA',
        'scope':'Rendering does not upgrade scientific, commercial or release qualification.'}
    (DOC/'paper.build.json').write_text(json.dumps(build,indent=2)+'\n')
    print(json.dumps({'pdf':str(DOC/'paper.pdf'),'outputs':len(outputs),'words_approx':len(body.split())}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence-commit',required=True);a=p.parse_args();build(a.evidence_commit)
