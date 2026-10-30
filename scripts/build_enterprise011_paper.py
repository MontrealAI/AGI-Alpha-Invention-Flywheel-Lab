import argparse
import hashlib
import html
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run, out = Path(args.run), Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    report = json.loads((run/'REPORT.json').read_text())
    frozen = json.loads((run/'FROZEN.json').read_text())
    scale = json.loads((run/'SCALE.json').read_text())
    r, s = report['representative'], report['representative_ledger_summary']
    money = lambda n: f'${n/1_000_000:,.2f}'
    by_id = {x['id']: x for x in report['all_world_summaries']}
    def effect(control):
        diffs = [by_id[x['id'].removesuffix(control)+'strategic_autonomous']['summary']['profit'] - x['summary']['profit'] for x in report['controls'] if x['id'].endswith(control)]
        return money(sum(diffs)/len(diffs))
    rows = [(k, v['successful_runs'], v['runs'], f"{v['success_fraction']:.1%}", money(v['profit_microUSD']['mean']), f"{v['cash_survival_fraction']:.1%}") for k,v in report['regimes'].items()]
    md = ['# AGI ALPHA: a conditional commercial flywheel', '', 'Transformational intelligence | Enterprise-011 | 30 October 2026', '', report['conclusion'], '',
          f"The fixed-source experiment executed 96 distinct synthetic packets across three services and evaluated 188 prespecified trajectories. The central region passed {report['central_region']['successful_runs']}/{report['central_region']['runs']} trajectories. These are simulated customers and payments, with actual deterministic artifact production and separate acceptance checks.", '',
          '## Commercial result', '', '| Regime | Passed / runs | Success | Mean complete-cost profit | Cash survival |', '| --- | ---: | ---: | ---: | ---: |']
    md += [f'| {name} | {ok}/{n} | {fraction} | {profit} | {cash} |' for name,ok,n,fraction,profit,cash in rows]
    md += ['', 'Alternative trajectories are separate worlds; their receipts are never added into one business revenue figure.', '',
           'The first successful registered trajectory, rather than the best selected outcome, provides this example:', '',
           f"- Services: {', '.join(r['services_settled'])}; {r['paid_jobs']} settled jobs; {r['customers']} customers; {r['repeat_buyers']} repeat customers.",
           f"- Simulated collections {money(s['collections'])}; complete modeled costs {money(s['expenses'])}; profit {money(s['profit'])}; available earned funds {money(s['unrestrictedEarned'])}.",
           f"- {r['earned_funded_cycles']} profitable earned-funded cycles; consumed earned production/acquisition/support tranches {money(r['reinvested_earned'])}.",
           f"- Initial capital $5,000; seed-backed protection {money(s['equityProtectionBacking'])}; working reserve {money(s['workingCapital'])}; tail reserve {money(s['tailReserve'])}. Full seed repayment is not demonstrated.", '',
           '## Conditions and experiment', '',
           'Each of 24 cycles has at most four distinct work packets. Reconciliation covers 12 invoices, KPI reporting covers 10 metrics, and evidence matrices cover eight requirements. The corresponding authored human-effort assumptions are 0.65, 0.65 and 0.8 hours, with loaded hourly scenarios and external tools. Turnaround assumptions are separate from labor hours. No program runtime is treated as human labor.', '',
           'Baseline costs are $350 shared setup, $3 per selected attempt, $0.50 acquisition per slot and $0.50 one-time provider onboarding, plus bundle coordination, collection fees and a disclosed positive-profit tax provision. Every attempt and lost bid is costed. Billing is unavailable; these are conditional envelopes, not measured model invoices. No paid frontier-model API was called.', '',
           'Ordinary and differentiated segments assume recurring demand, overlapping provider/rival trust, and buyer value for 2-hour complete delivery versus a 24-hour rival SLA. Their urgency values are $0.50 and $1 per hour. Matched tests also vary utility/logit choice, responsive/lagged competitors, onboarding, fixed versus strategic prices, bundling and allocation. Public seller observations exclude private reservation values and budgets. Finite price search is a conditional heuristic, not a proven market equilibrium.', '',
           'Acceptance is derived from independently implemented arithmetic and provenance contracts. Native protected exchange events derive the cash ledger, expenses, settlement and reserves; investments require prior unrestricted earned funds. The earned-funded claim covers the reserved production/acquisition/support/coordination tranche. Other onboarding, fees and taxes remain separately charged; seed capital may continue protecting reserves.', '',
           '## Robustness and limits', '',
           'The source, costs, scenario families and thresholds were frozen before seeds 2610301101-2610301108. Primary coverage is 128 trajectories, with 60 matched-control and sensitivity trajectories. Setup upper-bound, attempt-cost bounds, half/double human hours, half arrivals and latency parity are executed separately. Four regime hypotheses are not an exhaustive forecast. Wilson intervals describe seeded simulator proportions and do not infer actual market demand.', '',
           f"Matched strategic pricing improves mean profit by {effect('fixed_autonomous')} over the fixed-price autonomous arm. Autonomous onboarding changes mean profit by {effect('strategic_original')}; dynamic allocation by {effect('strategic_fixed_allocation')}; bundling by {effect('strategic_no_bundle')}. These small controlled panels establish no universal onboarding or allocation advantage, and bundle gains vary in sign. Upper setup and half-arrival cases pass 0/4; latency parity passes 1/4. The conditional result depends on modest setup, recurring demand and valuable SLA differentiation.", '',
           'Development failures remain preserved. Before confirmation, workload timing was corrected and actual operation extended from 12 to 24 cycles to test recovery of setup through realized repeated work. Lost-bid production costs and public exposure probabilities were aligned in the pricing objective before the freeze.', '',
           'The separate 120-month scale projection models finite acquisition, retention, capacity, supplier constraints, costs, reserves and cash. Its initial $250,000 scale allocation, $400 work products and larger workload mix are new hypotheses, not an extrapolation financed by this small cohort. It reports censored nonattainment of $1B, $10B, $100B and $1T annual collected revenue rather than deriving growth time from customer arithmetic.', '',
           'A supplemental $25 earned-funded frontier experiment exercises inherited structural matching, bounded strategy synthesis, evidence-grounded repair and retained applicability. Equal-content ordinary reuse and the conventional control tie inheritance. No capability-compounding advantage or Blue Sky enablement is established. The prospective $30 avoided-rework valuation is an assumption and never enters income.', '',
           f"After this optional frontier allocation, complete modeled costs are {money(report['frontier']['after']['expenses'])} and profit/unrestricted earned funds are {money(report['frontier']['after']['profit'])}. The earlier commercial balance is a subtotal, not another independently spendable balance.", '',
           '## Separate verdicts', '', '| Evidence category | Verdict |', '| --- | --- |']
    md += [f'| {k.replace("_", " ")} | {v} |' for k,v in report['verdicts'].items()]
    md += ['', '## Reproduction and provenance', '', f"Exact implementation commit: `{frozen['git_commit']}`. Executable source digest: `{frozen['source']['sha256']}`. Freeze digest: `{frozen['freeze_sha256']}`.", '',
           'Install `requirements-commercial010.txt`; run `python3 -m enterprise run --output NEW_PATH`. Audit the committed run with `python3 -m enterprise audit --output RUN_PATH`. Extracted packages contain `source/`; use that directory for the same commands without Git. Confirmation replay is not another independent fresh sample.', '',
           'The source-bound run includes all inputs, deliveries, acceptance receipts, native event tapes, rejected probes, controls, sensitivities and scale trajectories. Actual customer outreach, real receipts and deployment were not performed. This engineering experiment supports the stated conditional simulation result only.', '',
           'Reference calibration: BLS Bookkeeping, Accounting, and Auditing Clerks (May 2025 hourly wage $24.36; updated August 2026), https://www.bls.gov/ooh/office-and-administrative-support/bookkeeping-accounting-and-auditing-clerks.htm ; BLS ECEC June 2026 (private wages $32.82, total compensation $46.89; released 9 September 2026), https://www.bls.gov/ecec/ . These references calibrate wage proxies, not task times, selling prices or demand.']
    text = '\n'.join(md)+'\n'
    (out/'enterprise-011.md').write_text(text)
    blocks, table = [], False
    for line in md:
        if line.startswith('|'):
            cells = [html.escape(x.strip()) for x in line.strip('|').split('|')]
            if all(set(c) <= set('-: ') for c in cells):
                continue
            if not table:
                blocks.append('<table>'); table = True
                blocks.append('<tr>'+''.join('<th>'+c+'</th>' for c in cells)+'</tr>')
            else:
                blocks.append('<tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr>')
            continue
        if table:
            blocks.append('</table>'); table = False
        if line.startswith('## '):
            blocks.append('<h2>'+html.escape(line[3:])+'</h2>')
        elif line.startswith('# '):
            blocks.append('<h1>'+html.escape(line[2:])+'</h1>')
        elif line:
            blocks.append('<p>'+html.escape(line.removeprefix('- '))+'</p>')
    if table:
        blocks.append('</table>')
    (out/'enterprise-011.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>AGI ALPHA enterprise-011</title><style>body{max-width:980px;margin:48px auto;padding:0 28px;font:17px/1.65 system-ui;color:#172d38;overflow-wrap:anywhere}h1,h2{color:#075e68}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{padding:10px;border-bottom:1px solid #ccd8dc;text-align:left}th{background:#eef5f6}</style>'+''.join(blocks))
    def tex_escape(value):
        return str(value).translate(str.maketrans({'\\': r'\textbackslash{}','&': r'\&','%': r'\%','$': r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}'}))
    paragraphs = []
    in_table = False
    for line in md:
        if line.startswith('Transformational intelligence |'):
            continue
        if line.startswith('|'):
            continue
        if line.startswith('# '):
            continue
        if line.startswith('## '):
            paragraphs.append('\\section*{'+tex_escape(line[3:])+'}')
            if line == '## Commercial result':
                paragraphs.append(r'\begin{center}\small\begin{tabular}{lrrr}\toprule Regime & Passed & Mean profit & Survival \\\midrule')
                paragraphs += [tex_escape(name.replace('_',' '))+' & '+f'{ok}/{n}'+' & '+tex_escape(profit)+' & '+tex_escape(cash)+r' \\' for name,ok,n,fraction,profit,cash in rows]
                paragraphs.append(r'\bottomrule\end{tabular}\end{center}')
            if line == '## Separate verdicts':
                paragraphs += [r'\textbf{'+tex_escape(k.replace('_',' '))+r':} '+tex_escape(v)+r'\par' for k,v in report['verdicts'].items()]
        elif line.startswith('Exact implementation commit:'):
            paragraphs.append(r'{\footnotesize Implementation commit: \texttt{'+frozen['git_commit']+r'}\\ Executable source: \texttt{'+frozen['source']['sha256']+r'}\\ Full freeze, protocol and paper bindings: enterprise-011.inputs.json.\par}')
        elif line:
            paragraphs.append(tex_escape(line.removeprefix('- ')).replace('`','')+'\n')
    tex = r'''\documentclass[10pt]{article}
\usepackage[margin=0.7in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern,booktabs,xcolor,microtype}
\usepackage[hidelinks]{hyperref}
\definecolor{accent}{HTML}{075E68}
\setlength{\parindent}{0pt}\setlength{\parskip}{4.5pt}
\hypersetup{pdftitle={AGI ALPHA: a conditional commercial flywheel},pdfauthor={AGI ALPHA}}
\begin{document}
{\LARGE\bfseries\color{accent} AGI ALPHA\\[4pt] A conditional commercial flywheel}\par
{\large Transformational intelligence}\par
Enterprise-011 \hfill 30 October 2026\par\medskip
'''+ '\n'.join(paragraphs)+ '\n\\end{document}\n'
    (out/'enterprise-011.tex').write_text(tex)
    subprocess.run(['pdflatex','-no-shell-escape','-interaction=nonstopmode','-halt-on-error','enterprise-011.tex'],cwd=out,check=True,stdout=subprocess.DEVNULL)
    bindings = {'source_commit': frozen['git_commit'], 'source_sha256': frozen['source']['sha256'], 'freeze_sha256': frozen['freeze_sha256'], 'report_sha256': hashlib.sha256((run/'REPORT.json').read_bytes()).hexdigest(), 'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('enterprise-011.*') if p.suffix in {'.pdf','.tex','.md','.html'}}}
    (out/'enterprise-011.inputs.json').write_text(json.dumps(bindings,indent=2)+'\n')


if __name__ == '__main__':
    main()
