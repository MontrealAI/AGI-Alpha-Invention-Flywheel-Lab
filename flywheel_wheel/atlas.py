"""Six-ring causal/economic wheel. Visual structure does not confer claim or authority."""
from __future__ import annotations
import base64
import hashlib
import html
import math
from .readout import EvidenceError, SCHEMA, canonical, empty_snapshot

RINGS = (
    ('invention', 'INVENTION', '#BDA0FF', 230,
     ('OBSERVE', 'ANALOGIZE', 'REFRAME', 'SYNTHESIZE', 'COMPOSE', 'TEST', 'ABSTRACT', 'EVOLVE'),
     'Construct mechanisms, missing interfaces, strategies and better ways to construct them.'),
    ('evidence', 'EVIDENCE', '#69DCE8', 320,
     ('SCOPE', 'SOURCE', 'PROBE', 'CHALLENGE', 'CORRECT', 'CONFIRM', 'REVALIDATE', 'ARCHIVE'),
     'Current mission semantics and independent checks. Out-Reflect is conditional, not an oracle.'),
    ('incentives', 'INCENTIVES', '#F3C881', 410,
     ('CONTRACT', 'PROVISION', 'CONTRIBUTE', 'REVIEW', 'ADJUDICATE', 'SETTLE', 'REMEDY', 'REALIGN'),
     'Reward accepted work, completed review and adjudicated defects; never pay verifiers for approval.'),
    ('assets', 'ASSETS', '#83DFC0', 500,
     ('CONSTRUCT', 'QUALIFY', 'LICENSE', 'DEPLOY', 'MAINTAIN', 'MEASURE', 'RETIRE', 'ADAPT'),
     'Executable capabilities plus rights, dependencies and upkeep. Asset valuation is not available cash.'),
    ('commerce', 'COMMERCE', '#83B7FF', 590,
     ('NEED', 'OFFER', 'PRICE', 'ONBOARD', 'DELIVER', 'ACCEPT', 'COLLECT', 'RENEW'),
     'Voluntary buyer choice, autonomous delivery, remedies and collection. Optimize contribution, not win rate.'),
    ('capital', 'CAPITAL', '#FFAC89', 680,
     ('COLLECT', 'RECONCILE', 'PROTECT', 'PROVISION', 'CHOOSE', 'RESERVE', 'DEPLOY', 'RECOVER'),
     'The existing native account alone commits funds. Planning, forecasts and rewards create no money.'),
)
MECHANISMS = (
    ('Structural transfer', 'Map the causal structure, not surface vocabulary.'),
    ('Adversarial discovery', 'Verify consequential counterexamples and missing conditions.'),
    ('Strategic invention', 'Change the route instead of merely increasing resources.'),
    ('Problem transformation', 'Replace representations or remove unnecessary dependencies.'),
    ('Instrument invention', 'Construct a measurement that makes a decision answerable.'),
    ('Open-world reasoning', 'Neither explanation, insufficient evidence and stopping remain valid.'),
    ('Evidence construction', 'Challenge scope and bounded reference corruption without self-certification.'),
    ('Mechanism synthesis', 'Construct executable operations with typed preconditions and effects.'),
    ('Causal composition', 'Search sequence, branching, topology and feedback under bounded resources.'),
    ('Interface invention', 'Construct a missing connector between otherwise incompatible means.'),
    ('Generative abstraction', 'Package working composites as tools for constructing new tools.'),
    ('Qualified inheritance', 'Reuse structure; rebuild mission proof and obtain authority separately.'),
    ('Discovery improvement', 'Separate better starting tools from better invention procedures.'),
    ('Economic mechanism design', 'Align buyer value, truthful review and contributor incentives.'),
    ('Productive expansion', 'Finance and physically validate maintainable useful capacity.'),
)


def esc(value):
    return html.escape(str(value), quote=True)


def pt(radius, angle, cx=870, cy=920):
    a = math.radians(angle)
    return cx + radius * math.cos(a), cy + radius * math.sin(a)


def arc(radius, start, end, reverse=False):
    p, q = pt(radius, start), pt(radius, end)
    return f'M {p[0]:.2f} {p[1]:.2f} A {radius} {radius} 0 {int(abs(end-start)>180)} {0 if reverse else 1} {q[0]:.2f} {q[1]:.2f}'


def sector(inner, outer, start, end):
    a,b,c,d = pt(outer,start),pt(outer,end),pt(inner,end),pt(inner,start)
    return (f'M {a[0]:.2f} {a[1]:.2f} A {outer} {outer} 0 0 1 {b[0]:.2f} {b[1]:.2f} '
            f'L {c[0]:.2f} {c[1]:.2f} A {inner} {inner} 0 0 0 {d[0]:.2f} {d[1]:.2f} Z')


def check(snapshot):
    if type(snapshot) is not dict or snapshot.get('schema') != SCHEMA or snapshot.get('funding_authority') is not False:
        raise EvidenceError('READ_ONLY_SCOPED_SNAPSHOT_REQUIRED')


def render_svg(snapshot=None):
    snapshot = empty_snapshot() if snapshot is None else snapshot
    check(snapshot)
    s = ['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 2240 1800" role="img" aria-labelledby="atlas-title atlas-desc">',
         '<title id="atlas-title">AGI ALPHA: six concentric causal and economic flywheels</title>',
         '<desc id="atlas-desc">Transformational intelligence coordinates invention, evidence, incentives, assets, commerce and capital. Gates separate proof from authority and asset value from cash. This is an architecture, not proof of implemented self-improvement or wealth.</desc>',
         '<defs><radialGradient id="space"><stop stop-color="#152544"/><stop offset="1" stop-color="#070F20"/></radialGradient>',
         '<radialGradient id="hub"><stop stop-color="#3D315E"/><stop offset="1" stop-color="#121B31"/></radialGradient>',
         '<marker id="tip" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#CCD8ED"/></marker>',
         '<style>text{font-family:Arial,Helvetica,sans-serif} .faint{fill:#A6B7D0} .phase{font-size:17px;font-weight:700;letter-spacing:1.2px} .sub{font-size:15px;letter-spacing:1px}</style></defs>',
         '<rect width="2240" height="1800" fill="url(#space)"/>',
         '<text x="84" y="91" fill="#F4F2FF" font-size="48" font-weight="700" letter-spacing="3">AGI ALPHA</text>',
         '<text x="84" y="139" fill="#D1BEDF" font-size="29" letter-spacing="4">TRANSFORMATIONAL INTELLIGENCE FLYWHEEL HARNESS</text>',
         '<text x="84" y="180" class="faint" font-size="20">Invent better means. Establish what works. Finance qualified reuse. Expand useful production.</text>']
    for r in range(180, 761, 30):
        s.append(f'<circle cx="870" cy="920" r="{r}" fill="none" stroke="#627A99" stroke-opacity="0.10"/>')
    for deg in range(0,360,5):
        x,y=pt(750,deg);u,v=pt(765 if deg%30==0 else 756,deg)
        s.append(f'<path d="M{x:.2f},{y:.2f} L{u:.2f},{v:.2f}" stroke="#8FA4BF" stroke-opacity="0.5"/>')
    for deg in range(-90,270,45):
        a,b=pt(170,deg);c,d=pt(731,deg)
        s.append(f'<path d="M{a:.2f},{b:.2f} L{c:.2f},{d:.2f}" stroke="#A9BDD8" stroke-opacity="0.25" stroke-dasharray="3 9"/>')
    for name,label,color,radius,phases,description in RINGS:
        s.append(f'<g id="ring-{name}" class="ring" data-ring="{name}"><title>{esc(label+": "+description)}</title>')
        for i, phase in enumerate(phases):
            start=-90+i*45+3;end=start+39
            s.append(f'<path d="{sector(radius-34,radius+34,start,end)}" fill="{color}" fill-opacity="0.10" stroke="{color}" stroke-width="1.4" stroke-opacity="0.70"/>')
            mid=(start+end)/2
            bottom=math.sin(math.radians(mid))>0
            text_r=radius+5 if bottom else radius-5
            t0,t1=(end,start) if bottom else (start,end)
            pid=f'label-{name}-{i}'
            s.append(f'<path id="{pid}" d="{arc(text_r,t0,t1,bottom)}" fill="none"/>')
            s.append(f'<text class="phase" fill="{color}"><textPath xlink:href="#{pid}" startOffset="50%" text-anchor="middle">{esc(phase)}</textPath></text>')
            x,y=pt(radius-23,mid)
            s.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.7" fill="{color}" fill-opacity="0.7"/>')
        s.append(f'<path d="{arc(radius+40,-77,-57)}" fill="none" stroke="{color}" stroke-width="2" marker-end="url(#tip)"/>')
        s.append('</g>')
    # Deliberate cross-ring couplings, each separated by a visible checkpoint.
    for angle, caption in [(-90,'PURPOSE'),(-45,'SCOPE'),(0,'ACCEPTANCE'),(45,'SETTLEMENT'),(90,'LIQUIDITY'),(135,'RIGHTS'),(180,'LINEAGE'),(225,'REVALIDATION')]:
        x,y=pt(171,angle);u,v=pt(732,angle)
        s.append(f'<path d="M{x:.2f},{y:.2f} L{u:.2f},{v:.2f}" fill="none" stroke="#B5C7E1" stroke-opacity="0.28" stroke-dasharray="4 8"/>')
        gx,gy=pt(365,angle)
        s.append(f'<rect x="{gx-5:.2f}" y="{gy-5:.2f}" width="10" height="10" transform="rotate(45 {gx} {gy})" fill="#E9E2CB"/>')
        tx,ty=pt(740,angle)
        if angle == -90: ty = 209
        anchor='end' if math.cos(math.radians(angle))>.2 else 'start' if math.cos(math.radians(angle))<-.2 else 'middle'
        s.append(f'<text x="{tx:.2f}" y="{ty+5:.2f}" text-anchor="{anchor}" class="sub" fill="#D4DEEC">{caption}</text>')
    s.extend(['<circle cx="870" cy="920" r="165" fill="url(#hub)" stroke="#C5ACE5" stroke-width="2"/>',
              '<circle cx="870" cy="920" r="150" fill="none" stroke="#AB96D6" stroke-opacity="0.45"/>',
              '<text x="870" y="856" text-anchor="middle" fill="#E7DBFF" font-size="18" letter-spacing="3">GOVERNED HUB</text>',
              '<text x="870" y="897" text-anchor="middle" fill="#FFF" font-size="23" font-weight="700">TRANSFORMATIONAL</text>',
              '<text x="870" y="930" text-anchor="middle" fill="#FFF" font-size="27" font-weight="700">INTELLIGENCE</text>',
              '<path d="M780 950H960" stroke="#A78DC7"/>',
              '<text x="870" y="978" text-anchor="middle" class="faint" font-size="17">Preserve the purpose.</text>',
              '<text x="870" y="1004" text-anchor="middle" class="faint" font-size="17">Invent the means.</text>'])
    # Six independently selectable ring explanations.
    for i,(name,label,color,radius,phases,description) in enumerate(RINGS):
        y=290+i*177
        s.append(f'<g class="ring-card" data-ring="{name}"><rect x="1735" y="{y}" width="425" height="153" rx="15" fill="#111E33" stroke="{color}" stroke-opacity="0.45"/>')
        s.append(f'<circle cx="1766" cy="{y+34}" r="8" fill="{color}"/><text x="1792" y="{y+41}" fill="{color}" font-size="24" font-weight="700">{i+1:02d} / {label}</text>')
        import textwrap
        for j,line in enumerate(textwrap.wrap(description,43)):
            s.append(f'<text x="1758" y="{y+76+j*23}" fill="#D0DAE9" font-size="16">{esc(line)}</text>')
        s.append('</g>')
    s.extend(['<rect x="1735" y="1370" width="425" height="184" rx="15" fill="#142438" stroke="#5E8D8A"/>',
              '<text x="1758" y="1405" fill="#97E4C9" font-size="22" font-weight="700">PRODUCTIVE FRONTIER</text>',
              '<text x="1758" y="1444" fill="#D0DAE9" font-size="17">Energy / compute / manufacturing</text>',
              '<text x="1758" y="1472" fill="#D0DAE9" font-size="17">Science / materials / infrastructure</text>',
              '<text x="1758" y="1512" fill="#E6CB96" font-size="16">Physical validation required separately.</text>',
              '<rect x="85" y="1645" width="2075" height="106" rx="15" fill="#111E33" stroke="#3E5473"/>',
              '<text x="113" y="1682" fill="#E6D7B4" font-size="22" font-weight="700">PROOF IS NOT AUTHORITY  /  ASSET VALUE IS NOT CASH  /  A FORECAST IS NOT A RECEIPT</text>',
              f'<text x="113" y="1719" fill="#B1C1D6" font-size="18">Evidence scope: {esc(snapshot["scope"])}. No automatic payouts, new rights, or physical operations.</text>',
              '</svg>'])
    return '\n'.join(s)


SCRIPT = """(()=>{const all=[...document.querySelectorAll('[data-select]')];function select(id){document.querySelectorAll('svg .ring,svg .ring-card').forEach(e=>{e.style.opacity=id==='all'||e.dataset.ring===id?'1':'.18'});all.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.select===id)));document.getElementById('focus-state').textContent=id==='all'?'All six loops visible. This view grants no operating authority.':'Focus: '+id+'. Other rings remain part of the same governed system.';}all.forEach(b=>b.addEventListener('click',()=>select(b.dataset.select)));})();"""


def render_html(snapshot=None, svg=None):
    snapshot = empty_snapshot() if snapshot is None else snapshot
    check(snapshot)
    svg = render_svg(snapshot) if svg is None else svg
    token = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    buttons = '<button type="button" data-select="all" aria-pressed="true">All loops</button>'
    buttons += ''.join(f'<button type="button" data-select="{n}" aria-pressed="false">{esc(label.title())}</button>' for n,label,*_ in RINGS)
    mechanisms = ''.join(f'<tr><th scope="row">{i+1:02d} / {esc(n)}</th><td>{esc(d)}</td></tr>' for i,(n,d) in enumerate(MECHANISMS))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-{token}'; img-src data:; base-uri 'none'; form-action 'none'">
<title>AGI ALPHA | Transformational Intelligence Flywheel</title>
<style>:root{{color-scheme:dark}}body{{margin:0;background:#070f20;color:#e5eaf3;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1500px;margin:auto;padding:24px}}h1{{font-size:clamp(24px,4vw,42px);margin-bottom:8px}}p{{max-width:1050px}}nav{{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}}button{{font:inherit;color:#eee;background:#172840;border:1px solid #68809f;border-radius:8px;padding:8px 14px;cursor:pointer}}button[aria-pressed=true]{{border-color:#e5cb94;background:#343349}}button:focus-visible{{outline:3px solid #c6aaff;outline-offset:3px}}svg{{width:100%;height:auto;border:1px solid #344760;border-radius:18px}}.notice{{padding:16px;background:#172439;border-left:3px solid #c5a16b}}table{{border-collapse:collapse;width:100%;margin:20px 0}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #2d405a;vertical-align:top}}th{{width:32%}}code{{color:#c3b4f6}}details{{border:1px solid #32485f;padding:16px;margin:20px 0}}summary{{cursor:pointer;font-weight:bold}}footer{{margin-top:30px;color:#b4c4d8}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto}}}}@media print{{button{{display:none}}body{{print-color-adjust:exact}}}}</style></head>
<body><main><h1>AGI ALPHA Flywheel Harness</h1><p><strong>Transformational intelligence</strong> changes the means, representations and causal arrangements that make useful outcomes possible. The circular architecture separates capability, evidence, incentives, assets, commerce and capital so their benefits can reinforce each other without confusing their claims.</p>
<p class="notice"><strong>Read-only architecture.</strong> Scope: <code>{esc(snapshot['scope'])}</code>. The diagram is not proof of economic superiority, recursive self-improvement or physical productive expansion. No execution, investment, payment or permission is granted by this interface.</p>
<nav aria-label="Highlight a flywheel layer">{buttons}</nav><p id="focus-state" role="status" aria-live="polite">All six loops visible. This view grants no operating authority.</p>{svg}
<details open><summary>How the six loops couple</summary><p>An independently accepted capability can enter the asset inventory. Lawful reuse may improve a service; a voluntary buyer may accept and pay. After costs and obligations, the canonical account may authorize a new commitment. Incentive contracts reward defined work and verified contributions, while separate adjudication protects against rewarding favorable verdicts. Each arrow is a separately tested hypothesis or authorized action.</p><p>Preserve four mission objects: <strong>WORLD / POLICY / PROOF / AUTHORITY</strong>. A successor retains compatible structure and history, but starts with empty current proof and authority. Cross-ring plans must be rechecked against current native state.</p></details>
<h2>The 15 mechanism families</h2><table><caption>Mechanisms accumulated in the design, not a claim that every mechanism is autonomously implemented.</caption><tbody>{mechanisms}</tbody></table>
<h2>Implemented coupling boundary</h2><p><code>flywheel_wheel.coupling</code> filters declared asset qualifications, expiry, reuse rights and incentive contracts, compiles shared costs once, and calls the repository's existing <code>portfolio_scale.transformational.choose</code>. Its output is a state-bound, simulated planning proposal, never a second ledger or payment instruction. Completed checking is distinct from a favorable verdict; contingent reward caps consume proposed budget but are not automatically payable.</p>
<h2>Independent measures of progress</h2><p>Keep accepted output, complete cost, collected cash, available earned funds, successor benefit, discovery improvement and physical capacity separate. A conventional specialist may win. Unknown evidence or an unaffordable experiment must remain unresolved.</p>
<footer>Static local interface. No telemetry, network calls, credentials, account mutation or scheduling. All interactions only highlight parts of the wheel.</footer></main><script>{SCRIPT}</script></body></html>'''
