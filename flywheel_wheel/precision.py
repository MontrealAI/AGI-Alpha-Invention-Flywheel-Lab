"""A complete, uncropped engineering wheel; graphics never confer evidence or authority."""
from __future__ import annotations
import base64
import hashlib
import html
import math
from .readout import EvidenceError, canonical, empty_snapshot
from .preflight import fresh_output, write_new

CX, CY = 1400, 1510
GATES = ('PURPOSE', 'SCOPE', 'ACCEPTANCE', 'SETTLEMENT', 'LIQUIDITY', 'RIGHTS', 'LINEAGE', 'REVALIDATION')
SCRIPT = """(()=>{const names={all:['invention','evidence','incentives','assets','commerce','capital'],commerce:['evidence','assets','commerce','capital'],inheritance:['invention','evidence','assets','capital'],incentives:['evidence','incentives','commerce','capital']};const messages={all:'All six loops. Arrows represent dependencies, not automatic success.',commerce:'Voluntary order → current proof → accepted delivery → collection → obligations → available earnings. No invention prerequisite.',inheritance:'Construct → independently qualify → retain → fresh successor comparison. Better tools and better invention procedures are separate claims.',incentives:'Provision a bounded contract → perform specified work → independent adjudication → native authorization. A verifier is not rewarded for approving.'};document.querySelectorAll('button[data-path]').forEach(b=>b.addEventListener('click',()=>{const k=b.dataset.path;document.querySelectorAll('[data-ring]').forEach(g=>g.style.opacity=names[k].includes(g.dataset.ring)?'1':'.14');document.querySelectorAll('button[data-path]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));document.getElementById('route').textContent=messages[k];}));})();"""


def polar(r, a):
    a=math.radians(a)
    return CX+r*math.cos(a), CY+r*math.sin(a)


def arc(r, a, b, reverse=False):
    x,y=polar(r,a);u,v=polar(r,b)
    return f'M{x:.3f},{y:.3f} A{r},{r} 0 {int(abs(b-a)>180)} {int(not reverse)} {u:.3f},{v:.3f}'


def wedge(r, a, b):
    x,y=polar(r+42,a);u,v=polar(r+42,b);j,k=polar(r-42,b);m,n=polar(r-42,a)
    return f'M{x:.3f},{y:.3f} A{r+42},{r+42} 0 0 1 {u:.3f},{v:.3f} L{j:.3f},{k:.3f} A{r-42},{r-42} 0 0 0 {m:.3f},{n:.3f} Z'


def render_svg(rings=None):
    if rings is None:
        from .atlas import RINGS
        rings=RINGS
    if len(rings)!=6 or any(len(row[4])!=8 for row in rings):
        raise EvidenceError('SIX_RING_EIGHT_STAGE_ARCHITECTURE_REQUIRED')
    e=html.escape
    s=['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 2800 3040" role="img" aria-labelledby="title desc">',
       '<title id="title">AGI ALPHA — Transformational Intelligence Flywheel Harness</title>',
       '<desc id="desc">Full circular engineering architecture: six concentric loops, forty-eight stages, eight explicit gates. Invention, evidence, incentives, assets, commerce and capital surround an authorized purpose. Read-only architecture, not a record of achieved capability.</desc>',
       '<defs><radialGradient id="bg"><stop stop-color="#192640"/><stop offset="1" stop-color="#060C18"/></radialGradient><radialGradient id="core"><stop stop-color="#40375F"/><stop offset="1" stop-color="#121C31"/></radialGradient><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7" fill="#D9C793"/></marker><style>text{font-family:Arial,Helvetica,sans-serif}.caps{letter-spacing:3px}.micro{letter-spacing:2px}</style></defs>',
       '<rect width="2800" height="3040" fill="url(#bg)"/>',
       '<text x="1400" y="105" text-anchor="middle" fill="#E6D4AA" font-size="34" class="caps">AGI ALPHA</text>',
       '<text x="1400" y="181" text-anchor="middle" fill="#F4F3F8" font-size="62" font-weight="700" class="caps">FLYWHEEL HARNESS</text>',
       '<text x="1400" y="239" text-anchor="middle" fill="#C9B5E8" font-size="32" class="caps">TRANSFORMATIONAL INTELLIGENCE</text>',
       '<text x="1400" y="286" text-anchor="middle" fill="#B8C8DB" font-size="23">Invent the means · establish the evidence · retain the capability · finance the next construction</text>']
    for r in (248,268,378,398,508,528,638,658,768,788,898,918,1028,1048,1094,1118):
        s.append(f'<circle cx="{CX}" cy="{CY}" r="{r}" fill="none" stroke="#7991AE" stroke-opacity=".28" stroke-width="1"/>')
    for deg in range(0,360,2):
        x,y=polar(1095,deg);u,v=polar(1111 if deg%10==0 else 1102,deg)
        s.append(f'<path d="M{x:.2f} {y:.2f}L{u:.2f} {v:.2f}" stroke="#B8B38F" stroke-opacity=".6"/>')
    for i, gate in enumerate(GATES):
        deg=-90+i*45;x,y=polar(237,deg);u,v=polar(1075,deg)
        s.append(f'<path d="M{x:.2f} {y:.2f}L{u:.2f} {v:.2f}" stroke="#C1AD7E" stroke-width="2" stroke-opacity=".45"/>')
        for r in (388,518,648,778,908,1038):
            x,y=polar(r,deg)
            s.append(f'<path d="M{x-6:.2f} {y:.2f}L{x:.2f} {y-6:.2f}L{x+6:.2f} {y:.2f}L{x:.2f} {y+6:.2f}Z" fill="#E6D4AA"/>')
        x,y=polar(1152,deg)
        s.append(f'<rect x="{x-132:.2f}" y="{y-24:.2f}" width="264" height="48" rx="24" fill="#101C2D" stroke="#8C8163"/><text x="{x:.2f}" y="{y+8:.2f}" text-anchor="middle" fill="#E6D4AA" font-size="20" class="micro">{gate}</text>')
    for j,(name,label,color,_,phases,description) in enumerate(rings):
        r=323+j*130
        s.append(f'<g data-ring="{e(name)}" class="ring"><title>{e(label+": "+description)}</title>')
        for i,phase in enumerate(phases):
            a=-90+i*45+3.2;b=a+38.6;mid=(a+b)/2
            s.append(f'<path d="{wedge(r,a,b)}" fill="{color}" fill-opacity=".09" stroke="{color}" stroke-opacity=".7" stroke-width="1.6"/>')
            low=math.sin(math.radians(mid))>.05
            text_r=r+5 if low else r-5
            pid=f't-{j}-{i}'
            s.append(f'<path id="{pid}" d="{arc(text_r,b,a,True) if low else arc(text_r,a,b)}" fill="none"/>')
            s.append(f'<text fill="{color}" font-size="{20 if j==0 else 23}" font-weight="700" letter-spacing="1.5"><textPath xlink:href="#{pid}" startOffset="50%" text-anchor="middle">{e(phase)}</textPath></text>')
            x,y=polar(r-27,mid)
            s.append(f'<text x="{x:.2f}" y="{y+4:.2f}" text-anchor="middle" fill="{color}" font-size="11" opacity=".75">{j+1:02d}.{i+1:02d}</text>')
            s.append(f'<path d="{arc(r+33,a+3,a+11)}" fill="none" stroke="{color}" stroke-width="2" marker-end="url(#arrow)"/>')
            for k in range(5):
                x,y=polar(r+51,a+7+k*5);u,v=polar(r+56,a+7+k*5)
                s.append(f'<path d="M{x:.2f} {y:.2f}L{u:.2f} {v:.2f}" stroke="{color}" stroke-opacity=".45"/>')
        s.append('</g>')
    s.extend([f'<circle cx="{CX}" cy="{CY}" r="235" fill="url(#core)" stroke="#D4BC85" stroke-width="3"/>',
      f'<circle cx="{CX}" cy="{CY}" r="217" fill="none" stroke="#D5BCF0" stroke-opacity=".4"/>',
      f'<text x="{CX}" y="{CY-108}" text-anchor="middle" fill="#D7BD8A" font-size="20" class="caps">AUTHORIZED PURPOSE</text>',
      f'<text x="{CX}" y="{CY-40}" text-anchor="middle" fill="#FFFFFF" font-size="29" font-weight="700">TRANSFORMATIONAL</text>',
      f'<text x="{CX}" y="{CY+4}" text-anchor="middle" fill="#FFFFFF" font-size="37" font-weight="700">INTELLIGENCE</text>',
      f'<path d="M{CX-152} {CY+32}H{CX+152}" stroke="#8F80AF"/>',
      f'<text x="{CX}" y="{CY+75}" text-anchor="middle" fill="#D3CDE2" font-size="24">Change the means.</text>',
      f'<text x="{CX}" y="{CY+110}" text-anchor="middle" fill="#D3CDE2" font-size="24">Preserve the purpose.</text>',
      f'<text x="{CX}" y="{CY+160}" text-anchor="middle" fill="#B5C3D7" font-size="16">WORLD · POLICY · PROOF · AUTHORITY</text>'])
    for j,(name,label,color,*_) in enumerate(rings):
        x=160+(j%3)*850;y=2740+(j//3)*70
        s.append(f'<g data-ring="{e(name)}"><circle cx="{x}" cy="{y}" r="10" fill="{color}"/><text x="{x+28}" y="{y+9}" fill="{color}" font-size="27" font-weight="700">0{j+1}  {e(label)}</text></g>')
    s.extend(['<text x="1400" y="2910" text-anchor="middle" fill="#C2CFDD" font-size="24">PRODUCTIVE FRONTIER: ENERGY · SCIENCE · COMPUTE · MATERIALS · MANUFACTURING · INFRASTRUCTURE</text>',
      '<text x="1400" y="2962" text-anchor="middle" fill="#D8C298" font-size="24">PROOF ≠ AUTHORITY     ASSET VALUE ≠ CASH     FORECAST ≠ RECEIPT</text>',
      '<text x="1400" y="3007" text-anchor="middle" fill="#97AFC6" font-size="19">Architecture and research implementation. Financial execution, real commerce and physical deployment require separate qualification.</text></svg>'])
    return '\n'.join(s)


def render_html(svg):
    digest=base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    buttons=''.join(f'<button type="button" data-path="{key}" aria-pressed="{str(key=="all").lower()}">{name}</button>' for key,name in [('all','Complete wheel'),('commerce','Commercial cycle'),('inheritance','Inventive inheritance'),('incentives','Incentives and trust')])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none';style-src 'unsafe-inline';script-src 'sha256-{digest}';base-uri 'none';form-action 'none'"><title>AGI ALPHA — Precision Flywheel</title><style>body{{margin:0;background:#060c18;color:#dce6f1;font:17px/1.6 system-ui,sans-serif}}main{{max-width:1450px;margin:auto;padding:24px}}h1{{font-size:clamp(25px,4vw,46px);color:#ead7ac}}nav{{display:flex;flex-wrap:wrap;gap:12px}}button{{font:inherit;color:#e8d8f5;border:1px solid #7a7492;border-radius:8px;background:#15243b;padding:12px;cursor:pointer}}button[aria-pressed=true]{{border-color:#edd39d}}button:focus-visible{{outline:3px solid #d9b8ff;outline-offset:3px}}svg{{width:100%;height:auto}}aside{{padding:18px;border:1px solid #49566d;border-radius:8px}}@media print{{nav{{display:none}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto}}}}</style><main><h1>AGI ALPHA Flywheel Harness</h1><p>Six coupled loops. Every cross-loop transfer is a separate evidence and authorization question.</p><nav aria-label="Trace a causal route">{buttons}</nav><p id="route" role="status" aria-live="polite">All six loops. Arrows represent dependencies, not automatic success.</p>{svg}<aside><strong>What compounds:</strong> transferable capability, valid evidence, maintainable productive assets, customer relationships and actually available earned resources. <strong>What does not transfer automatically:</strong> current proof, permission, buyer demand, liquidity or a profitable margin. This interface only changes visual emphasis; it never sends commands, handles credentials, moves money or contacts customers.</aside></main><script>{SCRIPT}</script></html>'''


def publish(output, rings=None):
    target=fresh_output(output)
    svg=render_svg(rings)
    target.mkdir()
    write_new(target/'wheel.svg',svg.encode())
    write_new(target/'index.html',render_html(svg).encode())
    write_new(target/'snapshot.json',canonical(empty_snapshot())+b'\n')
    return {'scope':'ARCHITECTURE_ONLY_NO_ENTERPRISE_INPUT','output':str(target),'funding_authority':False}
