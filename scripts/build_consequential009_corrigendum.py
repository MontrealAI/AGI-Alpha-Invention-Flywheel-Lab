import argparse, hashlib, html, json, re, subprocess
from pathlib import Path
from pypdf import PdfReader, PdfWriter

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'evidence/consequential009/verifier/summary-gap-r1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def escape(s):
    mapping={'\\':r'\textbackslash{}','_':r'\_\allowbreak{}','%':r'\%','&':r'\&','$':r'\$','#':r'\#','{':r'\{','}':r'\}'}
    parts=[]
    for x in re.split('([0-9a-f]{40,64})',str(s)):
        if re.fullmatch('[0-9a-f]{40,64}',x):parts.append(r'\texttt{'+r'\allowbreak{}'.join(x[i:i+12] for i in range(0,len(x),12))+'}')
        else:parts.append(''.join(mapping.get(c,c) for c in x))
    return ''.join(parts)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-anchor',required=True);parser.add_argument('--output',default='docs/consequential009');args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',args.source_anchor):raise ValueError('IMMUTABLE_PUBLIC_PATCH_ANCHOR_REQUIRED')
    out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True);original=out/'paper.pdf';original_hash=sha(original)
    original_qa=read(ROOT/'evidence/consequential009/paper/PDF_QA.json')
    if original_hash!=original_qa['pdf_sha256']:raise ValueError('ORIGINAL_PAPER_CHANGED')
    review=read(BASE/'REPAIRED_REVIEW.json');inputs=[BASE/'COUNTEREXAMPLES.json',BASE/'REPAIRED_REVIEW.json',BASE/'REGRESSIONS.log',ROOT/'verification/consequential009/cohort_check.py',ROOT/'verification/consequential009/reference_check.py']
    counts={}; rows=[]
    for kind,label in [('cohort','Circuit report'),('reference','Reference report')]:
        entry=review['native_acceptance'][kind];receipt=ROOT/entry['path'];r=read(receipt)
        if sha(receipt)!=entry['sha256'] or not r['accepted'] or not all(c['passed'] for c in r['checks']):raise ValueError('NATIVE_REPAIR_RECEIPT_NOT_QUALIFIED')
        checker=ROOT/'verification/consequential009'/('cohort_check.py' if kind=='cohort' else 'reference_check.py')
        if sha(checker)!=entry['verifier_sha256']:raise ValueError('PATCHED_CHECKER_SOURCE_CHANGED')
        bad=BASE/kind/'forged-REPAIRED_ACCEPTANCE.json'
        if read(bad)['accepted'] is not False:raise ValueError('ORIGINAL_FORGED_WITNESS_NOT_REJECTED')
        inputs.extend([receipt,bad]);counts[kind]=len(r['checks']);rows.append([label,str(counts[kind])+'/'+str(counts[kind]),'Accepted','Rejected'])
    if not review['original_forged_reports_now_rejected']:raise ValueError('REPAIR_REVIEW_REFUSED')
    paragraphs=[
      'This corrects the validation scope of the accompanying nine-page study, When More Measurements Cannot Help. The original PDF and its 95-input scientific freeze remain unchanged. Its historical 131-check circuit receipt and 153-check reference receipt belong to their exact earlier checker editions; those passes are not transferred to the repaired validators.',
      'Configured review of public checkpoint 49838402 exposed a report-integrity defect. Both earlier validators could accept altered REPORT summary counts or completion flags while independently checked detailed plans and readouts remained correct. The reference validator could also accept forged summary claims of drift/high-noise success despite detailed records correctly requiring abstention. Exact counterexamples and original accepting receipts are preserved. No wrong numerical value was found in the actual native reports.',
      'The repair independently reconciles summary counts, acquisition costs, completion flags and stress decisions with recomputed plans and readouts. Candidate code, cohorts, measurements, thresholds and acceptance endpoints are unchanged. The original forged summaries are now rejected. Fresh native receipts from the repaired checker sources are reported below; eleven targeted regression methods also pass.',
      'The scientific and commercial conclusions are unchanged: conditional ideal-network enablement, parity with known complete methods, and no demonstrated physical calibration or after-cost discovery advantage. The nominal SIM USD 12.25 surplus and joint adverse SIM USD 87.75 loss remain authored conditional results. Qualified unrestricted simulated earnings remain zero; neither this integrity repair nor the additional reference instrument is claimed as earned-funded construction. Mission completion and live commerce remain unestablished.',
      'Public-source reproducibility is separately qualified: the published 49838402 paper builder was actually run without compilation on its downloaded source tree, using all 95 archive-aware inputs. All four generated text derivatives match the original final files byte-for-byte. This does not qualify a later patched runtime or release download; each requires its own source-matched receipt.'
    ]
    source_url='https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/'+args.source_anchor
    manifest={'schema':'consequential009-corrigendum-inputs/v1','patch_anchor':args.source_anchor,'original_paper_sha256':original_hash,'original_scientific_anchor':'326be47e40df57f868b1543e4d5385d490319cea','builder_qualification_source':'49838402a170f7c0447ca65fad97a37099a622ef','inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size} for p in inputs]}
    manifest_raw=json.dumps(manifest,indent=2,sort_keys=True)+'\n';(out/'CORRIGENDUM_SOURCE_MANIFEST.json').write_text(manifest_raw);manifest_hash=hashlib.sha256(manifest_raw.encode()).hexdigest()
    preamble=[r'\documentclass[10pt,letterpaper]{article}',r'\usepackage[margin=0.68in]{geometry}',r'\usepackage[T1]{fontenc}',r'\usepackage{lmodern,microtype,booktabs,array,xcolor,xurl}',r'\usepackage[colorlinks=true,urlcolor=blue]{hyperref}',r'\hypersetup{pdftitle={Postfreeze qualification corrigendum},pdfauthor={AGI ALPHA experimental engineering program}}',r'\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}',r'\setlength{\emergencystretch}{3em}',r'\pagestyle{empty}',r'\begin{document}',r'{\Large\sffamily\bfseries Postfreeze Qualification Corrigendum}\par',r'{\small AGI ALPHA Consequential009 / 30 October 2026}\par\vspace{5pt}\hrule\vspace{6pt}']
    parts=preamble+[escape(x)+r'\par' for x in paragraphs[:3]]
    parts += [r'\begin{center}\small\begin{tabular}{p{0.24\linewidth}p{0.19\linewidth}p{0.17\linewidth}p{0.18\linewidth}}\toprule Report & Fresh checks & Native artifact & Forged summary\\\midrule']
    parts += [' & '.join(escape(x) for x in row)+r'\\' for row in rows]
    parts += [r'\bottomrule\end{tabular}\end{center}']+[escape(x)+r'\par' for x in paragraphs[3:]]
    parts += [r'{\footnotesize\textbf{Patched public source:} \url{'+source_url+r'}\par',r'\textbf{Native receipts SHA256:} circuit '+escape(review['native_acceptance']['cohort']['sha256'])+r'; reference '+escape(review['native_acceptance']['reference']['sha256'])+r'.\par',r'\textbf{Original PDF SHA256:} '+escape(original_hash)+r'.\par',r'\textbf{Correction input-manifest SHA256:} '+escape(manifest_hash)+r'.\par}',r'\end{document}']
    (out/'corrigendum.tex').write_text('\n'.join(parts)+'\n')
    qa=ROOT/'evidence/consequential009/paper/corrigendum';qa.mkdir(parents=True,exist_ok=True)
    for n in (1,2):
        proc=subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','corrigendum.tex'],cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (qa/f'build-{n}.log').write_text(proc.stdout)
        if proc.returncode:raise RuntimeError('CORRIGENDUM_COMPILE_FAILED')
    correction=out/'corrigendum.pdf';reader=PdfReader(correction)
    if len(reader.pages)!=1:raise ValueError('CORRIGENDUM_MUST_BE_ONE_PAGE')
    writer=PdfWriter();writer.append(original);writer.append(correction);writer.add_metadata({'/Title':'When More Measurements Cannot Help - with qualification corrigendum','/Author':'AGI ALPHA experimental engineering program'})
    with (out/'paper-with-corrigendum.pdf').open('wb') as stream:writer.write(stream)
    if len(PdfReader(out/'paper-with-corrigendum.pdf').pages)!=10:raise ValueError('COMBINED_PAGE_COUNT')
    if sha(original)!=original_hash:raise ValueError('ORIGINAL_PAPER_WAS_MODIFIED')
    body=''.join('<p>'+html.escape(x)+'</p>' for x in paragraphs[:3])+'<table><tr><th>Report</th><th>Fresh checks</th><th>Native artifact</th><th>Forged summary</th></tr>'+''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</table>'+''.join('<p>'+html.escape(x)+'</p>' for x in paragraphs[3:])
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Postfreeze qualification corrigendum</title><style>body{font:18px/1.6 Georgia,serif;background:#edf2f5;color:#172e3b;margin:0}main{max-width:1000px;background:white;margin:auto;padding:48px}h1{font:700 32px/1.2 system-ui;color:#146b72}table{width:100%;border-collapse:collapse;font:15px/1.5 system-ui}th,td{padding:8px;border-bottom:1px solid #d6e0e6;text-align:left}.source{font:14px/1.5 monospace;overflow-wrap:anywhere}a{color:#1459a0}@media(max-width:650px){main{padding:24px}} </style><main><h1>Postfreeze Qualification Corrigendum</h1><p>AGI ALPHA Consequential009 ·30 October 2026</p>'+body+'<p class="source">Patched public source: <a href="'+source_url+'">'+args.source_anchor+'</a><br>Original PDF SHA256: '+original_hash+'<br>Input manifest SHA256: '+manifest_hash+'</p><p><a href="paper-with-corrigendum.pdf">Combined 10-page PDF</a> · <a href="corrigendum.pdf">One-page corrigendum</a> · <a href="index.html">Original reading edition</a></p></main></html>'
    (out/'corrigendum.html').write_text(page+'\n')
    original_html=(out/'index.html').read_text();banner='<aside class="status"><strong>Postfreeze qualification correction:</strong> earlier validators omitted some REPORT summary reconciliation. <a href="corrigendum.html">Read the verified correction</a> or <a href="paper-with-corrigendum.pdf">download the combined 10-page edition</a>. The original scientific freeze remains unchanged.</aside>'
    (out/'index-qualified.html').write_text(original_html.replace('<main>','<main>'+banner,1))
    result={'schema':'consequential009-corrigendum-build/v1','patch_anchor':args.source_anchor,'original_paper_unchanged':sha(original)==original_hash,'original_pdf_sha256':original_hash,'corrigendum_pdf_sha256':sha(correction),'combined_pdf_sha256':sha(out/'paper-with-corrigendum.pdf'),'original_pages':9,'corrigendum_pages':1,'combined_pages':10,'native_checks':counts,'source_manifest_sha256':manifest_hash,'html_derivative_origin_sha256':sha(out/'index.html'),'qualified_html_sha256':sha(out/'index-qualified.html'),'browser_render_of_new_derivative':'Not claimed by builder','complete_actual_monetary_cost':None}
    (qa/'BUILD.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
