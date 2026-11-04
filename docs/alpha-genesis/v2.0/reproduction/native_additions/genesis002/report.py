"""Read-only browser report. All untrusted text is escaped."""
from __future__ import annotations
import html
from pathlib import Path
from .common import read


def render(output):
    out=Path(output);r=read(out/'REPORT.json')
    esc=lambda x:html.escape(str(x),quote=True)
    money=lambda x:f'${x/100:,.2f}'
    rows=[]
    for i in range(r['cycles']):
        e=read(out/'episodes'/f'{i:06d}.json');d=read(out/'intents'/f'{i:06d}.json')['decision'];s=d['selected']
        rows.append('<tr><td>'+str(i+1)+'</td><td>'+esc(s['offer_id'] if s else 'Do not enter')+'</td><td>'+esc(s['method_id'] if s else '—')+'</td><td>'+esc(e['status'])+'</td><td>'+esc(e['funding']['funding'] if e['funding'] else '—')+'</td></tr>')
    research=r['research']['decision'] if r['research'] else 'No economically funded research trial'
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GENESIS Ω — Enterprise execution</title><style>
:root{color-scheme:dark;font-family:system-ui,sans-serif}body{margin:0;background:#120f1c;color:#f7f0e5}main{max-width:1100px;margin:auto;padding:50px 24px}h1{font-size:clamp(2rem,5vw,4rem);line-height:1.04;margin:16px 0}h2{font-size:1.3rem}.kicker{font-size:.78rem;letter-spacing:.16em;color:#dfbf80}.hero{max-width:800px;font-size:1.15rem;line-height:1.6}.scope{border:1px solid #b18b5a;padding:18px;background:#292133;border-radius:12px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin:28px 0}.card{padding:20px;border:1px solid #5b496e;border-radius:12px;background:#211a2e}.big{font-size:2rem;color:#e7c990}.small{font-size:.9rem;color:#d5cbe1;line-height:1.6}table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{text-align:left;padding:12px;border-bottom:1px solid #564762}.overflow{overflow-x:auto}a{color:#d9b9ff}footer{margin-top:40px;line-height:1.7}code{overflow-wrap:anywhere}.tag{color:#d4b1ff;font-weight:650}@media print{body{background:white;color:black}.card,.scope{background:white;color:black}.small,.big,.tag,a{color:black}main{padding:0}}</style></head><body><main>
<div class="kicker">TRANSFORMATIONAL INTELLIGENCE ∞ · EXECUTED ENGINEERING INCREMENT</div><h1>ALPHA GENESIS<br>FLYWHEEL Ω</h1><p class="hero">See the frontier. Choose the best complete means. Deliver, check, settle—and fund the next experiment only when resources and expected value justify it.</p>
<div class="scope"><strong>SIMULATION — NOT LIVE COMMERCE.</strong> Deterministic producers executed real code on synthetic records. Buyers, prices and cost envelopes are authored. No frontier-model call, actual revenue, physical breakthrough or general self-improvement is claimed.</div>
<div class="cards">'''+''.join(f'<div class="card"><div>{esc(label)}</div><div class="big">{esc(value)}</div><div class="small">{esc(note)}</div></div>' for label,value,note in [
    ('Accepted & settled',r['settled'],'Synthetic customer deliveries'),('Modeled collected revenue',money(r['modeled_revenue_cents']),'Not actual receipts'),('Modeled net result',money(r['modeled_profit_cents']),'After declared costs, tax provision and research'),('Real revenue','$0.00','No external financial activity')])+'''</div>
<h2>The complete execution path</h2><div class="overflow"><table><thead><tr><th>Cycle</th><th>Selected opportunity</th><th>Method</th><th>Result</th><th>Production funding</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<h2>Improve how the work is chosen</h2><p class="tag">'''+esc(research)+'''</p><p class="small">A candidate router is trained on one synthetic seed, frozen, then checked on another against the direct conventional constructor. A tie retains the simpler existing method. This is limited router selection, not an invented general discovery procedure.</p>
<h2>The three levels—actual status</h2><div class="cards"><div class="card"><strong>1. See the frontier</strong><p class="small">On-demand public-release observer; no credentials and no automatic capability promotion. Global coverage and continuous monitoring are not established.</p></div><div class="card"><strong>2. See the consequences</strong><p class="small">Finite declared offers and qualified adapters lead to actual source-bound production and native simulated settlement. Open-world opportunity invention remains unimplemented.</p></div><div class="card"><strong>3. Improve the machinery</strong><p class="small">Earned-funded router trial with a strong comparator. No superiority over the direct conventional route is inferred from a tie.</p></div></div>
<footer><a href="REPORT.json">Machine-readable result</a> · <a href="CONTRACT.json">Frozen contract</a> · <a href="QUALIFICATION.json">Method checks</a><p class="small">The authoritative accounts remain the existing JournalAccount and adaptive Account. Seed can still back permanent protection reserves. Do not upload private account directories or signing material. This local report is not a production application or a revenue claim.</p></footer></main></body></html>'''
