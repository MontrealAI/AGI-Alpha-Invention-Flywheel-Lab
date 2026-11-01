"""Offline accessible circular wheel plus an explicitly non-authoritative evidence display."""
from __future__ import annotations
from html import escape
from pathlib import Path
from xml.etree import ElementTree
from .readout import SCHEMA, RINGS, EvidenceError, canonical, sha

SCOPE_PRESENTATION = 'READ_ONLY_NOT_FINANCIAL_OR_EXECUTION_AUTHORITY'
SVG = Path(__file__).resolve().parents[1] / 'docs' / 'flywheel-wheel' / 'architecture.svg'

def _e(v):
    return escape(str(v), quote=True)

def _check(s):
    if type(s) is not dict or s.get('schema') != SCHEMA or s.get('funding_authority') is not False:
        raise EvidenceError('READ_ONLY_WHEEL_SNAPSHOT_REQUIRED')
    if set(s.get('rings', {})) != set(RINGS):
        raise EvidenceError('THREE_INDEPENDENT_WHEELS_REQUIRED')
    for ring, labels in RINGS.items():
        if set(s['rings'][ring]) != set(labels):
            raise EvidenceError('EXACT_RING_STAGES_REQUIRED')
        if any(type(v) is not str or len(v) > 90 or '<' in v or '>' in v for v in s['rings'][ring].values()):
            raise EvidenceError('BOUNDED_STATUS_REQUIRED')

def render_svg(snapshot):
    """Keep the actual wheel geometry. Overlay source-linked state; never invent gains."""
    _check(snapshot)
    base = SVG.read_text(encoding='utf8')
    if not base.endswith('</svg>'):
        raise EvidenceError('TRUSTED_STATIC_WHEEL_TEMPLATE_REQUIRED')
    ElementTree.fromstring(base)
    mode = snapshot['scope']
    if mode == 'ARCHITECTURE_ONLY_NO_ENTERPRISE_INPUT':
        text = 'ARCHITECTURE ONLY  |  NO AUDITED ENTERPRISE INPUT'
    elif mode == 'RECORDED_CONDITIONAL_SIMULATION_AFTER_CANONICAL_AUDIT':
        text = f'CANONICAL AUDIT ACCEPTED  |  {len(snapshot["worlds"])} SEPARATE SIMULATED BUSINESSES'
    else:
        raise EvidenceError('UNKNOWN_WHEEL_EVIDENCE_SCOPE')
    overlay = ('<g id="evidence-annotation" aria-label="Current wheel evidence scope">'
               '<rect x="1247" y="1207" width="781" height="88" rx="12" fill="#0c1428"/>'
               '<text x="1268" y="1244" fill="#f9ca94" font-family="DejaVu Sans,Arial,sans-serif" font-size="19" font-weight="700">'
               + _e(text) + '</text>'
               '<text x="1268" y="1275" fill="#b8cae3" font-family="DejaVu Sans,Arial,sans-serif" font-size="17">'
               'Invention, real commerce and physical-scale gains need separate proof.</text>'
               '</g>')
    result = base[:-6] + overlay + '</svg>'
    ElementTree.fromstring(result)
    return result

def render_html(snapshot, svg=None):
    _check(snapshot)
    svg = svg if svg is not None else render_svg(snapshot)
    data = []
    for ring in ('commerce','invention','production'):
        entries = ''.join('<li><strong>' + _e(label) + '</strong><span>' + _e(snapshot['rings'][ring][label]) + '</span></li>' for label in RINGS[ring])
        data.append('<section><h2>' + _e(ring.title()) + '</h2><ol>' + entries + '</ol></section>')
    worlds = ''.join('<tr><td>' + _e(x['id']) + '</td><td>' + f'{x["modeled_profit_microUSD"]/1_000_000:.6f}' + '</td><td>' + f'{x["modeled_cash_microUSD"]/1_000_000:.6f}' + '</td></tr>' for x in snapshot['worlds'])
    if not worlds:
        worlds = '<tr><td colspan="3">No audited enterprise was provided.</td></tr>'
    limits = ''.join('<li>' + _e(x) + '</li>' for x in snapshot['limits'])
    styles = '''body{margin:0;background:#071124;color:#e7effc;font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1420px;margin:auto;padding:20px}h1{font-size:clamp(25px,4vw,45px);margin-bottom:4px}h2{font-size:20px}small,.muted{color:#b8c7dd}figure{margin:14px 0 24px}figure svg{width:100%;height:auto;display:block}article{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}section{background:#0e1d36;border:1px solid #40516e;border-radius:14px;padding:18px}ol{list-style:decimal;margin:0;padding-left:23px}li{padding:8px 0}section li span{display:block;color:#bfd1eb;font-size:12px;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}td,th{border-bottom:1px solid #344761;text-align:left;padding:8px}caption{caption-side:bottom;text-align:left;color:#adc1da;padding:12px}a{color:#9bd6ff}header{margin:20px 0}.alert{background:#142642;padding:18px;border-radius:10px;border-left:4px solid #dfbd7f}code{color:#c9ddf5;overflow-wrap:anywhere}@media print{body{background:#fff;color:#111}section{background:#fff;color:#111}figure{break-inside:avoid}}'''
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
      '<title>AGI ALPHA Flywheel Harness — Transformational Intelligence</title><style>' + styles + '</style></head><body><main>'
      '<header><h1>🌌♾️ AGI ALPHA Flywheel Harness</h1><p class="muted">Transformational Intelligence · three real circular feedback wheels · evidence-gated coupling</p></header>'
      '<figure>' + svg + '<figcaption>A wheel is not a chain. Each ring repeats independently; transfers across rings need proof, permission and actual resources.</figcaption></figure>'
      '<div class="alert"><strong>Evidence boundary:</strong> ' + _e(snapshot['scope']) + '. '
      'Commercial: ' + _e(snapshot['commercial_claim']) + '; Invention: ' + _e(snapshot['invention_claim']) + '; Physical production: ' + _e(snapshot['productive_claim']) + '. '
      '<br><small>No execution, collection, investment, release or authority can be triggered from this page.</small></div>'
      '<article>' + ''.join(data) + '</article>'
      '<section><h2>Native commercial worlds — individually, never pooled</h2><table><thead><tr><th>Simulated business</th><th>Modeled profit (USD)</th><th>Modeled cash (USD)</th></tr></thead><tbody>' + worlds + '</tbody></table>'
      '<p>Actual customers: ' + _e(snapshot['real_customers']) + '. Real collections (microUSD): ' + _e(snapshot['real_collections_microUSD']) + '. Host/model billing: unknown.</p></section>'
      '<section><h2>Claims that remain outside this evidence</h2><ul>' + limits + '</ul></section>'
      '<footer><small>Read-only presentation · ' + _e(SCOPE_PRESENTATION) + ' · Snapshot SHA-256: ' + sha(snapshot) + '</small></footer></main></body></html>')
