"""Local, escaped, script-free operating report. Not a hosted product claim."""
from html import escape


def render(audit, execution):
    cards = []
    for row in execution['rows']:
        picked = row['decision']['selected']
        title = escape(row['job_id'])
        detail = escape(picked['tool'] if picked else 'No economically admissible trade')
        funding = escape(row['resource_receipt']['funding'] if row['resource_receipt'] else 'Not funded')
        cards.append(f'<article><h3>{title}</h3><p>{detail}</p><p>Accepted: {row["accepted"]} · Funding: {funding}</p></article>')
    money = lambda n: f'${n / 1_000_000:,.2f}'
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ALPHA GENESIS Ω · Operating evidence</title><style>
:root{color-scheme:dark}body{margin:0;background:#14111d;color:#f4eee2;font:17px/1.65 system-ui}main{max-width:960px;margin:auto;padding:52px 24px}h1{font-size:clamp(2.3rem,6vw,4.6rem);line-height:1.04}h2{color:#dbbf86}.eyebrow{letter-spacing:.16em;color:#dbbf86;font-size:.8rem}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}article,.note{padding:20px;border:1px solid #544369;background:#211b2c;border-radius:16px}strong{color:#dbc2ff}a{color:#ddc8ff}.note{margin:24px 0}.number{font-size:2rem}.small{font-size:.85rem;color:#d0c7da}footer{margin-top:36px}</style><main>
<div class="eyebrow">TRANSFORMATIONAL INTELLIGENCE ∞ · EXECUTABLE RESEARCH</div><h1>ALPHA GENESIS<br>FLYWHEEL Ω</h1><p>See the frontier. Select the useful means. Deliver, verify and fund what comes next.</p>
<div class="note"><strong>NATIVE SIMULATION — not actual sales.</strong><br>Actual computational artifacts; authored buyer preferences, prices and complete-cost assumptions. No live model calls, customer contact or physical actuation.</div>
<div class="grid">''' + ''.join(f'<article><div class="small">{escape(label)}</div><div class="number">{escape(str(value))}</div></article>' for label, value in [
        ('Accepted and collected artifacts', audit['accepted_collected_deliveries']),
        ('Deliveries funded from earned surplus', audit['earned_funded_deliveries']),
        ('Modeled complete-history profit', money(audit['simulated_profit_microUSD']))]) + '</div><h2>What actually ran</h2><div class="grid">' + ''.join(cards) + '''</div><h2>Evidence, not a score</h2><p>This run does not establish a Blue Sky breakthrough, improved discovery or real commercial self-sustainability. A strong ordinary instrument remains in the portfolio and may win.</p><p><a href="AUDIT.json">Independent audit</a> · <a href="execution.json">Execution decisions</a> · <a href="native-export.json">Native financial evidence</a></p><footer class="small">Build the advantage that builds the next advantage. Publication of this report is not product deployment.</footer></main></html>'''
