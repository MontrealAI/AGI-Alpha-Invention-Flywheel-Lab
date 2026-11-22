"""Export an inspectable digital construction and separate qualification status."""
from __future__ import annotations
import csv
import hashlib
import html
import json
import math
from pathlib import Path
import time
from .model import read, validate, construct, canonical, digest
from .check import check, homogeneous_obstruction


def save(path, obj):
    with Path(path).open('xb') as f:
        f.write(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False).encode()+b'\n')


def layout(s, design):
    count=sum(x['count'] for x in design['contacts'])
    side=math.ceil(math.sqrt(count)); pitch=s['pitch_mm']
    # Spatially distribute the smaller family rather than create a dense cluster.
    expanded=[(x['family'],x['height_mm']) for x in design['contacts'] for _ in range(x['count'])]
    positions=[]
    for i,(fid,h) in enumerate(expanded):
        # Use a bijective serpentine placement, independent of the physical model.
        row=i//side; col=i%side if row%2==0 else side-1-i%side
        positions.append({'family':fid,'height_mm':h,'x_mm':(col+.5)*pitch,'y_mm':(row+.5)*pitch})
    return {'width_mm':side*pitch,'depth_mm':side*pitch,'sites':positions}


def scad(s, g):
    lookup={f['id']:f for f in s['families']}
    b=s['base_thickness_mm'];w=g['width_mm'];d=g['depth_mm']
    lines=['// GENESIS digital research coupon. Units: mm. NOT physically qualified.',
           '// One geometry does NOT manufacture the required distinct contact families.',
           '// Site family/material assignments are preserved in layout.json.', '$fn=64;', 'union() {',
           f'  cube([{w:.12g},{d:.12g},{b:.12g}]);']
    for site in g['sites']:
        r=lookup[site['family']]['radius_mm'];h=site['height_mm'];x=site['x_mm'];y=site['y_mm']
        lines.extend([f'  // family {site["family"]!r}', '  intersection() {',
          f'    translate([{x:.12g},{y:.12g},{b+h-r:.12g}]) sphere(r={r:.12g});',
          f'    translate([{x-r:.12g},{y-r:.12g},{b-0.001:.12g}]) cube([{2*r:.12g},{2*r:.12g},{h+0.002:.12g}]);',
          '  }'])
    return '\n'.join(lines+['}'])+'\n'


def drawing(s, g):
    scale=18; pad=30;w=g['width_mm']*scale;d=g['depth_mm']*scale
    look={f['id']:f for f in s['families']}
    rows=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w+2*pad} {d+2*pad}">',
          f'<rect x="{pad}" y="{pad}" width="{w}" height="{d}" fill="none" stroke="currentColor"/>']
    for i,p in enumerate(g['sites']):
        r=look[p['family']]['radius_mm']; h=p['height_mm']; cap=math.sqrt(2*r*h-h*h)
        x=pad+p['x_mm']*scale;y=pad+p['y_mm']*scale
        rows.append(f'<circle cx="{x}" cy="{y}" r="{cap*scale}" fill="none" stroke="currentColor"><title>{html.escape(p["family"])}; height {h} mm</title></circle>')
        rows.append(f'<text x="{x}" y="{y-12}" text-anchor="middle" font-size="8" fill="currentColor">{i+1}</text>')
    return '\n'.join(rows+['</svg>'])


def test_plan(s, verdict):
    return '''# Physical acceptance plan — not executed

This package contains an analytic geometry and a contact-family placement map.
A single-material 3D print does not reproduce the distinct calibration families.
No purchase, instrument control, human-use device or customer delivery is authorized.

1. Establish whether both declared contact families can be produced on one base.
   Measure topography, radii, heights, modulus and effective static/dynamic shear
   response. Do not substitute nominal batch fits for same-coupon calibration.
2. Freeze a new physical protocol before measurements. Compare separate family
   coupons, the proposed mixed coupon, and the strongest complete conventional
   alternative with equal construction freedom. Include interactions and wear.
3. Measure normal, static and dynamic force at every registered indentation with
   traceable uncertainty, independent repeats and randomized order. Record both
   accepted and failed coupons. Include calibration/model discrepancy, load-rate,
   temperature, contact preparation and possible hysteresis.
4. Require simultaneous support for all target intervals and the intended end-use
   outcome. Fit parameters on development coupons; confirm on new coupons and
   operating conditions not used to select geometry or tune the thresholds.
5. Physical fit is not commercial acceptance: establish a voluntary buyer, its
   best complete alternative, fabrication/support obligations, complete cost,
   permission to operate and collected payment before reporting actual commerce.

## Immediate decision

Current parameter-box sensitivity does not establish the requested behavior.
Recalibrate / investigate transfer before fabrication for use. The parameter boxes
are stress assumptions derived from marginal published-data fits, not a calibrated
joint confidence region and not a prediction interval for a mixed surface. This
stress test does not include modulus, geometry, interactions, wear or discrepancy.

## Successor hypothesis — untested

Use the independently qualified family-calibration and geometry constructor on a
new static/dynamic specification. Compare a control allowed to build the same
means, counting discovery, calibration, upkeep and transfer. More designs alone
are not evidence that the method of invention improved.
'''


def report_page(s, report):
    v=report['independent_check'];rows=''
    for r in v.get('rows',[]):
        rows += '<tr>'+''.join(f'<td>{r[k]:.6g}</td>' for k in ('indentation_mm','normal_N','static_N','dynamic_N','ratio'))+'</tr>'
    status='Nominal model passes' if v['accepted'] else 'No accepted numerical construction'
    geom='<img src="layout.svg" alt="Numbered contact placement map" style="width:100%;max-height:430px;background:#f7f3e9">' if v['accepted'] else ''
    source=html.escape(s['source']['url'],quote=True)
    downloads=('<a href="surface.scad" download>Editable CAD (.scad)</a><a href="layout.json" download>Contact / family map</a><a href="response.csv" download>Calculated responses</a>' if v['accepted'] else '')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GENESIS · A question becomes a construction</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#12101c;color:#f5f0e7;font:17px/1.6 system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:40px 22px}}h1{{font-size:clamp(32px,6vw,64px);line-height:1.05;letter-spacing:-2px}}h2{{line-height:1.25}}a{{color:#efc87c}}.eyebrow{{color:#efc87c;letter-spacing:3px;font-size:12px}}.lead{{font-size:23px;max-width:850px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}}.card{{padding:24px;background:#201c2c;border:1px solid #504257;border-radius:14px;margin:20px 0}}.tag{{display:inline-block;border:1px solid #967448;padding:6px 12px;border-radius:22px;margin:4px;font-size:13px}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:15px}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #554960}}code{{font-size:14px;word-break:break-word}}.muted{{color:#c7bbcd}}.links a{{display:inline-block;margin:7px 18px 7px 0}}footer{{margin-top:50px;border-top:1px solid #504257;padding-top:20px;font-size:14px}}
</style></head><body><main>
<div class="eyebrow">MONTREAL.AI · QUEBEC.AI · RESEARCH CONSTRUCTION</div>
<h1>ALPHA GENESIS<br>From possibility to artifact.</h1>
<p class="lead">A designed contact surface whose predicted hold-to-slide ratio changes with indentation—rather than remaining fixed by one contact family.</p>
<div class="tag">{status}</div><div class="tag">Physical qualification: NOT ESTABLISHED</div><div class="tag">Commercial qualification: NOT ESTABLISHED</div>
<div class="grid"><section class="card"><h2>What was constructed</h2><p>{v.get('contacts',0)} contacts selected by an ordinary integer optimizer. Editable CAD, exact site assignments, a scalar numerical check, and a physical acceptance plan.</p><p>Design targets are a research specification, not an observed customer requirement.</p></section>
<section class="card"><h2>The important result</h2><p>Nominal feasibility is separate from robustness. The published-fit sensitivity boxes do not justify this design's requested physical behavior.</p><p><strong>Decision: investigate calibration and transfer. Do not claim a qualified product.</strong></p></section></div>
<div class="links">{downloads}<a href="PHYSICAL_TEST_PLAN.md">Physical test plan</a><a href="REPORT.json">All evidence</a></div>
<section class="card"><h2>Inspect the construction</h2>{geom}<p class="muted">Geometry alone cannot reproduce different material or surface-conditioning families. The mesh is not a validated material recipe.</p></section>
<section class="card"><h2>Independent numerical reconstruction</h2><div class="scroll"><table><thead><tr><th>Indentation (mm)</th><th>Normal (N)</th><th>Static (N)</th><th>Dynamic (N)</th><th>Static/dynamic</th></tr></thead><tbody>{rows}</tbody></table></div><p class="muted">Calculated from the stated independent-contact model. No new physical measurement was made.</p></section>
<div class="grid"><section class="card"><h2>Compare fairly</h2><p>A fixed single-family shear ratio cannot meet the two disjoint ratio intervals. An ordinary mixed-family constructor is allowed the same operations; the solver used here is that conventional method. No GENESIS algorithmic superiority is claimed.</p></section><section class="card"><h2>Source → consequence → test</h2><p>The <a href="{source}">pinned public prerequisite study</a> supplies nominal coefficients and unresolved calibration evidence. GENESIS constructs an explicit digital candidate and preserves the uncertainty rather than converting a fit into a sale.</p></section></div>
<footer>Actual revenue: $0. No financial account, physical device, external agent or credentials touched. This is one executable research capability—not a self-sustaining enterprise or a general autonomous inventor. Source, input and output identities are recorded in MANIFEST.json.</footer></main></body></html>'''


def build(request_path, output):
    s=validate(read(request_path)); out=Path(output).absolute()
    if any(p.is_symlink() for p in (out,*out.parents)):
        raise ValueError('symlink output ancestry')
    out.mkdir(parents=True,exist_ok=False)
    save(out/'request.json',s)
    started=time.perf_counter();cpu=time.process_time()
    candidate=construct(s); verdict=check(s,candidate)
    controls=[]
    for family in s['families']:
        c=construct(s,family['id']);controls.append({'family':family['id'],'candidate':c,'check':check(s,c)})
    report={'schema':'genesis/surface-report/v1','scope':'ACTUAL_DIGITAL_CONSTRUCTION_CONDITIONAL_PHYSICAL_MODEL',
            'request_sha256':digest(s),'candidate':candidate,'independent_check':verdict,
            'single_family_controls':controls,'homogeneous_obstruction':homogeneous_obstruction(s),
            'strong_complete_control':'Same unrestricted conventional mixed-integer constructor is the selected means; not a weaker competitor.',
            'actual_revenue_USD':0,'physical_measurements_made':False,'autonomous_discovery_claim':False,
            'release_decision':'HOLD_PHYSICAL_CALIBRATION_AND_BUYER_EVIDENCE',
            'wall_seconds':time.perf_counter()-started,'cpu_seconds':time.process_time()-cpu,
            'monetary_cost':None,'telemetry_scope':'This process construction and checking; excludes frontier reasoning, source retrieval, CAD rendering, host dollars and physical work.'}
    save(out/'REPORT.json',report)
    save(out/'design.json',candidate)
    if verdict['accepted']:
        g=layout(s,candidate);save(out/'layout.json',g)
        (out/'surface.scad').write_text(scad(s,g),encoding='utf-8')
        (out/'layout.svg').write_text(drawing(s,g),encoding='utf-8')
        with (out/'response.csv').open('x',newline='') as f:
            cols=['indentation_mm','normal_N','static_N','dynamic_N','ratio']
            writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader()
            writer.writerows({k:r[k] for k in cols} for r in verdict['rows'])
    (out/'PHYSICAL_TEST_PLAN.md').write_text(test_plan(s,verdict),encoding='utf-8')
    (out/'OPEN_ME.html').write_text(report_page(s,report),encoding='utf-8')
    source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))}
    outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    save(out/'MANIFEST.json',{'source_sha256':source,'output_sha256':outputs,
                            'scope':'Byte identity only; not semantic truth or physical qualification.'})
    return report


def audit(output):
    out=Path(output).absolute()
    if any(p.is_symlink() for p in (out,*out.parents)):
        raise ValueError('symlink output ancestry')
    m=read(out/'MANIFEST.json')
    if set(m)!={'source_sha256','output_sha256','scope'}:
        raise ValueError('manifest schema')
    for name,expected in m['output_sha256'].items():
        p=out/name
        if Path(name).name != name or p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise ValueError('output identity changed: '+name)
    source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))}
    if source != m['source_sha256']:raise ValueError('executing source changed')
    s=validate(read(out/'request.json'));r=read(out/'REPORT.json');d=read(out/'design.json')
    if d!=r['candidate'] or check(s,d)!=r['independent_check']:
        raise ValueError('independent reconstruction differs')
    if r.get('scope')!='ACTUAL_DIGITAL_CONSTRUCTION_CONDITIONAL_PHYSICAL_MODEL':
        raise ValueError('scope changed')
    if r.get('release_decision') != 'HOLD_PHYSICAL_CALIBRATION_AND_BUYER_EVIDENCE':
        raise ValueError('unsupported release decision')
    if r.get('homogeneous_obstruction') != homogeneous_obstruction(s):
        raise ValueError('obstruction claim changed')
    controls=r.get('single_family_controls')
    if not isinstance(controls,list) or len(controls)!=len(s['families']):
        raise ValueError('missing comparator')
    for f,c in zip(s['families'],controls):
        if c['family']!=f['id'] or c['candidate']['family_restriction']!=f['id'] or check(s,c['candidate'])!=c['check']:
            raise ValueError('comparator binding')
    if r['actual_revenue_USD'] != 0 or r['physical_measurements_made'] is not False or r['autonomous_discovery_claim'] is not False:
        raise ValueError('unsupported claim')
    if r['independent_check']['accepted']:
        g=layout(s,d)
        if g!=read(out/'layout.json') or scad(s,g)!=(out/'surface.scad').read_text() or drawing(s,g)!=(out/'layout.svg').read_text():
            raise ValueError('CAD/layout differs from accepted design')
    return {'accepted':True,'scope':'Source-bound digital artifacts and independent model arithmetic; no physical or commercial qualification.'}
